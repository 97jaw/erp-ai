"""Tests for gateway.core.smart_suggestions."""

from __future__ import annotations

from gateway.core.intent_analyzer import Intent
from gateway.core.proactive_intelligence import PredictedAction
from gateway.core.result_synthesizer import SynthesizedResult
from gateway.core.smart_suggestions import SmartSuggestionsGenerator, remember_shown_suggestions
from tests.core.test_context_stack import _make_context_stack


def _compare_intent() -> Intent:
    return Intent(
        primary_action="compare",
        subject_area="financial",
        specific_intent="Compare revenue Q1 2026 vs Q1 2025 by top clients",
        expected_output="table",
    )


def _revenue_table() -> SynthesizedResult:
    return SynthesizedResult(
        text="National Guard led revenue growth in Q1 2026.",
        visualization={
            "visual_type": "DATA_TABLE",
            "label": "Revenue comparison",
            "data": {
                "headers": ["Client", "Revenue (AED)"],
                "rows": [["National Guard", 1_200_000], ["Client B", 800_000]],
            },
        },
    )


def test_generate_returns_three_diverse_specific_suggestions() -> None:
    generator = SmartSuggestionsGenerator()
    suggestions = generator.generate(
        _revenue_table(),
        _compare_intent(),
        _make_context_stack(),
        tool_names=["group_and_aggregate"],
        tool_results=[{"groups": [{"partner_id": [1, "National Guard"], "amount_total:sum": 1_200_000}]}],
    )

    assert len(suggestions) == 3
    assert any("National Guard" in item for item in suggestions)
    categories = {item.split()[0].lower() for item in suggestions}
    assert len(suggestions) == len(set(suggestions))
    assert not categories.issubset({"compare"})


def test_predicted_actions_are_prioritized() -> None:
    generator = SmartSuggestionsGenerator()
    predicted = [
        PredictedAction(
            action="compare_expenses",
            likelihood=0.9,
            pre_computable=True,
            suggestion_text="Compare project expenses for National Guard",
            query_message="Compare project expenses for National Guard last quarter",
        ),
    ]
    suggestions = generator.generate(
        _revenue_table(),
        _compare_intent(),
        _make_context_stack(),
        tool_names=["group_and_aggregate"],
        tool_results=[],
        predicted_actions=predicted,
    )
    assert suggestions[0] == "Compare project expenses for National Guard"


def test_remember_shown_suggestions_avoids_repeats() -> None:
    context = _make_context_stack()
    remember_shown_suggestions(context, ["Show revenue by client for last quarter"])
    generator = SmartSuggestionsGenerator()
    suggestions = generator.generate(
        SynthesizedResult(text="No table"),
        Intent(primary_action="fetch_data", subject_area="financial", specific_intent="Revenue"),
        context,
        tool_names=[],
        tool_results=[],
    )
    assert "Show revenue by client for last quarter" not in suggestions
