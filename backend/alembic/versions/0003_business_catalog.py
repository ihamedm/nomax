"""business catalog

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-26

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "businesses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("subcategory_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("short_description", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("phone_business", sa.String(length=11), nullable=True),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("geo_lat", sa.Float(), nullable=True),
        sa.Column("geo_lng", sa.Float(), nullable=True),
        sa.Column("instagram", sa.String(length=100), nullable=True),
        sa.Column("is_24h", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.String(length=255), nullable=True),
        sa.Column("rating_avg", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("rating_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("profile_image_url", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "geo_lat IS NULL OR (geo_lat BETWEEN -90 AND 90)", name="ck_business_geo_lat"
        ),
        sa.CheckConstraint(
            "geo_lng IS NULL OR (geo_lng BETWEEN -180 AND 180)", name="ck_business_geo_lng"
        ),
        sa.CheckConstraint("rating_avg >= 0 AND rating_avg <= 5", name="ck_business_rating_avg"),
        sa.CheckConstraint("rating_count >= 0", name="ck_business_rating_count"),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["subcategory_id"], ["subcategories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_businesses_slug", "businesses", ["slug"], unique=True)
    op.create_index("ix_businesses_owner_id", "businesses", ["owner_id"])
    op.create_index("ix_businesses_category_id", "businesses", ["category_id"])
    op.create_index("ix_businesses_subcategory_id", "businesses", ["subcategory_id"])
    op.create_index(
        "idx_businesses_status",
        "businesses",
        ["status"],
        postgresql_where=sa.text("status = 'approved'"),
    )
    op.create_index(
        "idx_businesses_category",
        "businesses",
        ["category_id", "subcategory_id"],
    )

    # Generated geography column: the ORM only writes lat/lng, while all radial
    # search uses this indexed column with ST_DWithin/ST_Distance.
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN geo geography(Point, 4326)
        GENERATED ALWAYS AS (
            CASE
                WHEN geo_lat IS NULL OR geo_lng IS NULL THEN NULL
                ELSE ST_SetSRID(ST_MakePoint(geo_lng, geo_lat), 4326)::geography
            END
        ) STORED
        """
    )
    op.execute("CREATE INDEX idx_businesses_geo ON businesses USING GIST (geo)")


def downgrade() -> None:
    op.drop_index("idx_businesses_geo", table_name="businesses")
    op.drop_index("idx_businesses_category", table_name="businesses")
    op.drop_index("idx_businesses_status", table_name="businesses")
    op.drop_index("ix_businesses_subcategory_id", table_name="businesses")
    op.drop_index("ix_businesses_category_id", table_name="businesses")
    op.drop_index("ix_businesses_owner_id", table_name="businesses")
    op.drop_index("ix_businesses_slug", table_name="businesses")
    op.drop_table("businesses")
