"""business avatar and license verification

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("businesses", sa.Column("avatar_url", sa.String(length=255), nullable=True))
    op.add_column(
        "businesses",
        sa.Column(
            "is_license_verified",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    # Existing verified rows came from the license flow; identity verification
    # starts empty because there was no way to set it before.
    op.execute(
        "UPDATE businesses SET is_license_verified = is_verified, is_verified = false"
    )


def downgrade() -> None:
    op.drop_column("businesses", "is_license_verified")
    op.drop_column("businesses", "avatar_url")
