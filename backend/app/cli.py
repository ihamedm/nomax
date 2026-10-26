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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="nomax", description="NOMAX operator commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-superadmin", help="create or promote a superadmin account")
    create.add_argument("--phone", required=True, help="Iranian mobile number (09..., 98..., or 10 digits)")
    create.add_argument("--name", default=None, help="optional display name")

    args = parser.parse_args(argv)

    if args.command == "create-superadmin":
        try:
            asyncio.run(_create_superadmin(args.phone, args.name))
        except AppError as exc:
            print(f"error: {exc.message}", file=sys.stderr)
            return 1
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
