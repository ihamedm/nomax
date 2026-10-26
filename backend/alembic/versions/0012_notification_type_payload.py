"""notification type/payload
Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("type", sa.String(length=40), nullable=False, server_default="system"))
        batch.add_column(sa.Column("payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("payload")
        batch.drop_column("type")
