from __future__ import annotations

from gateway.suggestion_pool import (
    SuggestionContext,
    build_post_response_suggestions,
    detect_suggestion_context,
    pick_diverse_suggestions,
    rotate_post_response_suggestions,
)


def test_detect_pandl_context_from_visualization() -> None:
    context = detect_suggestion_context(
        ["get_financial_report"],
        {"visual_type": "FINANCIAL_REPORT", "label": "Profit & Loss", "kpis": {}},
    )
    assert context == SuggestionContext.PANDL


def test_build_post_response_suggestions_returns_three() -> None:
    suggestions, meta = build_post_response_suggestions(
        model_suggestions=[],
        tool_names=["get_financial_report"],
        tool_results=[{"kpis": {"net_profit": 100, "margin": 20}}],
        visualization={"visual_type": "FINANCIAL_REPORT", "kpis": {"net_profit": 100, "margin": 20}},
        language="en",
        session_id="sess-1",
    )
    assert len(suggestions) == 3
    assert meta is not None
    assert meta.get("token")
    assert meta.get("has_more") is True


def test_rotate_returns_fresh_batch() -> None:
    _, meta = build_post_response_suggestions(
        model_suggestions=[],
        tool_names=["get_financial_report"],
        tool_results=[],
        visualization={"visual_type": "FINANCIAL_REPORT", "kpis": {"net_profit": 1, "margin": 1}},
        language="en",
        session_id="sess-2",
    )
    assert meta
    first = rotate_post_response_suggestions(meta["token"])
    second = rotate_post_response_suggestions(meta["token"])
    assert len(first[0]) == 3
    assert first[0]
    assert second[0]
    assert set(first[0]) != set(second[0]) or not second[1]


def test_pick_diverse_suggestions_mixes_categories() -> None:
    pool = [
        "Break down expenses by account",
        "Compare with last month",
        "Generate executive PDF report",
        "Why is margin lower?",
        "Show top 5 cost categories",
    ]
    picked = pick_diverse_suggestions(pool, 3)
    assert len(picked) == 3
    assert len(set(picked)) == 3
