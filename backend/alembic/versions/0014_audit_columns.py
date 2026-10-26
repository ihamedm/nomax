"""audit columns on remaining tables + ad placement
Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

TABLES = ("offers", "scheduled_jobs", "device_tokens", "notifications", "notification_deliveries", "ads")


def upgrade() -> None:
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
            batch.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("ads") as batch:
        batch.add_column(sa.Column("placement", sa.String(length=40), nullable=False, server_default="home_banner"))
        batch.add_column(sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ads") as batch:
        batch.drop_column("ends_at")
        batch.drop_column("starts_at")
        batch.drop_column("placement")
    for table in TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_column("deleted_at")
            batch.drop_column("updated_at")
