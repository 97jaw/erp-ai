"""Tests for P&L multi-step clarification."""

from __future__ import annotations

from gateway.agent.financial_clarification import (
    detect_scope_pick,
    detect_target_move_pick,
    is_arabic_pl_query,
    pl_clarification_complete,
    run_pl_clarification_preflight,
)
from gateway.agent.menu_preflight import detect_financial_report_type
from gateway.agent.session_entities import clear_entities, update_entities


def test_arabic_pl_detection() -> None:
    assert is_arabic_pl_query("أرني الربح والخسارة")
    assert detect_financial_report_type("أرني الربح والخسارة") == "pl"


def test_pl_clarification_asks_date_first() -> None:
    session_id = "pl-clarify-date"
    clear_entities(session_id)
    update_entities(session_id, intent="financial_reports", financial_report_type="pl")
    result = run_pl_clarification_preflight(
        "show profit and loss",
        session_id=session_id,
        language="en",
    )
    assert result is not None
    assert result.ui_blocks[0]["type"] == "date_quick"


def test_pl_clarification_asks_scope_after_date() -> None:
    session_id = "pl-clarify-scope"
    clear_entities(session_id)
    update_entities(
        session_id,
        intent="financial_reports",
        financial_report_type="pl",
        date_from="2026-01-01",
        date_to="2026-03-31",
    )
    result = run_pl_clarification_preflight(
        "2026-01-01 to 2026-03-31",
        session_id=session_id,
        language="en",
    )
    assert result is not None
    assert result.ui_blocks[0]["type"] == "pill_select"
    assert "company" in result.ui_blocks[0]["options"][0]["id"]


def test_scope_and_target_move_picks() -> None:
    assert detect_scope_pick("Company-wide (all projects)") == "company"
    assert detect_scope_pick("Specific project") == "project"
    assert detect_target_move_pick("Posted entries only") == "posted"
    assert detect_target_move_pick("All entries (incl. drafts)") == "all"


def test_pl_clarification_complete_requires_all_fields() -> None:
    session_id = "pl-complete"
    clear_entities(session_id)
    update_entities(
        session_id,
        intent="financial_reports",
        financial_report_type="pl",
        date_from="2026-01-01",
        date_to="2026-03-31",
        financial_scope="company",
        financial_target_move="posted",
    )
    assert pl_clarification_complete(session_id)
