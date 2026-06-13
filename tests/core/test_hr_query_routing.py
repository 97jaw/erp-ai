"""Phase M2.2b — deterministic HR query routing tests."""

from __future__ import annotations

from gateway.core.hr_query_routing import (
    is_hr_orchestration_query,
    is_hr_person_query,
    is_hr_project_staff_query,
    resolve_hr_tool,
)
from gateway.core.intent_analyzer import Intent
from tests.core.test_context_stack import _make_context_stack


def _intent(**overrides: object) -> Intent:
    base = {
        "primary_action": "fetch_data",
        "subject_area": "hr",
        "specific_intent": "lookup",
        "entities": [],
        "implicit_requirements": [],
        "ambiguities": [],
        "expected_output": "summary",
        "urgency": "normal",
        "estimated_complexity": "simple",
        "requires_clarification": False,
        "clarification_question": None,
        "out_of_scope": False,
        "out_of_scope_reason": None,
    }
    base.update(overrides)
    return Intent(**base)


def test_labor_vs_staff_routes_to_is_labor_aggregate() -> None:
    tool, payload = resolve_hr_tool(
        "how many labor vs staff",
        _intent(specific_intent="how many labor vs staff"),
        _make_context_stack(),
    )
    assert tool == "aggregate_odoo"
    assert payload["model"] == "hr.employee"
    assert payload["group_by"] == ["is_labor"]


def test_pending_leave_routes_to_employee_request() -> None:
    tool, payload = resolve_hr_tool(
        "pending leave requests",
        _intent(specific_intent="pending leave requests"),
        _make_context_stack(),
    )
    assert tool == "query_odoo"
    assert payload["model"] == "employee.requests"


def test_transfers_not_stock_moves() -> None:
    tool, payload = resolve_hr_tool(
        "transfers this year",
        _intent(specific_intent="transfers this year", subject_area="hr"),
        _make_context_stack(),
    )
    assert payload["model"] == "employee.requests"


def test_unresolved_requests_not_project_tasks() -> None:
    tool, payload = resolve_hr_tool(
        "who has unresolved requests",
        _intent(specific_intent="who has unresolved requests", subject_area="hr"),
        _make_context_stack(),
    )
    assert payload["model"] == "employee.requests"


def test_biggest_department_analyze_action() -> None:
    tool, payload = resolve_hr_tool(
        "biggest department",
        _intent(primary_action="analyze", specific_intent="biggest department", subject_area="hr"),
        _make_context_stack(),
    )
    assert tool == "aggregate_odoo"
    assert payload["group_by"] == ["department_id"]


def test_branches_general_subject() -> None:
    tool, payload = resolve_hr_tool(
        "branches we have",
        _intent(subject_area="general", specific_intent="branches we have"),
        _make_context_stack(),
    )
    assert tool == "aggregate_odoo"
    assert payload["group_by"] == ["branch_id"]


def test_visa_compliance_filters_hr_employee() -> None:
    tool, payload = resolve_hr_tool(
        "visas expiring in 30 days",
        _intent(specific_intent="visas expiring in 30 days"),
        _make_context_stack(),
    )
    assert tool == "query_odoo"
    assert payload["model"] == "hr.employee"
    assert any("visa_expire" in str(clause) for clause in payload["domain"])


def test_hr_person_query_detection() -> None:
    assert is_hr_person_query("AABID SADIK's assigned vehicle")
    assert is_hr_person_query("show me Ahmed Ali details")


def test_project_staff_query_detection() -> None:
    assert is_hr_project_staff_query("who works on Villa 34")


def test_who_works_in_department_lists_employees() -> None:
    tool, payload = resolve_hr_tool(
        "who works in the Civil department",
        _intent(subject_area="hr", specific_intent="list civil department employees"),
    )
    assert tool == "query_odoo"
    assert payload["model"] == "hr.employee"
    assert ["department_id.name", "ilike", "civil"] in payload["domain"]


def test_strategy_planner_delegates_hr_routing() -> None:
    from gateway.core.strategy_planner import StrategyPlanner

    intent = Intent(
        primary_action="fetch_data",
        subject_area="hr",
        specific_intent="pending leave requests",
        entities=[],
        expected_output="table",
    )
    tool, payload = StrategyPlanner._resolve_universal_read_tool(intent, _make_context_stack())
    assert tool == "query_odoo"
    assert payload["model"] == "employee.requests"


def test_is_hr_orchestration_for_attendance() -> None:
    assert is_hr_orchestration_query(
        "who was absent yesterday",
        _intent(specific_intent="who was absent yesterday"),
    )
