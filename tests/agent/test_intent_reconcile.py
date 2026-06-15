"""Tests for stale financial intent reconciliation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.agent.financial_fast_path import try_financial_fast_path
from gateway.agent.intent_reconcile import (
    is_non_financial_topic,
    message_continues_financial_flow,
    reconcile_session_intent,
)
from gateway.agent.session_entities import clear_entities, get_entities, update_entities


def test_message_continues_financial_flow_for_date_pick() -> None:
    assert message_continues_financial_flow("2026-01-01 to 2026-03-31")
    assert message_continues_financial_flow("show general ledger")


def test_employee_query_is_non_financial_topic() -> None:
    assert is_non_financial_topic("show me employee of ICT")
    assert is_non_financial_topic("how many department do we have?")


def test_reconcile_clears_stale_financial_intent() -> None:
    session_id = "reconcile-gl-hr"
    clear_entities(session_id)
    update_entities(
        session_id,
        intent="financial_reports",
        financial_report_type="general_ledger",
        date_from="2026-01-01",
        date_to="2026-03-31",
    )
    reconcile_session_intent(session_id, "show me employee of ICT")
    entities = get_entities(session_id)
    assert entities.get("intent") == "hr"
    assert "financial_report_type" not in entities


@pytest.mark.asyncio
async def test_financial_fast_path_skips_unrelated_hr_query() -> None:
    session_id = "fastpath-gl-hr"
    clear_entities(session_id)
    update_entities(
        session_id,
        intent="financial_reports",
        financial_report_type="general_ledger",
        date_from="2026-01-01",
        date_to="2026-03-31",
    )
    reconcile_session_intent(session_id, "show me employee of ICT")
    with patch(
        "gateway.agent.tools_registry.execute_tool",
        new_callable=AsyncMock,
    ) as mock_tool:
        result = await try_financial_fast_path(
            session_id=session_id,
            message="show me employee of ICT",
            user=MagicMock(),
            adapter=MagicMock(),
            language="en",
        )
    assert result is None
    mock_tool.assert_not_called()


def test_extract_department_name_from_employee_query() -> None:
    from gateway.agent.simple_query_fast_path import _extract_department_name

    assert _extract_department_name("show me employee of ICT") == "ICT"
    assert _extract_department_name("show me employees of ICT") == "ICT"
