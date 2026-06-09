"""Phase 10 edge cases — empty results, concurrent same query, Arabic."""

from __future__ import annotations

import asyncio

import pytest

from gateway.core.entity_gate import ConfirmedEntityRef
from gateway.core.failure_handler import contains_fabricated_excuse
from gateway.core.intent_analyzer import EntityReference, Intent
from tests.core.test_entity_resolver import PROJECT_CATALOG
from tests.integration.test_intelligent_handler import (
    ZAYIDIA_CATALOG,
    _handler,
    _stack_for_user,
    _super_admin,
)


@pytest.mark.asyncio
async def test_empty_entity_query_shows_not_found_not_fabrication() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="show me XYZNONEXISTENT999 costs",
        entities=[EntityReference(type="project", value="XYZNONEXISTENT999", confidence=0.9)],
    )
    response = await _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=[],
    ).handle("show me XYZNONEXISTENT999 costs", _super_admin(), adapter=object())

    assert response.awaiting_clarification or response.failure_mode == "no_data_found"
    assert not contains_fabricated_excuse(response.text)
    assert "couldn't find" in response.text.lower() or response.failure_mode == "no_data_found"


@pytest.mark.asyncio
async def test_concurrent_same_zayidia_query_all_get_confirm() -> None:
    intent = Intent(
        primary_action="other",
        subject_area="general",
        specific_intent="show me Zayidia Boys School costs",
    )
    handler = _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=[PROJECT_CATALOG[3]],
    )
    user = _super_admin()
    adapter = object()
    message = "show me Zayidia Boys School costs"

    results = await asyncio.gather(
        *[handler.handle(message, user, adapter=adapter) for _ in range(5)],
    )
    for response in results:
        assert response.awaiting_clarification
        assert response.clarification is not None
        assert "hatta hospital" not in response.text.lower()
        assert any(
            "zayidia" in str(option.get("label", "")).lower()
            for option in (response.clarification.get("options") or [])
        )


@pytest.mark.asyncio
async def test_arabic_query_handler_does_not_fabricate_errors() -> None:
    from tests.integration.test_intelligent_handler import ArabicSynthesizer, _build_pl_strategy
    from tests.core.test_execution_orchestrator import MockToolExecutor
    from gateway.core.strategy_planner import ExecutionStep, Strategy

    intent = Intent(
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="أرني تقرير الأرباح والخسائر لهذا الشهر",
    )
    response = await _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        synthesizer=ArabicSynthesizer(),
    ).handle(
        "أرني تقرير الأرباح والخسائر لهذا الشهر",
        _super_admin(),
        adapter=object(),
        language="ar",
        strategy_override=_build_pl_strategy(),
        executor=MockToolExecutor(
            responses={
                ("get_financial_report", 1): {
                    "rows": [{"label": "Net Profit", "amount": 40000}],
                    "net_profit": 40000,
                },
            },
        ),
    )
    assert not contains_fabricated_excuse(response.text)


@pytest.mark.asyncio
async def test_confirmed_entity_turn_two_no_regression() -> None:
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="show me Zayidia Boys School costs",
    )
    handler = _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=ZAYIDIA_CATALOG,
    )
    confirmed = [
        ConfirmedEntityRef(type="project", id=201, name="Zayidia Boys School Renovation"),
    ]
    from tests.core.test_execution_orchestrator import MockToolExecutor

    second = await handler.handle(
        "show me Zayidia Boys School costs",
        _super_admin(),
        adapter=object(),
        confirmed_entities=confirmed,
        executor=MockToolExecutor(
            responses={
                ("get_project_expense_summary", 1): {
                    "status": "success",
                    "project_id": 201,
                    "project_name": "Zayidia Boys School Renovation",
                    "currency": "AED",
                    "wo_amount": 200000,
                    "total_expenses": 125000,
                    "spend_percent_of_wo": 62.5,
                    "top_expenses": [],
                    "expense_lines": [],
                    "variance_amount": 75000,
                    "is_over_budget": False,
                    "_source": "project_expense_summary_mobile",
                },
            },
        ),
    )
    assert not second.awaiting_clarification
    assert "get_project_expense_summary" in second.tools_called
