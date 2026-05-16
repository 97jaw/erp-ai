#!/usr/bin/env python3
"""Verify Partner Ageing against Odoo UI.

Usage:
  source venv/bin/activate
  python scripts/verify_partner_ageing_odoo_api.py --as-of-date 2026-05-16
  python scripts/verify_partner_ageing_odoo_api.py --as-of-date 2026-05-16 --result-selection supplier
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
    parser = argparse.ArgumentParser(description="Verify Partner Ageing via Odoo API")
    parser.add_argument("--as-of-date", required=True, help="Ageing as-on date YYYY-MM-DD")
    parser.add_argument("--company-id", type=int, default=1)
    parser.add_argument(
        "--result-selection",
        choices=["customer", "supplier", "receivable", "payable"],
        default="customer",
        help="customer=receivables, supplier=payables",
    )
    parser.add_argument("--operating-unit-ids", default="")
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Show top N partners by total (default 10)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print all partners and bucket columns",
    )
    args = parser.parse_args()

    ou_ids = [
        int(part.strip())
        for part in args.operating_unit_ids.split(",")
        if part.strip()
    ] or None

    adapter = get_adapter()
    result = adapter.accounting.get_partner_ageing(
        as_of_date=args.as_of_date,
        result_selection=args.result_selection,
        company_id=args.company_id,
        operating_unit_ids=ou_ids,
    )

    if result.get("error"):
        print(json.dumps(result, indent=2))
        return 1

    period_list = result.get("period_list") or []
    totals = result.get("totals") or {}
    print(f"As of: {result.get('as_of_date')}")
    print(f"Source: {result.get('source')}")
    print(f"Selection: {result.get('result_selection')}")
    print(f"Partners: {result.get('partner_count')}")
    print(f"Buckets: {', '.join(period_list)}")
    grand = round(float(totals.get("total") or 0), 2)
    sum_signed = round(float(totals.get("sum_partner_totals") or 0), 2)
    print(f"Grand total (Odoo footer): {grand}")
    print(f"Sum of signed partner totals: {sum_signed}")

    partners = result.get("partners") or {}
    if abs(sum_signed - grand) > 1.0:
        print(
            f"WARNING: signed partner sum ({sum_signed}) != footer total ({grand}).",
            file=sys.stderr,
        )

    ranked = sorted(
        partners.items(),
        key=lambda item: float(item[1].get("total_outstanding") or 0),
        reverse=True,
    )
    show = ranked if args.verbose else ranked[: max(args.top, 1)]

    print(f"\nTop {len(show)} partner(s) by |outstanding| (signed total in brackets):")
    for _pid, row in show:
        label = row.get("partner_name") or _pid
        signed = row.get("total")
        print(f"  {label}: {row.get('total_outstanding')}  (signed: {signed})")

    if args.verbose:
        headers = (result.get("data") or {}).get("headers") or []
        print(f"\nColumns: {headers}")
        for row in (result.get("data") or {}).get("rows") or []:
            print("  " + " | ".join(str(cell) for cell in row))

    print("\nCompare with Odoo Partner Ageing (same as-on date, partner type, operating units).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
