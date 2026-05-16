#!/usr/bin/env python3
"""Live trial balance via Odoo XML-RPC (no Postgres / containers required).

Usage (from repo root, with venv activated):
  pip install -r requirements.txt
  python scripts/verify_trial_balance_odoo_api.py --date-from 2026-05-01 --date-to 2026-05-13

Compare printed debit/credit with Odoo: Accounting → Trial Balance (same dates).
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
    parser = argparse.ArgumentParser(description="Trial balance via Odoo API (no direct SQL)")
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--company-id", type=int, default=1)
    parser.add_argument(
        "--display-accounts",
        choices=["all", "balance_not_zero"],
        default="all",
        help="Match Odoo Apply default: all (unless 'With balance not zero' option checked)",
    )
    parser.add_argument(
        "--operating-unit-ids",
        default="",
        help="Comma-separated operating.unit IDs from Odoo UI filter (empty = all OUs)",
    )
    args = parser.parse_args()

    for key in ("ODOO_V14_URL", "ODOO_V14_DB", "ODOO_V14_USER", "ODOO_V14_PASSWORD"):
        if not os.environ.get(key):
            print(f"Missing {key} in .env", file=sys.stderr)
            return 1

    if os.environ.get("ODOO_POSTGRES_DSN"):
        print(
            "Note: ODOO_POSTGRES_DSN is set — get_trial_balance will try SQL first. "
            "Unset it to test Odoo API only.\n",
            file=sys.stderr,
        )

    adapter = get_adapter()
    ou_ids = [
        int(part.strip())
        for part in args.operating_unit_ids.split(",")
        if part.strip()
    ] or None

    result = adapter.accounting.get_trial_balance(
        date_from=args.date_from,
        date_to=args.date_to,
        company_id=args.company_id,
        display_accounts=args.display_accounts,
        operating_unit_ids=ou_ids,
    )

    if result.get("error"):
        print(json.dumps(result, indent=2))
        return 1

    totals = result.get("totals") or {}
    print(f"Period: {result.get('date_from')} → {result.get('date_to')}")
    print(f"Source: {result.get('source', 'odoo_api_or_synthesized')}")
    print(f"Accounts: {result.get('row_count', '?')}")
    print("\n--- Compare these with Odoo Trial Balance ---")
    if totals.get("initial_debit") is not None:
        print(f"Initial  Debit:  {totals.get('initial_debit')}")
        print(f"Initial  Credit: {totals.get('initial_credit')}")
    print(f"Period   Debit:  {totals.get('debit')}")
    print(f"Period   Credit: {totals.get('credit')}")
    if totals.get("ending_debit") is not None:
        print(f"Ending   Debit:  {totals.get('ending_debit')}")
        print(f"Ending   Credit: {totals.get('ending_credit')}")
    print(f"Balanced (period): {totals.get('balanced')}")
    applied = result.get("applied_filters") or {}
    odoo_filters = applied.get("odoo_filters") or {}
    print("\n--- Odoo filters used (must match UI header) ---")
    print(f"Company: {odoo_filters.get('company_name')}")
    print(f"Dates:   {odoo_filters.get('date_from')} → {odoo_filters.get('date_to')}")
    print(f"Display: {odoo_filters.get('display_accounts')}")
    print(f"Strict:  {odoo_filters.get('strict_range')}")
    print(f"OUs:     {odoo_filters.get('operating_unit_ids') or odoo_filters.get('operating_units')}")
    print(f"Journals:{odoo_filters.get('journals') or 'All'}")
    print("\nOdoo UI total row (from your screenshot, 01/05–16/05):")
    print("  Initial Debit/Credit:  6,634,722,532.90")
    print("  Period Debit/Credit:      62,160,741.88 / 67,990,204.74")
    print("  Ending Debit/Credit:   6,696,883,274.78 / 6,702,712,737.64")
    print("\nIf numbers differ, copy Operating Unit IDs from UI into:")
    print("  --operating-unit-ids 1,2,3")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
