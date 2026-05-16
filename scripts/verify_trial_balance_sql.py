#!/usr/bin/env python3
"""Compare SQL trial balance totals with Odoo (manual verification helper).

Usage:
  export ODOO_POSTGRES_DSN=postgresql://...
  python scripts/verify_trial_balance_sql.py --date-from 2026-05-01 --date-to 2026-05-13

Compare printed debit/credit totals with Accounting → Reports → Trial Balance in Odoo.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gateway.accounting_sql.query_accounting import execute_query_accounting  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify SQL trial balance against Odoo UI")
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--company-id", type=int, default=1)
    args = parser.parse_args()

    if not os.environ.get("ODOO_POSTGRES_DSN"):
        print("Set ODOO_POSTGRES_DSN to the Odoo database.", file=sys.stderr)
        return 1

    result = execute_query_accounting(
        {
            "report_type": "trial_balance",
            "date_from": args.date_from,
            "date_to": args.date_to,
            "company_id": args.company_id,
        }
    )

    if result.get("error"):
        print(json.dumps(result, indent=2))
        return 1

    totals = result["totals"]
    print(f"Period: {result['date_from']} → {result['date_to']}")
    print(f"Accounts: {result['row_count']}")
    print(f"Debit:  {totals['debit']:,.2f}")
    print(f"Credit: {totals['credit']:,.2f}")
    print(f"Diff:   {totals['difference']:,.2f}")
    print(f"Balanced: {totals['balanced']}")
    print("\nCompare these totals with Odoo Trial Balance for the same period.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
