# RESUME — Platform Stabilization & Multi-Tenant SaaS Foundation

> Read this first if resuming the stabilization work. It captures plan state that
> is NOT recoverable from git alone.

## ✅ STATUS — PLATFORM ADMIN CONSOLE INITIATIVE COMPLETE (2026-05-26)
A second initiative (on top of the stabilization rebuild) added a **platform
back-office** + **gated workspace provisioning**. All phases A–F done, validated,
committed locally (NOT pushed) on `platform/stabilization-saas-foundation`:
- `632907e` A — platform auth tier (PlatformRole none/support/admin/superadmin),
  WorkspaceRequest + AuditLog models, migration 0002, `PlatformRequire`, fail-closed
  env bootstrap (`PLATFORM_SUPERADMINS`), `/me.platform_role`
- `4c4a704` B — workspace request → admin approve/reject (transactional provision)
- `f5611d1` C/D schema — Invitation + SupportTicket models, migration 0003
- `885760f` C/D — 21 `/api/v1/admin/**` routes (vendors/members/users/ops/audit/
  read-only-view-as/support), all PlatformRequire-gated + audited
- `e11ba5b` E — admin console frontend (`/admin` route tree, role-gated UI) +
  ConsoleHome "Request a workspace" empty-state
- Phase F — `tests/conftest.py` (per-test engine reset fixes async-loop reuse),
  rewrote stale `test_config_validators.py` to the Clerk contract, added
  `test_admin_authz_matrix.py` (authz matrix + approval e2e). **55 tests pass**
  (`pytest` now installed in venv). insecure-defaults sweep: no new fail-open.

**Become the first admin:** set `PLATFORM_SUPERADMINS=<your clerk_id-or-email>` in
env (see backend/.env.example) and log in — auto-granted superadmin. Or run
`PYTHONPATH=. python scripts/grant_platform_role.py <email|clerk_id> superadmin`.
**Run tests:** `createdb agency_test && DATABASE_URL=...agency_test... alembic upgrade head`,
then `PYTHONPATH=. venv/bin/python -m pytest`. Migration head is now `b49ef0fcc0b4` (0003).
**Known pre-existing (not from this work):** Supabase `CERT_NONE` SSL workaround in
db/session.py; Clerk default session token omits `email` (we fall back to a
placeholder — add an `email` claim in Clerk to fix); dead salon config in .env.example
(telegram/whatsapp) can be pruned.

## ✅ STATUS — OVERNIGHT RUN COMPLETE (2026-05-25)
All phases 2→6 done, validated, committed locally (NOT pushed). The app is a
full-fledged working app against the local disposable DB. Commits on
`platform/stabilization-saas-foundation`:
- `b28f1fa` Phase 2+3 — Clerk auth/authz (RS256 JWKS, TenantRequire) + transactional outbox worker
- `01f603b` Phase 4 — purge salon runtime + rewrite API under `/api/v1`, integrate auth+outbox
- `e6fc9ac` Phase 5 — fixes from live verification (body resolution, unauth 401)

### Acceptance criteria — all met
- ✅ `alembic upgrade head` builds 12 tables on fresh `agency_platform_dev`.
- ✅ `import app.main` clean; uvicorn boots (salon lifespan stripped).
- ✅ Public `/api/v1/v/{slug}/**` work end-to-end; lead + OutboxEvent persist in ONE txn (verified in DB).
- ✅ `/api/v1/console/{vendor_id}/**` gated by TenantRequire: unauth→401, malformed→401, wrong-tenant→403, member→pass.
- ✅ ARQ worker drains outbox (live drain + retry/backoff + terminal FAILED + idempotency).
- ✅ Frontend `npm run build` succeeds; FastAPI serves the SPA + same-origin `/api/v1`. Public site calls the real endpoints.
- ✅ Tests authored & passing as standalone runners (pytest not installed): auth unit 12/12, auth integration 8/8, outbox integration 3/3.

### How to run locally
```
cd backend
export DATABASE_URL="postgresql+asyncpg://isafar@localhost:5432/agency_platform_dev?sslmode=disable"
export ENVIRONMENT=development REDIS_URL="redis://localhost:6379/0"
dropdb --if-exists agency_platform_dev && createdb agency_platform_dev
PYTHONPATH=. venv/bin/python -m alembic upgrade head
PYTHONPATH=. venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
# worker (needs Redis): PYTHONPATH=. venv/bin/arq app.worker.WorkerSettings
# frontend: cd frontend && npm run build   (or npm run dev)
```

