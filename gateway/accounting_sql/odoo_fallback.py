from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def execute_report_via_odoo(adapter: Any, params: dict[str, Any]) -> dict[str, Any]:
    report_type = params["report_type"]
    accounting = adapter.accounting
    date_from = params["date_from"]
    date_to = params["date_to"]
    company_id = int(params.get("company_id", 1))
    operating_unit_ids = params.get("operating_unit_ids")
    target_moves = params.get("target_moves", "posted")

    if report_type == "trial_balance":
        return accounting.get_trial_balance(
            date_from=date_from,
            date_to=date_to,
            target_moves=target_moves,
            company_id=company_id,
            display_accounts=params.get("display_accounts", "all"),
            operating_unit_ids=operating_unit_ids,
            journal_ids=params.get("journal_ids"),
            account_ids=params.get("account_ids"),
            strict_range=params.get("strict_range"),
            show_hierarchy=bool(params.get("show_hierarchy", False)),
        )

    if report_type == "general_ledger":
        return accounting.get_general_ledger(
            date_from=date_from,
            date_to=date_to,
            target_moves=target_moves,
            account_ids=params.get("account_ids"),
            partner_ids=params.get("partner_ids"),
            analytic_ids=params.get("analytic_ids"),
            operating_unit_ids=operating_unit_ids,
            company_id=company_id,
            display_accounts=params.get("display_accounts"),
            include_details=bool(params.get("include_details", True)),
            initial_balance=bool(params.get("initial_balance", True)),
        )

    if report_type in {"pandl", "balance_sheet", "bs"}:
        bs_type = "balance_sheet" if report_type in {"balance_sheet", "bs"} else "pandl"
        return accounting.get_financial_report(
            report_type=bs_type,
            date_from=date_from,
            date_to=date_to,
            target_move=target_moves,
            company_id=company_id,
            analytic_ids=params.get("analytic_ids"),
            operating_unit_ids=operating_unit_ids,
        )

    if report_type == "partner_ageing":
        return accounting.get_partner_ageing(
            as_of_date=params.get("as_of_date") or date_to,
            date_from=date_from,
            result_selection=params.get("result_selection", "customer"),
            partner_ids=params.get("partner_ids"),
            operating_unit_ids=operating_unit_ids,
            company_id=company_id,
            include_details=bool(params.get("include_details", False)),
        )

    if report_type == "cost_analysis":
        return accounting.get_cost_analysis(
            date_from=date_from,
            date_to=date_to,
            company_id=company_id,
            analytic_ids=params.get("analytic_ids"),
            operating_unit_ids=operating_unit_ids,
            limit=int(params.get("limit", 5000)),
        )

    return {
        "error": "report_not_implemented_yet",
        "message": f"Odoo fallback not implemented for report_type '{report_type}'.",
        "report_type": report_type,
    }
