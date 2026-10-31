"""business gallery images

Revision ID: 0022
Revises: 0021

Businesses can now publish up to five ordered gallery images. The existing
``profile_image_url`` remains the denormalised main image used by cards and
search results, while ``business_images.is_main`` points at the same URL.
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "business_images",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("url", sa.String(length=255), nullable=False),
        sa.Column("is_main", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("sort_order >= 0", name="ck_business_images_sort_order"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_business_images_business_id", "business_images", ["business_id"]
    )

    # Keep existing cover photos visible as the first gallery item.
    op.execute(
        """
        INSERT INTO business_images (id, business_id, url, is_main, sort_order)
        SELECT gen_random_uuid(), id, profile_image_url, true, 0
        FROM businesses
        WHERE profile_image_url IS NOT NULL AND profile_image_url <> ''
        """
    )


def downgrade() -> None:
    op.drop_index("ix_business_images_business_id", table_name="business_images")
    op.drop_table("business_images")
