from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402  (registers all models on Base.metadata)
from app.db.session import normalize_database_url_for_asyncpg  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object_, name, type_, reflected, compare_to):
    """Restrict autogenerate to the public schema. Guards against ever
    touching an external provider's managed schemas (auth/storage/realtime)
    if the configured database happens to be a managed Postgres."""
    if type_ == "schema" and name not in (None, "public"):
        return False
    if type_ == "table" and getattr(object_, "schema", None) not in (None, "public"):
        return False
    return True


def _do_run_migrations(connection) -> None:
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


async def run_migrations_online() -> None:
    """Run migrations through an async (asyncpg) engine — the app uses no sync
    DB driver, so neither does Alembic."""
    settings = get_settings()
    clean_url, ssl_mode = normalize_database_url_for_asyncpg(settings.database_url)

    connect_args: dict = {}
    if ssl_mode in ("require", "verify-full", "verify-ca"):
        import ssl as _ssl

        import certifi

        ctx = _ssl.create_default_context(cafile=certifi.where())
        ctx.check_hostname = False
        ctx.verify_mode = _ssl.CERT_NONE
        connect_args["ssl"] = ctx

    engine = create_async_engine(clean_url, poolclass=NullPool, connect_args=connect_args)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await engine.dispose()


def run_migrations_offline() -> None:
    clean_url, _ = normalize_database_url_for_asyncpg(get_settings().database_url)
    context.configure(
        url=clean_url,
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


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
