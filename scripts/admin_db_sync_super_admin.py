#!/usr/bin/env python3
"""Apply pending migrations and ensure super_admin role has all permissions."""
from __future__ import annotations

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from admin.db.connection import close_admin_db, init_admin_db  # noqa: E402


async def main() -> int:
    db = await init_admin_db()
    try:
        applied = await db.run_migrations()
        if applied:
            print("Applied migrations:", ", ".join(applied))
        else:
            print("No new migrations.")

        count = await db.fetchval(
            """
            SELECT COUNT(*)
            FROM role_permissions rp
            JOIN roles r ON r.id = rp.role_id
            WHERE r.name = 'super_admin'
            """
        )
        total = await db.fetchval("SELECT COUNT(*) FROM permissions")
        print(f"super_admin role permissions: {count} / {total}")
        return 0
    finally:
        await close_admin_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
