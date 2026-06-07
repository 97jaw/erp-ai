"""Layer 1 brain tests — perceive, understand, opinionate (10+ data types)."""

from __future__ import annotations

import pytest

from visualize.brain import run_full_brain, run_inspection, run_pattern_analysis, run_recommendation
from visualize.perceive import DataInspector
from visualize.understand import PatternAnalyzer


def _item(viz: dict, question: str = "", text: str = "") -> dict:
    return {"question": question, "text": text, "visualization": viz}


# --- Fixtures: 10+ business data types ---

PANDL_VIZ = {
    "visual_type": "FINANCIAL_REPORT",
    "label": "Profit and Loss",
    "date_from": "2026-01-01",
    "date_to": "2026-04-30",
    "kpis": {
        "total_income": {"value": 5_200_000, "label": "Revenue"},
        "total_expense": {"value": 4_100_000, "label": "Expenses"},
        "net_profit": {"value": 1_100_000, "label": "Net Profit"},
        "margin": {"value": 21.2, "label": "Margin %"},
    },
    "data": {
        "rows": [
            {"name": "Wages", "amount": 1_200_000},
            {"name": "Materials", "amount": 900_000},
            {"name": "Subcontractors", "amount": 750_000},
            {"name": "Equipment", "amount": 400_000},
            {"name": "Overheads", "amount": 350_000},
            {"name": "Insurance", "amount": 200_000},
            {"name": "Fuel", "amount": 150_000},
            {"name": "Misc", "amount": 150_000},
        ],
        "monthly_data": [
            {"period": "Jan 2026", "value": 1_000_000},
            {"period": "Feb 2026", "value": 1_050_000},
            {"period": "Mar 2026", "value": 1_150_000},
            {"period": "Apr 2026", "value": 1_200_000},
        ],
    },
}

BALANCE_SHEET_VIZ = {
    "visual_type": "DATA_TABLE",
    "label": "Balance Sheet Q1",
    "data": {
        "rows": [
            {"account_name": "Cash", "balance": 500_000},
            {"account_name": "Receivables", "balance": 1_200_000},
            {"account_name": "Payables", "balance": -400_000},
        ],
    },
}

CASH_FLOW_VIZ = {
    "visual_type": "DATA_TABLE",
    "label": "Cash Flow Statement",
    "data": {"rows": [{"category": "Operating", "amount": 300_000}] * 12},
}

TRIAL_BALANCE_VIZ = {
    "visual_type": "DATA_TABLE",
    "label": "Trial Balance",
    "total_records": 85,
    "data": {"rows": [{"account": f"Acc {i}", "debit": i * 1000} for i in range(85)]},
}

AGEING_VIZ = {
    "visual_type": "GROUPED_TABLE",
    "label": "Partner Ageing",
    "data": {
        "group_by": ["partner"],
        "groups": [
            {"name": "Client A", "rows": [{"amount": 50_000}, {"amount": 30_000}]},
            {"name": "Client B", "rows": [{"amount": 80_000}]},
        ],
    },
}

LEDGER_VIZ = {
    "visual_type": "DATA_TABLE",
    "label": "General Ledger",
    "data": {"rows": [{"entry": i, "amount": i * 500} for i in range(30)]},
}

PROJECT_VIZ = {
    "visual_type": "DATA_TABLE",
    "label": "Project Costs — Tower A",
    "data": {
        "rows": [
            {"project": "Tower A", "budget": 2_000_000, "actual": 2_280_000},
            {"project": "Tower B", "budget": 1_500_000, "actual": 1_420_000},
        ],
        "budget_variance_pct": 14,
    },
}

EXPENSE_VIZ = {
    "visual_type": "GROUPED_TABLE",
    "label": "Expense Breakdown",
    "data": {
        "group_by": ["category", "month"],
        "groups": [{"name": f"Cat {i}", "rows": [{"amount": 10_000 * (i + 1)}]} for i in range(8)],
    },
}

REVENUE_VIZ = {
    "visual_type": "BAR_CHART",
    "label": "Sales Revenue by Region",
    "data": {
        "labels": ["Dubai", "Abu Dhabi", "Sharjah"],
        "values": [2_000_000, 1_500_000, 800_000],
    },
}

CLIENT_VIZ = {
    "visual_type": "DATA_TABLE",
    "label": "Client Portfolio",
    "data": {"rows": [{"client": f"C{i}", "revenue": 100_000 * i} for i in range(1, 15)]},
}

VENDOR_VIZ = {
    "visual_type": "DATA_TABLE",
    "label": "Vendor Analysis",
    "data": {"rows": [{"vendor": f"V{i}", "spend": 50_000 * i} for i in range(1, 10)]},
}

KPI_VIZ = {
    "visual_type": "KPI_CARD",
    "label": "Executive KPIs",
    "value": 4_200_000,
    "kpis": {
        "revenue": {"value": 4_200_000, "trend": "up", "change_pct": 12},
        "margin_pct": {"value": 8.5, "trend": "down", "change_pct": -3},
    },
}

LINE_CHART_VIZ = {
    "visual_type": "LINE_CHART",
    "label": "Monthly Trend",
    "data": {
        "labels": ["Jan", "Feb", "Mar", "Apr"],
        "values": [100, 120, 115, 140],
    },
}

