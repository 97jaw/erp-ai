"""Routing integration tests for HR/Payroll composer wiring."""

from gateway.core.hr_query_routing import resolve_hr_tool
from gateway.core.intent_analyzer import Intent
from gateway.core.payroll_query_routing import resolve_payroll_tool


def _intent(**overrides: object) -> Intent:
    base = {
        "primary_action": "fetch_data",
        "subject_area": "other",
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


def test_resolve_payroll_distribution_routes_detail_tool() -> None:
    routed = resolve_payroll_tool(
        "need payslip distribution of rmay 2026 file id 2721",
        _intent(),
        None,
    )
    assert routed is not None
    tool, payload = routed
    assert tool == "get_payslip_detail"
    assert payload["employee_file_id"] == "2721"


def test_resolve_hr_request_routes_list_tool() -> None:
    routed = resolve_hr_tool(
        "recent employee request for jawad ur rehman",
        _intent(subject_area="hr"),
        None,
    )
    assert routed is not None
    tool, payload = routed
    assert tool == "list_employee_requests"
    assert payload.get("employee_name") == "jawad ur rehman"


def test_resolve_termination_not_headcount() -> None:
    routed = resolve_hr_tool(
        "this month is how many employees terminated?",
        _intent(expected_output="number"),
        None,
    )
    assert routed is not None
    tool, payload = routed
    assert tool == "aggregate_odoo"
    assert payload["model"] == "employee.request"
    assert payload["model"] != "hr.employee"
