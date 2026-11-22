"""subcategory visible tags

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL means "not configured": the wizard shows the first few standard tags.
    op.add_column("subcategories", sa.Column("visible_tags", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("subcategories", "visible_tags")
