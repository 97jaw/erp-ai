#!/bin/sh
set -e

# Ensure runtime packages are present (survive image rebuilds before bake-in)
python -c "import reportlab, openpyxl" 2>/dev/null || {
  echo "[entrypoint] Installing reportlab + openpyxl..."
  pip install --no-cache-dir reportlab openpyxl -q
}

if [ -n "${OOA_DB_URL:-}" ]; then
  echo "[entrypoint] Running admin DB migrations..."
  python scripts/admin_db_migrate.py || {
    echo "[entrypoint] Migration failed — check OOA_DB_URL and Postgres connectivity" >&2
    exit 1
  }
else
  echo "[entrypoint] OOA_DB_URL not set — skipping migrations (auth/admin features limited)"
fi

exec "$@"
