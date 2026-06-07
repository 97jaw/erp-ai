#!/usr/bin/env python3
"""Phase 7 acceptance — proactive intelligence and smart suggestions."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


async def run_offline() -> int:
    from admin.auth.principal import CurrentUser
    from gateway.core.intent_analyzer import Intent
    from gateway.core.precompute_cache import PrecomputeCache
    from gateway.core.proactive_intelligence import ProactiveIntelligence
    from gateway.core.result_synthesizer import SynthesizedResult
    from gateway.core.smart_suggestions import SmartSuggestionsGenerator
    from gateway.core.strategy_fixtures import build_revenue_comparison_strategy
    from gateway.intelligent_handler import IntelligentQueryHandler
    from tests.core.test_context_stack import _make_context_stack
    from tests.core.test_execution_orchestrator import MockToolExecutor
    from tests.core.test_intelligent_handler import FixedIntentAnalyzer, _aggregate_rows, _compare_intent

    failures: list[str] = []

    print("OFFLINE TEST 1: Proactive prediction + scheduling")
    cache = PrecomputeCache()
    proactive = ProactiveIntelligence(client=None, cache=cache)
    synthesized = SynthesizedResult(
        text="National Guard revenue increased in Q1 2026.",
        visualization={
            "visual_type": "DATA_TABLE",
            "data": {"rows": [["National Guard", 1_000_000]]},
        },
    )
    actions = await proactive.anticipate(synthesized, _compare_intent(), _make_context_stack())
    if len(actions.predicted_actions) < 2:
        failures.append("Expected at least 2 predicted actions")

    completed: list[str] = []

    async def _runner(**kwargs) -> None:  # noqa: ANN003
        completed.append(kwargs["cache_key"])
        cache.put_ready(
            kwargs["session_id"],
            kwargs["cache_key"],
            text="Precomputed response",
            visualization={"visual_type": "DATA_TABLE", "data": {"rows": []}},
        )

    proactive.schedule_precompute(actions, session_id="phase7", runner=_runner)
    if not actions.scheduled_cache_keys:
        failures.append("Expected scheduled precompute keys")
    await asyncio.sleep(0.05)

    print("OFFLINE TEST 2: Smart suggestions are specific and diverse")
    generator = SmartSuggestionsGenerator()
    suggestions = generator.generate(
        synthesized,
        _compare_intent(),
        _make_context_stack(),
        tool_names=["group_and_aggregate"],
        tool_results=[{"groups": [{"partner_id": [1, "National Guard"], "amount_total:sum": 1_000_000}]}],
    )
    if len(suggestions) != 3:
        failures.append(f"Expected 3 suggestions, got {len(suggestions)}")
    if not any("National Guard" in item for item in suggestions):
        failures.append("Suggestions should reference entities from the response")
    if len(set(suggestions)) != 3:
        failures.append("Suggestions should be unique")

    print("OFFLINE TEST 3: Handler attaches suggestions and schedules proactive cache")
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("National Guard", 1000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("National Guard", 800)]},
        },
    )
    handler = IntelligentQueryHandler(
        intent_analyzer=FixedIntentAnalyzer(_compare_intent()),
        proactive_layer=proactive,
        precompute_cache=cache,
    )
    user = CurrentUser(
        id=4291,
        file_id="2721",
        name="Super Admin",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"data.all_projects"}),
        department_ids=(1,),
    )
    response = await handler.handle(
        "Compare revenue Q1 2026 vs Q1 2025 by top clients",
        user,
        adapter=object(),
        session_id="phase7",
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )
    if len(response.suggestions) != 3:
        failures.append("Handler should return 3 smart suggestions")
    if not response.proactive_cache_keys:
        failures.append("Handler should schedule proactive cache keys")

    cached = cache.lookup("phase7", response.suggestions[0])
    if cached is None and response.suggestions:
        # Background precompute may still be running; at least pending entry should exist.
        if not cache.list_keys("phase7"):
            failures.append("Expected cache entries after proactive scheduling")

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1

    print("\nPhase 7 offline acceptance PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 7 proactive layer acceptance")
    parser.parse_args()
    return asyncio.run(run_offline())


if __name__ == "__main__":
    raise SystemExit(main())
