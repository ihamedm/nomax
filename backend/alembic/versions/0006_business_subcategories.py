"""multiple business subcategories

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "business_subcategories",
        sa.Column(
            "business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "subcategory_id",
            sa.Integer(),
            sa.ForeignKey("subcategories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    # Existing single-subcategory rows become the first join row.
    op.execute(
        """
        INSERT INTO business_subcategories (business_id, subcategory_id)
        SELECT id, subcategory_id FROM businesses
        WHERE subcategory_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_table("business_subcategories")
