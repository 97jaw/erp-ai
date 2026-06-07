from __future__ import annotations

from pathlib import Path

import pytest

from gateway.pdf_reports import REPORTS_DIR
from visualize.pdf_generator import generate_visualize_pdf
from visualize.themes import VISUALIZE_THEMES


@pytest.mark.parametrize("theme_id", list(VISUALIZE_THEMES.keys()))
def test_generate_visualize_pdf_each_theme(theme_id: str) -> None:
    result = generate_visualize_pdf({
        "title": f"Theme Test — {theme_id}",
        "subtitle": "Visualize Phase 3",
        "theme": theme_id,
        "layout": "executive",
        "sections": [
            {
                "type": "kpi_grid",
                "title": "Key Metrics",
                "data": {
                    "kpis": [
                        {"label": "Revenue", "value": 11851889.97, "unit": "AED", "trend": "up"},
                        {"label": "Profit", "value": 8163749.36, "unit": "AED", "trend": "positive"},
                    ],
                },
            },
            {
                "type": "table",
                "title": "Summary",
                "data": {
                    "headers": ["Metric", "Value"],
                    "rows": [["Revenue", "11.85M"], ["Expenses", "3.69M"]],
                },
            },
        ],
    })

    assert "error" not in result, result.get("message")
    assert result["theme"] == theme_id
    assert result["layout"] == "executive"
    assert result["size_bytes"] > 1200

    pdf_path = REPORTS_DIR / Path(result["pdf_url"]).name
    assert pdf_path.exists()


def test_list_theme_and_layout_catalogs() -> None:
    from visualize.layouts import list_layouts
    from visualize.themes import list_themes

    assert len(list_themes()) == 4
    assert len(list_layouts()) == 4
