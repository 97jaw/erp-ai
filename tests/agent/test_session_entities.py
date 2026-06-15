"""Tests for agent session entity memory (payroll context)."""

from gateway.agent.session_entities import (
    apply_confirmed_entities,
    build_entity_context_prompt,
    clear_entities,
    enrich_fleet_tool_input,
    enrich_payroll_tool_input,
    enrich_procurement_tool_input,
    enrich_project_tool_input,
    extract_period_from_text,
    update_entities,
    update_entities_from_message,
)
from gateway.core.entity_gate import ConfirmedEntityRef


def test_extract_period_may_2026() -> None:
    period = extract_period_from_text("need payslip of may 2026")
    assert period is not None
    assert period["period_month"] == 5
    assert period["period_year"] == 2026
    assert period["period_label"] == "May 2026"
    assert period["date_from"] == "2026-04-21"
    assert period["date_to"] == "2026-05-20"


def test_session_entities_persist_employee_and_period() -> None:
    clear_entities("pay-test")
    update_entities_from_message("pay-test", "need payslip of may 2026")
    update_entities(
        "pay-test",
        employee_name="Jawad ur rehman",
        employee_file_id="4255",
        employee_id=123,
    )

    prompt = build_entity_context_prompt("pay-test")
    assert "Jawad" in prompt
    assert "May 2026" in prompt
    assert "get_payslip_detail" in prompt

    enriched = enrich_payroll_tool_input(
        "pay-test",
        "get_payslip_detail",
        {"detail_type": "full"},
    )
    assert enriched["employee_file_id"] == "4255"
    assert enriched["date_from"] == "2026-04-21"
    assert enriched["date_to"] == "2026-05-20"
    clear_entities("pay-test")


def test_project_confirmed_entity_enriches_expense_tool() -> None:
    clear_entities("proj-test")
    apply_confirmed_entities(
        "proj-test",
        [ConfirmedEntityRef(type="project", id=14549, name="Zayidia Boys School")],
    )
    enriched = enrich_project_tool_input("proj-test", "get_project_expense_summary", {})
    assert enriched["project_id"] == 14549
    assert enriched["project_name"] == "Zayidia Boys School"
    prompt = build_entity_context_prompt("proj-test")
    assert "Zayidia" in prompt
    assert "get_project_expense_summary" in prompt
    clear_entities("proj-test")


def test_fleet_employee_pick_enriches_fleet_tool() -> None:
    clear_entities("fleet-test")
    update_entities_from_message("fleet-test", "adil khan's vehicle")
    apply_confirmed_entities(
        "fleet-test",
        [
            ConfirmedEntityRef(
                type="employee",
                id=698,
                name="Adil Khan Rahim Khan (1579) - Electrical Dept",
            )
        ],
    )
    enriched = enrich_fleet_tool_input("fleet-test", "search_fleet_vehicles", {})
    assert enriched["employee_file_id"] == "1579"
    assert "Adil Khan" in enriched["employee_name"]
    prompt = build_entity_context_prompt("fleet-test")
    assert "search_fleet_vehicles" in prompt
    clear_entities("fleet-test")


def test_procurement_project_pick_preserves_intent() -> None:
    clear_entities("po-test")
    update_entities_from_message(
        "po-test",
        "purchase orders for project national guard",
    )
    apply_confirmed_entities(
        "po-test",
        [
            ConfirmedEntityRef(
                type="project",
                id=999,
                name="National Guard Airport (Design & Construction)",
            )
        ],
    )
    enriched = enrich_procurement_tool_input("po-test", "get_project_records", {})
    assert enriched["project_id"] == 999
    assert enriched["record_type"] == "purchase_orders"
    prompt = build_entity_context_prompt("po-test")
    assert "get_project_records" in prompt
    clear_entities("po-test")
