"""ads
Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("image_url", sa.String(length=255), nullable=True),
        sa.Column("target_url", sa.String(length=255), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ads")
