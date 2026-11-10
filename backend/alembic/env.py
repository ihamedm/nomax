from logging.config import fileConfig
import warnings

import asyncio
from alembic import context
from sqlalchemy.exc import SAWarning
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.db.base import Base  # noqa: F401
from app import models  # noqa: F401  (import every model so metadata is complete)

# Reflection cannot map the PostGIS `geography` type (we filter the column out
# below, but SQLAlchemy still warns while reading it).
warnings.filterwarnings(
    "ignore",
    message="Did not recognize type 'geography' of column 'geo'",
    category=SAWarning,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_name(name: str | None, type_: str, parent_names: dict) -> bool:
    """Keep PostGIS-managed objects out of autogenerate/``alembic check``.

    ``spatial_ref_sys`` belongs to the extension, and ``businesses.geo`` is a
    generated geography column created with raw SQL in the baseline because the
    ORM cannot represent it portably (the test suite runs on SQLite).
    """
    if type_ == "table" and name == "spatial_ref_sys":
        return False
    if type_ == "column" and name == "geo" and parent_names.get("table_name") == "businesses":
        return False
    return True


def include_object(obj, name: str | None, type_: str, reflected: bool, compare_to) -> bool:
    if type_ == "index" and name == "idx_businesses_geo":
        return False
    return True


def run_migrations_offline() -> None:
    context.configure(
        url=str(settings.DATABASE_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_name=include_name,
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_name=include_name,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(str(settings.DATABASE_URL))
    async with engine.begin() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
