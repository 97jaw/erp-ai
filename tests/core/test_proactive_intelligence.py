"""Tests for gateway.core.proactive_intelligence."""

from __future__ import annotations

import asyncio

import pytest

from gateway.core.intent_analyzer import Intent
from gateway.core.precompute_cache import PrecomputeCache
from gateway.core.proactive_intelligence import ProactiveIntelligence
from gateway.core.result_synthesizer import SynthesizedResult
from tests.core.test_context_stack import _make_context_stack


def _revenue_comparison_synthesized() -> SynthesizedResult:
    return SynthesizedResult(
        text="National Guard led revenue growth in Q1 2026.",
        visualization={
            "visual_type": "DATA_TABLE",
            "label": "Revenue comparison",
            "data": {
                "headers": ["Client", "Period 1 Revenue (AED)", "Period 2 Revenue (AED)", "Change (AED)"],
                "rows": [
                    ["National Guard", 1_200_000, 980_000, 220_000],
                    ["Client B", 800_000, 810_000, -10_000],
                ],
            },
        },
    )


def _compare_intent() -> Intent:
    return Intent(
        primary_action="compare",
        subject_area="financial",
        specific_intent="Compare revenue Q1 2026 vs Q1 2025 by top clients",
        expected_output="table",
    )


@pytest.mark.asyncio
async def test_rule_based_prediction_returns_three_actions() -> None:
    layer = ProactiveIntelligence(client=None)
    proactive = await layer.anticipate(
        _revenue_comparison_synthesized(),
        _compare_intent(),
        _make_context_stack(),
    )
    assert len(proactive.predicted_actions) == 3
    assert any("National Guard" in action.suggestion_text for action in proactive.predicted_actions)


@pytest.mark.asyncio
async def test_schedule_precompute_only_for_high_likelihood_actions() -> None:
    cache = PrecomputeCache()
    layer = ProactiveIntelligence(client=None, cache=cache, likelihood_threshold=0.7)
    proactive = await layer.anticipate(
        _revenue_comparison_synthesized(),
        _compare_intent(),
        _make_context_stack(),
    )

    scheduled_keys: list[str] = []

    async def _runner(**kwargs) -> None:  # noqa: ANN003
        scheduled_keys.append(kwargs["cache_key"])

    layer.schedule_precompute(
        proactive,
        session_id="session-proactive",
        runner=_runner,
    )

    await asyncio.sleep(0.05)

    assert len(proactive.scheduled_cache_keys) >= 1
    assert len(scheduled_keys) == len(proactive.scheduled_cache_keys)


@pytest.mark.asyncio
async def test_out_of_scope_returns_empty_predictions() -> None:
    layer = ProactiveIntelligence(client=None)
    intent = Intent(
        primary_action="fetch_data",
        subject_area="hr",
        specific_intent="what is my payslip",
        out_of_scope=True,
    )
    proactive = await layer.anticipate(
        SynthesizedResult(text="Unavailable"),
        intent,
        _make_context_stack(),
    )
    assert proactive.predicted_actions == []
