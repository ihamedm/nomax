"""quote dispatch engine: waves, retries and manual assignment

Revision ID: 0021
Revises: 0020

The original dispatcher was a one-shot pass. These columns make the request row
the durable dispatch schedule, while `quote_dispatch_runs` keeps an audit trail
for every auto/retry/manual wave.
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "quote_requests",
        sa.Column("dispatch_round", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "quote_requests",
        sa.Column("dispatch_status", sa.String(length=24), nullable=False, server_default="pending"),
    )
    op.add_column(
        "quote_requests",
        sa.Column("last_dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "quote_requests",
        sa.Column("next_dispatch_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_quote_requests_dispatch_status", "quote_requests", ["dispatch_status"])
    op.create_index("ix_quote_requests_next_dispatch_at", "quote_requests", ["next_dispatch_at"])

    op.add_column(
        "quote_deliveries",
        sa.Column("round", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "quote_deliveries",
        sa.Column("source", sa.String(length=20), nullable=False, server_default="auto"),
    )
    op.add_column(
        "quote_deliveries",
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_quote_deliveries_round", "quote_deliveries", ["round"])

    op.create_table(
        "quote_dispatch_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Uuid(), nullable=False),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(length=20), nullable=False, server_default="initial"),
        sa.Column("candidate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["request_id"], ["quote_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_quote_dispatch_runs_request_id", "quote_dispatch_runs", ["request_id"]
    )
    op.create_index(
        "ix_quote_dispatch_runs_created_at", "quote_dispatch_runs", ["created_at"]
    )

    # Backfill operational state. Delivered waves count as round one; requests
    # that were silently dropped by the old UTC/subcategory logic are scheduled
    # immediately so the new worker can recover them.
    op.execute(
        """
        UPDATE quote_requests AS q
        SET dispatch_round = 1,
            last_dispatched_at = (
                SELECT MAX(d.sent_at) FROM quote_deliveries AS d WHERE d.request_id = q.id
            )
        WHERE EXISTS (SELECT 1 FROM quote_deliveries AS d WHERE d.request_id = q.id)
        """
    )
    op.execute(
        """
        UPDATE quote_requests
        SET dispatch_status = CASE
                WHEN status = 'active' AND dispatch_round > 0 THEN 'active'
                WHEN status = 'active' THEN 'pending'
                ELSE 'completed'
            END,
            next_dispatch_at = CASE
                WHEN status = 'active' AND dispatch_round > 0 THEN now() + interval '1 minute'
                WHEN status = 'active' THEN now()
                ELSE NULL
            END
        """
    )
    op.execute(
        """
        UPDATE quote_deliveries AS d
        SET responded_at = (
            SELECT MIN(o.created_at)
            FROM offers AS o
            WHERE o.request_id = d.request_id AND o.business_id = d.business_id
        )
        WHERE EXISTS (
            SELECT 1 FROM offers AS o
            WHERE o.request_id = d.request_id AND o.business_id = d.business_id
        )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_quote_dispatch_runs_created_at", table_name="quote_dispatch_runs")
    op.drop_index("ix_quote_dispatch_runs_request_id", table_name="quote_dispatch_runs")
    op.drop_table("quote_dispatch_runs")

    op.drop_index("ix_quote_deliveries_round", table_name="quote_deliveries")
    op.drop_column("quote_deliveries", "responded_at")
    op.drop_column("quote_deliveries", "source")
    op.drop_column("quote_deliveries", "round")

    op.drop_index("ix_quote_requests_next_dispatch_at", table_name="quote_requests")
    op.drop_index("ix_quote_requests_dispatch_status", table_name="quote_requests")
    op.drop_column("quote_requests", "next_dispatch_at")
    op.drop_column("quote_requests", "last_dispatched_at")
    op.drop_column("quote_requests", "dispatch_status")
    op.drop_column("quote_requests", "dispatch_round")
