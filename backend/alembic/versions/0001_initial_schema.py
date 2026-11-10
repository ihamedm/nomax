"""initial schema (squashed baseline)

Revision ID: 0001
Revises:
Create Date: 2026-11-04

This baseline replaces the 23 development migrations (0001-0023). It is
generated from ``app.models``, so the ORM metadata is the single source of
truth and ``alembic check`` stays silent. The old chain mixed schema changes
with one-off data backfills that are meaningless on an empty database; those
were dropped. Seed data lives in ``app.cli`` (seed-categories,
seed-demo-businesses, create-superadmin), not in migrations.

PostGIS-specific pieces that cannot be expressed in the ORM metadata are added
manually below: the extension, the generated ``geo`` geography column and its
GIST index.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        # The generated `geo` column and GIST index below need PostGIS.
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.create_table('ads',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('image_url', sa.String(length=255), nullable=True),
    sa.Column('target_url', sa.String(length=255), nullable=True),
    sa.Column('body', sa.Text(), nullable=True),
    sa.Column('placement', sa.String(length=40), server_default='home_banner', nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('app_settings',
    sa.Column('key', sa.String(length=80), nullable=False),
    sa.Column('value', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('categories',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('icon', sa.String(length=16), nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_categories_slug'), 'categories', ['slug'], unique=True)
    op.create_table('contact_messages',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('phone', sa.String(length=11), nullable=False),
    sa.Column('subject', sa.String(length=160), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('is_read', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('scheduled_jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=60), nullable=False),
    sa.Column('payload', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=False),
    sa.Column('run_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('idempotency_key', sa.String(length=120), nullable=False),
    sa.Column('locked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('idempotency_key')
    )
    op.create_index(op.f('ix_scheduled_jobs_run_at'), 'scheduled_jobs', ['run_at'], unique=False)
    op.create_index(op.f('ix_scheduled_jobs_status'), 'scheduled_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_scheduled_jobs_type'), 'scheduled_jobs', ['type'], unique=False)
    op.create_table('sms_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('phone', sa.String(length=11), nullable=False),
    sa.Column('purpose', sa.String(length=30), nullable=False),
    sa.Column('provider', sa.String(length=30), nullable=False),
    sa.Column('provider_message_id', sa.String(length=120), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sms_logs_created_at'), 'sms_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_sms_logs_phone'), 'sms_logs', ['phone'], unique=False)
    op.create_table('tags',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('is_custom', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('phone', sa.String(length=11), nullable=False),
    sa.Column('national_id', sa.String(length=10), nullable=True),
    sa.Column('full_name', sa.String(length=120), nullable=True),
    sa.Column('role', sa.Enum('customer', 'owner', 'admin', 'superadmin', name='userrole', native_enum=False, length=20), server_default='customer', nullable=False),
    sa.Column('permissions', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    sa.Column('is_verified', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('is_phone_verified', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('is_national_id_verified', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('national_id_verified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('hashed_password', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('national_id')
    )
    op.create_index(op.f('ix_users_phone'), 'users', ['phone'], unique=True)
    op.create_table('admin_audit_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.String(length=100), nullable=True),
    sa.Column('before', sa.JSON(), nullable=True),
    sa.Column('after', sa.JSON(), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_admin_audit_logs_actor_id'), 'admin_audit_logs', ['actor_id'], unique=False)
    op.create_table('category_suggestions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=30), nullable=False),
    sa.Column('parent_category_id', sa.Integer(), nullable=True),
    sa.Column('suggested_name', sa.String(length=120), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['parent_category_id'], ['categories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('device_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('token', sa.String(length=255), nullable=False),
    sa.Column('platform', sa.String(length=20), server_default='android', nullable=False),
    sa.Column('app_version', sa.String(length=40), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'token', name='uq_device_provider_token')
    )
    op.create_index(op.f('ix_device_tokens_user_id'), 'device_tokens', ['user_id'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('type', sa.String(length=40), server_default='system', nullable=False),
    sa.Column('payload', sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('is_read', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_table('subcategories',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=80), nullable=False),
    sa.Column('icon', sa.String(length=16), nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('standard_tags', sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('category_id', 'slug', name='uq_subcategories_category_slug')
    )
    op.create_index(op.f('ix_subcategories_category_id'), 'subcategories', ['category_id'], unique=False)
    op.create_table('businesses',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('subcategory_id', sa.Integer(), nullable=True),
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('slug', sa.String(length=200), nullable=False),
    sa.Column('short_description', sa.String(length=120), server_default='', nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('phone_business', sa.String(length=11), nullable=True),
    sa.Column('address', sa.String(length=255), nullable=False),
    sa.Column('geo_lat', sa.Float(), nullable=True),
    sa.Column('geo_lng', sa.Float(), nullable=True),
    sa.Column('instagram', sa.String(length=100), nullable=True),
    sa.Column('is_24h', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('is_verified', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='businessstatus', native_enum=False, length=20), server_default='pending', nullable=False),
    sa.Column('rejection_reason', sa.String(length=255), nullable=True),
    sa.Column('rating_avg', sa.Float(), server_default=sa.text('0'), nullable=False),
    sa.Column('rating_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('view_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('profile_image_url', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('geo_lat IS NULL OR (geo_lat BETWEEN -90 AND 90)', name='ck_business_geo_lat'),
    sa.CheckConstraint('geo_lng IS NULL OR (geo_lng BETWEEN -180 AND 180)', name='ck_business_geo_lng'),
    sa.CheckConstraint('rating_avg >= 0 AND rating_avg <= 5', name='ck_business_rating_avg'),
    sa.CheckConstraint('rating_count >= 0', name='ck_business_rating_count'),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['subcategory_id'], ['subcategories.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_businesses_category_pair', 'businesses', ['category_id', 'subcategory_id'], unique=False)
    op.create_index('idx_businesses_status', 'businesses', ['status'], unique=False, postgresql_where=sa.text("status = 'approved'"))
    op.create_index(op.f('ix_businesses_owner_id'), 'businesses', ['owner_id'], unique=False)
    op.create_index(op.f('ix_businesses_slug'), 'businesses', ['slug'], unique=True)
    op.create_index(op.f('ix_businesses_subcategory_id'), 'businesses', ['subcategory_id'], unique=False)
    if is_postgres:
        # Generated geography column: the ORM only writes lat/lng, while all
        # radial search uses this indexed column with ST_DWithin/ST_Distance.
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
    op.create_table('notification_deliveries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('notification_id', sa.Uuid(), nullable=False),
    sa.Column('device_token_id', sa.Uuid(), nullable=False),
    sa.Column('provider', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='queued', nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['device_token_id'], ['device_tokens.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['notification_id'], ['notifications.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_deliveries_notification_id'), 'notification_deliveries', ['notification_id'], unique=False)
    op.create_table('quote_requests',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('subcategory_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=160), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('address', sa.String(length=255), server_default='', nullable=False),
    sa.Column('neighborhood', sa.String(length=120), nullable=True),
    sa.Column('geo_lat', sa.Float(), nullable=True),
    sa.Column('geo_lng', sa.Float(), nullable=True),
    sa.Column('is_urgent', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('accepted_offer_id', sa.Uuid(), nullable=True),
    sa.Column('phone_revealed_to', sa.Uuid(), nullable=True),
    sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('dispatch_round', sa.Integer(), server_default='0', nullable=False),
    sa.Column('dispatch_status', sa.String(length=24), server_default='pending', nullable=False),
    sa.Column('last_dispatched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_dispatch_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['customer_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subcategory_id'], ['subcategories.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quote_requests_accepted_at'), 'quote_requests', ['accepted_at'], unique=False)
    op.create_index(op.f('ix_quote_requests_category_id'), 'quote_requests', ['category_id'], unique=False)
    op.create_index(op.f('ix_quote_requests_created_at'), 'quote_requests', ['created_at'], unique=False)
    op.create_index(op.f('ix_quote_requests_customer_id'), 'quote_requests', ['customer_id'], unique=False)
    op.create_index(op.f('ix_quote_requests_dispatch_status'), 'quote_requests', ['dispatch_status'], unique=False)
    op.create_index(op.f('ix_quote_requests_next_dispatch_at'), 'quote_requests', ['next_dispatch_at'], unique=False)
    op.create_index(op.f('ix_quote_requests_status'), 'quote_requests', ['status'], unique=False)
    op.create_index('uq_quote_active_per_user', 'quote_requests', ['customer_id'], unique=True, sqlite_where=sa.text("status = 'active'"), postgresql_where=sa.text("status = 'active'"))
    op.create_table('search_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('query', sa.String(length=160), nullable=True),
    sa.Column('normalized_query', sa.String(length=160), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('subcategory_id', sa.Integer(), nullable=True),
    sa.Column('results_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('source', sa.String(length=20), server_default='search', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['subcategory_id'], ['subcategories.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_search_logs_category_id'), 'search_logs', ['category_id'], unique=False)
    op.create_index(op.f('ix_search_logs_created_at'), 'search_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_search_logs_normalized_query'), 'search_logs', ['normalized_query'], unique=False)
    op.create_index(op.f('ix_search_logs_subcategory_id'), 'search_logs', ['subcategory_id'], unique=False)
    op.create_index(op.f('ix_search_logs_user_id'), 'search_logs', ['user_id'], unique=False)
    op.create_table('bookmarks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'business_id', name='uq_bookmark_user_business')
    )
    op.create_index(op.f('ix_bookmarks_business_id'), 'bookmarks', ['business_id'], unique=False)
    op.create_index(op.f('ix_bookmarks_user_id'), 'bookmarks', ['user_id'], unique=False)
    op.create_table('business_images',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('url', sa.String(length=255), nullable=False),
    sa.Column('is_main', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.CheckConstraint('sort_order >= 0', name='ck_business_images_sort_order'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_business_images_business_id'), 'business_images', ['business_id'], unique=False)
    op.create_table('business_tags',
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('tag_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('business_id', 'tag_id')
    )
    op.create_table('licenses',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('license_number', sa.String(length=80), nullable=False),
    sa.Column('image_url', sa.String(length=255), nullable=True),
    sa.Column('is_verified_by_admin', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_licenses_business_id'), 'licenses', ['business_id'], unique=False)
    op.create_table('offers',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('request_id', sa.Uuid(), nullable=False),
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('price', sa.Numeric(precision=12, scale=0), nullable=True),
    sa.Column('unit', sa.String(length=30), nullable=True),
    sa.Column('brand', sa.String(length=120), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['request_id'], ['quote_requests.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'request_id', name='uq_offer_business_request')
    )
    op.create_index('idx_offers_pending', 'offers', ['request_id'], unique=False, postgresql_where=sa.text("status = 'pending'"))
    op.create_index(op.f('ix_offers_business_id'), 'offers', ['business_id'], unique=False)
    op.create_index(op.f('ix_offers_request_id'), 'offers', ['request_id'], unique=False)
    op.create_table('quote_deliveries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('request_id', sa.Uuid(), nullable=False),
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('round', sa.Integer(), server_default='1', nullable=False),
    sa.Column('source', sa.String(length=20), server_default='auto', nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['request_id'], ['quote_requests.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('request_id', 'business_id', name='uq_quote_delivery_request_business')
    )
    op.create_index(op.f('ix_quote_deliveries_business_id'), 'quote_deliveries', ['business_id'], unique=False)
    op.create_index(op.f('ix_quote_deliveries_request_id'), 'quote_deliveries', ['request_id'], unique=False)
    op.create_index(op.f('ix_quote_deliveries_round'), 'quote_deliveries', ['round'], unique=False)
    op.create_index(op.f('ix_quote_deliveries_seen_at'), 'quote_deliveries', ['seen_at'], unique=False)
    op.create_index(op.f('ix_quote_deliveries_sent_at'), 'quote_deliveries', ['sent_at'], unique=False)
    op.create_table('quote_dispatch_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('request_id', sa.Uuid(), nullable=False),
    sa.Column('round', sa.Integer(), nullable=False),
    sa.Column('trigger', sa.String(length=20), server_default='initial', nullable=False),
    sa.Column('candidate_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('delivered_count', sa.Integer(), server_default='0', nullable=False),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['request_id'], ['quote_requests.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_quote_dispatch_runs_created_at'), 'quote_dispatch_runs', ['created_at'], unique=False)
    op.create_index(op.f('ix_quote_dispatch_runs_request_id'), 'quote_dispatch_runs', ['request_id'], unique=False)
    op.create_table('reviews',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=True),
    sa.Column('author_name', sa.String(length=120), nullable=True),
    sa.Column('reply', sa.Text(), nullable=True),
    sa.Column('replied_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
    sa.Column('is_private', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('owner_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('rating BETWEEN 1 AND 5', name='ck_review_rating'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'user_id', name='uq_review_business_user')
    )
    op.create_index('idx_reviews_business_status', 'reviews', ['business_id', 'status'], unique=False)
    op.create_index('idx_reviews_owner_unseen', 'reviews', ['business_id', 'status'], unique=False, postgresql_where=sa.text("owner_seen_at IS NULL AND status IN ('pending', 'private')"))
    op.create_index(op.f('ix_reviews_business_id'), 'reviews', ['business_id'], unique=False)
    op.create_index(op.f('ix_reviews_user_id'), 'reviews', ['user_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_reviews_user_id'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_business_id'), table_name='reviews')
    op.drop_index('idx_reviews_owner_unseen', table_name='reviews', postgresql_where=sa.text("owner_seen_at IS NULL AND status IN ('pending', 'private')"))
    op.drop_index('idx_reviews_business_status', table_name='reviews')
    op.drop_table('reviews')
    op.drop_index(op.f('ix_quote_dispatch_runs_request_id'), table_name='quote_dispatch_runs')
    op.drop_index(op.f('ix_quote_dispatch_runs_created_at'), table_name='quote_dispatch_runs')
    op.drop_table('quote_dispatch_runs')
    op.drop_index(op.f('ix_quote_deliveries_sent_at'), table_name='quote_deliveries')
    op.drop_index(op.f('ix_quote_deliveries_seen_at'), table_name='quote_deliveries')
    op.drop_index(op.f('ix_quote_deliveries_round'), table_name='quote_deliveries')
    op.drop_index(op.f('ix_quote_deliveries_request_id'), table_name='quote_deliveries')
    op.drop_index(op.f('ix_quote_deliveries_business_id'), table_name='quote_deliveries')
    op.drop_table('quote_deliveries')
    op.drop_index(op.f('ix_offers_request_id'), table_name='offers')
    op.drop_index(op.f('ix_offers_business_id'), table_name='offers')
    op.drop_index('idx_offers_pending', table_name='offers', postgresql_where=sa.text("status = 'pending'"))
    op.drop_table('offers')
    op.drop_index(op.f('ix_licenses_business_id'), table_name='licenses')
    op.drop_table('licenses')
    op.drop_table('business_tags')
    op.drop_index(op.f('ix_business_images_business_id'), table_name='business_images')
    op.drop_table('business_images')
    op.drop_index(op.f('ix_bookmarks_user_id'), table_name='bookmarks')
    op.drop_index(op.f('ix_bookmarks_business_id'), table_name='bookmarks')
    op.drop_table('bookmarks')
    op.drop_index(op.f('ix_search_logs_user_id'), table_name='search_logs')
    op.drop_index(op.f('ix_search_logs_subcategory_id'), table_name='search_logs')
    op.drop_index(op.f('ix_search_logs_normalized_query'), table_name='search_logs')
    op.drop_index(op.f('ix_search_logs_created_at'), table_name='search_logs')
    op.drop_index(op.f('ix_search_logs_category_id'), table_name='search_logs')
    op.drop_table('search_logs')
    op.drop_index('uq_quote_active_per_user', table_name='quote_requests', sqlite_where=sa.text("status = 'active'"), postgresql_where=sa.text("status = 'active'"))
    op.drop_index(op.f('ix_quote_requests_status'), table_name='quote_requests')
    op.drop_index(op.f('ix_quote_requests_next_dispatch_at'), table_name='quote_requests')
    op.drop_index(op.f('ix_quote_requests_dispatch_status'), table_name='quote_requests')
    op.drop_index(op.f('ix_quote_requests_customer_id'), table_name='quote_requests')
    op.drop_index(op.f('ix_quote_requests_created_at'), table_name='quote_requests')
    op.drop_index(op.f('ix_quote_requests_category_id'), table_name='quote_requests')
    op.drop_index(op.f('ix_quote_requests_accepted_at'), table_name='quote_requests')
    op.drop_table('quote_requests')
    op.drop_index(op.f('ix_notification_deliveries_notification_id'), table_name='notification_deliveries')
    op.drop_table('notification_deliveries')
    op.drop_index(op.f('ix_businesses_subcategory_id'), table_name='businesses')
    op.drop_index(op.f('ix_businesses_slug'), table_name='businesses')
    op.drop_index(op.f('ix_businesses_owner_id'), table_name='businesses')
    op.drop_index('idx_businesses_status', table_name='businesses', postgresql_where=sa.text("status = 'approved'"))
    op.drop_index('idx_businesses_category_pair', table_name='businesses')
    # idx_businesses_geo and the geo column are dropped with the table.
    op.drop_table('businesses')
    op.drop_index(op.f('ix_subcategories_category_id'), table_name='subcategories')
    op.drop_table('subcategories')
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_device_tokens_user_id'), table_name='device_tokens')
    op.drop_table('device_tokens')
    op.drop_table('category_suggestions')
    op.drop_index(op.f('ix_admin_audit_logs_actor_id'), table_name='admin_audit_logs')
    op.drop_table('admin_audit_logs')
    op.drop_index(op.f('ix_users_phone'), table_name='users')
    op.drop_table('users')
    op.drop_table('tags')
    op.drop_index(op.f('ix_sms_logs_phone'), table_name='sms_logs')
    op.drop_index(op.f('ix_sms_logs_created_at'), table_name='sms_logs')
    op.drop_table('sms_logs')
    op.drop_index(op.f('ix_scheduled_jobs_type'), table_name='scheduled_jobs')
    op.drop_index(op.f('ix_scheduled_jobs_status'), table_name='scheduled_jobs')
    op.drop_index(op.f('ix_scheduled_jobs_run_at'), table_name='scheduled_jobs')
    op.drop_table('scheduled_jobs')
    op.drop_table('contact_messages')
    op.drop_index(op.f('ix_categories_slug'), table_name='categories')
    op.drop_table('categories')
    op.drop_table('app_settings')
    op.drop_table('ads')
    # ### end Alembic commands ###
