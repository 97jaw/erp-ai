from __future__ import annotations

from gateway.quality_response import polish_agent_response


def test_polish_builds_bar_chart_from_tool_result_without_model_visual() -> None:
    tool_result = {
        "model": "account.move",
        "group_by": ["partner_id"],
        "aggregates": ["amount_total:sum"],
        "groups": [
            {
                "partner_id": [1, "Alpha"],
                "amount_total:sum": 1000,
                "group_label": "Alpha",
            },
            {
                "partner_id": [2, "Beta"],
                "amount_total:sum": 500,
                "group_label": "Beta",
            },
        ],
    }
    text, visual = polish_agent_response(
        "Revenue comparison by client",
        "",
        None,
        ["group_and_aggregate"],
        [tool_result],
        "en",
    )
    assert visual is not None
    assert visual["visual_type"] == "BAR_CHART"
    assert text.strip()
    assert "AED" in text
