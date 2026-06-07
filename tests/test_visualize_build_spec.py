"""Tests for Layer 2 build spec mapping."""

from visualize.build_spec import (
    map_recommendation_layout,
    recommendation_to_pdf_sections,
)
from visualize.direct_build import execute_direct_build
from visualize.sessions import create_session


def test_map_recommendation_layout():
    assert map_recommendation_layout("executive_summary") == "executive"
    assert map_recommendation_layout("detailed_analytical") == "detailed"


def test_recommendation_to_pdf_sections_includes_table():
    inspection = {
        "report_subject": "P&L May 2026",
        "date_range": "May 2026",
        "row_count": 2,
        "metrics": [{"label": "Net profit", "value": 100, "unit": "AED"}],
    }
    analysis = {
        "findings": [{"text": "Revenue grew 5%", "color": "green", "icon": "up"}],
    }
    recommendation = {
        "sections": [
            {"type": "cover", "order": 1, "label": "Cover", "config": {}},
            {"type": "kpi_dashboard", "order": 3, "label": "KPIs", "config": {}},
            {"type": "data_table", "order": 6, "label": "Table", "config": {}},
        ],
    }
    items = [{
        "visualization": {
            "visual_type": "DATA_TABLE",
            "data": {
                "headers": ["Account", "Amount"],
                "rows": [],
                "all_rows": [{"Account": "Sales", "Amount": 100}],
            },
        },
    }]
    sections = recommendation_to_pdf_sections(
        inspection=inspection,
        analysis=analysis,
        recommendation=recommendation,
        dropped_items=items,
        title="P&L",
    )
    types = [s["type"] for s in sections]
    assert "cover" in types
    assert "kpi_grid" in types
    assert "table" in types
    table = next(s for s in sections if s["type"] == "table")
    assert len(table["data"]["rows"]) == 1


def test_execute_direct_build_pdf(monkeypatch):
    session = create_session(user_id=1, items=[{
        "question": "P&L",
        "visualization": {
            "visual_type": "DATA_TABLE",
            "data": {
                "headers": ["A", "B"],
                "all_rows": [{"A": "x", "B": 1}],
            },
        },
    }])

    def fake_pdf(spec, session_id=None):
        return {"pdf_url": "/reports/test.pdf", "format": "pdf"}

    def fake_brain(items):
        return {
            "inspection": {"report_subject": "P&L", "row_count": 1, "metrics": []},
            "analysis": {"findings": []},
            "recommendation": {
                "format": "pdf",
                "theme": "elegant_gold",
                "layout": "executive_summary",
                "sections": [{"type": "cover", "order": 1, "config": {}}],
                "section_labels": ["Cover"],
            },
        }

    monkeypatch.setattr("visualize.direct_build.run_full_brain", fake_brain)
    monkeypatch.setattr("visualize.direct_build.generate_visualize_pdf", fake_pdf)

    result = execute_direct_build(session, output_format="pdf")
    assert result.get("pdf_url") == "/reports/test.pdf"
