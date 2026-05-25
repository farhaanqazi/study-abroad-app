# Study-Abroad Vendor Platform — Architecture Brief & Request for Guidance

**From:** Engineering (platform lead)
**To:** VP / Senior Engineering Manager
**Re:** Current architecture, what we've actually got, what's left to build, and where I'd value your judgment

---

## Why I'm writing

We pivoted this codebase from a salon-booking chatbot into a multi-tenant **lead-management platform for study-abroad agencies**. The backend domain is largely in place, but we're at the point where the next decisions are *architectural and strategic*, not just "write the next endpoint." Before I commit the team to a direction, I want a second set of experienced eyes on the shape of the system and the trade-offs ahead.

I've kept this brief honest about the warts. I'd rather you react to the real state than a polished version of it.

---

## What the product is meant to be

Two surfaces, two audiences, one multi-tenant backend:

1. **Student-facing public site** — each vendor (agency) gets a page at `/v/<slug>`. Students read about the agency, run a **cost-of-study calculator**, and submit leads (general inquiries, callback requests, full applications). Optionally, the same vendor is reachable via a **Telegram/WhatsApp chatbot**.

2. **Vendor-owner management console** — agency staff log in, **set up their public site** (branding/content), **manage their cost/price tables** (which drive the calculator), and **work the leads** that come in.

Everything is **tenant-scoped by `vendor`**. A vendor owns its channels, its cost settings, its leads, and its public-site content.

---

## Current architecture (as actually built)

### Backend — FastAPI, async, multi-tenant

- **FastAPI** app, all routes under `/api/v1`. In production the same FastAPI process also serves the built React SPA via a catch-all fallback — single origin, single deployable.
- **SQLAlchemy 2.0 (async) + asyncpg** against PostgreSQL. In production that's a **Supabase-hosted Postgres** (the connection string lives in `.env`; SSL is forced via `sslmode=require`, and we currently disable cert verification to tolerate the Supabase pooler's cert).
- **Alembic** for migrations (see "Known liabilities" — the chain is currently broken).
- **Redis** for conversation state and per-message dedup.
- **slowapi** rate limiting, plus a middleware stack: request IDs, timing, security headers, structured JSON logging, centralized exception handling.

### Channels & conversation layer

- **Telegram and WhatsApp webhooks**, routed per-vendor by slug (`/webhooks/<channel>/<vendor-slug>`). Bot tokens are stored **per vendor** in `vendor_channels.provider_config`; WhatsApp uses HMAC signature verification, Telegram a secret-token check.
- Inbound messages are normalized, deduped via Redis, and handed to a **`ConversationService`** — which, today, is a **121-line echo orchestrator**: it resolves the tenant, loads/saves state, and replies `received: <text>`.
- A **`LLMService`** wrapping **Groq** is wired into the service constructor but **not yet driving any conversation**. The "smart bot" doesn't exist yet — the plumbing for it does.

### Lead capture & cost engine (public API)

Per-vendor, resolved by slug:

- `POST /v/{slug}/inquiries | /callback | /applications` — lead submissions; each fires a **background SMTP email** to the agency (and student) via `EmailService.notify_lead`.
- `POST /v/{slug}/qr/log` — fire-and-forget QR-scan logging.
- `GET /v/{slug}/config | /stats` — public vendor config and headline stats (baselines + live application count).
- `GET /v/{slug}/cost-options` + `POST /v/{slug}/cost-estimate` — the **cost calculator**: server computes `tuition×years + rent×months + food×months` from the vendor's configured rates, stores the submission *with the student's contact details* (gated lead-magnet), and returns the breakdown.

### Management API (console)

Per-vendor, currently keyed by `vendor_id` **in the URL with no authentication**:

- `GET /vendors/{id}/inquiries | callbacks | applications | cost-estimates` — paginated, read-only.
- `GET|POST|PUT|DELETE /vendors/{id}/cost-settings` — full CRUD on the rate table behind the calculator.

### Data model (PostgreSQL)

`vendors`, `vendor_channels`, `users` (roles: `admin` / `vendor_owner` / `reception`), `vendor_cost_settings`, and the lead tables `inquiries`, `callbacks`, `applications`, `qr_logs`, `cost_estimates`. Notably, **`users` has no password/credential column** — it was designed to link to an external identity provider by ID (originally Supabase Auth).

### Frontend — React 19 / Vite / Tailwind

- **React 19, Vite 8 (rolldown engine), Tailwind v4, React Query, Zustand.**
- **What exists:** exactly three routes — a placeholder home (`/`), the public vendor site (`/v/:slug`), and a catch-all redirect. The vendor site renders the agency name (fetched from the API) and an inquiry form.
- **What does not exist on the frontend:** any login, any management console, the calculator UI, the callback/application forms, and any site-customization screens. The old salon app *had* a full dashboard suite (owner/admin/reception dashboards, user management, analytics, login) — those were **deleted during the pivot, not ported.**

---

## What's solid vs. what's missing

