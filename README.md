# Study-Abroad Vendor Platform

> Multi-tenant SaaS for study-abroad agencies. Each agency (a **vendor**) gets a public marketing site with lead-capture forms and a cost-estimate calculator, a tenant-scoped **management console** to customize that site and work its leads, and sits under a **platform-admin** layer for onboarding, oversight, and support. FastAPI + React, PostgreSQL + Redis, Clerk auth, transactional-outbox notifications.

There are three audiences:

- **Students / visitors** → a vendor's public site at `/v/<slug>`: hero, stats, cost calculator, and lead forms (inquiry / callback / application).
- **Vendor staff** → the console at `/console`: edit the public site (draft → publish), review captured leads, and tune the cost calculator. Access is by **Clerk login + per-vendor membership role** (owner / agent / viewer).
- **Platform operators** → the `/admin` **API**: approve workspace requests, manage vendors and members, handle support tickets, and "view as" a vendor. Gated by a **platform role** (support / admin / superadmin). _(The admin React pages exist but aren't wired into the SPA router yet — see Project status.)_

---

## What it does

- **Per-vendor public sites** — `/v/<slug>` resolves a vendor and renders its published site config (hero copy, brand colour, About, toggleable sections). Falls back to sensible defaults when unconfigured.
- **Lead capture** — inquiries, request-a-callback, full applications, QR-scan logging, and a gated cost-estimate calculator. Every lead is written **together with a notification event in one transaction** (transactional outbox); an ARQ worker delivers the email.
- **Cost-estimate calculator** — student picks country / study level / duration; the server computes tuition + accommodation + food from the vendor's configured rates and stores the submission (with contact details) as a lead.
- **Vendor console (authenticated)** — Site editor (draft → publish), Leads dashboard (inquiries / callbacks / applications / cost-estimates), and Cost-settings CRUD. Reads need any membership; writes need agent+.
- **Self-service onboarding** — any signed-in user can submit a **workspace request** (business name + desired slug); a platform admin approves it, which provisions the vendor and an owner membership.
- **Platform admin** — vendor list/detail, suspend/activate, member management + invitations, user platform-role assignment, support tickets, and read-only "view-as" into a vendor's leads/site.

---

## Architecture

```
Visitor ─► Public vendor site (React SPA)
            │  GET/POST /api/v1/v/<slug>/…
            ▼
      ┌──────────────────────────── FastAPI ────────────────────────────┐
      │  /v/<slug>/…        public lead capture + site/config (no auth)   │
      │  /me                current user + memberships + platform role    │
      │  /workspace-requests self-service onboarding                      │──► PostgreSQL
      │  /console/<id>/…    tenant-scoped console  (Clerk + TenantRequire) │    (SQLAlchemy 2.0 async)
      │  /admin/…           platform admin         (Clerk + platform role) │──► Redis (ARQ queue)
      │                                                                    │
      │  LeadCaptureService ─► lead row + OutboxEvent  (one transaction)   │
      └────────────────────────────────────────────────────────────────────┘
                                   │ outbox_events (PENDING)
                                   ▼
                      ARQ worker ─► drains outbox ─► SMTP (lead emails)
                      (FOR UPDATE SKIP LOCKED, retries+backoff, idempotent)
```

Everything is **tenant-scoped by vendor**. Public routes resolve the vendor by `slug`; the console resolves by `vendor_id` in the path and verifies the caller's membership; admin routes verify a platform role. Auth is **Clerk** (RS256 JWT verified against Clerk's JWKS); users are provisioned lazily on first authenticated request. In production FastAPI also serves the built frontend (`frontend/dist`) via an SPA fallback, so it runs as a single origin.

### Notifications: transactional outbox (no dual write)

`LeadCaptureService` persists the lead **and** an `OutboxEvent` describing its notification in the **same transaction** — never commit-then-enqueue. A scheduled ARQ worker claims due `PENDING` events with `FOR UPDATE SKIP LOCKED`, dispatches them (SMTP today), and on failure reschedules with exponential backoff up to `max_attempts`, then parks as `FAILED`. A `ProcessedEvent` ledger makes delivery idempotent, so a crash-replay can't double-send.

### Data model (PostgreSQL)

| Table | Purpose |
|---|---|
| `vendors` | Tenant: unique slug, business name, active flag |
| `users` | Identity synced from Clerk (`clerk_id`, email); platform role |
| `vendor_memberships` | User ↔ vendor with role (`owner`/`agent`/`viewer`) — the authorization root |
| `vendor_site_configs` | Published `config` + `draft_config` (JSONB) for the public site |
| `vendor_cost_settings` | Per `(vendor, country, study_level)` rates that drive the calculator |
| `inquiries` / `callbacks` / `applications` / `cost_estimates` / `qr_logs` | Lead tables |
| `outbox_events` / `processed_events` | Transactional outbox + idempotency ledger |
| `workspace_requests` | Self-service onboarding requests (pending → approved/rejected) |
| `invitations` | Pending vendor-member invites |
| `support_tickets` / `support_ticket_messages` | Support inbox |
| `audit_logs` | Admin/action audit trail |

Schema is managed by **Alembic** (`0001_initial_base` → `0002_platform_admin_workspace_requests` → `0003_invitations_support_tickets`).

---

## API surface

All routes are under `API_PREFIX` (default `/api/v1`). Interactive docs at `/docs`.

