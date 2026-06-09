#!/usr/bin/env python3
"""Compare mobile summary vs dashboard expense APIs for a project."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

# Allow running from repo root: python scripts/verify_project_expense_parity.py
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from gateway.tools.project_expense import (  # noqa: E402
    DASHBOARD_METHOD,
    SERVICE_MODEL,
    SUMMARY_METHOD,
    _normalize_summary_from_dashboard,
    _normalize_summary_from_mobile,
    _unwrap_odoo_payload,
    _validate_summary_payload,
)


def _print_summary(label: str, summary: dict[str, Any]) -> None:
    print(f"\n{label}")
    print(f"  Project: {summary.get('project_name')} (id={summary.get('project_id')})")
    print(f"  W.O amount: {summary.get('wo_amount'):,.2f}")
    print(f"  Total expenses: {summary.get('total_expenses'):,.2f}")
    print(f"  Spend %: {summary.get('spend_percent_of_wo')}")
    tops = summary.get("top_expenses") or []
    if tops:
        print("  Top trades:")
        for row in tops[:3]:
            print(
                f"    - {row.get('name')}: {float(row.get('amount') or 0):,.2f} "
                f"({float(row.get('percent') or 0):.1f}%)",
            )


def _divergence(mobile: dict[str, Any], dashboard: dict[str, Any], tolerance: float) -> list[str]:
    issues: list[str] = []
    for field in ("wo_amount", "total_expenses"):
        left = float(mobile.get(field) or 0)
        right = float(dashboard.get(field) or 0)
        allowed = max(tolerance, abs(left) * 0.01)
        if abs(left - right) > allowed:
            issues.append(f"{field} mobile={left:,.2f} dashboard={right:,.2f}")
    return issues


async def _fetch(adapter: Any, method: str, project_id: int) -> dict[str, Any]:
    return await asyncio.to_thread(
        adapter.call_method,
        SERVICE_MODEL,
        method,
        [project_id],
    )


async def run_parity_check(
    adapter: Any,
    project_id: int,
    *,
    tolerance: float = 1.0,
) -> int:
    mobile_raw = await _fetch(adapter, SUMMARY_METHOD, project_id)
    dashboard_raw = await _fetch(adapter, DASHBOARD_METHOD, project_id)

    mobile_status, mobile_data, mobile_error = _unwrap_odoo_payload(mobile_raw)
    dashboard_status, dashboard_data, dashboard_error = _unwrap_odoo_payload(dashboard_raw)

    if mobile_status != "success" or not isinstance(mobile_data, dict):
        print(f"Mobile API failed: {mobile_error}")
        return 1
    if dashboard_status != "success" or not isinstance(dashboard_data, dict):
        print(f"Dashboard API failed: {dashboard_error}")
        return 1

    if not _validate_summary_payload(mobile_data):
        print("Mobile payload failed validation")
        return 1

    mobile = _normalize_summary_from_mobile(project_id, mobile_data)
    dashboard = _normalize_summary_from_dashboard(project_id, dashboard_data)

    _print_summary("Mobile summary", mobile)
    _print_summary("Dashboard summary", dashboard)

    issues = _divergence(mobile, dashboard, tolerance)
    if issues:
        print("\nParity check FAILED:")
        for issue in issues:
            print(f"  - {issue}")
        return 2

    print("\nParity check PASSED")
    return 0


def _build_adapter() -> Any:
    from adapters.v14.connector import OdooV14Adapter

    return OdooV14Adapter(
        url=os.environ["ODOO_URL"],
        db=os.environ["ODOO_DB"],
        username=os.environ["ODOO_USERNAME"],
        password=os.environ["ODOO_PASSWORD"],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_id", type=int, help="Odoo project.project ID")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=1.0,
        help="Absolute tolerance for W.O and total expense comparison (default: 1 AED)",
    )
    args = parser.parse_args()

    missing = [key for key in ("ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD") if not os.environ.get(key)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 1

    adapter = _build_adapter()
    return asyncio.run(run_parity_check(adapter, args.project_id, tolerance=args.tolerance))


if __name__ == "__main__":
    raise SystemExit(main())
