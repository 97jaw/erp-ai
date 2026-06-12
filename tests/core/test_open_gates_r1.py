"""Phase R1 — Open the gates: intent, manifest, and routing regression tests."""

from __future__ import annotations

import json

import pytest

from gateway.core.capability_manifest import CAPABILITY_MANIFEST
from gateway.core.intent_analyzer import Intent, IntentAnalyzer
from gateway.core.project_expense_routing import select_project_expense_tool
from gateway.core.strategy_planner import StrategyPlanner, match_company_report
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_intent_analyzer import MockJsonClient


def _intent_json(**overrides: object) -> str:
    payload = {
        "primary_action": "fetch_data",
        "subject_area": "general",
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
    payload.update(overrides)
    return json.dumps(payload)


async def _analyze(query: str, llm_payload: str) -> Intent:
    analyzer = IntentAnalyzer(client=MockJsonClient(llm_payload))
    return await analyzer.analyze(query, _make_context_stack())


@pytest.mark.asyncio
async def test_r1_01_employee_count_not_out_of_scope() -> None:
    """how many employees → in scope (HR read via query_odoo)."""
    intent = await _analyze(
        "how many employees do we have",
        _intent_json(subject_area="hr", specific_intent="Count employees"),
    )
    assert intent.out_of_scope is False
    assert CAPABILITY_MANIFEST.can_do("universal.odoo_read")
    assert CAPABILITY_MANIFEST.can_do("hr.employees")
    assert IntelligentQueryHandler._requires_deep_think(
        "how many employees do we have",
        intent,
    )


@pytest.mark.asyncio
async def test_r1_02_recent_purchase_orders_not_out_of_scope() -> None:
    """list recent purchase orders → in scope."""
    intent = await _analyze(
        "list recent purchase orders",
        _intent_json(subject_area="inventory", specific_intent="List POs"),
    )
    assert intent.out_of_scope is False
    assert CAPABILITY_MANIFEST.can_do("purchase.read")


@pytest.mark.asyncio
async def test_r1_03_stock_levels_not_out_of_scope() -> None:
    """stock levels → in scope."""
    intent = await _analyze(
        "stock levels",
        _intent_json(subject_area="inventory", specific_intent="Stock on hand"),
    )
    assert intent.out_of_scope is False
    assert CAPABILITY_MANIFEST.can_do("inventory.stock")


@pytest.mark.asyncio
async def test_r1_04_create_invoice_still_refused() -> None:
    """create an invoice → write operation, still out of scope."""
    intent = await _analyze(
        "create an invoice",
        _intent_json(
            primary_action="other",
            subject_area="financial",
            specific_intent="Create invoice",
            out_of_scope=False,
        ),
    )
    assert intent.out_of_scope is True
    reason = (intent.out_of_scope_reason or "").lower()
    assert "read" in reason or "create" in reason or "modify" in reason


@pytest.mark.asyncio
async def test_r1_05_weather_still_out_of_scope() -> None:
    """what's the weather → non-ERP, still out of scope."""
    intent = await _analyze(
        "what's the weather",
        _intent_json(
            primary_action="ask_question",
            subject_area="general",
            specific_intent="Weather forecast",
            out_of_scope=False,
        ),
    )
    assert intent.out_of_scope is True
    reason = (intent.out_of_scope_reason or "").lower()
    assert "erp" in reason or "odoo" in reason


def test_r1_06_villa_34_expense_uses_specialized_tool() -> None:
    """Villa 34 expense → get_project_expense_summary (regression)."""
    from gateway.core.intent_analyzer import EntityReference

    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="Villa 34 expense",
        entities=[EntityReference(type="project", value="Villa 34", confidence=0.9)],
    )
    context = _make_context_stack()
    context.working_memory.session_facts["confirmed_entities"] = {
        "project": {"id": 15157, "name": "Villa Maintenance No. 34"},
    }
    selected = select_project_expense_tool("Villa 34 expense", intent, context)
    assert selected is not None
    tool_name, _tool_input = selected
    assert tool_name == "get_project_expense_summary"


