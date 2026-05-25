# Study-Abroad Vendor Platform

> Multi-tenant lead-management platform for study-abroad agencies — public vendor sites, a cost-estimate calculator, lead capture (inquiries / callbacks / applications), a per-vendor management console, and Telegram + WhatsApp chatbot intake. FastAPI + React + Redis.

Each **vendor** (agency) gets a public site under its own slug, a set of lead-capture forms that email the business on every submission, and a console to review those leads and tune the cost calculator. Telegram and WhatsApp webhooks are wired per-vendor as an additional inbound channel.

---

## What it does

- **Per-vendor public sites** — `/v/<vendor-slug>` resolves a vendor by slug and renders its landing page + contact form.
- **Lead capture** — inquiries, request-a-callback, full study-abroad applications, and QR-scan logging. Every lead (except QR logs) fires a background email to the vendor's business inbox and the student.
- **Cost-estimate calculator** — a gated lead magnet. The student picks a country / study level / duration; the server computes tuition + stay + food from the vendor's configured rates and stores the submission (with contact details) as a lead.
- **Vendor management console (API)** — list inquiries, callbacks, applications, and cost-estimates for a vendor; full CRUD on the per-vendor cost settings that drive the calculator.
- **Multi-channel chatbot intake** — Telegram and WhatsApp webhooks with per-vendor bot-token routing, signature verification, and Redis-backed dedup + conversation state.

---

## Architecture

```
Browser ──► Public vendor site (React SPA)
              │  POST /api/v1/v/<slug>/inquiries | /callback | /applications | /cost-estimate
              ▼
        ┌──────────────────────── FastAPI ────────────────────────┐
        │  leads API (public, per-vendor)                          │
        │  vendor_console API (management, per-vendor-id)          │──► PostgreSQL (SQLAlchemy 2.0 async)
        │  webhooks API (telegram/whatsapp, per-vendor)            │──► Redis (state + dedup)
        │  ConversationService ─► MessageDispatcher ─► channels    │──► SMTP (lead emails)
        └──────────────────────────────────────────────────────────┘
Telegram / WhatsApp ──► /api/v1/webhooks/<channel>/<slug> ──► ConversationService
```

Everything is **tenant-scoped by vendor**. Public lead routes resolve the vendor by `slug`; the management console resolves by `vendor_id` in the path. In production FastAPI also serves the built frontend (`frontend/dist`) via an SPA fallback, so it runs as a single origin.

### Data model (PostgreSQL)

| Table | Purpose |
|---|---|
| `vendors` | Tenant: name, unique slug, timezone, language, config blobs |
| `vendor_channels` | Per-vendor Telegram/WhatsApp config (bot token, webhook secret) |
| `vendor_cost_settings` | Per `(vendor, country, study_level)` rates that drive the calculator |
| `users` | Dashboard users — roles: `admin`, `vendor_owner`, `reception` |
| `inquiries` | Contact-form submissions |
| `callbacks` | Request-a-callback submissions |
| `applications` | Full study-abroad applications |
| `cost_estimates` | Calculator submissions (inputs + computed breakdown + contact) |
| `qr_logs` | Fire-and-forget QR-scan logs |

---

## API surface

All routes are mounted under `API_PREFIX` (default `/api/v1`).

**Public — lead capture** (`/v/{vendor_slug}`):

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/inquiries` | Submit a contact inquiry |
| `POST` | `/callback` | Request a callback |
| `POST` | `/applications` | Submit an application |
| `POST` | `/qr/log` | Log a QR scan |
| `GET`  | `/config` | Public vendor config (name, slug) |
| `GET`  | `/stats` | Headline stats (baselines + live application count) |
| `GET`  | `/cost-options` | Countries / levels the vendor has configured |
| `POST` | `/cost-estimate` | Compute + store a gated cost estimate |

**Management console** (`/vendors/{vendor_id}`):

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/inquiries`, `/callbacks`, `/applications`, `/cost-estimates` | List leads (paginated, read-only) |
| `GET` / `POST` / `PUT` / `DELETE` | `/cost-settings[/{id}]` | Manage the calculator's rate table |

**Webhooks** (`/webhooks`): `GET|POST /whatsapp/{vendor_slug}`, `POST /telegram/{vendor_slug}`.

Interactive docs at `/docs` when the server is running.

---

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI |
| ORM | SQLAlchemy 2.0 (async, asyncpg) |
| Migrations | Alembic |
| State / dedup / rate-limit | Redis, slowapi |
| LLM | Groq (`LLMService` wrapper) |
| Channels | Telegram Bot API, WhatsApp Cloud API |
| Email | SMTP (`EmailService`) |
| Frontend | React 19, Vite, Tailwind CSS v4, React Query, Zustand |

---

## Setup

**Prerequisites:** Python 3.10+, Node 18+, PostgreSQL, Redis. (Groq key + Telegram/WhatsApp tokens only needed for the chatbot channel.)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in DATABASE_URL, REDIS_URL, etc.
alembic upgrade head          # create the schema
uvicorn app.main:app --reload # http://localhost:8000  (docs at /docs)
```

Key environment variables (see [backend/.env.example](backend/.env.example) for the full list):

- `DATABASE_URL` — async PostgreSQL URL (`postgresql+asyncpg://…`)
- `REDIS_URL` — conversation state + message dedup
- `BUSINESS_EMAIL` + `EMAIL_SMTP_*` — where lead notifications are sent
- `BASE_STUDENTS` / `BASE_COUNTRIES` / `BASE_UNIVERSITIES` / `BASE_EXPERIENCE` — headline-stat baselines
- `GROQ_API_KEY`, `TELEGRAM_*`, `WHATSAPP_*` — chatbot channel (optional)

### Frontend

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # outputs frontend/dist (served by FastAPI in prod)
```

---

## Connecting a chatbot channel

Bot tokens live per-vendor in `vendor_channels.provider_config`. To wire a Telegram bot:

1. Create a bot with `@BotFather`, copy the token.
2. Add a `vendor_channels` row (`vendor_id`, `channel='telegram'`, `is_enabled=true`, `provider_config={"bot_token": "..."}`).
3. Point Telegram's webhook at `<WEBHOOK_BASE_URL>/api/v1/webhooks/telegram/<vendor-slug>` with the secret token set to `<bot_token>` with `:` replaced by `_`.

---

## Project status

This is an actively-evolving platform, not a finished product. What's solid vs. pending:

- ✅ **Backend domain is built** — lead capture, cost calculator, vendor console, multi-tenant webhooks, lead emails.
- 🚧 **Auth is deferred** — the management console is scoped by `vendor_id` in the URL with no login yet. The `users` table and roles exist; a real session layer (deriving `vendor_id` from the logged-in user) is still to be added. Handlers are shaped so this can be slotted in without changing their signatures.
- 🚧 **The chatbot is still an echo orchestrator** — webhooks run end-to-end, but [`ConversationService.handle_inbound`](backend/app/services/conversation_service.py) currently replies `received: <text>`. The Groq `LLMService` is wired but not yet driving domain conversations.
- 🚧 **Frontend is the public site only** — vendor landing page + inquiry form. The management-console UI (over the existing API) is not built yet.
