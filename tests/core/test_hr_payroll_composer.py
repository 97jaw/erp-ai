"""Tests for unified HR/Payroll query composer."""

from gateway.core.hr_payroll_composer import (
    build_payslip_period_domain,
    classify_payroll_subtype,
    compose_hr_request_plan,
    compose_payroll_plan,
    compose_separation_plan,
    extract_employee_name,
    extract_inline_file_id,
    is_hr_request_query,
    is_separation_count_query,
    plan_to_route,
    resolve_payroll_subtype,
    strip_conversational_filler,
)
from gateway.core.intent_analyzer import Intent
from gateway.core.working_memory import WorkingMemory
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
    assert extract_inline_file_id("need payslip may 2026 for jawadfile id 2721") == "2721"


def test_extract_employee_name_strips_concatenated_file_id() -> None:
    name = extract_employee_name("need payslip may 2026 for jawadfile id 2721")
    assert name.lower() == "jawad"
    assert "file" not in name.lower()


def test_extract_employee_name_strips_assigned_vehicle_phrase() -> None:
    assert extract_employee_name("adil khan assigned vehicle").lower() == "adil khan"


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
    assert payload["detail_type"] == "full"


def test_classify_payroll_subtype_typo_alary_calculation() -> None:
    assert classify_payroll_subtype("alary calculation … may 2026 file id 2721") == "payslip_full"


def test_classify_payroll_subtype_overtime_lines() -> None:
    assert classify_payroll_subtype("show overtime breakdown on payslip") == "payslip_lines_overtime"


def test_classify_payroll_subtype_worked_days() -> None:
    assert classify_payroll_subtype("worked days on payslip for jawad") == "payslip_worked_days"


def test_map_subtype_to_detail_tool_input() -> None:
    from gateway.core.hr_payroll_composer import map_subtype_to_detail_tool_input

    assert map_subtype_to_detail_tool_input("payslip_full") == {"detail_type": "full"}
    assert map_subtype_to_detail_tool_input("payslip_lines_overtime") == {
        "detail_type": "lines",
        "line_filter": "overtime",
    }


def test_resolve_payroll_subtype_inherits_prior_salary_calculation() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["pending_hr_context"] = {
        "domain": "payroll",
        "subtype": "payslip_full",
        "prior_query": "salary calculation may 2026 file id 2721",
        "awaiting": [],
        "resolved": {"date_from": "2026-05-01", "date_to": "2026-05-31"},
    }
    assert resolve_payroll_subtype("2721", ctx) == "payslip_full"
    plan = compose_payroll_plan("2721", _intent(subject_area="payroll"), ctx)
    assert plan is not None
    assert plan.tool_input.get("detail_type") == "full"


def test_compose_payroll_salary_calculation_typo_routes_lines() -> None:
    plan = compose_payroll_plan(
        "alary calculation … may 2026 file id 2721",
        _intent(subject_area="payroll"),
        None,
    )
    assert plan is not None
    assert plan.tool == "get_payslip_detail"
    assert plan.tool_input.get("detail_type") == "full"


def test_compose_payroll_drill_down_overtime_follow_up() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["pending_hr_context"] = {
        "domain": "payroll",
        "subtype": "payslip_header",
        "prior_query": "need payslip for jawad may 2026",
        "resolved": {
            "employee_file_id": "2721",
            "employee_name_hint": "jawad ur rehman",
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
        },
    }
    plan = compose_payroll_plan("show overtime on that payslip", _intent(subject_area="payroll"), ctx)
    assert plan is not None
    assert plan.tool_input.get("line_filter") == "overtime"
    assert plan.tool_input.get("employee_file_id") == "2721"


def test_build_payslip_period_domain_may_2026() -> None:
    domain = build_payslip_period_domain(5, 2026)
    assert ["name", "ilike", "May-2026"] in domain
    assert ["date_from", "<=", "2026-05-31"] in domain
    assert ["date_to", ">=", "2026-05-01"] in domain


def test_compose_payroll_need_payslip_for_jawad_may() -> None:
    plan = compose_payroll_plan(
        "need payslip for jawad may 2026",
        _intent(subject_area="payroll"),
        None,
    )
    assert plan is not None
    assert plan.tool == "get_payslip_detail"
    assert plan.tool_input.get("detail_type") == "header"
    assert plan.employee_name_hint == "jawad"
    assert plan.period is not None
    assert plan.period.label == "May 2026"


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
    assert plan.tool == "get_payslip_detail"
    assert plan.tool_input.get("detail_type") == "header"
    assert plan.period is not None
    assert plan.period.date_from.startswith("2026-05")


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
    assert payload["model"] == "employee.requests"
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


def test_validation_status_follow_up_after_hr_request_list() -> None:
    from gateway.core.hr_payroll_composer import compose_hr_request_detail_plan, is_hr_request_detail_query
    from gateway.core.project_attribute_utils import is_project_attribute_query
    from gateway.core.project_profile_routing import is_project_profile_query

    ctx = _make_context_stack()
    ctx.working_memory.session_facts["pending_hr_context"] = {
        "domain": "hr",
        "subtype": "hr_request_list",
        "resolved": {
            "employee_name_hint": "jawad ur rehman",
            "recent_request_ids": [39540],
        },
    }
    assert is_hr_request_detail_query("validation status", ctx)
    assert not is_project_attribute_query("validation status")
    assert not is_project_profile_query("validation status", _intent(subject_area="project_attribute"), ctx)
    plan = compose_hr_request_detail_plan("validation status", _intent(subject_area="hr"), ctx)
    assert plan is not None
    assert plan.tool_input.get("request_id") == 39540


def test_extract_request_reference_validation_status_of_partial_number() -> None:
    from gateway.core.hr_payroll_composer import (
        compose_hr_request_detail_plan,
        extract_request_reference,
        is_hr_request_detail_query,
    )

    request_id, request_name = extract_request_reference("validation status of 04557")
    assert request_id is None
    assert request_name == "04557"
    assert is_hr_request_detail_query("validation status of 04557", None)
    plan = compose_hr_request_detail_plan(
        "validation status of 04557",
        _intent(subject_area="hr"),
        _make_context_stack(),
    )
    assert plan is not None
    assert plan.tool_input.get("request_name") == "04557"


def test_session_scope_persists_hr_context_between_turns() -> None:
    from gateway.session_scope import SessionScopeStore

    SessionScopeStore.clear("sess-hr-1")
    wm = WorkingMemory()
    wm.session_facts["pending_hr_context"] = {
        "domain": "payroll",
        "resolved": {
            "employee_file_id": "2721",
            "date_from": "2026-05-01",
            "date_to": "2026-05-31",
        },
    }
    wm.session_facts["last_payslip_scope"] = {"employee_file_id": "2721"}
    SessionScopeStore.persist_hr_session("sess-hr-1", wm)

    loaded = SessionScopeStore.get("sess-hr-1")
    assert loaded["pending_hr_context"]["domain"] == "payroll"
    assert loaded["pending_hr_context"]["resolved"]["employee_file_id"] == "2721"
    assert loaded["last_payslip_scope"]["employee_file_id"] == "2721"
