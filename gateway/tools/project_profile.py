"""Project profile tool — reads project.project header fields directly (no Deep Think).

Project Model Phase 1. Answers attribute questions (engineer/trade amounts,
W.O distribution, dates, client, contract, team, status, audit) from the
project header via a curated single-record read. Actual computed financials
(expense summary/breakdown, P&L) remain Deep Think territory.

Field map verified against live Elrace Odoo 2026-06-11:
  Civil Amount      = project_eng_amount  (label: 'Civil Engineer Amount')
  Electrical Amount = electrical_eng_amount
  Mechanical Amount = mechanical_eng_amount
  ICT Amount        = it_eng_amount
"""

from __future__ import annotations

import logging
from typing import Any

from gateway.core.context_stack import ContextStack

logger = logging.getLogger(__name__)

PROFILE_SOURCE = "project_profile"

PROJECT_PROFILE_TOOL_NAMES = frozenset({"get_project_profile"})

PROFILE_FOCUS_VALUES = (
    "amounts",
    "wo_amount",
    "estimation",
    "engineers",
    "civil",
    "electrical",
    "mechanical",
    "ict",
    "team",
    "schedule",
    "identity",
    "status",
    "all",
)

# Focuses that narrow the answer to engineering discipline allocations only.
ENGINEER_TRADE_FOCUSES = frozenset({"civil", "electrical", "mechanical", "ict"})

PROJECT_PROFILE_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_project_profile",
        "description": (
            "Read the project HEADER PROFILE directly from Odoo — agreement/budget "
            "allocations (W.O amount, estimation, Civil/Electrical/Mechanical/ICT "
            "distribution, engineer role amounts), client & contract, schedule "
            "(start/end/duration/completion), assigned team (engineers, managers), "
            "status, progress %, and audit trail (created/last updated by).\n\n"
            "USE THIS WHEN:\n"
            "- User asks for engineer/trade AMOUNTS or W.O distribution of a project\n"
            "- User asks who the project manager / engineers / team are\n"
            "- User asks project dates, duration, status, progress, client, contract\n"
            "- User asks 'last updated by' or audit details\n\n"
            "DO NOT USE for:\n"
            "- Actual spend/expenses (use get_project_expense_summary — Deep Think)\n"
            "- GL drill-down (use get_project_expense_breakdown — Deep Think)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "Odoo project.project ID. Must be resolved before calling.",
                },
                "focus": {
                    "type": "string",
                    "enum": list(PROFILE_FOCUS_VALUES),
                    "default": "all",
                    "description": "Which profile section the user asked about.",
                },
            },
            "required": ["project_id"],
        },
    },
]


def _m2o(value: Any) -> dict[str, Any] | None:
    """Odoo many2one read value [id, display_name] -> {id, name}; False -> None."""
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return {"id": value[0], "name": str(value[1])}
    return None


