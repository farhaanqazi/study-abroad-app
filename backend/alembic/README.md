# Alembic migration playbook

This directory holds the Alembic configuration for managing the Postgres
schema. It replaces hand-applied SQL files in `backend/sql/` for all
**future** schema changes. The existing files in `backend/sql/` remain
the canonical record of how the baseline schema was built.

## Where the schema currently lives

- `backend/sql/schema.sql` — comprehensive idempotent baseline
- `backend/sql/migration_v2.sql` — incremental patch on top of schema.sql; still applied by the legacy `run_migration.py` shim during fresh-local-Postgres bootstrap
- `backend/sql/legacy/migration_v3.sql`, `migration_v4_auto_complete.sql`, `migration_v5_morning_reminder.sql` — historical patches already applied to all live environments; kept for reference only
- `backend/sql/rollback_v2.sql` — manual rollback
- `backend/sql/seed_demo.sql` — demo data

The Alembic baseline (`versions/0001_initial_baseline.py`) is intentionally
empty. It marks "the schema as it exists after schema.sql + v2..v5 have been
applied" as the starting point. Real DDL changes start at revision 0002.

## One-time setup per environment

### Existing Supabase database (production / staging)

The schema is already applied. Mark it as managed by Alembic:

```bash
cd backend
alembic stamp head
```

Do **not** run `alembic upgrade head` instead — `stamp` records the head
revision without executing any DDL, which is what you want when the schema
is already in place. (For the empty 0001 baseline `upgrade head` is a no-op,
but the habit matters for revision 0002 and beyond.)

### Fresh local Postgres

The schema must be applied before stamping. Two options:

1. Apply `sql/schema.sql` via psql or Supabase, then `alembic stamp head`.
2. Run the legacy `python run_migration.py` (still works, with deprecation
   notice), then `alembic stamp head`.

For a non-Supabase local Postgres, you also need to stub the `auth` schema
because `schema.sql` calls `auth.uid()` from RLS helpers. A `compat.sql`
is not yet provided — see gotcha #4 below.

## Daily workflow

```bash
cd backend

# Create a new revision (manual)
alembic revision -m "add_staff_availability_table"

# Create a new revision (autogenerate from model changes)
alembic revision --autogenerate -m "add_staff_availability_table"

# Apply pending migrations
alembic upgrade head

# Roll back one revision
alembic downgrade -1

# Inspect state
alembic current
alembic history --verbose
```

## Known gotchas in this project

1. **Native PG enums declared with `create_type=False`** (e.g. [app/db/models/vendor.py:14](../app/db/models/vendor.py#L14)). The `include_object` filter in `env.py` skips ENUM objects so autogenerate doesn't repeatedly emit redundant CREATE/DROP TYPE ops. If you add a new enum, write the `CREATE TYPE` SQL manually and keep `create_type=False` on the column.

2. **RLS policies, triggers, and SECURITY DEFINER functions are invisible to autogenerate.** Any change to `current_user_role()`, `update_updated_at()`, `log_appointment_status_change()`, or any policy must be written by hand as `op.execute("...")` blocks in upgrade/downgrade.

3. **`ALTER TYPE … ADD VALUE` cannot run inside a transaction.** Wrap it:

   ```python
   with op.get_context().autocommit_block():
       op.execute("ALTER TYPE appointment_status ADD VALUE 'new_status'")
   ```

4. **`auth.uid()` is Supabase-only.** Migrations that touch RLS fail against plain Postgres unless `auth.uid()` is stubbed. For CI / local dev on plain Postgres, add a `compat.sql` that creates a stub `auth` schema returning NULL.

5. **Driver swap.** The app runs on `postgresql+asyncpg://`; Alembic runs on `postgresql+psycopg2://`. The conversion happens in `env.py:_migration_url()`. Don't change the model code's async driver — only the Alembic process uses psycopg2.

6. **Don't combine schema baseline with v3-v5 patches in one revision** when you eventually replace the empty 0001 with real DDL. Do it incrementally so each step can be tested forward-rolling in staging.

## What to do with backend/sql/ going forward

- `schema.sql` stays as the canonical bootstrap for fresh databases.
- New schema changes go through Alembic, **not** new `migration_vN.sql` files.
- The v3-v5 patches have been archived to `backend/sql/legacy/`. They are not re-applied by Alembic; their effects are already part of the live schema.
