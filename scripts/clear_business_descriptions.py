"""Clear the descriptive text of every business (one-off maintenance).

Usage (inside the API container):

    python /tmp/clear_business_descriptions.py           # dry run: count only
    python /tmp/clear_business_descriptions.py --yes     # actually clear

Sets ``description`` to NULL and ``short_description`` to '' for every row
(soft-deleted businesses included). Nothing else is touched.
"""

import argparse
import asyncio

import sqlalchemy as sa

from app.db.session import AsyncSessionLocal
from app.models.business import Business


async def clear_descriptions(apply: bool) -> None:
    async with AsyncSessionLocal() as session:
        pending = (
            await session.execute(
                sa.select(sa.func.count())
                .select_from(Business)
                .where(
                    sa.or_(
                        Business.description.is_not(None),
                        Business.short_description != "",
                    )
                )
            )
        ).scalar_one()
        print(f"businesses with description text: {pending}")
        if not apply:
            print("dry run: nothing changed (pass --yes to clear)")
            return
        result = await session.execute(
            sa.update(Business).values(description=None, short_description="")
        )
        await session.commit()
        print(f"cleared descriptions on {result.rowcount} businesses")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clear-business-descriptions",
        description="Clear description and short_description for every business.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="actually write; without it the script only reports the row count",
    )
    args = parser.parse_args()
    asyncio.run(clear_descriptions(args.yes))


if __name__ == "__main__":
    main()
