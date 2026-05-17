#!/usr/bin/env python3
"""Create or update the initial super admin user."""
from __future__ import annotations

import argparse
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
    parser = argparse.ArgumentParser(description="Create OOA super admin user")
    parser.add_argument("--file-id", default=os.environ.get("SUPER_ADMIN_FILE_ID", "2721"))
    parser.add_argument("--name", default=os.environ.get("SUPER_ADMIN_NAME", "Super Administrator"))
    parser.add_argument("--email", default=os.environ.get("SUPER_ADMIN_EMAIL", "admin@elrace.com"))
    parser.add_argument("--department", default="IT", help="Primary department code")
    args = parser.parse_args()

    db = await init_admin_db()
    try:
        repo = UserRepository(db)
        result = await repo.create_super_admin(
            file_id=args.file_id.strip(),
            name=args.name.strip(),
            email=args.email.strip() or None,
            department_code=args.department.strip(),
        )
        perm_count = await repo.super_admin_permission_count(args.file_id.strip())
        print("Super admin ready:")
        print(f"  user_id: {result['user_id']}")
        print(f"  file_id: {result['file_id']}")
        print(f"  role:    {result['role']}")
        print(f"  permissions via role: {perm_count}")
        return 0
    finally:
        await close_admin_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
