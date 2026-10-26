"""partial indexes
Revision ID: 0013
Revises: 0012
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_businesses_approved",
        "businesses",
        ["status"],
        postgresql_where="status = 'approved'",
    )
    op.create_index("idx_businesses_category_pair", "businesses", ["category_id", "subcategory_id"])
    op.create_index(
        "idx_offers_pending",
        "offers",
        ["request_id"],
        postgresql_where="status = 'pending'",
    )
    op.create_index("idx_reviews_business_status", "reviews", ["business_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_reviews_business_status", table_name="reviews")
    op.drop_index("idx_offers_pending", table_name="offers")
    op.drop_index("idx_businesses_category_pair", table_name="businesses")
    op.drop_index("idx_businesses_approved", table_name="businesses")
