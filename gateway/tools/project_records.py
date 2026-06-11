"""Project records tool — lists records linked to one project (no Deep Think).

Project Model Phase 2. Answers list questions (client invoices, LPO invoices,
purchase orders, timesheets, petty cash, staff, supervisors) by reading the
linked Odoo models directly. Aggregated financials (expense summary/breakdown,
P&L) remain Deep Think territory.

Linkage verified against live Elrace Odoo 2026-06-11:
  account.move.project_id / purchase.order.project_id -> analytic account
  hr.expense / hr.expense.sheet / staff.list / project.supervisor /
  account.analytic.line -> project.project
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from gateway.core.context_stack import ContextStack

logger = logging.getLogger(__name__)

RECORDS_SOURCE = "project_records"

PROJECT_RECORDS_TOOL_NAMES = frozenset({"get_project_records"})

RECORD_TYPE_VALUES = (
    "invoices",
    "client_invoices",
    "lpo_invoices",
    "purchase_orders",
    "timesheets",
    "petty_cash",
    "petty_cash_sheets",
    "staff",
    "supervisors",
)

# Types without a date dimension — no default period applies.
UNDATED_RECORD_TYPES = frozenset({"staff", "supervisors"})

DEFAULT_PERIOD_DAYS = 90  # last 3 months when no range specified

RECORD_TYPE_LABELS = {
    "invoices": "invoices",
    "client_invoices": "client invoices",
    "lpo_invoices": "LPO invoices",
    "purchase_orders": "purchase orders",
    "timesheets": "timesheet entries",
    "petty_cash": "petty cash expenses",
    "petty_cash_sheets": "petty cash sheets",
    "staff": "staff members",
    "supervisors": "supervisors",
}

PROJECT_RECORDS_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_project_records",
        "description": (
            "List records LINKED to a project, newest first: invoices (client "
            "and/or LPO vendor bills), purchase orders, timesheet entries, petty "
            "cash expenses/sheets, staff list, supervisors.\n\n"
            "USE THIS WHEN the user asks to SEE/LIST records of a project: "
            "'invoices of project X', 'LPO invoices for X', 'purchase orders of X', "
            "'timesheets for X', 'petty cash of X', 'staff list of X', "
            "'supervisors of X'.\n\n"
            "DO NOT USE for:\n"
            "- Expense totals/breakdown analysis (get_project_expense_summary / "
            "get_project_expense_breakdown — Deep Think)\n"
            "- Project header attributes (get_project_profile)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "Odoo project.project ID. Must be resolved before calling.",
                },
                "record_type": {
                    "type": "string",
                    "enum": list(RECORD_TYPE_VALUES),
                    "description": "Which linked records the user asked for.",
                },
                "date_from": {
                    "type": "string",
                    "description": "ISO date filter start (defaults to last 3 months for dated types).",
                },
                "date_to": {
                    "type": "string",
                    "description": "ISO date filter end.",
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "description": "Max rows to return (default 20).",
                },
            },
            "required": ["project_id", "record_type"],
        },
    },
]


def _m2o_name(value: Any) -> str | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1])
    return None


def _text(value: Any) -> str | None:
    if value is None or value is False:
        return None
    text = str(value).strip()
    return text or None


def _num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _normalize_row(record_type: str, row: dict[str, Any]) -> dict[str, Any]:
    """Flatten one raw Odoo row into display-ready values per record type."""
    if record_type in {"invoices", "client_invoices", "lpo_invoices"}:
        normalized = {
            "number": _text(row.get("name")),
            "date": _text(row.get("invoice_date")),
            "partner": _m2o_name(row.get("partner_id")),
            "total": _num(row.get("amount_total")),
            "due": _num(row.get("amount_residual")),
            "payment_state": _text(row.get("payment_state")),
            "reference": _text(row.get("ref")) or _text(row.get("invoice_origin")),
        }
        if record_type == "invoices":
            normalized["kind"] = (
                "client" if row.get("move_type") == "out_invoice" else "LPO"
            )
        return normalized
    if record_type == "purchase_orders":
        return {
            "number": _text(row.get("name")),
            "date": _text(row.get("date_order")),
            "vendor": _m2o_name(row.get("partner_id")),
            "total": _num(row.get("amount_total")),
            "state": _text(row.get("state")),
            "billing": _text(row.get("invoice_status")),
            "reception": _text(row.get("reception_status")),
        }
    if record_type == "timesheets":
        return {
            "date": _text(row.get("date")),
            "employee": _m2o_name(row.get("employee_id")),
            "description": _text(row.get("name")),
            "hours": _num(row.get("unit_amount")),
            "task": _m2o_name(row.get("task_id")),
        }
    if record_type in {"petty_cash", "petty_cash_sheets"}:
        return {
            "number": _text(row.get("seq_no")),
            "date": _text(row.get("date")),
            "employee": _m2o_name(row.get("employee_id")),
            "description": _text(row.get("name")),
            "total": _num(row.get("total_amount")),
            "state": _text(row.get("state")),
        }
    # staff / supervisors
    return {
        "code": _text(row.get("emp_code")),
        "name": _text(row.get("emp_name")) or _m2o_name(row.get("employee_id")),
        "job": _m2o_name(row.get("job_id")),
        "status": _text(row.get("status")),
        "access": _text(row.get("access")),
    }


def default_records_period(record_type: str) -> tuple[str | None, str | None]:
    """Last 3 months for dated types; people lists are undated."""
    if record_type in UNDATED_RECORD_TYPES:
        return None, None
    today = date.today()
    return (today - timedelta(days=DEFAULT_PERIOD_DAYS)).isoformat(), today.isoformat()


def execute_get_project_records(
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None = None,
) -> dict[str, Any]:
    """Run the project records read and normalize the payload."""
    del context
    project_id = int(tool_input["project_id"])
    record_type = str(tool_input.get("record_type") or "")
    if record_type not in RECORD_TYPE_VALUES:
        return {
            "status": "error",
            "_source": RECORDS_SOURCE,
            "error": f"Unknown record_type '{record_type}'.",
        }

    date_from = _text(tool_input.get("date_from"))
    date_to = _text(tool_input.get("date_to"))
    defaulted_period = False
    if record_type not in UNDATED_RECORD_TYPES and not date_from and not date_to:
        date_from, date_to = default_records_period(record_type)
        defaulted_period = True

    limit = int(tool_input.get("limit") or 20)

    result = adapter.read_project_records(
        record_type,
        project_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    project_name = None
    names = adapter.safe_search_read(
        "project.project", [["id", "=", project_id]], ["name"], limit=1,
    )
    if names:
        project_name = _text(names[0].get("name"))

    rows = [_normalize_row(record_type, row) for row in result.get("rows") or []]
    return {
        "status": "success",
        "_source": RECORDS_SOURCE,
        "project_id": project_id,
        "project_name": project_name or f"Project {project_id}",
        "record_type": record_type,
        "record_label": RECORD_TYPE_LABELS[record_type],
        "currency": "AED",
        "period": {
            "date_from": date_from,
            "date_to": date_to,
            "defaulted": defaulted_period,
        },
        "total_count": int(result.get("total_count") or 0),
        "returned_count": len(rows),
        "total_amount": result.get("total_amount"),
        "missing_analytic": bool(result.get("missing_analytic")),
        "rows": rows,
    }


def run_project_records_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None = None,
) -> dict[str, Any]:
    """Sync entry point for gateway execute_tool."""
    if tool_name == "get_project_records":
        return execute_get_project_records(tool_input, adapter, context)
    raise ValueError(f"Unknown project records tool: {tool_name}")
