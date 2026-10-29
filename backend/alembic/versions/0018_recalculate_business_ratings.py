"""recalculate business ratings from approved public reviews

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa


revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Demo/seed rows carried fabricated rating counts. Ratings must always be
    # derived from approved, non-private reviews.
    op.execute(
        sa.text(
            """
            UPDATE businesses
            SET rating_avg = COALESCE(
                    (
                        SELECT AVG(reviews.rating)
                        FROM reviews
                        WHERE reviews.business_id = businesses.id
                          AND reviews.status = 'approved'
                          AND reviews.is_private = false
                          AND reviews.deleted_at IS NULL
                    ),
                    0
                ),
                rating_count = (
                    SELECT COUNT(*)
                    FROM reviews
                    WHERE reviews.business_id = businesses.id
                      AND reviews.status = 'approved'
                      AND reviews.is_private = false
                      AND reviews.deleted_at IS NULL
                )
            """
        )
    )


def downgrade() -> None:
    # Fabricated seed ratings cannot be reconstructed.
    pass
