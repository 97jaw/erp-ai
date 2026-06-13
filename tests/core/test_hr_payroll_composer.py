"""Tests for unified HR/Payroll query composer."""

from gateway.core.hr_payroll_composer import (
    compose_hr_request_plan,
    compose_payroll_plan,
    compose_separation_plan,
    extract_employee_name,
    extract_inline_file_id,
    is_hr_request_query,
    is_separation_count_query,
    plan_to_route,
    strip_conversational_filler,
)
from gateway.core.intent_analyzer import Intent
from tests.core.test_context_stack import _make_context_stack


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


def test_strip_conversational_filler() -> None:
    assert strip_conversational_filler("its jawad ur rehman") == "jawad ur rehman"
    assert strip_conversational_filler("I mean jawad ur rehman").lower().startswith("jawad")


def test_extract_employee_name_jawad_not_need() -> None:
    assert extract_employee_name("need payslip may 2026 for jawad").lower().startswith("jawad")
    assert "need" not in extract_employee_name("need payslip may 2026 for jawad").lower()


def test_extract_inline_file_id() -> None:
    assert extract_inline_file_id("need payslip distribution of rmay 2026 file id 2721") == "2721"
    assert extract_inline_file_id("2721") == "2721"


def test_compose_payroll_distribution_with_file_id() -> None:
    plan = compose_payroll_plan(
        "need payslip distribution of rmay 2026 file id 2721",
        _intent(),
        None,
    )
    assert plan is not None
    assert plan.tool == "get_payslip_detail"
    assert plan.tool_input.get("employee_file_id") == "2721"
    assert plan.tool_input.get("detail_type") == "distribution"
    assert plan.tool_input.get("date_from", "").startswith("2026-05")


def test_compose_payroll_salary_calculation_with_file_id() -> None:
    plan = compose_payroll_plan(
        "need payslip salary calculation of rmay 2026 file id 2721",
        _intent(),
        None,
    )
    assert plan is not None
    routed = plan_to_route(plan)
    assert routed is not None
    tool, payload = routed
    assert tool == "get_payslip_detail"
    assert payload["detail_type"] == "lines"


def test_compose_payroll_name_correction_follow_up() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["pending_hr_context"] = {
        "domain": "payroll",
        "subtype": "payslip_header",
        "prior_query": "need payslip may 2026 for jawad",
        "awaiting": ["employee"],
        "resolved": {"date_from": "2026-05-01", "date_to": "2026-05-31"},
    }
    plan = compose_payroll_plan("its jawad ur rehman", _intent(), ctx)
    assert plan is not None
    assert plan.employee_name_hint == "jawad ur rehman"
    assert "its" not in (plan.employee_name_hint or "").lower()


def test_compose_hr_request_for_jawad() -> None:
    plan = compose_hr_request_plan(
        "recent employee request for jawad ur rehman",
        _intent(subject_area="hr"),
        None,
    )
    assert plan is not None
    routed = plan_to_route(plan)
    assert routed is not None
    tool, payload = routed
    assert tool == "list_employee_requests"
    assert payload.get("employee_name") == "jawad ur rehman"
    assert payload.get("date_from")
    assert payload.get("date_to")


def test_compose_separation_termination_count() -> None:
    plan = compose_separation_plan(
        "this month is how many employees terminated?",
        _intent(expected_output="number"),
        None,
    )
    assert plan is not None
    routed = plan_to_route(plan)
    assert routed is not None
    tool, payload = routed
    assert tool == "aggregate_odoo"
    assert payload["model"] == "employee.request"
    domain_text = str(payload["domain"])
    assert "termination" in domain_text.lower()
    assert "active" not in domain_text.lower()


def test_is_hr_request_query_broad_detection() -> None:
    assert is_hr_request_query(
        "recent employee request for jawad",
        _intent(subject_area="general"),
    )
    assert is_separation_count_query("how many employees terminated this month", _intent())
    assert not is_hr_request_query("pending leave requests", _intent(subject_area="hr"))