def _num(value: Any) -> float | None:
    """Odoo float read value; False/None (unset) -> None, real zero stays 0.0."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _text(value: Any) -> str | None:
    if value is None or value is False:
        return None
    text = str(value).strip()
    return text or None


def normalize_project_profile(record: dict[str, Any], focus: str = "all") -> dict[str, Any]:
    """Group the raw project.project read into labeled profile sections."""
    distribution = {
        "civil": _num(record.get("project_eng_amount")),
        "electrical": _num(record.get("electrical_eng_amount")),
        "mechanical": _num(record.get("mechanical_eng_amount")),
        "ict": _num(record.get("it_eng_amount")),
        "plumbing": _num(record.get("plumber_amount")),
    }
    role_allocations = {
        "branch_manager": _num(record.get("branch_manager_amount")),
        "project_manager": _num(record.get("project_manager_amount")),
    }
    return {
        "status": "success",
        "_source": PROFILE_SOURCE,
        "project_id": record.get("id"),
        "project_name": _text(record.get("name")) or f"Project {record.get('id')}",
        "focus": focus,
        "currency": "AED",
        "identity": {
            "name": _text(record.get("name")),
            "name_arabic": _text(record.get("project_name_arabic")),
            "wo_ref_no": _text(record.get("wo_ref_no")),
            "project_code": _text(record.get("project_code")),
            "project_number": _text(record.get("project_number")),
            "contract_no": _text(record.get("contract_no")),
        },
        "client_contract": {
            "client": _m2o(record.get("partner_id")),
            "client_shortname": _text(record.get("client_shortname")),
            "client_email": _text(record.get("partner_email")),
            "client_phone": _text(record.get("partner_phone")),
            "agreement": _m2o(record.get("agreement_id")),
        },
        "location": {
            "city": _m2o(record.get("city_id")),
            "city_text": _text(record.get("city")),
            "state": _m2o(record.get("state_id")),
            "country": _m2o(record.get("country_id")),
            "operating_unit": _m2o(record.get("operating_unit_id")),
            "latitude": _num(record.get("latitude")),
            "longitude": _num(record.get("longitude")),
        },
        "schedule": {
            "start_date": _text(record.get("date_start")),
            "end_date": _text(record.get("date")),
            "estimated_duration_days": _num(record.get("estimated_duration")),
            "completion_date": _text(record.get("compliation_date")),
            "pending_days": _num(record.get("pending_days")),
            "last_extend_date": _text(record.get("last_extend_date")),
            "extend_duration_days": _num(record.get("extend_duration")),
        },
        "amounts": {
            "wo_amount": _num(record.get("wo_amount")),
            "estimation_amount": _num(record.get("estimation_amount")),
            "extended_amount": _num(record.get("extended_amount")),
            "extension_total_amount": _num(record.get("extension_total_amount")),
            "distribution": distribution,
            "role_allocations": role_allocations,
            "rollups": {
                "invoice_total": _num(record.get("invoice_total_amount")),
                "client_invoice_total": _num(record.get("total_client_invoice")),
                "purchase_total": _num(record.get("purchase_total_amount")),
                "total_cost": _num(record.get("total_cost")),
                "project_cost": _num(record.get("project_cost")),
                "profit": _num(record.get("profit")),
            },
        },
        "team": {
            "project_manager": _m2o(record.get("user_id")),
            "projects_manager": _m2o(record.get("projects_manager")),
            "branch_manager": _m2o(record.get("branch_manager_id")),
            "civil_engineer": _m2o(record.get("project_eng_id")),
            "mechanical_engineer": _m2o(record.get("mechanical_eng_id")),
            "electrical_engineer": _m2o(record.get("electrical_eng_id")),
            "ict_engineer": _m2o(record.get("it_eng_id")),
            "plumber": _m2o(record.get("plumber_id")),
            "architect": _m2o(record.get("architect")),
            "document_controller": _m2o(record.get("document_controller")),
        },
        "project_status": {
            "state": _text(record.get("state")),
            "status": _m2o(record.get("project_status")),
            "status_computed": _text(record.get("project_status_compute")),
            "wo_type": _text(record.get("wo_type")),
            "active": bool(record.get("active")),
        },
        "progress": {
            "overall_percent": _num(record.get("progress_overall_percent")),
            "last_update": _text(record.get("progress_last_update")),
            "delayed_weeks": _num(record.get("progress_delayed_weeks")),
            "on_time_weeks": _num(record.get("progress_on_time_weeks")),
        },
        "audit": {
            "created_by": _m2o(record.get("create_uid")),
            "created_on": _text(record.get("create_date")),
            "last_updated_by": _m2o(record.get("write_uid")),
            "last_updated_on": _text(record.get("write_date")),
        },
    }


def execute_get_project_profile(
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None = None,
) -> dict[str, Any]:
    """Read and normalize the project header profile."""
    del context
    project_id = int(tool_input["project_id"])
    focus = str(tool_input.get("focus") or "all")
    if focus not in PROFILE_FOCUS_VALUES:
        focus = "all"

    record = adapter.read_project_profile(project_id)
    if not record:
        return {
            "status": "error",
            "_source": PROFILE_SOURCE,
            "project_id": project_id,
            "message": f"Project {project_id} not found in Odoo.",
        }
    return normalize_project_profile(record, focus)


def run_project_profile_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None = None,
) -> dict[str, Any]:
    """Sync entry point for gateway execute_tool."""
    if tool_name == "get_project_profile":
        return execute_get_project_profile(tool_input, adapter, context)
    raise ValueError(f"Unknown project profile tool: {tool_name}")
