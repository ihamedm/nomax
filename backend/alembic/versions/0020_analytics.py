"""analytics: search logs, quote deliveries and acceptance timestamps
Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("quote_requests", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_quote_requests_accepted_at", "quote_requests", ["accepted_at"])

    op.create_table(
        "search_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("query", sa.String(length=160), nullable=True),
        sa.Column("normalized_query", sa.String(length=160), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("subcategory_id", sa.Integer(), nullable=True),
        sa.Column("results_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="search"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["subcategory_id"], ["subcategories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("user_id", "normalized_query", "category_id", "subcategory_id", "created_at"):
        op.create_index(f"ix_search_logs_{column}", "search_logs", [column])

    op.create_table(
        "quote_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["quote_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id", "business_id", name="uq_quote_delivery_request_business"),
    )
    op.create_index("ix_quote_deliveries_request_id", "quote_deliveries", ["request_id"])
    op.create_index("ix_quote_deliveries_business_id", "quote_deliveries", ["business_id"])
    op.create_index("ix_quote_deliveries_sent_at", "quote_deliveries", ["sent_at"])
    op.create_index("ix_quote_deliveries_seen_at", "quote_deliveries", ["seen_at"])

    op.execute(
        """
        UPDATE quote_requests AS q
        SET accepted_at = COALESCE(o.updated_at, q.created_at)
        FROM offers AS o
        WHERE q.accepted_offer_id = o.id AND q.accepted_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_quote_deliveries_seen_at", table_name="quote_deliveries")
    op.drop_index("ix_quote_deliveries_sent_at", table_name="quote_deliveries")
    op.drop_index("ix_quote_deliveries_business_id", table_name="quote_deliveries")
    op.drop_index("ix_quote_deliveries_request_id", table_name="quote_deliveries")
    op.drop_table("quote_deliveries")
    for column in ("created_at", "subcategory_id", "category_id", "normalized_query", "user_id"):
        op.drop_index(f"ix_search_logs_{column}", table_name="search_logs")
    op.drop_table("search_logs")
    op.drop_index("ix_quote_requests_accepted_at", table_name="quote_requests")
    op.drop_column("quote_requests", "accepted_at")