### Deployment notes / non-blocking follow-ups (decided autonomously, none irreversible)
- **SMTP**: `.env` Gmail creds are REJECTED (BadCredentials) — live drain correctly retries+parks FAILED. Set working SMTP for real delivery. Worker logic is proven via monkeypatched-sender test (SENT path).
- **Frontend prod baseURL**: `frontend/.env` bakes `VITE_API_URL=http://localhost:8000` into the bundle. For same-origin SPA-served prod, build with `VITE_API_URL` unset (api.ts already falls back to relative `/api/v1`). Left the dev `.env` untouched.
- **Prod env**: `ENVIRONMENT=production` fail-fasts unless `CLERK_ISSUER`+`CLERK_AUDIENCE` set and `DATABASE_URL` has no placeholders (by design).
- **pytest/ruff/uv/Docker/py3.12** still absent in this env (venv is py3.10); tests run as standalone scripts. Validate in CI.
- Console currently exposes leads (read) + cost-settings (CRUD). Member-management / site-config console routes are future work, not in the acceptance set.

---

## OVERNIGHT MANDATE (read first)
The user is asleep and wants this driven to a **full-fledged working app**, autonomously, in
one continuous run. Don't stop for routine confirmations. "Working app" = acceptance criteria:
- `alembic upgrade head` builds the schema on a fresh disposable local DB (already proven).
- `python -c "import app.main"` is clean and the FastAPI app boots (uvicorn import check).
- Public lead-capture endpoints work end-to-end under `/api/v1` and persist lead + outbox row in one txn.
- `/api/v1/console/**` is auth-protected (401 unauth, 403 wrong tenant) via TenantRequire.
- ARQ worker imports and drains the outbox (validated against the local DB inline).
- Frontend `npm run build` succeeds and the public site calls the `/api/v1` endpoints.
- Integration tests authored; run what the env allows, document what's deferred.
Work through Phases 2→6 in order. Commit locally at each phase (NO push/merge/prod). If truly
blocked on an irreversible/destructive decision, leave a clear note in this file and continue
with the next independent task. Keep this doc + the todo list updated as you go.

## Where we are
- **Branch:** `platform/stabilization-saas-foundation` (off `main`). NOTHING pushed; do not `git push`.
- **Last commit:** `7c37d8c` — "Phase 0+1: foundation, multi-tenant models, clean Alembic baseline".
- **Migration head:** `e76c54a0aa89` (`0001_initial_base`). 12 target tables, native enums `user_role`/`outbox_status`, zero drift (`alembic check` clean), upgrade/downgrade validated repeatable.

## Phase status (from the blueprint execution plan)
- ✅ **Phase 0** — Foundation: `backend/pyproject.toml` (uv, requires-python>=3.12), root `docker-compose.yml`, Clerk fields + prod fail-fast in `app/core/config.py`, `app/db/session.py` (echo=False, `get_session`, `session_scope`), `Base.metadata` naming_convention in `app/db/models/common.py`.
- ✅ **Phase 1** — Models: `app/db/models/tenant.py` (User+clerk_id, Vendor+business_name, VendorMembership M2M unique+composite idx, VendorSiteConfig JSONB), `app/db/models/outbox.py` (OutboxEvent, ProcessedEvent). `UserRole` → owner/agent/viewer; added `OutboxStatus`. Salon `vendor.py`/`user.py` models deleted. `__init__.py` + `base.py` rewired.
- ✅ **Phase 1b** — Clean Alembic: `env.py` runs async (asyncpg, no psycopg2); 3 salon migrations deleted; single baseline; enum lifecycle made repeatable (create at top of upgrade w/ checkfirst, drop at end of downgrade).
- ✅ **Phase 2 — Auth & Authz** — DONE (`b28f1fa`). `app/core/auth/{__init__,protocol,clerk_provider}.py`, `app/api/dependencies/{__init__,auth}.py` + tests. RS256-only JWKS, lazy provisioning, `TenantRequire(owner>agent>viewer)`. (Phase 5 set HTTPBearer `auto_error=False` so missing header → 401.)
- ✅ **Phase 3 — Async task infra** — DONE (`b28f1fa`). `app/tasks/*`, `app/worker.py`, `app/services/leads.py`, `app/core/observability.py` + test. Transactional outbox, `FOR UPDATE SKIP LOCKED` drain, exp-backoff retries, ProcessedEvent idempotency, cron drain every 10s.
- ✅ **Phase 4 — Legacy purge + API rewrite** — DONE (`01f603b`). Removed `app/llm/`, `app/messaging/`, conversation/webhook/tenant/email services, salon schemas, `app/redis/state_store.py`, `app/api/webhooks.py`, salon enums, `sql/`, `run_migration.py`. Public leads → LeadCaptureService; console → `/api/v1/console/{vendor_id}/**` + TenantRequire. All importers fixed (`tenant.Vendor`, `vendor.business_name`).
- ✅ **Phase 5 — Integration tests + final verification** — DONE (`e6fc9ac`). Live end-to-end on local DB + 23 authored checks pass. See status block at top.
- ✅ **Phase 6 — Frontend** — DONE (no source change needed; already wired to `/api/v1`). `npm run build` green; FastAPI serves the SPA + deep links same-origin.

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
