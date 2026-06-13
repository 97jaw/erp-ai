"""Phase M6 — payroll query routing tests."""

from gateway.core.payroll_query_routing import (
    is_payroll_orchestration_query,
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
