from __future__ import annotations

from gateway.progressive_disclosure import apply_progressive_disclosure, detect_disclosure_level
from gateway.quality_response import polish_agent_response


def test_detect_disclosure_level_defaults_to_summary() -> None:
    assert detect_disclosure_level("show profit and loss") == "summary"
    assert detect_disclosure_level("show detailed account breakdown") == "standard"
    assert detect_disclosure_level("load all records") == "full"


def test_financial_report_summary_hides_rows_and_sets_expand_metadata() -> None:
    tool_result = {
        "report_name": "Profit & Loss",
        "date_from": "2026-01-01",
        "date_to": "2026-03-31",
        "kpis": {
            "total_income": 1000.0,
            "total_expense": 400.0,
            "net_profit": 600.0,
            "margin": 60.0,
        },
        "report_lines": [
            {"name": "Income", "balance": -1000.0, "debit": 0.0, "credit": 1000.0, "level": 1},
            {"name": "Sales", "balance": -1000.0, "debit": 0.0, "credit": 1000.0, "level": 2},
            {"name": "Rent", "balance": 400.0, "debit": 400.0, "credit": 0.0, "level": 2},
        ],
    }
    visual = {
        "visual_type": "FINANCIAL_REPORT",
        "label": "Profit & Loss",
        "kpis": tool_result["kpis"],
    }
    enriched = apply_progressive_disclosure(visual, "show profit and loss", [tool_result])
    assert enriched is not None
    assert enriched["level"] == "summary"
    assert enriched["can_expand"] is True
    assert enriched.get("query_id")
    assert enriched["total_records"] == 2
    assert enriched["data"]["detail_table"]["rows"]
    assert enriched["data"]["summary_chart"]["visual_type"] == "BAR_CHART"
    assert enriched["data"].get("rows") in (None, [])


def test_financial_report_standard_shows_first_page() -> None:
    rows = [
        {"name": f"Account {index}", "balance": float(index + 1), "debit": 0.0, "credit": 0.0, "level": 2}
        for index in range(30)
    ]
    tool_result = {
        "kpis": {
            "total_income": 1000.0,
            "total_expense": 400.0,
            "net_profit": 600.0,
            "margin": 60.0,
        },
        "report_lines": rows,
    }
    visual = {"visual_type": "FINANCIAL_REPORT", "label": "P&L", "kpis": tool_result["kpis"]}
    enriched = apply_progressive_disclosure(visual, "show account details", [tool_result])
    assert enriched["level"] == "standard"
    assert len(enriched["data"]["rows"]) == 20
    assert enriched["shown_records"] == 20
    assert enriched["total_records"] == 30


def test_polish_agent_response_applies_progressive_disclosure() -> None:
    tool_result = {
        "kpis": {
            "total_income": 500.0,
            "total_expense": 200.0,
            "net_profit": 300.0,
            "margin": 60.0,
        },
        "report_lines": [
            {"name": "Income", "balance": -500.0, "debit": 0.0, "credit": 500.0, "level": 1},
            {"name": "Sales", "balance": -500.0, "debit": 0.0, "credit": 500.0, "level": 2},
        ],
    }
    _, visual = polish_agent_response(
        "profit and loss",
        "",
        None,
        ["get_financial_report"],
        [tool_result],
        "en",
    )
    assert visual is not None
    assert visual.get("level") == "summary"
    assert visual.get("can_expand") is True
