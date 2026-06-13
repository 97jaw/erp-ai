"""Tests for fleet vehicle tools and routing."""

from gateway.core.fleet_query_routing import is_fleet_orchestration_query, resolve_fleet_tool
from gateway.core.hr_payroll_composer import compose_hr_request_detail_plan, is_hr_request_detail_query
from gateway.core.intent_analyzer import Intent
from gateway.fleet_tools import _present_vehicle, extract_license_plate
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


def test_extract_license_plate() -> None:
    assert extract_license_plate("vehicle with plate ABC-1234") == "ABC-1234"


def test_present_vehicle_includes_driver_and_project() -> None:
    row = {
        "id": 7,
        "name": "Toyota Hilux",
        "license_plate": "A 12345",
        "driver_id": [11, "Jawad Ahmad"],
        "employee_id": [11, "Jawad Ahmad"],
        "emp_id": "2591",
        "emp_mobile": "0501234567",
        "project_id": [14549, "Zayidia Boys School"],
        "location": "Al Ain",
    }
    presented = _present_vehicle(row)
    assert presented["driver_name"] == "Jawad Ahmad"
    assert presented["file_id"] == "2591"
    assert presented["mobile"] == "0501234567"
    assert presented["project_name"] == "Zayidia Boys School"
    assert presented["location"] == "Al Ain"


def test_fleet_query_routes_search_tool() -> None:
    ctx = _make_context_stack()
    message = "show jawad assigned vehicle"
    intent = _intent(specific_intent=message)
    assert is_fleet_orchestration_query(message, intent)
    tool, payload = resolve_fleet_tool(message, intent, ctx)
    assert tool == "search_fleet_vehicles"
    assert payload.get("employee_name", "").lower().startswith("jawad")


def test_hr_request_detail_query_detects_validation() -> None:
    ctx = _make_context_stack()
    ctx.working_memory.session_facts["pending_hr_context"] = {
        "domain": "hr",
        "resolved": {"employee_file_id": "2721", "recent_request_ids": [8834]},
    }
    message = "show validation status for request id 8834"
    assert is_hr_request_detail_query(message, ctx)
    plan = compose_hr_request_detail_plan(message, _intent(), ctx)
    assert plan is not None
    assert plan.tool == "get_employee_request_detail"
    assert plan.tool_input.get("request_id") == 8834
