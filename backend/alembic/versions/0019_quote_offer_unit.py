"""quote offer unit and lookup indexes
Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("offers", sa.Column("unit", sa.String(length=30), nullable=True))
    op.create_index("ix_quote_requests_status", "quote_requests", ["status"])
    op.create_index("ix_quote_requests_created_at", "quote_requests", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_quote_requests_created_at", table_name="quote_requests")
    op.drop_index("ix_quote_requests_status", table_name="quote_requests")
    op.drop_column("offers", "unit")
