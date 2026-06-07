#!/usr/bin/env python3
"""Phase 2 acceptance scenarios for intent analysis and strategy planning."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from admin.auth.principal import CurrentUser
from gateway.core.context_stack_builder import ContextStackBuilder
from gateway.core.intent_analyzer import Intent, IntentAnalyzer
from gateway.core.strategy_planner import StrategyPlanner


class Req:
    def __init__(self, message: str) -> None:
        self.message = message
        self.session_id = "phase2-acceptance"


class MockJsonClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self._responses = responses
        self.complete_json = AsyncMock(side_effect=self._complete_json)

    async def _complete_json(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int = 800,
    ) -> str:
        for key, payload in self._responses.items():
            if key.lower() in prompt.lower():
                return payload
        raise RuntimeError(f"No mock response matched prompt: {prompt[:120]}...")


MOCK_INTENT_RESPONSES = {
    "what is my payslip": json.dumps(
        {
            "primary_action": "fetch_data",
            "subject_area": "hr",
            "specific_intent": "Retrieve payslip information",
            "entities": [],
            "implicit_requirements": [],
            "ambiguities": [],
            "expected_output": "summary",
            "urgency": "normal",
            "estimated_complexity": "simple",
            "requires_clarification": False,
            "clarification_question": None,
            "out_of_scope": True,
            "out_of_scope_reason": "hr.payslips is unavailable; use HR portal",
        }
    ),
    "national guard project expenses last month": json.dumps(
        {
            "primary_action": "fetch_data",
            "subject_area": "project",
            "specific_intent": "Show National Guard project expenses for last month",
            "entities": [
                {
                    "type": "project",
                    "value": "National Guard",
                    "confidence": 0.93,
                },
                {
                    "type": "period",
                    "value": "last month",
                    "confidence": 0.9,
                },
            ],
            "implicit_requirements": ["Use last month date range"],
            "ambiguities": [],
            "expected_output": "summary",
            "urgency": "normal",
            "estimated_complexity": "simple",
            "requires_clarification": False,
            "clarification_question": None,
            "out_of_scope": False,
            "out_of_scope_reason": None,
        }
    ),
}

MOCK_STRATEGY_RESPONSE = json.dumps(
    {
        "steps": [
            {
                "step_number": 1,
                "description": "Fetch Q1 revenue by client",
                "tool": "group_and_aggregate",
                "tool_input": {"model": "account.move", "groupby": "partner_id"},
                "depends_on": [],
                "parallel_with": [2],
                "expected_output": "table",
                "fallback_if_fails": "Use search_odoo on posted invoices for Q1",
            },
            {
                "step_number": 2,
                "description": "Fetch Q4 revenue by client",
                "tool": "group_and_aggregate",
                "tool_input": {"model": "account.move", "groupby": "partner_id"},
                "depends_on": [],
                "parallel_with": [1],
                "expected_output": "table",
                "fallback_if_fails": "Use search_odoo on posted invoices for Q4",
            },
            {
                "step_number": 3,
                "description": "Compare top 5 clients across quarters",
                "tool": "compose_report",
                "tool_input": {"report_type": "comparison"},
                "depends_on": [1, 2],
                "parallel_with": [],
                "expected_output": "chart",
                "fallback_if_fails": "Return side-by-side KPI summary",
            },
        ],
        "synthesis_approach": "Rank clients by revenue change from Q1 to Q4",
        "quality_checks": [
            "Top 5 clients identified in both quarters",
            "Revenue values are non-zero where data exists",
        ],
        "estimated_duration_ms": 5000,
    }
)


async def build_context(message: str):
    user = CurrentUser(
        id=4291,
        file_id="2721",
        name="Super Admin User",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"data.all_projects"}),
        department_ids=(1,),
        department_codes=("Finance",),
    )
    return await ContextStackBuilder().build(user, Req(message))


def build_analyzer(live: bool) -> IntentAnalyzer:
    if live:
        return IntentAnalyzer()
    client = MockJsonClient(MOCK_INTENT_RESPONSES)
    return IntentAnalyzer(client=client)


def build_planner(live: bool) -> StrategyPlanner:
    if live:
        return StrategyPlanner()
    client = MockJsonClient({"Compare revenue Q1 vs Q4": MOCK_STRATEGY_RESPONSE})
    return StrategyPlanner(client=client)


async def run_scenarios(*, live: bool) -> None:
    if live and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is required for --live mode")

    analyzer = build_analyzer(live)
    planner = build_planner(live)

    print("=== SCENARIO 1: Out of scope detection ===")
    context1 = await build_context("what is my payslip")
    intent1 = await analyzer.analyze("what is my payslip", context1)
    print(json.dumps(intent1.to_dict(), indent=2))
    assert intent1.out_of_scope is True
    assert intent1.requires_clarification is False
    reason = (intent1.out_of_scope_reason or "").lower()
    assert any(token in reason for token in ("hr", "payroll", "payslip")), reason
    print("out_of_scope_reason:", intent1.out_of_scope_reason)
    print("SCENARIO 1 PASSED")

    print("\n=== SCENARIO 2: Project search intent ===")
    query2 = "national guard project expenses last month"
    context2 = await build_context(query2)
    intent2 = await analyzer.analyze(query2, context2)
    print(json.dumps(intent2.to_dict(), indent=2))
    assert intent2.primary_action == "fetch_data"
    assert intent2.subject_area == "project"
    project_entities = [entity for entity in intent2.entities if entity.type == "project"]
    assert len(project_entities) > 0
    assert "national guard" in project_entities[0].value.lower()
    print("SCENARIO 2 PASSED")

    print("\n=== SCENARIO 3: Multi-step strategy ===")
    context3 = await build_context("Compare revenue Q1 vs Q4 by top 5 clients")
    intent3 = Intent(
        primary_action="compare",
        subject_area="financial",
        specific_intent="Compare revenue Q1 vs Q4 by top 5 clients",
        implicit_requirements=["Rank top 5 clients by revenue"],
        expected_output="chart",
        urgency="normal",
        estimated_complexity="complex",
        requires_clarification=False,
        out_of_scope=False,
    )
    strategy = await planner.plan(intent3, context3)
    print(json.dumps(strategy.to_dict(), indent=2))
    assert len(strategy.steps) >= 3
    assert any(step.parallel_with for step in strategy.steps)
    print("SCENARIO 3 PASSED")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 2 acceptance scenarios")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live Claude API instead of recorded mock responses",
    )
    args = parser.parse_args()
    asyncio.run(run_scenarios(live=args.live))


if __name__ == "__main__":
    main()
