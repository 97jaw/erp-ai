"""Session stickiness and payroll follow-up routing (3-query user scenario)."""

from gateway.core.intent_analyzer import Intent
from gateway.core.payroll_query_routing import (
    _employee_name_hint,
    extract_employee_file_id,
    is_explicit_non_payroll_query,
    is_payroll_file_id_follow_up,
    is_payroll_orchestration_query,
    resolve_payroll_tool,
    should_block_project_entity_search,
)
from gateway.core.topic_shift import detect_topic_shift, infer_message_domain, infer_turn_domain
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


def _payroll_session_context() -> object:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["last_turn"] = {
        "message": "need payslip may 2026 for jawad",
        "subject_area": "payroll",
        "domain": "payroll",
    }
    ctx.working_memory.session_facts["pending_entity_clarification"] = {
        "query": "need payslip may 2026 for jawad",
        "payroll_context": True,
        "options": [],
    }
    return ctx


def test_employee_name_hint_extracts_jawad_not_need() -> None:
    hint = _employee_name_hint("need payslip may 2026 for jawad")
    assert hint.lower().startswith("jawad")
    assert "need" not in hint.lower()


def test_employee_name_hint_empty_for_project_expense_after_payroll_session() -> None:
    assert _employee_name_hint("show me project expense of national guard") == ""


def test_explicit_non_payroll_overrides_active_payroll_context() -> None:
    ctx = _payroll_session_context()
    message = "show me project expense of national guard"
    intent = _intent(specific_intent=message, subject_area="project")
    assert is_explicit_non_payroll_query(message)
    assert not is_payroll_orchestration_query(message, intent, ctx)
    assert resolve_payroll_tool(message, intent, ctx) is None


def test_file_id_follow_up_routes_to_get_payslip_detail() -> None:
    ctx = _payroll_session_context()
    message = "2721"
    intent = _intent(specific_intent=message)
    assert extract_employee_file_id(message) == "2721"
    assert is_payroll_file_id_follow_up(message, ctx)
    assert should_block_project_entity_search(message, ctx)
    routed = resolve_payroll_tool(message, intent, ctx)
    assert routed is not None
    tool, payload = routed
    assert tool == "get_payslip_detail"
    assert payload["employee_file_id"] == "2721"
    assert payload.get("date_from") == "2026-05-01"
    assert payload.get("date_to") == "2026-05-31"
    assert payload.get("detail_type") == "header"


def test_repeat_payslip_query_uses_jawad_filter() -> None:
    ctx = _payroll_session_context()
    message = "need payslip may 2026 for jawad"
    intent = _intent(specific_intent=message)
    routed = resolve_payroll_tool(message, intent, ctx)
    assert routed is not None
    tool, payload = routed
    assert tool == "get_payslip_detail"
    assert payload.get("employee_name", "").lower().startswith("jawad")
    assert "need" not in payload.get("employee_name", "").lower()
    assert payload.get("detail_type") == "header"


def test_topic_shift_detects_payroll_to_project_expense() -> None:
    last_turn = {
        "message": "need payslip may 2026 for jawad",
        "subject_area": "other",
        "domain": "payroll",
        "entity_values": ["jawad"],
    }
    message = "show me project expense of national guard"
    intent = _intent(
        specific_intent=message,
        subject_area="project",
        entities=[],
    )
    assert infer_message_domain(message) == "project"
    assert detect_topic_shift(message, intent, last_turn=last_turn)


def test_infer_turn_domain_from_payslip_tool() -> None:
    assert infer_turn_domain(["get_payslip_detail"], []) == "payroll"
    assert infer_turn_domain(["get_employee_payslips"], []) == "payroll"
    assert infer_turn_domain(
        ["query_odoo"],
        [{"model": "hr.payslip", "status": "success", "record_count": 0}],
    ) == "payroll"
    assert infer_turn_domain(["get_project_expenses"], []) == "project"
