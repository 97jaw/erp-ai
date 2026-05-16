#!/usr/bin/env python3
"""Verify Balance Sheet KPIs against Odoo UI (no Postgres required).

Usage:
  source venv/bin/activate
  python scripts/verify_balance_sheet_odoo_api.py --as-of-date 2026-05-16
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
    parser = argparse.ArgumentParser(description="Verify Balance Sheet via Odoo API")
    parser.add_argument("--as-of-date", required=True, help="Balance sheet as-of date YYYY-MM-DD")
    parser.add_argument("--company-id", type=int, default=1)
    parser.add_argument("--operating-unit-ids", default="")
    args = parser.parse_args()

    ou_ids = [
        int(part.strip())
        for part in args.operating_unit_ids.split(",")
        if part.strip()
    ] or None

    adapter = get_adapter()
    result = adapter.accounting.get_financial_report(
        report_type="balance_sheet",
        date_from="1900-01-01",
        date_to=args.as_of_date,
        company_id=args.company_id,
        operating_unit_ids=ou_ids,
    )

    if result.get("error"):
        print(json.dumps(result, indent=2))
        return 1

    kpis = result.get("kpis") or {}
    print(f"As of: {result.get('as_of_date') or args.as_of_date}")
    print(f"Source: {result.get('source')}")
    print(f"Total assets:      {kpis.get('total_assets')}")
    print(f"Total liabilities: {kpis.get('total_liabilities')}")
    print(f"Total equity:      {kpis.get('total_equity')}")
    print(f"Balanced:          {kpis.get('balanced')}")
    print("\nCompare with Odoo Balance Sheet (same as-of date and operating units).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
