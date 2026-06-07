"""Cost category reports must keep BAR_CHART after quality polish (dict-shaped rows)."""
from __future__ import annotations

from gateway.quality_response import polish_agent_response, polish_visualization
from gateway.visualization_builder import _cost_categories_visual, is_renderable_visualization


def test_cost_categories_bar_chart_survives_polish() -> None:
    tool_result = {
        "project_name": "National Guard Command",
        "total_cost": 36_000_000,
        "categories": [
            {"category": "LPO", "total": 19_600_000, "percentage": 54.5},
            {"category": "Invoices", "total": 12_500_000, "percentage": 34.7},
            {"category": "Staff", "total": 1_600_000, "percentage": 4.4},
            {"category": "Labor", "total": 1_200_000, "percentage": 3.3},
            {"category": "Materials", "total": 1_100_000, "percentage": 3.1},
        ],
    }
    visual = _cost_categories_visual(tool_result)
    assert visual is not None
    assert visual["visual_type"] == "BAR_CHART"

    polished = polish_visualization(visual, {"revenue": False, "chart": True})
    assert is_renderable_visualization(polished)
    assert len(polished["data"]["rows"]) == 5

    text, final_visual = polish_agent_response(
        "what is cost distribution of project national guard? need category wise amount and graphics",
        "The National Guard project shows a total cost of AED 36.0M.",
        None,
        ["get_project_cost_categories"],
        [tool_result],
        "en",
    )
    assert final_visual is not None
    assert final_visual["visual_type"] == "BAR_CHART"
    assert text.strip()
