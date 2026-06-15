"""Tests for deterministic menu preflight."""

from gateway.agent.menu_preflight import (
    detect_financial_report_type,
    is_financial_category_pick,
    run_menu_preflight,
)
from gateway.agent.session_entities import clear_entities, get_entities


def test_financial_category_pick() -> None:
    assert is_financial_category_pick("Financial Reports")
    assert is_financial_category_pick("Hi — 📊 Financial Reports")
    assert detect_financial_report_type("Trial Balance") == "trial_balance"
    assert detect_financial_report_type("Profit & Loss Statement") == "pl"


def test_menu_preflight_shows_report_submenu() -> None:
    clear_entities("menu-fin")
    result = run_menu_preflight(
        "Financial Reports",
        session_id="menu-fin",
        skip_clarification=True,
    )
    assert result is not None
    assert result.ui_blocks[0]["type"] == "pill_select"
    assert "Trial Balance" in str(result.ui_blocks[0])
    assert get_entities("menu-fin")["intent"] == "financial_reports"
    clear_entities("menu-fin")


def test_menu_preflight_shows_date_after_report_type() -> None:
    clear_entities("menu-fin2")
    update_entities = __import__(
        "gateway.agent.session_entities",
        fromlist=["update_entities"],
    ).update_entities
    update_entities("menu-fin2", intent="financial_reports")
    result = run_menu_preflight(
        "Trial Balance",
        session_id="menu-fin2",
        skip_clarification=True,
    )
    assert result is not None
    assert result.ui_blocks[0]["type"] == "date_quick"
    assert get_entities("menu-fin2")["financial_report_type"] == "trial_balance"
    clear_entities("menu-fin2")
