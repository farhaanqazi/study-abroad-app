"""DEPRECATED entry point.

Schema management is moving to Alembic. New workflow (run from backend/):

    alembic upgrade head           # apply pending migrations
    alembic stamp head             # mark an existing schema as managed
    alembic revision -m "..."      # create a new migration
    alembic history --verbose      # show revision history

This script is preserved only for fresh-local-Postgres bootstrap, because
Alembic's 0001 baseline is intentionally empty — the actual schema bootstrap
still lives in sql/schema.sql + sql/migration_v2..v5.sql + sql/seed_demo.sql.

After running this once on a fresh local DB, run:

    alembic stamp head

to register the database as Alembic-managed going forward. See
alembic/README.md for the full playbook.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import asyncpg

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402


def normalize_url_for_asyncpg(db_url: str) -> str:
    db_url = db_url.strip()
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://", "postgres://"):
        if db_url.startswith(prefix):
            return "postgresql://" + db_url.split("://", 1)[1]
    return db_url


def mask_database_url(db_url: str) -> str:
    parsed = urlparse(db_url)
    if not parsed.password:
        return db_url
    username = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:***@{host}{port}"
    return urlunparse(parsed._replace(netloc=netloc))


async def run_sql_file(conn, filepath: str) -> None:
    print(f"Executing {filepath}...")
    with open(filepath, "r", encoding="utf-8") as f:
        sql = f.read()
    await conn.execute(sql)
    print(f"Finished {filepath}.")


def _print_deprecation_banner() -> None:
    border = "=" * 72
    print(border, file=sys.stderr)
    print("DEPRECATED: run_migration.py is being replaced by Alembic.", file=sys.stderr)
    print("New workflow:  alembic upgrade head   (run from backend/)", file=sys.stderr)
    print("See backend/alembic/README.md for the playbook.", file=sys.stderr)
    print(border, file=sys.stderr)
    print(file=sys.stderr)


async def main() -> None:
    _print_deprecation_banner()

    db_url = get_settings().database_url
    if not db_url:
        print("DATABASE_URL not configured.")
        return

    db_url = normalize_url_for_asyncpg(db_url)

    print(f"Connecting to {mask_database_url(db_url)}...")
    try:
        conn = await asyncpg.connect(db_url)
        await run_sql_file(conn, "sql/migration_v2.sql")
        await run_sql_file(conn, "sql/seed_demo.sql")
        await conn.close()
        print("Legacy migrations applied.")
        print()
        print("NOTE: this script does not apply migration_v3..v5.")
        print("After verifying the schema is current, run `alembic stamp head`")
        print("to register the database under Alembic going forward.")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
