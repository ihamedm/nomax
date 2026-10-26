"""scheduled jobs outbox
Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=60), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index("ix_scheduled_jobs_type", "scheduled_jobs", ["type"])
    op.create_index("ix_scheduled_jobs_run_at", "scheduled_jobs", ["run_at"])
    op.create_index("ix_scheduled_jobs_status", "scheduled_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("scheduled_jobs")