**Public — lead capture** (`/v/{vendor_slug}`, no auth):

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/config` | Vendor name + **published site config** |
| `GET`  | `/stats` | Headline stats (baselines + live application count) |
| `GET`  | `/cost-options` | Countries / levels the vendor has configured |
| `POST` | `/inquiries`, `/callback`, `/applications`, `/qr/log` | Submit a lead |
| `POST` | `/cost-estimate` | Compute + store a gated cost estimate |

**Identity & onboarding** (Clerk auth):

| Method | Path | Purpose |
|---|---|---|
| `GET`  | `/me` | Current user, memberships, platform role |
| `GET`/`POST` | `/workspace-requests`, `/workspace-requests/mine` | Request a new workspace / list your requests |

**Vendor console** (`/console/{vendor_id}`, Clerk + `TenantRequire`):

| Method | Path | Role |
|---|---|---|
| `GET` | `/inquiries`, `/callbacks`, `/applications`, `/cost-estimates` | viewer+ |
| `GET`/`POST`/`PUT`/`DELETE` | `/cost-settings[/{id}]` | agent+ for writes |
| `GET` | `/site` · `PUT` `/site/draft` · `POST` `/site/publish` | agent+ for writes |

**Platform admin** (`/admin`, Clerk + platform role): vendor list/detail, `suspend`/`activate`, `health`, members + `members/invite`, `users` + `platform-role`, `support/tickets`, `workspace-requests` approve/reject, and `view-as` (leads / site-config).

---

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI |
| ORM / DB | SQLAlchemy 2.0 (async, asyncpg) + PostgreSQL |
| Migrations | Alembic |
| Async jobs | ARQ + Redis (transactional-outbox worker) |
| Auth | Clerk — backend verifies RS256 JWTs via JWKS (`python-jose`); frontend `@clerk/react` |
| Email | SMTP (`smtplib`, via the outbox worker) |
| Logging | `structlog` — JSON files + console, request/job correlation, secret redaction |
| Rate limiting | `slowapi` |
| Frontend | React 19, Vite, Tailwind CSS v4, TanStack Query, React Hook Form + Zod |

---

## Setup

**Prerequisites:** Python 3.10+, Node 18+, PostgreSQL, Redis. A Clerk app (publishable key + issuer) is needed for the console/admin; the public site works without it.

### One command (local)

```bash
./dev.sh              # backend API + outbox worker + frontend
./dev.sh --no-worker  # skip the worker (no Redis needed)
```

`dev.sh` points at a local disposable database, sets `CLERK_ISSUER`, and stops everything on Ctrl+C. Backend → http://127.0.0.1:8000 (docs at `/docs`), frontend → http://localhost:5173.

### Manual

**Backend**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -e .                 # deps from pyproject.toml
export DATABASE_URL="postgresql+asyncpg://USER@localhost:5432/agency_platform_dev"
export ENVIRONMENT=development CLERK_ISSUER="https://<your-app>.clerk.accounts.dev"
alembic upgrade head             # build the schema
uvicorn app.main:app --reload    # http://localhost:8000
# Notification worker (needs Redis):
arq app.worker.WorkerSettings
```

**Frontend**
```bash
cd frontend
npm install
# frontend/.env.local:
#   VITE_API_URL=http://localhost:8000
#   VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
npm run dev      # http://localhost:5173
npm run build    # outputs frontend/dist (served by FastAPI in prod)
```

### Key environment variables

- `DATABASE_URL` — async PostgreSQL URL (`postgresql+asyncpg://…`)
- `REDIS_URL` — ARQ queue for the outbox worker
- `CLERK_ISSUER` — your Clerk instance issuer (required for console/admin auth). `CLERK_AUDIENCE` is **optional** — when unset, audience is not enforced (Clerk's default session token carries none).
- `EMAIL_SMTP_*` + `BUSINESS_EMAIL` — where lead notifications are delivered
- `BASE_STUDENTS` / `BASE_COUNTRIES` / `BASE_UNIVERSITIES` / `BASE_EXPERIENCE` — public-stats baselines

> **Auth note:** Clerk's default session token has no `email` claim. The backend provisions users with a placeholder email derived from the Clerk ID until you add `email` to the session token in the Clerk Dashboard. To see real emails in the console, add `{"email": "{{user.primary_email_address}}"}` to the session-token claims.

---

## Logging

A single `structlog` pipeline (`app/core/observability.py`) renders pretty console output in development and JSON in production, and also writes rotating files: `backend/logs/app.log` (all levels) and `backend/logs/error.log` (errors with tracebacks). A `request_id` is bound per HTTP request and a `correlation_id` per worker job, so a single line traces a request across the API, service, and worker layers. Secrets/tokens are redacted; emails/phones are kept for debugging.

---

## Project status

A working multi-tenant platform — verified locally end-to-end. Notes:

- ✅ **Public site + lead capture + cost calculator** — live; leads persist with their outbox notification atomically.
- ✅ **Auth** — Clerk login, lazy user provisioning, per-vendor `TenantRequire` (owner/agent/viewer) and platform roles.
- ✅ **Vendor console** — Site editor (draft → publish), Leads dashboard, Cost-settings CRUD.
- ✅ **Outbox worker** — drains with retries/backoff + idempotency.
- ✅ **Onboarding + platform-admin API** — workspace requests, vendor/member management, invitations, support tickets, audit logs, and view-as are implemented as backend endpoints.
- 🚧 **Admin / onboarding UI** — the React pages exist (`frontend/src/pages/Admin/*`) but are **not yet wired into the router** (`App.tsx` routes only `/`, `/v/:slug`, `/console/**`), so `/admin` isn't reachable in the SPA yet. Workspace requests are approved via the API for now.
- 🚧 **Delivery + deploy** — SMTP needs real credentials for live email; container/CI deploy not finalized. Tests run as standalone scripts in the local venv (pytest not yet wired into the dev image).