def test_r1_07_pnl_uses_financial_report_tool() -> None:
    """show me P&L this year → get_financial_report (regression)."""
    matched = match_company_report("show me P&L this year")
    assert matched is not None
    tool_name, report_type = matched
    assert tool_name == "get_financial_report"
    assert report_type == "pandl"


@pytest.mark.asyncio
async def test_r1_08_managers_not_out_of_scope() -> None:
    intent = await _analyze(
        "who are the managers in the company",
        _intent_json(subject_area="hr", specific_intent="List managers"),
    )
    assert intent.out_of_scope is False


@pytest.mark.asyncio
async def test_r1_09_fleet_not_out_of_scope() -> None:
    intent = await _analyze(
        "fleet vehicles",
        _intent_json(subject_area="general", specific_intent="List fleet vehicles"),
    )
    assert intent.out_of_scope is False
    assert CAPABILITY_MANIFEST.can_do("fleet.read")


@pytest.mark.asyncio
async def test_r1_10_active_contracts_not_out_of_scope() -> None:
    intent = await _analyze(
        "active contracts",
        _intent_json(subject_area="hr", specific_intent="List active contracts"),
    )
    assert intent.out_of_scope is False


@pytest.mark.asyncio
async def test_r1_11_fsm_orders_not_out_of_scope() -> None:
    intent = await _analyze(
        "FSM orders this month",
        _intent_json(subject_area="general", specific_intent="FSM orders this month"),
    )
    assert intent.out_of_scope is False
    assert CAPABILITY_MANIFEST.can_do("fsm.read")


@pytest.mark.asyncio
async def test_r1_12_arabic_employee_count_not_out_of_scope() -> None:
    intent = await _analyze(
        "كم عدد الموظفين",
        _intent_json(subject_area="hr", specific_intent="Employee count in Arabic"),
    )
    assert intent.out_of_scope is False
    assert IntelligentQueryHandler._requires_deep_think("كم عدد الموظفين", intent)


def test_r1_strategy_planner_routes_hr_to_query_odoo() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="hr",
        specific_intent="how many employees",
        entities=[],
    )
    tool, payload = StrategyPlanner._resolve_universal_read_tool(intent)
    assert tool == "query_odoo"
    assert payload["model"] == "hr.employee"


def test_r1_strategy_planner_routes_purchase_orders_to_query_odoo() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="other",
        specific_intent="retrieve_recent_purchase_orders",
        entities=[],
    )
    tool, payload = StrategyPlanner._resolve_universal_read_tool(intent)
    assert tool == "query_odoo"
    assert payload["model"] == "purchase.order"


def test_r1_strategy_planner_routes_fleet_to_query_odoo() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="general",
        specific_intent="fleet vehicles",
        entities=[],
    )
    tool, payload = StrategyPlanner._resolve_universal_read_tool(intent)
    assert tool == "query_odoo"
    assert payload["model"] == "fleet.vehicle"


@pytest.mark.asyncio
async def test_r1_live_open_gates_data_queries() -> None:
    """Live Odoo: universal read returns data (or honest Odoo error), not gate refusal."""
    import os

    if not os.environ.get("ODOO_V14_URL"):
        pytest.skip("Odoo env not configured")

    from gateway.odoo_adapter_pool import get_shared_odoo_adapter
    from gateway.tools.universal_odoo import build_universal_context, execute_query_odoo

    adapter = get_shared_odoo_adapter()
    ctx = build_universal_context()

    result = await execute_query_odoo(
        adapter,
        {
            "model": "hr.employee",
            "domain": [["active", "=", True]],
            "fields": ["name"],
            "limit": 3,
        },
        ctx,
    )
    assert result["status"] == "success"
    assert result["record_count"] >= 1

