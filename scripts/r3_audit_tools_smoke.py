#!/usr/bin/env python3
"""Phase R3 — audit tool smoke tests (live Odoo)."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def _pp(label: str, payload: dict) -> None:
    print(f"\n{'=' * 72}")
    print(label)
    print("=" * 72)
    print(json.dumps(payload, indent=2, default=str))


async def main() -> int:
    from gateway.audit.tools import execute_get_audit_trail, execute_get_user_activity
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter

    adapter = get_shared_odoo_adapter()

    # Smoke 1: Villa 34 project audit trail
    r1 = await execute_get_audit_trail(
        adapter,
        {
            "model": "project.project",
            "record_id": 15157,
            "date_from": "2026-06-01",
        },
    )
    _pp("SMOKE 1 — get_audit_trail(project.project, 15157, date_from=2026-06-01)", r1)

    # Smoke 2: user activity for uid 4291
    r2 = await execute_get_user_activity(
        adapter,
        {"user_id": 4291, "date_from": "2026-06-01"},
    )
    _pp("SMOKE 2 — get_user_activity(user_id=4291, date_from=2026-06-01)", r2)

    # Smoke 3: record with no chatter (non-existent id)
    r3 = await execute_get_audit_trail(
        adapter,
        {"model": "project.project", "record_id": 999999991},
    )
    _pp("SMOKE 3 — get_audit_trail(project.project, 999999991) [no chatter]", r3)

    ok1 = (
        r1.get("status") == "success"
        and r1.get("changes_count", 0) >= 1
        and len(r1.get("timeline") or []) >= 1
    )
    ok2 = r2.get("status") == "success" and bool(r2.get("by_model"))
    ok3 = (
        r3.get("status") == "success"
        and r3.get("changes_count") == 0
        and (r3.get("timeline") or []) == []
    )

    print(f"\n{'=' * 72}")
    print(f"SMOKE 1 pass: {ok1}")
    print(f"SMOKE 2 pass: {ok2}")
    print(f"SMOKE 3 pass: {ok3}")
    print("=" * 72)

    return 0 if (ok1 and ok2 and ok3) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
