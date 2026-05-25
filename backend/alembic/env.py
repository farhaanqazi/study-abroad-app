from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402  (triggers model imports)


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _migration_url() -> str:
    """Return a sync DSN for psycopg2.

    The application uses `postgresql+asyncpg`; Alembic runs synchronously, so
    we swap the driver while keeping host, database, and credentials intact.
    """
    raw = get_settings().database_url.strip()
    for prefix in ("postgresql+asyncpg://", "postgres://", "postgresql://"):
        if raw.startswith(prefix):
            return "postgresql+psycopg2://" + raw.split("://", 1)[1]
    return raw


config.set_main_option("sqlalchemy.url", _migration_url())

target_metadata = Base.metadata


# Tables that exist in the database but are intentionally not modelled in SQLAlchemy.
# These are managed via raw SQL migrations (RLS-aware audit logs, operational
# tables, or legacy artifacts) and autogenerate would otherwise try to drop them.
IGNORED_TABLE_NAMES = {
    "appointment_status_log",  # populated by trigger; lives in sql/schema.sql
    "vendor_closures",          # operational table; lives in sql/schema.sql
    "schema_migrations",       # legacy migration tracker, predates Alembic
}


def include_object(object_, name, type_, reflected, compare_to):
    """Filter what autogenerate considers.

    - Skip non-public schemas so we don't try to manage Supabase's `auth`,
      `storage`, `realtime`, or `extensions` schemas.
    - Skip tables listed in IGNORED_TABLE_NAMES so autogenerate doesn't
      emit DROP TABLE ops for tables managed in raw SQL.
    - Skip native PostgreSQL ENUM type objects: they're declared with
      `create_type=False` in the models because they're owned by SQL
      migrations, and autogenerate would otherwise emit redundant
      CREATE/DROP TYPE ops on every run.
    """
    if type_ == "schema" and name not in (None, "public"):
        return False
    if type_ == "table":
        if getattr(object_, "schema", None) not in (None, "public"):
            return False
        if name in IGNORED_TABLE_NAMES:
            return False
    if type_ in ("column", "index", "unique_constraint", "foreign_key_constraint"):
        parent_table = getattr(object_, "table", None)
        if parent_table is not None and parent_table.name in IGNORED_TABLE_NAMES:
            return False
    if isinstance(object_, PG_ENUM):
        return False
    return True


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        include_schemas=False,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
            include_schemas=False,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
