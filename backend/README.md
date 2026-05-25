# Beauty Parlour Appointment Bot Backend

This project is a modular FastAPI backend for a multi-tenant beauty parlour appointment chatbot that works across WhatsApp webhooks, Telegram webhooks, and QR-based deep links that open those chats.

The codebase is rule-based for booking steps and uses the LLM only for:

- multilingual prompt localization
- free-text understanding
- option matching when users do not tap buttons
- date/time extraction fallback

The LLM layer is configured for Groq only.

## Project structure

```text
app/
  api/               HTTP routes for webhooks, appointments, public links
  core/              settings and enums
  db/                SQLAlchemy models and async session
  flows/             rule-based conversation engine
  llm/               Groq LLM adapter
  messaging/         Telegram and WhatsApp outbound adapters
  redis/             Redis state store
  schemas/           request/response/state models
  services/          orchestration, booking, tenant, notifications
  workers/           reminder/cancellation polling worker
sql/
  schema.sql         PostgreSQL schema
  seed_demo.sql      sample tenant and services
```

## Architecture

### 1. Multi-tenant backend

- `vendors` stores one tenant per parlour.
- `vendor_channels` stores WhatsApp/Telegram channel config per vendor.
- `vendor_services` stores each vendor's service catalog.
- `flow_config` in `vendors` lets each client override prompts/options and skip or change steps.

### 2. Conversation flow

The booking flow is implemented in [app/flows/engine.py](/c:/Users/91832/Desktop/beauty_palour/app/flows/engine.py).

Base step order:

1. Greeting
2. Language
3. Marriage type
4. Service
5. Sample images
6. Appointment date
7. Appointment time
8. Confirmation
9. Booking creation

The engine is deterministic. It moves step by step, stores collected slots in Redis, and only asks the LLM to help when the user sends unstructured text.

### 3. Redis state design

Redis stores live session state only, keyed by:

```text
conv:{vendor_id}:{channel}:{external_user_id}
```

Stored JSON fields:

- `session_id`
- `vendor_id`
- `channel`
- `external_user_id`
- `step`
- `slots.language`
- `slots.marriage_type`
- `slots.service_id`
- `slots.service_name`
- `slots.wants_sample_images`
- `slots.appointment_date`
- `slots.appointment_time`
- `attempt_count`
- `created_at`
- `updated_at`

TTL is loaded from `.env` through `SESSION_TTL_SECONDS` and refreshes on every inbound message.

### 4. PostgreSQL schema

Main tables:

- `vendors`
- `vendor_channels`
- `vendor_notification_contacts`
- `vendor_services`
- `customers`
- `appointments`
- `inbound_messages`
- `outbound_messages`
- `notification_jobs`

`notification_jobs` is the worker-safe queue for:

- customer reminder at 60 minutes
- customer reminder at 15 minutes
- vendor appointment digest at 60 minutes
- vendor appointment digest at 15 minutes
- customer cancellation notice

See [schema.sql](/c:/Users/91832/Desktop/beauty_palour/sql/schema.sql) for the exact PostgreSQL DDL.

### 5. Webhook handling

Webhook routes:

- `POST /api/v1/webhooks/telegram/{vendor_slug}`
- `GET /api/v1/webhooks/whatsapp/{vendor_slug}` for verification
- `POST /api/v1/webhooks/whatsapp/{vendor_slug}`

Flow:

1. Provider payload is normalized.
2. Vendor is resolved by `vendor_slug`.
3. Customer is created or updated from phone number or chat id.
4. Redis state is loaded.
5. Rule engine processes the message.
6. Appointment is created in PostgreSQL if confirmed.
7. Reminder jobs are scheduled.
8. Outbound reply is sent via Telegram or WhatsApp.
9. Inbound/outbound messages are logged.

### 6. Notifications and workers

The worker loop is in [notification_worker.py](/c:/Users/91832/Desktop/beauty_palour/app/workers/notification_worker.py).

- Run as many worker processes as you want, including `5`.
- Jobs are claimed with `FOR UPDATE SKIP LOCKED`.
- This prevents duplicate sends across concurrent workers.
- Vendor notification contacts receive upcoming appointment digests.
- If the vendor cancels an appointment, the user gets a cancellation message on their original channel.

### 7. QR code entry

The backend exposes deep links at:

- `GET /api/v1/vendors/{vendor_slug}/entry-links`

It returns Telegram and WhatsApp chat links. You can convert either URL into a QR code with any QR generator or in your frontend/admin panel.

## Run locally

### 1. Setup Environment

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
```

**⚠️ SECURITY:** Edit `.env` and set your actual credentials. Never commit `.env` to version control.

Required credentials to configure:
- `DATABASE_URL` - From Supabase Dashboard → Project Settings → Database
- `GROQ_API_KEY` - From https://console.groq.com/keys
- `TELEGRAM_BOT_TOKEN` - From @BotFather on Telegram
- `WHATSAPP_ACCESS_TOKEN` - From Meta Developer Dashboard

Install packages:

```bash
pip install -r requirements.txt
```

### 2. Create the database schema

```bash
python run_migration.py
```

Or manually:
```bash
psql -d beauty_parlour -f sql/schema.sql
psql -d beauty_parlour -f sql/seed_demo.sql
```

### 3. Start the API

```bash
python -m app.run_api
```

Start the notification worker pool:

```bash
python -m app.workers.run_pool
```

### Environment Reference

See `.env.example` for the complete list of configurable environment variables with descriptions.

**Important environment notes:**

- `appointment_at` is stored in PostgreSQL as `TIMESTAMPTZ` in UTC.
- Vendor timezones are respected when parsing and rendering appointment times.
- The current QR support is deep-link based, not image generation based.
- The current bot expects the vendor to be identified from the webhook URL slug.
- Sample images are stored as URLs in PostgreSQL and pushed back through the channel adapter.
- API worker count is read from `.env` by [app/run_api.py](/c:/Users/91832/Desktop/beauty_palour/app/run_api.py).
- Notification worker count is read from `.env` by [app/workers/run_pool.py](/c:/Users/91832/Desktop/beauty_palour/app/workers/run_pool.py).
- Conversation session TTL is read from `.env` through `SESSION_TTL_SECONDS`.
- General Redis default TTL is read from `.env` through `REDIS_TTL_SECONDS`.
