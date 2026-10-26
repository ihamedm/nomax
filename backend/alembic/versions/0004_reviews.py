"""reviews

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-26

"""
from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reviews",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("business_id", "user_id", name="uq_review_business_user"),
    )
    op.create_index("ix_reviews_business_id", "reviews", ["business_id"])
    op.create_index("ix_reviews_user_id", "reviews", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_reviews_user_id", table_name="reviews")
    op.drop_index("ix_reviews_business_id", table_name="reviews")
    op.drop_table("reviews")
