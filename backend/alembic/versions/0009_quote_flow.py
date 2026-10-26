"""quote flow fields
Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("quote_requests") as batch:
        batch.add_column(sa.Column("subcategory_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("address", sa.String(length=255), nullable=False, server_default=""))
        batch.add_column(sa.Column("neighborhood", sa.String(length=120), nullable=True))
        batch.add_column(sa.Column("geo_lat", sa.Float(), nullable=True))
        batch.add_column(sa.Column("geo_lng", sa.Float(), nullable=True))
        batch.add_column(sa.Column("is_urgent", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("accepted_offer_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("phone_revealed_to", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_quote_subcategory", "subcategories", ["subcategory_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index(
            "uq_quote_active_per_user",
            ["customer_id"],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )
    with op.batch_alter_table("offers") as batch:
        batch.add_column(sa.Column("brand", sa.String(length=120), nullable=True))
    op.execute("UPDATE quote_requests SET status = 'active' WHERE status = 'open'")


def downgrade() -> None:
    with op.batch_alter_table("offers") as batch:
        batch.drop_column("brand")
    with op.batch_alter_table("quote_requests") as batch:
        batch.drop_index("uq_quote_active_per_user")
        batch.drop_constraint("fk_quote_subcategory", type_="foreignkey")
        batch.drop_column("phone_revealed_to")
        batch.drop_column("accepted_offer_id")
        batch.drop_column("is_urgent")
        batch.drop_column("geo_lng")
        batch.drop_column("geo_lat")
        batch.drop_column("neighborhood")
        batch.drop_column("address")
        batch.drop_column("subcategory_id")
