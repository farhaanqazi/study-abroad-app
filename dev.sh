#!/usr/bin/env bash
#
# One-command local dev launcher.
#
#   ./dev.sh           start backend (API) + worker + frontend
#   ./dev.sh --no-worker   start backend + frontend only (skip the outbox worker)
#
# Press Ctrl+C ONCE to stop everything.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PY="$BACKEND/venv/bin/python"   # venv console scripts have a stale shebang; call python -m

# --- local config: point at the disposable local DB, never the .env prod URL ---
export DATABASE_URL="postgresql+asyncpg://isafar@localhost:5432/agency_platform_dev?sslmode=disable"
export ENVIRONMENT="development"
export PYTHONPATH="$BACKEND"

# Clerk issuer for backend token verification (must match the frontend publishable
# key's instance). Audience is optional; override CLERK_ISSUER here if you switch
# Clerk apps. Derivable from the pk_ key — not a secret.
export CLERK_ISSUER="${CLERK_ISSUER:-https://happy-lab-13.clerk.accounts.dev}"

RUN_WORKER=1
[[ "${1:-}" == "--no-worker" ]] && RUN_WORKER=0

pids=()
cleanup() {
  echo ""
  echo "▶ stopping all servers..."
  for pid in "${pids[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
  echo "▶ all stopped."
}
trap cleanup INT TERM EXIT

# --- quick preflight on the background services ---
echo "▶ checking Postgres & Redis..."
pg_isready >/dev/null 2>&1 || { echo "✗ Postgres is not running. Start it (e.g. 'brew services start postgresql@16') and retry."; exit 1; }
if [[ $RUN_WORKER -eq 1 ]]; then
  redis-cli ping >/dev/null 2>&1 || { echo "✗ Redis is not running. Start it ('brew services start redis') or run ./dev.sh --no-worker."; exit 1; }
fi

# --- 1) backend API ---
echo "▶ starting backend  → http://127.0.0.1:8000  (docs at /docs)"
( cd "$BACKEND" && "$PY" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload ) &
pids+=($!)

# --- 2) outbox worker (optional) ---
if [[ $RUN_WORKER -eq 1 ]]; then
  echo "▶ starting worker   → ARQ (drains the outbox)"
  ( cd "$BACKEND" && "$PY" -m arq app.worker.WorkerSettings ) &
  pids+=($!)
fi

# --- 3) frontend ---
echo "▶ starting frontend → http://localhost:5173"
( cd "$FRONTEND" && npm run dev ) &
pids+=($!)

echo ""
echo "▶ all servers starting. Press Ctrl+C once to stop everything."
wait
