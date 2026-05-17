#!/usr/bin/env python3
"""Apply admin panel PostgreSQL migrations."""
from __future__ import annotations

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from admin.db.connection import get_database_url, init_admin_db, close_admin_db  # noqa: E402


def _connection_help(exc: BaseException, url: str) -> str:
    host_hint = "5433" if ":5433" in url else "5432"
    lines = [
        f"Could not connect to PostgreSQL ({exc}).",
        f"  OOA_DB_URL={url}",
        "",
        "Choose one setup:",
        "",
        "  A) Docker admin DB (port 5433):",
        "     docker compose -f docker-compose.admin-db.yml up -d",
        "     OOA_DB_URL=postgresql://postgres:devpassword@localhost:5433/ooa",
        "",
        "  B) Local Homebrew Postgres (port 5432):",
        "     createdb ooa   # once",
        f"     OOA_DB_URL=postgresql://$USER@localhost:5432/ooa",
    ]
    if host_hint == "5433":
        lines.append("")
        lines.append("  Port 5433 is not accepting connections — start Docker (A) or switch to (B) in .env")
    return "\n".join(lines)


async def main() -> int:
    url = get_database_url()
    try:
        db = await init_admin_db()
    except (OSError, ConnectionRefusedError) as exc:
        print(_connection_help(exc, url), file=sys.stderr)
        return 1
    except Exception as exc:
        if "Connect call failed" in str(exc) or "Connection refused" in str(exc):
            print(_connection_help(exc, url), file=sys.stderr)
            return 1
        raise
    try:
        applied = await db.run_migrations()
        if applied:
            print("Applied migrations:")
            for name in applied:
                print(f"  - {name}")
        else:
            print("Database already up to date.")
        return 0
    finally:
        await close_admin_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
