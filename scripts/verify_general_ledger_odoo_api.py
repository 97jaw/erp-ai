#!/usr/bin/env python3
"""Verify General Ledger totals against Odoo UI.

Usage:
  source venv/bin/activate

  # List sample account codes (find a valid code first)
  python scripts/verify_general_ledger_odoo_api.py --list-accounts

  # Single account by code — fast (recommended)
  python scripts/verify_general_ledger_odoo_api.py \\
    --date-from 2026-05-01 --date-to 2026-05-16 --account-code 1102062

  # Single account by Odoo id (not the same as code)
  python scripts/verify_general_ledger_odoo_api.py \\
    --date-from 2026-05-01 --date-to 2026-05-16 --account-id 21386

  # Company-wide — uses get_ai_general_ledger on server (may take several minutes)
  python scripts/verify_general_ledger_odoo_api.py \\
    --date-from 2026-05-01 --date-to 2026-05-16
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


def _resolve_account_by_code(adapter, code: str, company_id: int) -> dict | None:
    rows = adapter.search_read(
        model="account.account",
        domain=[
            ["company_id", "=", company_id],
            ["code", "=", code],
        ],
        fields=["id", "code", "name"],
        limit=1,
    )
    return rows[0] if rows else None


def _resolve_account_by_id(adapter, account_id: int, company_id: int) -> dict | None:
    rows = adapter.search_read(
        model="account.account",
        domain=[
            ["company_id", "=", company_id],
            ["id", "=", account_id],
        ],
        fields=["id", "code", "name"],
        limit=1,
    )
    return rows[0] if rows else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify General Ledger via Odoo API")
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--company-id", type=int, default=1)
    parser.add_argument("--account-ids", default="", help="Odoo account.account ids (comma-separated)")
    parser.add_argument("--account-code", default="", help="Exact account code (e.g. 1102062)")
    parser.add_argument("--account-id", type=int, default=0, help="Odoo account.account id (e.g. 21386)")
    parser.add_argument("--operating-unit-ids", default="")
    parser.add_argument(
        "--display-accounts",
        choices=["all", "balance_not_zero"],
        default=None,
        help="Default: all when filtering one account; balance_not_zero company-wide",
    )
    parser.add_argument(
        "--include-details",
        action="store_true",
        help="Include every move line (slow). Default: on for one account, off company-wide.",
    )
    parser.add_argument(
        "--list-accounts",
        action="store_true",
        help="Print sample account codes and exit",
    )
    parser.add_argument(
        "--target-moves",
        choices=["posted", "all_entries"],
        default="posted",
        help="Match Odoo GL target moves (default: posted)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print each GL line and a raw posted move-line count from Odoo",
    )
    args = parser.parse_args()

    adapter = get_adapter()

    if args.list_accounts:
        rows = adapter.search_read(
            model="account.account",
            domain=[["company_id", "=", args.company_id]],
            fields=["id", "code", "name"],
            order="code asc",
            limit=25,
        )
        print(f"Sample accounts (company_id={args.company_id}):")
        for row in rows:
            print(f"  code={row['code']:<16} id={row['id']:<8} {row['name']}")
        print(
            "\nUse --account-code with the code column (e.g. 1102062), "
            "or --account-id with the id column (e.g. 21386)."
        )
        return 0

    if not args.date_from or not args.date_to:
        print("Required: --date-from and --date-to (or use --list-accounts)", file=sys.stderr)
        return 1

    account_ids = [
        int(part.strip())
        for part in args.account_ids.split(",")
        if part.strip()
    ] or None
    ou_ids = [
        int(part.strip())
        for part in args.operating_unit_ids.split(",")
        if part.strip()
    ] or None

    if args.account_code:
        row = _resolve_account_by_code(adapter, args.account_code, args.company_id)
        if not row:
            print(
                f"No account for code '{args.account_code}'. "
                "Run with --list-accounts — use the code column, not id.",
                file=sys.stderr,
            )
            return 1
        account_ids = [row["id"]]
        print(f"Resolved code {row['code']} → id {row['id']} ({row['name']})")

    if args.account_id:
        row = _resolve_account_by_id(adapter, args.account_id, args.company_id)
        if not row:
            print(f"No account with id {args.account_id}.", file=sys.stderr)
            return 1
        account_ids = [row["id"]]
        print(f"Using account id {row['id']}: {row['code']} {row['name']}")

    include_details = args.include_details or bool(account_ids)
    display_accounts = args.display_accounts

    if not account_ids:
        print(
            "Company-wide GL: project.financial.service.get_ai_general_ledger "
            f"(timeout {os.environ.get('ODOO_XMLRPC_TIMEOUT', '600')}s). "
            "Deploy elrace_dashboard if this fails.",
            file=sys.stderr,
        )
    else:
        print("Single-account GL — should complete in under a minute.", file=sys.stderr)

    gl_kwargs: dict = {
        "date_from": args.date_from,
        "date_to": args.date_to,
        "company_id": args.company_id,
        "account_ids": account_ids,
        "operating_unit_ids": ou_ids,
        "include_details": include_details,
        "target_moves": args.target_moves,
    }
    if display_accounts:
        gl_kwargs["display_accounts"] = display_accounts

    if args.verbose and account_ids:
        move_state = "posted" if args.target_moves == "posted" else False
        domain = [
            ["account_id", "in", account_ids],
            ["date", ">=", args.date_from],
            ["date", "<=", args.date_to],
        ]
        if move_state:
            domain.append(["parent_state", "=", "posted"])
        raw_count = adapter.search_count(model="account.move.line", domain=domain)
        print(
            f"Raw account.move.line count ({args.target_moves}, same dates): {raw_count}",
            file=sys.stderr,
        )

    result = adapter.accounting.get_general_ledger(**gl_kwargs)

    if result.get("error"):
        print(json.dumps(result, indent=2))
        return 1

    totals = result.get("totals") or {}
    print(f"Period: {result.get('date_from')} → {result.get('date_to')}")
    print(f"Source: {result.get('source')}")
    print(f"Accounts: {result.get('account_count')}")
    print(f"Move lines: {result.get('line_count')}")
    print(f"Total debit:  {totals.get('debit')}")
    print(f"Total credit: {totals.get('credit')}")

    if args.verbose:
        for code, account in sorted((result.get("accounts") or {}).items()):
            name = account.get("name") or ""
            print(f"\n{code} {name}")
            print(
                f"  Account totals — debit: {account.get('debit')}  "
                f"credit: {account.get('credit')}  balance: {account.get('balance')}"
            )
            for line in account.get("lines") or []:
                print(
                    f"  {line.get('date', ''):<12} "
                    f"{str(line.get('move_name', '')):<22} "
                    f"D:{line.get('debit', 0):>12} "
                    f"C:{line.get('credit', 0):>12} "
                    f"Bal:{line.get('balance', 0):>12}"
                )

    print("\nCompare with Odoo General Ledger (same dates and filters).")
    if (
        result.get("line_count") == 2
        and totals.get("debit") == 0
        and totals.get("credit") == 0
    ):
        print(
            "Note: 2 lines with zero period debit/credit usually means only "
            "Initial/Ending balance rows — no posted moves in range. "
            "Run with -v to see line labels, or try --target-moves all_entries."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