ALL_FIXTURES = [
    ("financial_pandl", PANDL_VIZ, "Show P&L"),
    ("financial_balance_sheet", BALANCE_SHEET_VIZ, "Balance sheet"),
    ("financial_cash_flow", CASH_FLOW_VIZ, "Cash flow"),
    ("financial_trial_balance", TRIAL_BALANCE_VIZ, "Trial balance"),
    ("partner_ageing", AGEING_VIZ, "Ageing"),
    ("general_ledger", LEDGER_VIZ, "Ledger"),
    ("project_costs", PROJECT_VIZ, "Projects"),
    ("expense_breakdown", EXPENSE_VIZ, "Expenses"),
    ("revenue_analysis", REVENUE_VIZ, "Revenue"),
    ("client_portfolio", CLIENT_VIZ, "Clients"),
    ("vendor_analysis", VENDOR_VIZ, "Vendors"),
    ("kpi_dashboard", KPI_VIZ, "KPIs"),
    ("chart_analysis", LINE_CHART_VIZ, "Trend"),
]


@pytest.mark.parametrize("expected_type,viz,question", ALL_FIXTURES)
def test_detect_data_type(expected_type: str, viz: dict, question: str) -> None:
    inspector = DataInspector()
    result = inspector.inspect_single(_item(viz, question=question))
    assert result["primary_data_type"] == expected_type
    assert result["display_type"]
    assert result["item_count"] == 1


def test_inspect_empty_items() -> None:
    result = run_inspection([])
    assert result["item_count"] == 0
    assert result["primary_data_type"] == "general_data"


def test_inspect_multiple_items() -> None:
    items = [_item(PANDL_VIZ, "P&L"), _item(REVENUE_VIZ, "Revenue")]
    result = run_inspection(items)
    assert result["item_count"] == 2
    assert result["primary_data_type"] == "mixed_bundle"
    assert result["row_count"] > 0


def test_pandl_inspection_fields() -> None:
    ins = run_inspection([_item(PANDL_VIZ, question="P&L this month")])
    assert ins["has_time_series"] is True
    assert ins["row_count"] == 8
    assert ins["metric_count"] >= 3
    assert ins["date_range"] is not None
    assert ins["currency"] == "AED"


def test_pattern_analysis_trends() -> None:
    items = [_item(PANDL_VIZ)]
    ins = run_inspection(items)
    analysis = run_pattern_analysis(items, ins)
    assert "findings" in analysis
    assert isinstance(analysis["trends"], list)
    if analysis["trends"]:
        assert "insight" in analysis["trends"][0]


def test_pattern_concentration() -> None:
    viz = {
        "visual_type": "DATA_TABLE",
        "label": "Expenses",
        "data": {
            "rows": [
                {"name": "A", "amount": 500_000},
                {"name": "B", "amount": 300_000},
                {"name": "C", "amount": 100_000},
                {"name": "D", "amount": 50_000},
                {"name": "E", "amount": 30_000},
                {"name": "F", "amount": 20_000},
            ],
        },
    }
    ins = run_inspection([_item(viz)])
    analysis = run_pattern_analysis([_item(viz)], ins)
    assert analysis["concentrations"] or analysis["findings"]


def test_business_threshold_low_margin() -> None:
    viz = {
        "visual_type": "FINANCIAL_REPORT",
        "label": "P&L",
        "kpis": {"margin": {"value": 5}},
        "data": {"rows": []},
    }
    ins = run_inspection([_item(viz)])
    analysis = run_pattern_analysis([_item(viz)], ins)
    thresholds = analysis.get("thresholds", [])
    assert any(t.get("metric") == "margin" for t in thresholds)


def test_recommendation_structure() -> None:
    items = [_item(PANDL_VIZ, question="P&L")]
    ins = run_inspection(items)
    analysis = run_pattern_analysis(items, ins)
    rec = run_recommendation(ins, analysis)
    assert rec["format"] in ("pdf", "excel", "ppt")
    assert rec["layout"]
    assert rec["theme"]
    assert rec["section_labels"]
    assert rec["estimated_pages"] >= 2
    assert len(rec["alternatives"]) >= 1


def test_full_brain_pipeline() -> None:
    result = run_full_brain([_item(PANDL_VIZ, question="P&L Q1")])
    assert "inspection" in result
    assert "analysis" in result
    assert "recommendation" in result
    assert result["analysis"]["findings"] is not None
    assert result["recommendation"]["format"]


def test_excel_recommendation_for_large_dataset() -> None:
    rows = [{"id": i, "amount": i * 100} for i in range(120)]
    viz = {
        "visual_type": "DATA_TABLE",
        "label": "Large export",
        "data": {"rows": rows},
    }
    items = [_item(viz)]
    ins = run_inspection(items)
    analysis = run_pattern_analysis(items, ins)
    rec = run_recommendation(ins, analysis)
    assert rec["format"] == "excel"


def test_build_inspection_lines_helper() -> None:
    from visualize.perceive import DataInspector

    ins = DataInspector().inspect_single(_item(PANDL_VIZ, question="P&L"))
    assert ins["display_type"] == "P&L Statement"
