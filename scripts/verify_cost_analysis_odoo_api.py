#!/usr/bin/env python3
"""Verify Cost Analysis (expense by project/analytic account) via Odoo API.

Usage:
  source venv/bin/activate

  # Company-wide top projects
  python scripts/verify_cost_analysis_odoo_api.py \\
    --date-from 2026-01-01 --date-to 2026-05-16

  # Single project by analytic account id
  python scripts/verify_cost_analysis_odoo_api.py \\
    --date-from 2026-01-01 --date-to 2026-05-16 --analytic-id 42

  # Resolve project by name (partial match)
  python scripts/verify_cost_analysis_odoo_api.py \\
    --date-from 2026-01-01 --date-to 2026-05-16 --project-name "Zayidia"
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


def _resolve_project_analytic(adapter, name: str) -> int | None:
    projects = adapter.search_read(
        model="project.project",
        domain=[["name", "ilike", name]],
        fields=["id", "name", "analytic_account_id"],
        limit=5,
    )
    if not projects:
        return None
    if len(projects) > 1:
        print("Multiple projects matched:", file=sys.stderr)
        for row in projects:
            analytic = row.get("analytic_account_id")
            aid = analytic[0] if isinstance(analytic, (list, tuple)) else analytic
            print(f"  id={row['id']} analytic={aid} {row['name']}", file=sys.stderr)
    analytic = projects[0].get("analytic_account_id")
    if not analytic:
        print(f"Project '{projects[0]['name']}' has no analytic account.", file=sys.stderr)
        return None
    aid = analytic[0] if isinstance(analytic, (list, tuple)) else analytic
    print(f"Resolved project '{projects[0]['name']}' → analytic_account_id {aid}", file=sys.stderr)
    return int(aid)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Cost Analysis via Odoo API")
    parser.add_argument("--date-from", required=True)
    parser.add_argument("--date-to", required=True)
    parser.add_argument("--company-id", type=int, default=1)
    parser.add_argument("--analytic-id", type=int, default=0)
    parser.add_argument("--project-name", default="", help="Resolve analytic via project.project")
    parser.add_argument("--operating-unit-ids", default="")
    parser.add_argument("--top", type=int, default=10, help="Top N projects by cost")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    ou_ids = [
        int(part.strip())
        for part in args.operating_unit_ids.split(",")
        if part.strip()
    ] or None

    adapter = get_adapter()
    analytic_ids = None
    if args.analytic_id:
        analytic_ids = [args.analytic_id]
    elif args.project_name:
        aid = _resolve_project_analytic(adapter, args.project_name)
        if not aid:
            return 1
        analytic_ids = [aid]

    result = adapter.accounting.get_cost_analysis(
        date_from=args.date_from,
        date_to=args.date_to,
        company_id=args.company_id,
        analytic_ids=analytic_ids,
        operating_unit_ids=ou_ids,
    )

    if result.get("error"):
        print(json.dumps(result, indent=2))
        return 1

    totals = result.get("totals") or {}
    projects = result.get("projects") or {}
    print(f"Period: {result.get('date_from')} → {result.get('date_to')}")
    print(f"Source: {result.get('source')}")
    print(f"Projects: {result.get('project_count')}")
    print(f"Lines: {result.get('line_count')}")
    print(f"Total cost: {totals.get('total_cost')}")

    ranked = sorted(
        projects.items(),
        key=lambda item: float(item[1].get("total_cost") or 0),
        reverse=True,
    )
    show = ranked if args.verbose else ranked[: max(args.top, 1)]
    print(f"\nTop {len(show)} project(s) by cost:")
    for _key, row in show:
        print(f"  {row.get('name')}: {row.get('total_cost')}")

    if args.verbose:
        for row in (result.get("data") or {}).get("rows") or []:
            print("  " + " | ".join(str(cell) for cell in row))

    print(
        "\nCompare with Odoo: expense accounts on analytic/project for the same dates "
        "(Accounting reports or project expense dashboard)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
