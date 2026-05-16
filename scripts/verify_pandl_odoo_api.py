#!/usr/bin/env python3
"""Verify P&L KPIs against Odoo UI (no Postgres required).

Usage:
  source venv/bin/activate
  python scripts/verify_pandl_odoo_api.py --date-from 2026-05-01 --date-to 2026-05-16
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from gateway.main import get_adapter  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P&L via Odoo API")
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--company-id", type=int, default=1)
    parser.add_argument(
        "--operating-unit-ids",
        default="",
        help="Comma-separated operating.unit IDs (match Odoo UI filter)",
    )
    args = parser.parse_args()

    ou_ids = [
        int(part.strip())
        for part in args.operating_unit_ids.split(",")
        if part.strip()
    ] or None

    adapter = get_adapter()
    result = adapter.accounting.get_financial_report(
        report_type="pandl",
        date_from=args.date_from,
        date_to=args.date_to,
        company_id=args.company_id,
        operating_unit_ids=ou_ids,
    )

    if result.get("error"):
        print(json.dumps(result, indent=2))
        return 1

    kpis = result.get("kpis") or {}
    print(f"Period: {result.get('date_from')} → {result.get('date_to')}")
    print(f"Source: {result.get('source')}")
    print(f"Total income:  {kpis.get('total_income')}")
    print(f"Total expense: {kpis.get('total_expense')}")
    print(f"Net profit:    {kpis.get('net_profit')}")
    print(f"Margin:        {kpis.get('margin')}%")
    print("\nCompare with Odoo Profit & Loss report (same dates and operating units).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
