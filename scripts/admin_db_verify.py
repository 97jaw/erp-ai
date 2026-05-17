#!/usr/bin/env python3
"""Verify admin PostgreSQL schema and seed data."""
from __future__ import annotations

import asyncio
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from admin.db.connection import init_admin_db, close_admin_db  # noqa: E402
from admin.db.repositories.users import UserRepository  # noqa: E402


async def main() -> int:
    db = await init_admin_db()
    try:
        ok = await db.health_check()
        print(f"Health check (SELECT 1): {'OK' if ok else 'FAIL'}")
        if not ok:
            return 1

        repo = UserRepository(db)
        counts = await repo.count_seed_data()
        print("Table counts:")
        for key, value in counts.items():
            print(f"  {key}: {value}")

        roles = await db.fetch(
            "SELECT name, level FROM roles ORDER BY level DESC LIMIT 5"
        )
        print("\nTop roles:")
        for row in roles:
            print(f"  {row['name']} (level {row['level']})")

        perms = await db.fetchval("SELECT COUNT(*) FROM permissions")
        rp = await db.fetchval(
            """
            SELECT COUNT(*) FROM role_permissions rp
            JOIN roles r ON r.id = rp.role_id
            WHERE r.name = 'super_admin'
            """
        )
        print(f"\nPermissions total: {perms}")
        print(f"super_admin role_permissions: {rp}")
        if perms and int(rp or 0) < int(perms or 0):
            print("WARNING: super_admin missing some permissions", file=sys.stderr)

        expected_min = {
            "roles": 7,
            "permissions": 30,
            "departments": 8,
            "role_permissions": 20,
        }
        failed = False
        for key, minimum in expected_min.items():
            if counts.get(key, 0) < minimum:
                print(f"FAIL: expected {key} >= {minimum}, got {counts.get(key)}", file=sys.stderr)
                failed = True
        return 1 if failed else 0
    finally:
        await close_admin_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
