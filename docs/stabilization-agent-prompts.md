# Ready-to-dispatch sub-agent prompts (Phases 2 & 3)

Resume mode chosen by user: **delegate to sub-agents**, run in parallel (disjoint file
scopes; orchestrator integrates in Phase 4). Dispatch both in a single message so they run
concurrently. Working dir for both: `backend/`.

---

## AGENT-AUTH (Phase 2)

You are AGENT-AUTH in a multi-agent build of a multi-tenant study-abroad SaaS (FastAPI, SQLAlchemy 2.0 async, Postgres). Working dir: `backend`. Another agent is concurrently editing `app/tasks/`, `app/worker.py`, `app/services/leads.py` — DO NOT touch those.

### STRICT WRITE BOUNDARY — create/edit ONLY these files:
- app/core/auth/__init__.py
- app/core/auth/protocol.py
- app/core/auth/clerk_provider.py
- app/api/dependencies/__init__.py
- app/api/dependencies/auth.py
- tests/unit/test_auth_provider.py
- tests/integration/test_auth_authz.py

DO NOT modify: app/main.py, app/api/router.py, any existing app/api/*.py, app/db/**, app/core/config.py, app/core/enums.py, pyproject.toml. Integration wiring is the orchestrator's job.

### Frozen interfaces (already implemented, read-only):
- `from app.db.models.tenant import User, Vendor, VendorMembership` — User(id:UUID, clerk_id:str unique, email:str unique, deleted_at, memberships:list[VendorMembership]); VendorMembership(user_id, vendor_id, role:UserRole); Vendor(id, slug).
- `from app.core.enums import UserRole` — OWNER="owner", AGENT="agent", VIEWER="viewer" (owner > agent > viewer).
- `from app.db.session import get_session` — FastAPI dependency yielding AsyncSession.
- `from app.core.config import get_settings` with fields `clerk_issuer`, `clerk_audience`, `effective_clerk_jwks_url` (property), `clerk_jwks_cache_ttl_seconds`. `clerk_secret_key` exists but must NEVER be sent to the JWKS endpoint.
- venv deps: fastapi, python-jose[cryptography], httpx, sqlalchemy, structlog. (ruff/pytest NOT installed.)

### Requirements:
1. protocol.py — provider-agnostic. `AuthClaims` (subject/clerk_id, email, raw claims, issuer, audience) + `IdentityProvider` Protocol with `async def verify(token)->AuthClaims`. NO clerk/jose imports.
2. clerk_provider.py — `ClerkProvider(IdentityProvider)`: fetch JWKS via httpx from `effective_clerk_jwks_url` (public, no secret); TTL key cache; refetch once on unknown kid; select by header `kid`; validate signature/iss/aud/exp/nbf; **RS256 ONLY (algorithms=["RS256"]), reject any non-RS256 alg** (anti algorithm-confusion); never decode without verification; raise a clear auth error on failure.
3. dependencies/auth.py — HTTPBearer (auto_error→401); cached provider accessor; `get_current_user` does token verify + **lazy provisioning** (insert User on first sight by clerk_id+email; handle unique-violation race); `TenantRequire(*roles)` dependency FACTORY: read `vendor_id` from path, load caller's membership, 403 if none or role not permitted (expand allowed set by owner>agent>viewer hierarchy), return context (user, vendor_id, role). Map to 401/403; structlog without logging secrets/tokens; never expose internals.
4. NO fail-open: misconfigured provider (missing issuer/audience/jwks) must FAIL CLOSED.
5. Tests: unit (kid selection, non-RS256 rejected, bad iss/aud/exp rejected — craft tokens with an RSA keypair) + integration (missing→401, malformed→401, valid→lazy provision, wrong-tenant→403, correct→pass; monkeypatch provider, no network).

### Validation:
- `cd backend && PYTHONPATH=. venv/bin/python -c "import app.core.auth.protocol, app.core.auth.clerk_provider, app.api.dependencies.auth; print('auth imports OK')"` must pass.
- pytest NOT installed — don't block on it; smoke-test via inline `venv/bin/python` asyncio if useful. Report ran-vs-deferred.

Return: files created, design decisions (RS256 enforcement, role hierarchy, lazy-provision race), import-check result, wiring notes for `/api/v1/console`.

---

## AGENT-ASYNC (Phase 3)

You are AGENT-ASYNC in a multi-agent build of a multi-tenant study-abroad SaaS (FastAPI, SQLAlchemy 2.0 async, Postgres, Redis, ARQ). Working dir: `backend`. Another agent is concurrently editing `app/core/auth/` and `app/api/dependencies/` — DO NOT touch those.

### STRICT WRITE BOUNDARY — create/edit ONLY these files:
- app/tasks/__init__.py
- app/tasks/arq_settings.py
- app/tasks/outbox_processor.py
- app/tasks/senders.py
- app/worker.py
- app/services/leads.py
- app/core/observability.py
- tests/integration/test_outbox_worker.py

DO NOT modify: app/main.py, app/api/**, app/db/**, app/core/config.py, app/core/enums.py, app/core/logging_config.py, pyproject.toml. Integration wiring is the orchestrator's job.

### Frozen interfaces (already implemented, read-only):
- `from app.db.models.outbox import OutboxEvent, ProcessedEvent` — OutboxEvent(id, vendor_id, event_type, aggregate_type, aggregate_id, payload:dict JSONB, status:OutboxStatus, attempts, max_attempts=5, available_at:datetime tz, dedup_key unique, processed_at, failure_reason); ProcessedEvent(id, source, external_id, dedup_hash) UNIQUE(source, external_id).
- `from app.core.enums import OutboxStatus` — PENDING/PROCESSING/SENT/FAILED.
- `from app.db.models.leads import Inquiry, Callback, Application, CostEstimate, QrLog` (all have vendor_id).
- `from app.db.session import session_scope` (async CM: commit on clean exit, rollback on error), `get_session`.
- `from app.core.config import get_settings` → `redis_url`, `email_smtp_host/port/user/password`, `email_from`, `business_email`.
- venv deps: arq, redis, sqlalchemy, asyncpg, structlog, httpx. (ruff/pytest NOT installed.)

### Requirements:
1. TRANSACTIONAL OUTBOX (central constraint): in `LeadCaptureService`, persist lead row + its OutboxEvent in the SAME transaction (one commit). NEVER commit-then-enqueue. Service validates, persists lead, persists OutboxEvent (event_type "lead.inquiry"/"lead.application"/..., payload=notification details, vendor_id, aggregate_type/aggregate_id), returns accepted(lead id). NO SMTP/HTTP in service.
2. Worker drains outbox (worker.py + outbox_processor.py): claim due PENDING (`available_at<=now`) oldest-first marking PROCESSING (use `FOR UPDATE SKIP LOCKED`); dispatch by event_type to senders; success→SENT+processed_at; failure→attempts+1, reschedule PENDING w/ `available_at=now+backoff` while attempts<max_attempts else FAILED+failure_reason. A failing event must NEVER crash the worker (catch per-event, log, continue).
3. Idempotency via ProcessedEvent: helper `already_processed(session, source, external_id, dedup_hash=None)->bool` insert-or-detect via unique constraint; duplicate side effect = no-op.
4. senders.py: `send_email(...)` stdlib smtplib via `asyncio.to_thread`; `send_webhook(...)` httpx async w/ timeout; both raise on failure; if SMTP unconfigured raise clear error (fail loud).
5. observability.py: structlog JSON config + correlation-id contextvar (request ids + worker job ids), `get_logger`. NO print.
6. arq_settings.py: `RedisSettings.from_dsn(settings.redis_url)` (no hardcoded localhost); WorkerSettings references it, registers processor, sets cron drain or enqueued jobs (document choice).

### Validation:
- `cd backend && PYTHONPATH=. venv/bin/python -c "import app.tasks.arq_settings, app.tasks.outbox_processor, app.tasks.senders, app.worker, app.services.leads, app.core.observability; print('async imports OK')"` must pass.
- pytest NOT installed — don't block. MAY validate against LIVE LOCAL DB with inline asyncio: `DATABASE_URL="postgresql+asyncpg://isafar@localhost:5432/agency_platform_dev?sslmode=disable"` (schema at head). Assert: lead+outbox committed together; failing sender reschedules then FAILED; duplicate (source,external_id) no-op. NEVER touch Supabase/remote DB.

Return: files created, how single-transaction outbox is enforced, retry/backoff + idempotency design, import-check result, live-DB checks run, wiring notes (worker launch command, where LeadCaptureService is called from routes).
