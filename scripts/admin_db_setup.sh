#!/usr/bin/env bash
# Phase 1 admin database setup (Docker or local Postgres)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v docker >/dev/null 2>&1; then
  docker compose -f docker-compose.admin-db.yml up -d
  export OOA_DB_URL="${OOA_DB_URL:-postgresql://postgres:devpassword@localhost:5433/ooa}"
else
  echo "Docker not found — using local Postgres on port 5432 (database: ooa)"
  export OOA_DB_URL="${OOA_DB_URL:-postgresql://${USER}@localhost:5432/ooa}"
  psql -d postgres -tc "SELECT 1 FROM pg_database WHERE datname = 'ooa'" | grep -q 1 \
    || psql -d postgres -c "CREATE DATABASE ooa"
fi

export JWT_SECRET="${JWT_SECRET:-dev-change-me-jwt-secret}"
source venv/bin/activate 2>/dev/null || true
pip install -q asyncpg==0.30.0

python scripts/admin_db_migrate.py
python scripts/admin_db_verify.py
python scripts/admin_db_create_super_admin.py
echo "Done. Set OOA_DB_URL and JWT_SECRET in .env before starting the gateway."
