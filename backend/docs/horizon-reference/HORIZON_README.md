# Horizon Education — Web App

Single-page consultancy site with a Node/Express backend, PostgreSQL for persistence, Redis for rate limiting, and Gmail SMTP for transactional email.

## What works

- **Inquiry form** → saved to Postgres → user gets confirmation email + business inbox gets notified
- **Request a Callback** → saved to Postgres → user gets confirmation + business inbox gets a "callback requested" alert
- **Onboarding application (4-step form)** → saved to Postgres → user + business both notified
- **QR code generator** → defaults to the live site URL, async-logs every generation to Postgres
- **Live stats** on the home page (real Postgres counts on top of baseline numbers)
- **Rate limiting** on every form (Redis sliding window) — fails open if Redis is down

## Prerequisites

- **Docker Desktop** (for Postgres + Redis) — https://docker.com/products/docker-desktop
- **Node.js 20+** — `brew install node`
- **ngrok** — `brew install ngrok` then `ngrok config add-authtoken <token>` (free account)

## Setup (first time)

```bash
# 1. Start Postgres + Redis
docker compose up -d

# 2. Install Node deps
npm install

# 3. Copy env template and fill in your Gmail App Password
cp .env.example .env
# Edit .env — set GMAIL_APP_PASSWORD
```

### Generating a Gmail App Password

1. Go to https://myaccount.google.com/security
2. Turn on **2-Step Verification** if not already on
3. Visit https://myaccount.google.com/apppasswords
4. Create one named "Horizon Web" → copy the 16-character password
5. Paste it into `.env` as `GMAIL_APP_PASSWORD`

> Without these credentials the server runs in **dry-run mode** — emails are logged to the console instead of sent. Useful for testing UI without spamming.

## Run

```bash
npm start
# → http://localhost:3000
```

Visit the site, submit forms, and watch the console for `[db]` and `[email]` activity.

## Make it public with ngrok

In a second terminal:

```bash
ngrok http 3000
```

Copy the `https://....ngrok-free.app` URL ngrok prints — that's your live site. Anyone in the world can open it.

The QR generator on the site auto-detects whatever origin you opened the page from, so when you visit via the ngrok URL and click Generate, the QR will encode the ngrok URL. Print it on flyers — scans bring people back to the live site.

> ⚠️ Free ngrok URLs change every restart. For a fixed URL, upgrade ngrok ($8/mo) or deploy to Railway/Render later.

## Useful queries

```bash
# Open psql in the running container
docker exec -it horizon-postgres psql -U horizon -d horizon
```

```sql
-- Recent inquiries
SELECT id, name, email, left(message, 60) AS msg, created_at FROM inquiries ORDER BY created_at DESC LIMIT 20;

-- Recent callback requests
SELECT id, name, phone, email, preferred_time, created_at FROM callbacks ORDER BY created_at DESC LIMIT 20;

-- Recent applications
SELECT id, name, email, phone, course, country, intake, created_at FROM applications ORDER BY created_at DESC LIMIT 20;

-- QR generation log
SELECT url, COUNT(*) AS scans FROM qr_logs GROUP BY url ORDER BY scans DESC;
```

## Stopping everything

```bash
# Stop Node server: Ctrl+C in its terminal
# Stop ngrok: Ctrl+C in its terminal
# Stop containers (data is preserved):
docker compose down

# Wipe data and start fresh:
docker compose down -v
```

## File map

```
index.html           — single-page frontend
server.js            — Express app
db.js                — Postgres pool + migrations
redis.js             — Redis client + rate limiter
email.js             — Nodemailer (Gmail SMTP)
migrations.sql       — schema
docker-compose.yml   — Postgres + Redis containers
.env.example         — env template
```

## Troubleshooting

**`[db] migrations failed: ECONNREFUSED`** — Postgres isn't running. `docker compose up -d`.

**Emails not arriving** — Check the server console. If it says `[email:dry-run]`, your `GMAIL_APP_PASSWORD` isn't set or isn't valid. Regenerate it from Google. Also check spam folder; first emails from a new sender often land there.

**`429 Too many requests`** — Rate limit hit. Wait 5–10 min or restart Redis: `docker compose restart redis`.

**ngrok says "tunnel session failed: account limited"** — Free ngrok allows one tunnel at a time. Close other ngrok sessions or open the dashboard at `localhost:4040`.
