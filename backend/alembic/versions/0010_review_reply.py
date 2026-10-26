"""review reply and author
Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("reviews") as batch:
        batch.add_column(sa.Column("author_name", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("reply", sa.Text(), nullable=True))
        batch.add_column(sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reviews") as batch:
        batch.drop_column("replied_at")
        batch.drop_column("reply")
        batch.drop_column("author_name")
