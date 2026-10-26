"""NOMAX operator CLI.

Usage:
    python3 -m app.cli create-superadmin --phone 09123456789 --name "Ali Rezaei"
"""

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.errors import AppError
from app.core.security import normalize_phone
from app.db.demo import seed_demo_businesses
from app.db.seed import seed_categories
from app.db.session import AsyncSessionLocal
from app.models.user import User, UserRole


async def _create_superadmin(phone: str, full_name: str | None) -> None:
    normalized = normalize_phone(phone)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.phone == normalized))
        user = result.scalar_one_or_none()
        if user is None:
            session.add(
                User(
                    phone=normalized,
                    full_name=full_name,
                    role=UserRole.SUPERADMIN,
                    permissions=[],
                    is_phone_verified=True,
                )
            )
            action = "created"
        else:
            user.role = UserRole.SUPERADMIN
            user.is_phone_verified = True
            user.deleted_at = None
            if full_name:
                user.full_name = full_name
            action = "promoted"
        await session.commit()
    print(f"{action} superadmin: {normalized}")


async def _seed_categories() -> None:
    async with AsyncSessionLocal() as session:
        stats = await seed_categories(session)
        await session.commit()
    print(
        "categories seeded: "
        f"{stats['categories_created']} created, {stats['categories_updated']} updated; "
        f"{stats['subcategories_created']} subcategories created, "
        f"{stats['subcategories_updated']} updated"
    )


async def _seed_demo(reset: bool) -> None:
    async with AsyncSessionLocal() as session:
        stats = await seed_demo_businesses(session, reset=reset)
        await session.commit()
    print(
        "demo businesses seeded: "
        f"{stats['created']} created, {stats['updated']} updated "
        f"({stats['total']} total, development only)"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nomax", description="NOMAX operator commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-superadmin", help="create or promote a superadmin account")
    create.add_argument("--phone", required=True, help="Iranian mobile number (09..., 98..., or 10 digits)")
    create.add_argument("--name", default=None, help="optional display name")

    subparsers.add_parser("seed-categories", help="idempotently seed the 18-category catalog")

    demo = subparsers.add_parser(
        "seed-demo-businesses", help="seed development businesses around Behbahan"
    )
    demo.add_argument("--reset", action="store_true", help="delete and recreate demo rows")

    args = parser.parse_args(argv)

    if args.command == "create-superadmin":
        try:
            asyncio.run(_create_superadmin(args.phone, args.name))
        except AppError as exc:
            print(f"error: {exc.message}", file=sys.stderr)
            return 1
        return 0

    if args.command == "seed-categories":
        asyncio.run(_seed_categories())
        return 0

    if args.command == "seed-demo-businesses":
        try:
            asyncio.run(_seed_demo(args.reset))
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
