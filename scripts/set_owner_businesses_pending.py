"""Set every business of one owner back to pending (one-off maintenance).

Usage (inside the API container):

    python /tmp/set_owner_businesses_pending.py           # dry run: count only
    python /tmp/set_owner_businesses_pending.py --yes     # actually set pending

Looks the owner up by phone (default 09123456789) and updates all of their
businesses, soft-deleted rows included. Resetting to pending clears
``rejection_reason`` and ``pending_changes`` so the rows are consistent.
"""

import argparse
import asyncio

import sqlalchemy as sa

from app.db.session import AsyncSessionLocal
from app.models.business import Business, BusinessStatus
from app.models.user import User

DEFAULT_PHONE = "09123456789"


async def set_pending(phone: str, apply: bool) -> None:
    async with AsyncSessionLocal() as session:
        owner_id = (
            await session.execute(sa.select(User.id).where(User.phone == phone))
        ).scalar_one_or_none()
        if owner_id is None:
            print(f"no user with phone {phone}")
            return

        total = (
            await session.execute(
                sa.select(sa.func.count())
                .select_from(Business)
                .where(Business.owner_id == owner_id)
            )
        ).scalar_one()
        print(f"owner {owner_id}: {total} businesses")
        if not apply:
            print("dry run: nothing changed (pass --yes to set pending)")
            return

        result = await session.execute(
            sa.update(Business)
            .where(
                Business.owner_id == owner_id,
                Business.status != BusinessStatus.PENDING,
            )
            .values(
                status=BusinessStatus.PENDING,
                rejection_reason=None,
                pending_changes=None,
            )
        )
        await session.commit()
        print(f"set {result.rowcount} businesses to pending")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="set-owner-businesses-pending",
        description="Set every business of one owner to pending.",
    )
    parser.add_argument("--phone", default=DEFAULT_PHONE, help=f"owner phone (default {DEFAULT_PHONE})")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="actually write; without it the script only reports the row count",
    )
    args = parser.parse_args()
    asyncio.run(set_pending(args.phone, args.yes))


if __name__ == "__main__":
    main()
