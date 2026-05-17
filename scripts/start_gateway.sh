#!/usr/bin/env bash
# Start OOA FastAPI gateway for local dev + Prometheus scraping (host 0.0.0.0:8000)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PORT="${OOA_GATEWAY_PORT:-8000}"
HOST="${OOA_GATEWAY_HOST:-0.0.0.0}"

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  if ! source .env 2>/dev/null; then
    echo "Failed to load .env — quote values that contain spaces, e.g.:"
    echo '  SUPER_ADMIN_NAME="Super Administrator"'
    exit 1
  fi
  set +a
fi

# Prefer Docker admin DB when compose stack is used
export OOA_DB_URL="${OOA_DB_URL:-postgresql://postgres:devpassword@localhost:5433/ooa}"

if lsof -ti:"$PORT" >/dev/null 2>&1; then
  echo "Port $PORT is in use. Stop it first:"
  echo "  lsof -ti:$PORT | xargs kill -9"
  exit 1
fi

if [ -z "${JWT_SECRET:-}" ]; then
  echo "JWT_SECRET is not set. Add it to .env or export it."
  exit 1
fi

mkdir -p logs
export OOA_LOG_JSON="${OOA_LOG_JSON:-true}"
export OOA_LOG_FILE="${OOA_LOG_FILE:-logs/ooa-gateway.jsonl}"

echo "Starting gateway on http://${HOST}:${PORT}"
echo "OOA_DB_URL=$OOA_DB_URL"
echo "OOA_LOG_FILE=$OOA_LOG_FILE"
exec uvicorn gateway.main:app --host "$HOST" --port "$PORT" --reload
