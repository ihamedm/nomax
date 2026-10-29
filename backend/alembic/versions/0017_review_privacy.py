"""review privacy and owner seen state

Revision ID: 0017
Revises: 0016
"""
from alembic import op
import sqlalchemy as sa


revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reviews") as batch:
        batch.add_column(
            sa.Column(
                "is_private",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch.add_column(
            sa.Column("owner_seen_at", sa.DateTime(timezone=True), nullable=True)
        )
    op.create_index(
        "idx_reviews_owner_unseen",
        "reviews",
        ["business_id", "status"],
        postgresql_where=sa.text("owner_seen_at IS NULL AND status IN ('pending', 'private')"),
    )


def downgrade() -> None:
    op.drop_index("idx_reviews_owner_unseen", table_name="reviews")
    with op.batch_alter_table("reviews") as batch:
        batch.drop_column("owner_seen_at")
        batch.drop_column("is_private")
