"""Import Behbahan businesses from the scraped dataset.

Usage (inside the API container or any environment with the backend installed):

    python /tmp/import_behbahan_businesses.py \
      --csv /tmp/import-data/businesses.csv \
      --root /tmp/import-data \
      --limit 10 --dry-run

    python /tmp/import_behbahan_businesses.py \
      --csv /tmp/import-data/businesses.csv \
      --root /tmp/import-data \
      --count 25

    # Test a small batch that starts after the rows already imported:
    python /tmp/import_behbahan_businesses.py \
      --csv /tmp/import-data/businesses.csv \
      --root /tmp/import-data \
      --offset 10 --count 3

Ownership rules:

* Rows whose dataset phone is an Iranian mobile (``09xxxxxxxxx``) become the
  owner account for that business. A newly created owner has no display name
  and is unverified; reused accounts keep their existing profile/verification.
* Rows without a mobile phone (no phone, or a landline only) are assigned to an
  admin/superadmin manager so an operator can claim or complete them later.
  Pass ``--manager-phone`` to choose the manager explicitly, otherwise the
  first superadmin (falling back to an admin) is used.

The importer is idempotent by deterministic slug: rerunning it skips businesses
that already exist. Images in ``<root>/<index>/images`` are processed by the
same pipeline as user uploads and stored in the configured local/S3 location.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import itertools
import re
from pathlib import Path

import sqlalchemy as sa

from app.core.config import settings
from app.core.security import normalize_phone
from app.db.session import AsyncSessionLocal
from app.models.business import Business, BusinessImage, BusinessStatus
from app.models.category import Category, Subcategory
from app.models.user import User, UserRole
from app.services.image_processor import InvalidImage, process_image
from app.services.storage import save_image_bundle, user_upload_prefix

# The dataset categories are free-text Neshan labels. Only the labels needed by
# the test batch are mapped explicitly; anything else falls back to «سایر».
CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "آبمیوه و بستنی": ("food", "juice"),
    "فروشگاه": ("retail", "supermarket"),
    "کلینیک دامپزشکی": ("agriculture", "vet"),
    "دندان پزشکی": ("medical", "dentist"),
    "دندانپزشکی": ("medical", "dentist"),
    "رستوران": ("food", "restaurant"),
    "فروشگاه لباس زنانه": ("retail", "women_clothing"),
    "شیشه بر خودرو": ("automotive", "parts"),
    "فروشگاه لوازم خانگی": ("retail", "home_goods"),
    "خودپرداز": ("office-services", "bank"),
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
FALLBACK_CATEGORY = ("other", "other")
MOBILE_RE = re.compile(r"09\d{9}")


def _natural_key(path: Path) -> tuple:
    return tuple(
        int(part) if part.isdigit() else part.lower()
        for part in re.split(r"(\d+)", path.name)
    )


def _clean_phone(value: str) -> str | None:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if digits.startswith("98") and len(digits) == 12:
        digits = "0" + digits[2:]
    if digits.startswith("9") and len(digits) == 10:
        digits = "0" + digits
    return digits if re.fullmatch(r"0\d{10}", digits) else None


def _clean_instagram(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    raw = raw.split("?", 1)[0].rstrip("/")
    if "instagram.com/" in raw:
        raw = raw.split("instagram.com/", 1)[1]
    raw = raw.strip().lstrip("@")
    return raw[:100] or None


def _short_description(about: str) -> str:
    text = " ".join((about or "").split())
    if len(text) <= 120:
        return text
    return text[:117].rstrip() + "…"


def _slug(index: str, title: str) -> str:
    digest = hashlib.sha1(f"{index}:{title}".encode("utf-8")).hexdigest()[:6]
    return f"behbahan-{int(index):04d}-{digest}"


def _image_paths(root: Path, index: str) -> list[Path]:
    folder = root / index / "images"
    if not folder.is_dir():
        return []
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return sorted(files, key=_natural_key)[: settings.MAX_BUSINESS_IMAGES]


def _is_mobile_phone(phone: str | None) -> bool:
    return bool(phone and MOBILE_RE.fullmatch(phone))


async def _get_or_create_owner(session, phone: str) -> User:
    normalized = normalize_phone(phone)
    owner = (
        await session.execute(sa.select(User).where(User.phone == normalized))
    ).scalar_one_or_none()
    if owner is None:
        owner = User(
            phone=normalized,
            # Imported owners stay unnamed until they complete their profile;
            # the public page then shows the «unverified owner» warning.
            full_name=None,
            role=UserRole.OWNER,
            permissions=[],
            # Imported rows have not completed the OTP/identity flow, so they
            # stay unverified until an operator marks them from the dashboard.
            is_verified=False,
            is_phone_verified=True,
        )
        session.add(owner)
        await session.flush()
        print(f"owner created: {normalized} ({owner.id})")
    else:
        if owner.deleted_at is not None:
            owner.deleted_at = None
        if owner.role == UserRole.CUSTOMER:
            owner.role = UserRole.OWNER
        owner.is_phone_verified = True
        await session.flush()
        print(f"owner reused: {normalized} ({owner.id})")
    return owner


async def _get_manager(session, manager_phone: str | None) -> User:
    manager_roles = (UserRole.ADMIN, UserRole.SUPERADMIN)
    if manager_phone:
        normalized = normalize_phone(manager_phone)
        manager = (
            await session.execute(sa.select(User).where(User.phone == normalized))
        ).scalar_one_or_none()
        if (
            manager is None
            or manager.deleted_at is not None
            or manager.role not in manager_roles
        ):
            raise SystemExit(
                f"manager account not found or not an admin: {normalized}; "
                "create one with `nomax create-superadmin` or pass --manager-phone"
            )
        print(f"manager selected: {manager.phone} ({manager.id})")
        return manager

    manager = (
        await session.execute(
            sa.select(User)
            .where(User.role.in_(manager_roles), User.deleted_at.is_(None))
            .order_by(
                sa.case((User.role == UserRole.SUPERADMIN, 0), else_=1),
                User.created_at,
            )
        )
    ).scalars().first()
    if manager is None:
        raise SystemExit(
            "no admin/superadmin manager exists to own rows without a mobile "
            "phone; create one with `nomax create-superadmin` or pass --manager-phone"
        )
    print(f"manager selected: {manager.phone} ({manager.id})")
    return manager


def _resolve_category(
    categories: dict[str, Category],
    subcategories: dict[tuple[str, str], Subcategory],
    label: str,
) -> tuple[Category, Subcategory]:
    category_slug, subcategory_slug = CATEGORY_MAP.get(label, FALLBACK_CATEGORY)
    category = categories.get(category_slug)
    subcategory = subcategories.get((category_slug, subcategory_slug))
    if category is None or subcategory is None:
        category = categories["other"]
        subcategory = subcategories[("other", "other")]
    return category, subcategory


async def _upload_images(owner_id, root: Path, index: str) -> list[str]:
    urls: list[str] = []
    for path in _image_paths(root, index):
        try:
            data = path.read_bytes()
            processed = await asyncio.to_thread(
                process_image, data, crop="original"
            )
            saved = await save_image_bundle(
                processed.main.data,
                {
                    name: variant.data
                    for name, variant in processed.variants.items()
                },
                prefix=user_upload_prefix("businesses", owner_id),
            )
            urls.append(saved["url"])
            print(f"  image {path.name}: {saved['size']} bytes")
        except (InvalidImage, OSError, ValueError) as exc:
            print(f"  image {path.name}: skipped ({exc})")
    return urls


async def import_rows(args) -> None:
    csv_path = Path(args.csv)
    root = Path(args.root)
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")
    if not root.is_dir():
        raise SystemExit(f"dataset root not found: {root}")

    async with AsyncSessionLocal() as session:
        categories = {
            row.slug: row
            for row in (await session.execute(sa.select(Category))).scalars()
        }
        categories_by_id = {row.id: row for row in categories.values()}
        subcategories = {
            (categories_by_id[row.category_id].slug, row.slug): row
            for row in (await session.execute(sa.select(Subcategory))).scalars()
        }

        owners: dict[str, User] = {}
        manager: User | None = None
        created = skipped = malformed = 0
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(itertools.islice(reader, args.offset, args.offset + args.limit))

        total = len(rows)
        print(
            f"import rows: {total} "
            f"(offset {args.offset}, limit {args.limit})"
        )
        for position, row in enumerate(rows, start=1):
            index = (row.get("index") or "").strip()
            title = (row.get("title") or "").strip()
            if not index or not title:
                print(f"[{position}/{total}] skip malformed row: {row!r}")
                malformed += 1
                continue
            slug = _slug(index, title)
            existing = (
                await session.execute(
                    sa.select(Business).where(Business.slug == slug)
                )
            ).scalar_one_or_none()
            if existing is not None:
                print(f"[{position}/{total}] skip existing {index}: {title} ({slug})")
                skipped += 1
                continue

            category, subcategory = _resolve_category(
                categories, subcategories, (row.get("category") or "").strip()
            )
            phone = _clean_phone(row.get("phone") or "")
            about = (row.get("about") or "").strip()
            try:
                lat = float(row["latitude"]) if row.get("latitude") else None
                lng = float(row["longitude"]) if row.get("longitude") else None
            except ValueError:
                lat = lng = None

            mobile_phone = phone if _is_mobile_phone(phone) else None
            print(
                f"[{position}/{total}] {index}: {title} -> "
                f"{category.name}/{subcategory.name} "
                f"({len(_image_paths(root, index))} images, "
                f"owner {'mobile ' + mobile_phone if mobile_phone else 'manager'})"
            )
            if args.dry_run:
                continue

            if mobile_phone is not None:
                owner = owners.get(mobile_phone)
                if owner is None:
                    owner = await _get_or_create_owner(session, mobile_phone)
                    owners[mobile_phone] = owner
            else:
                # Landline-only rows have no identifiable mobile owner yet;
                # park them under a manager account for later triage.
                if manager is None:
                    manager = await _get_manager(session, args.manager_phone)
                owner = manager

            business = Business(
                owner_id=owner.id,
                category_id=category.id,
                subcategory_id=subcategory.id,
                name=title[:160],
                slug=slug,
                short_description=_short_description(about),
                description=about or None,
                phone_business=phone,
                address=(row.get("address") or "").strip()[:255],
                geo_lat=lat,
                geo_lng=lng,
                instagram=_clean_instagram(row.get("instagram") or ""),
                status=BusinessStatus.APPROVED,
                is_verified=False,
            )
            session.add(business)
            await session.flush()

            image_urls = await _upload_images(owner.id, root, index)
            for sort_order, url in enumerate(image_urls):
                session.add(
                    BusinessImage(
                        business_id=business.id,
                        url=url,
                        is_main=sort_order == 0,
                        sort_order=sort_order,
                    )
                )
            business.profile_image_url = image_urls[0] if image_urls else None
            await session.commit()
            created += 1
            print(f"  imported {business.id} with {len(image_urls)} images")

        if args.dry_run:
            print(f"dry run: {total} rows inspected, nothing written")
        else:
            print(
                f"done: {created} imported, {skipped} skipped, "
                f"{malformed} malformed out of {total} rows"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import Behbahan businesses")
    parser.add_argument("--csv", required=True, help="path to businesses.csv")
    parser.add_argument("--root", required=True, help="folder containing <index>/images")
    parser.add_argument(
        "--limit",
        "--count",
        dest="limit",
        type=int,
        default=10,
        help="maximum number of CSV rows to inspect (default 10)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="number of CSV rows to skip before importing (for test batches)",
    )
    parser.add_argument(
        "--manager-phone",
        default=None,
        help=(
            "admin/superadmin phone that owns rows without a mobile phone; "
            "defaults to the first superadmin/admin"
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit/--count must be at least 1")
    if args.offset < 0:
        parser.error("--offset must be zero or greater")
    asyncio.run(import_rows(args))


if __name__ == "__main__":
    main()
