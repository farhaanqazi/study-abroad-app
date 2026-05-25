# RESUME — Platform Stabilization & Multi-Tenant SaaS Foundation

> Read this first if resuming the stabilization work. It captures plan state that
> is NOT recoverable from git alone.

## Where we are
- **Branch:** `platform/stabilization-saas-foundation` (off `main`). NOTHING pushed; do not `git push`.
- **Last commit:** `7c37d8c` — "Phase 0+1: foundation, multi-tenant models, clean Alembic baseline".
- **Migration head:** `e76c54a0aa89` (`0001_initial_base`). 12 target tables, native enums `user_role`/`outbox_status`, zero drift (`alembic check` clean), upgrade/downgrade validated repeatable.

## Phase status (from the blueprint execution plan)
- ✅ **Phase 0** — Foundation: `backend/pyproject.toml` (uv, requires-python>=3.12), root `docker-compose.yml`, Clerk fields + prod fail-fast in `app/core/config.py`, `app/db/session.py` (echo=False, `get_session`, `session_scope`), `Base.metadata` naming_convention in `app/db/models/common.py`.
- ✅ **Phase 1** — Models: `app/db/models/tenant.py` (User+clerk_id, Vendor+business_name, VendorMembership M2M unique+composite idx, VendorSiteConfig JSONB), `app/db/models/outbox.py` (OutboxEvent, ProcessedEvent). `UserRole` → owner/agent/viewer; added `OutboxStatus`. Salon `vendor.py`/`user.py` models deleted. `__init__.py` + `base.py` rewired.
- ✅ **Phase 1b** — Clean Alembic: `env.py` runs async (asyncpg, no psycopg2); 3 salon migrations deleted; single baseline; enum lifecycle made repeatable (create at top of upgrade w/ checkfirst, drop at end of downgrade).
- ⏭️ **Phase 2 (NEXT) — Auth & Authz** — NOT STARTED. Was about to delegate to a sub-agent (prompt below). Owns ONLY: `app/core/auth/{__init__,protocol,clerk_provider}.py`, `app/api/dependencies/{__init__,auth}.py`, `tests/unit/test_auth_provider.py`, `tests/integration/test_auth_authz.py`.
- ⏭️ **Phase 3 — Async task infra** — NOT STARTED. Sub-agent owns ONLY: `app/tasks/{__init__,arq_settings,outbox_processor,senders}.py`, `app/worker.py`, `app/services/leads.py`, `app/core/observability.py`, `tests/integration/test_outbox_worker.py`.
- ⏭️ **Phase 4 — Legacy purge + API rewrite** — NOT STARTED. Remove salon runtime: `app/llm/`, `app/messaging/`, `app/services/conversation_service.py`, salon schemas (`app/schemas/state.py`,`messages.py`), salon enums (AppointmentStatus/ConversationStep/NotificationJob*/ChannelType/DigestPreference), `sql/`, `run_migration.py`, `backend/docs/horizon-reference/`. Rewrite routers under `/api/v1/console/**` with `TenantRequire`; public lead routes delegate to LeadCaptureService. Fix importers that referenced deleted `app.db.models.vendor`/`user` (e.g. `app/api/leads.py`, `app/api/vendor_console.py`, `app/api/deps.py`, `app/api/webhooks.py`, `app/main.py`).
- ⏭️ **Phase 5 — Integration tests + final verification** — NOT STARTED.

## Critical environment gotchas (verified 2026-05-25)
- **No Docker, no `uv`, no Python 3.12** here. venv is Python 3.10. So `docker-compose.yml`/`pyproject.toml` are AUTHORED but NOT runtime-validated here — validate on your machine/CI.
- **venv `alembic`/console scripts have a STALE SHEBANG** (venv relocated from old salon path). Run tools as modules: `venv/bin/python -m alembic ...`. `venv/bin/python` itself works.
- **`ruff` and `pytest` are NOT installed** in the venv. Tests are authored but unrun here; validate via `venv/bin/python -c "import ..."` and inline asyncio scripts.
- **Local disposable DB for migration/worker validation ONLY:**
  `export DATABASE_URL="postgresql+asyncpg://isafar@localhost:5432/agency_platform_dev?sslmode=disable"` and `export ENVIRONMENT=development`, run from `backend/` with `PYTHONPATH=.`. Recreate with `dropdb --if-exists agency_platform_dev && createdb agency_platform_dev`.
- **The `.env` `DATABASE_URL` is a PRODUCTION Supabase pooler.** NEVER run alembic/worker/tests against it. Forbidden per user rules (no irreversible prod actions).

## Hard constraints (user-imposed, this cycle)
- Full execution autonomy; don't ask for routine confirmations. BUT: no `git push`, no merge to protected branches, no deploy/credential changes, no irreversible prod actions.
- Apply skills from `_local/`: **fastapi-patterns** (`_local/.qwen/skills/fastapi-patterns.md`) and Trail-of-Bits **insecure-defaults** (`_local/trailofbits-skills/plugins/insecure-defaults/`). Two deliberate overrides recorded: (1) use the blueprint's transactional OUTBOX, not BackgroundTasks, for notifications; (2) Clerk auth must be RS256/JWKS only — reject HS256 (algorithm-confusion).

## Architectural reconciliations already decided
- Models live under `app/db/models/` (single package w/ shared `Base`), NOT a separate `app/models/domain.py` — one metadata source.
- Kept the rich typed lead tables (inquiries/callbacks/applications/cost_estimates/qr_logs); the blueprint's "Lead.status/processed_at/failure_reason" is satisfied by `OutboxEvent` (durable processing/audit), not per-lead status.
- Added `slowapi` to deps (rate-limiting public lead routes) beyond the blueprint's list.

## Resume mode (user-chosen)
**Delegate to sub-agents.** On resume, re-dispatch AGENT-AUTH (Phase 2) and AGENT-ASYNC
(Phase 3) IN PARALLEL (single message, two Agent calls — disjoint file scopes). Orchestrator
integrates them in Phase 4.

## The two ready-to-dispatch sub-agent prompts
Verbatim, with frozen interface contracts and strict write boundaries:
**`docs/stabilization-agent-prompts.md`**. Copy each block into an Agent (general-purpose) call.
