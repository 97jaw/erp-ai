"""Phase M6 — payroll query routing tests."""

from gateway.core.payroll_query_routing import (
    _employee_name_hint,
    is_payroll_orchestration_query,
    requires_payroll_project_confirmation,
    resolve_payroll_tool,
)
from gateway.core.intent_analyzer import Intent
from tests.core.test_context_stack import _make_context_stack


def _intent(**overrides: object) -> Intent:
    base = {
        "primary_action": "fetch_data",
        "subject_area": "payroll",
        "specific_intent": "lookup",
        "entities": [],
        "implicit_requirements": [],
        "ambiguities": [],
        "expected_output": "number",
        "urgency": "normal",
        "estimated_complexity": "simple",
        "requires_clarification": False,
        "clarification_question": None,
        "out_of_scope": False,
        "out_of_scope_reason": None,
    }
    base.update(overrides)
    return Intent(**base)


def test_labor_cost_without_confirmed_project_requires_entity_pick() -> None:
    ctx = _make_context_stack()
    message = "labor cost for Villa Maintenance No. 34 this month"
    intent = _intent(specific_intent=message, subject_area="project")
    assert requires_payroll_project_confirmation(message, intent, ctx)
    assert resolve_payroll_tool(message, intent, ctx) is None


def test_labor_cost_routes_to_cost_allocation() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": 15157, "name": "Villa Maintenance No. 34"},
    }
    tool, payload = resolve_payroll_tool(
        "labor cost for Villa Maintenance No. 34 this month",
        _intent(specific_intent="labor cost for Villa Maintenance No. 34 this month"),
        ctx,
    )
    assert tool == "aggregate_odoo"
    assert payload["model"] == "hr.payslip.cost.allocation"
    assert payload["aggregates"] == ["amount:sum"]
    assert ["project_id", "=", 15157] in payload["domain"]
    assert payload["group_by"] == ["project_id"]


def test_labor_cost_ignores_breakdown_in_llm_intent() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": 15157, "name": "Villa Maintenance No. 34"},
    }
    tool, payload = resolve_payroll_tool(
        "labor cost for Villa Maintenance No. 34 this month",
        _intent(
            specific_intent="labor cost breakdown by employee for Villa Maintenance No. 34",
        ),
        ctx,
    )
    assert payload["group_by"] == ["project_id"]


def test_employee_cost_across_projects_routes_to_cost_allocation() -> None:
    tool, payload = resolve_payroll_tool(
        "AABID SADIK cost across projects this year",
        _intent(specific_intent="employee labor cost across projects"),
    )
    assert tool == "aggregate_odoo"
    assert payload["model"] == "hr.payslip.cost.allocation"
    assert payload["group_by"] == ["project_id"]
    assert ["employee_id.name", "ilike", "AABID"] in payload["domain"]
    assert ["year", "=", str(__import__("datetime").date.today().year)] in payload["domain"]


def test_breakdown_by_employee_uses_employee_group() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": 15157, "name": "Villa Maintenance No. 34"},
    }
    tool, payload = resolve_payroll_tool(
        "labor cost breakdown by employee for Villa 34",
        _intent(subject_area="payroll"),
        ctx,
    )
    assert payload["group_by"] == ["employee_id"]
    assert ["project_id", "=", 15157] in payload["domain"]


def test_hr_orchestration_skips_payroll_labor_cost() -> None:
    from gateway.core.hr_query_routing import is_hr_orchestration_query

    intent = _intent(
        specific_intent="labor cost for Villa Maintenance No. 34 this month",
        subject_area="project",
    )
    assert is_payroll_orchestration_query(
        "labor cost for Villa Maintenance No. 34 this month",
        intent,
    )
    assert not is_hr_orchestration_query(
        "labor cost for Villa Maintenance No. 34 this month",
        intent,
    )


def test_name_and_month_year_routes_to_payslip_query() -> None:
    ctx = _make_context_stack()
    message = "jawad ur rehman, may 2026"
    intent = _intent(
        primary_action="fetch_data",
        subject_area="other",
        specific_intent=message,
    )
    assert is_payroll_orchestration_query(message, intent, ctx)
    tool, payload = resolve_payroll_tool(message, intent, ctx)
    assert tool == "get_payslip_detail"
    assert payload.get("employee_name", "").lower().startswith("jawad")
    assert payload.get("date_from", "").startswith("2026-05")
    assert payload.get("detail_type") == "header"


def test_need_payslip_for_jawad_uses_jawad_not_need() -> None:
    ctx = _make_context_stack()
    message = "need payslip may 2026 for jawad"
    intent = _intent(specific_intent=message, subject_area="other")
    hint = _employee_name_hint(message)
    assert hint.lower().startswith("jawad")
    tool, payload = resolve_payroll_tool(message, intent, ctx)
    assert tool == "get_payslip_detail"
    assert payload.get("employee_name", "").lower().startswith("jawad")
    assert "need" not in payload.get("employee_name", "").lower()
    assert payload.get("detail_type") == "header"


def test_payroll_follow_up_after_prior_payslip_turn() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["last_turn"] = {
        "message": "show payslip amount for jawad",
        "subject_area": "payroll",
    }
    message = "jawad ur rehman, may 2026"
    intent = _intent(subject_area="other", specific_intent=message)
    assert is_payroll_orchestration_query(message, intent, ctx)


def test_name_only_follow_up_routes_get_payslip_detail() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["pending_hr_context"] = {
        "domain": "payroll",
        "subtype": "payslip_header",
        "prior_query": "need payslip may 2026 for jawad",
        "awaiting": ["employee"],
        "resolved": {
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
            "label": "May 2026",
        },
    }
    message = "jawad ur rehman"
    intent = _intent(subject_area="other", specific_intent=message)
    assert is_payroll_orchestration_query(message, intent, ctx)
    tool, payload = resolve_payroll_tool(message, intent, ctx)
    assert tool == "get_payslip_detail"
    assert payload.get("employee_name", "").lower().startswith("jawad")
    assert payload.get("detail_type") == "header"


def test_overtime_follow_up_routes_payslip_detail_not_unscoped_list() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["pending_hr_context"] = {
        "domain": "payroll",
        "subtype": "payslip_header",
        "resolved": {
            "employee_file_id": "2721",
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
        },
    }
    message = "show overtime on that payslip"
    intent = _intent(subject_area="payroll", specific_intent=message)
    tool, payload = resolve_payroll_tool(message, intent, ctx)
    assert tool == "get_payslip_detail"
    assert payload.get("line_filter") == "overtime"
    assert payload.get("employee_file_id") == "2721"