| Capability | Backend | Frontend |
|---|---|---|
| Public site (name + inquiry) | ✅ | ✅ |
| Lead capture (4 types) | ✅ | ⚠️ inquiry only |
| Cost calculator | ✅ | ❌ |
| Lead inbox (read) | ✅ | ❌ |
| Cost/price management | ✅ | ❌ |
| **Authentication** | ❌ | ❌ |
| **Vendor site customization** | ❌ (only name/slug exposed) | ❌ |
| Smart chatbot (LLM-driven) | ❌ (echo only; Groq wired) | n/a |

The headline: **the read/write APIs for the management domain mostly exist; authentication, site-customization, and the entire management UI do not.** We verified the existing slice end-to-end locally — submit a lead on the public site, read it back through the console API, run a cost estimate with correct math.

---

## The direction I'm leaning (and want challenged)

- **Auth via a third-party provider (Clerk or similar).** The `users` table is already shaped for external identity (no passwords stored), so a hosted IdP fits the existing model: Clerk owns login/session, our `users` row owns role + `vendor_id`. This avoids us building/owning password storage, resets, MFA, etc. I want your read on whether outsourcing identity here is the right call for a B2B multi-tenant product, and what it costs us in lock-in and data-residency terms.
- **Lead inbox first, then pricing, then site-setup.** Inbox and pricing are thin UIs over endpoints that already exist — fast wins that make the console immediately useful. Site customization is the heaviest net-new piece (new model fields/JSONB, new endpoints, an editor UI, and rendering it on the public site).
- **Treat the chatbot as a later, optional channel** rather than core to v1. The web funnel (site → calculator → lead) is the product's spine; the bot is an acquisition channel we can light up once the LLM layer is actually built.

---

## Known liabilities I'm carrying (full disclosure)

1. **The Alembic chain is broken.** `0001` is an empty baseline (real schema lives in `sql/schema.sql`), `0002` alters a salon table (`appointments`) that no longer exists, and `0003` adds the new lead tables on top. A fresh `alembic upgrade head` fails. We're effectively bootstrapping schema from raw SQL. This needs to be reconciled before any serious schema evolution.
2. **Supabase coupling.** Prod DB is Supabase; `sql/schema.sql` carries RLS policies that depend on Supabase's `auth` schema and `auth.uid()`. We stripped Supabase *auth* but are still on Supabase *Postgres*. There's an unresolved question of how much we lean into the Supabase platform vs. treat it as plain Postgres.
3. **Legacy salon residue** in the schema — `appointments`, `customers`, notification-job tables, and salon-era enums still exist in `schema.sql`. Harmless at runtime, but it's debt and confusion.
4. **The management API is unauthenticated** — `/vendors/{id}/...` is wide open by URL id. Fine for the current pre-auth phase; a hard blocker for anything real.
5. **Dev-environment fragility** — the committed Python venv has a hardcoded interpreter path from the old project; console scripts (e.g. `alembic`) break. Onboarding a new dev means recreating the venv.

---

## Where I'd genuinely value your judgment

I'm deliberately *not* pre-deciding these. I want your experience to shape them.

- **Architecture & boundaries.** Is the single-FastAPI-process-serves-everything (API + SPA + webhooks) model the right one as this grows, or should we be splitting the public site, the management console, and the channel/webhook workers into separate deployables sooner rather than later? Where would you draw the seams?

- **Multi-tenancy strategy.** We're doing application-level tenant scoping (every row carries `vendor_id`). Given we're on Supabase Postgres with RLS available, is row-level security worth adopting as a defense-in-depth layer, or is that a trap that complicates more than it protects? And how do you think about the "one owner, many vendors" case vs. "one login, one vendor"?

- **Identity.** Beyond "Clerk vs. build it" — how would you think about the long-term cost of outsourcing identity for a platform whose whole value is the customer (vendor) relationship and their leads' PII? What would make you comfortable, or not?

- **The chatbot question.** We inherited a real channel/LLM substrate but it does nothing yet. Is that an asset to invest in, or a distraction we should quarantine until the web product proves out? I can argue it either way and want your instinct.

- **Tech-debt sequencing.** Given limited cycles, how would you weigh "fix the migration/schema foundation now" against "ship the management console and show value"? I'm worried about building more on a cracked foundation, but also about polishing plumbing while the product stalls.

- **Data model for site customization.** Vendors will want to shape their public page (branding, copy, which forms, featured countries). Do we model that as typed columns, a JSONB blob (`entry_config` already exists), or a small CMS-like content table? Each has obvious trade-offs in flexibility vs. queryability vs. validation. I lean JSONB; talk me into or out of it.

- **What am I not asking that I should be?** You've shipped more of these than I have. If something about this architecture would worry you that I haven't flagged, that's the most valuable thing you could tell me.

---

## What I'd like out of this

A point of view on the above — especially auth, the tech-debt-vs-features sequencing, and the deployment/boundaries question. From there I'll turn it into a concrete phased plan with estimates. I'm not looking for permission; I'm looking for the considerations I'm too close to the code to see.
