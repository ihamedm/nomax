"""business likes

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("like_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_table(
        "business_likes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "business_id", name="uq_like_user_business"),
    )
    op.create_index(
        op.f("ix_business_likes_business_id"), "business_likes", ["business_id"], unique=False
    )
    op.create_index(
        op.f("ix_business_likes_user_id"), "business_likes", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_business_likes_user_id"), table_name="business_likes")
    op.drop_index(op.f("ix_business_likes_business_id"), table_name="business_likes")
    op.drop_table("business_likes")
    op.drop_column("businesses", "like_count")
