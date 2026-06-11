#!/usr/bin/env python3
"""Phase M0 — universal Odoo tool smoke tests against live Odoo."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def run_smoke() -> int:
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter
    from gateway.tools.universal_odoo import (
        build_universal_context,
        execute_aggregate_odoo,
        execute_query_odoo,
    )

    adapter = get_shared_odoo_adapter()
    ctx = build_universal_context()

    tests: list[tuple[str, dict]] = []

    print("=" * 60)
    print("PHASE M0 — Universal Odoo Tool Smoke Tests")
    print("=" * 60)

    # Smoke 1: query_odoo hr.employee → 5 employees
    print("\n[SMOKE 1] query_odoo hr.employee (limit 5)")
    r1 = await execute_query_odoo(
        adapter,
        {
            "model": "hr.employee",
            "domain": [["active", "=", True]],
            "fields": ["name", "department_id", "job_id"],
            "limit": 5,
        },
        ctx,
    )
    print(json.dumps(r1, indent=2, default=str))
    ok1 = r1.get("status") == "success" and r1.get("record_count", 0) >= 5
    tests.append(("query_odoo hr.employee → 5 employees", ok1))

    # Smoke 2: aggregate_odoo employees per department
    print("\n[SMOKE 2] aggregate_odoo hr.employee by department_id")
    r2 = await execute_aggregate_odoo(
        adapter,
        {
            "model": "hr.employee",
            "domain": [["active", "=", True]],
            "group_by": ["department_id"],
            "aggregates": ["id:count"],
            "limit": 20,
        },
        ctx,
    )
    print(json.dumps(r2, indent=2, default=str))
    ok2 = r2.get("status") == "success" and r2.get("group_count", 0) >= 1
    tests.append(("aggregate_odoo employees per department", ok2))

    # Smoke 3: query_odoo res.users → blocked
    print("\n[SMOKE 3] query_odoo res.users → must be blocked")
    r3 = await execute_query_odoo(
        adapter,
        {"model": "res.users", "fields": ["name", "login"], "limit": 5},
        ctx,
    )
    print(json.dumps(r3, indent=2, default=str))
    ok3 = r3.get("status") == "error" and r3.get("error_code") == "model_forbidden"
    tests.append(("query_odoo res.users → blocked", ok3))

    print("\n" + "=" * 60)
    print("M0 SUMMARY")
    print("=" * 60)
    passed = 0
    for name, ok in tests:
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}")
        if ok:
            passed += 1
    print(f"\n{passed}/{len(tests)} passed")
    return 0 if passed == len(tests) else 1


def main() -> int:
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return asyncio.run(run_smoke())


if __name__ == "__main__":
    raise SystemExit(main())
