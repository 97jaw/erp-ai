"""Deterministic strategies for orchestration tests and acceptance demos."""

from __future__ import annotations

from typing import Any

from gateway.core.strategy_planner import ExecutionStep, Strategy


def build_single_tool_strategy(
    *,
    tool: str,
    tool_input: dict[str, Any],
    description: str = "",
    expected_output: str = "summary",
) -> Strategy:
    """Single-step strategy for forced tool execution (e.g. active follow-up)."""
    return Strategy(
        steps=[
            ExecutionStep(
                step_number=1,
                description=description or f"Execute {tool}",
                tool=tool,
                tool_input=tool_input,
                depends_on=[],
                parallel_with=[],
                expected_output=expected_output,
                fallback_if_fails=f"Retry {tool} with resolved project scope",
            ),
        ],
        synthesis_approach=(
            "Return the single tool result directly with a concise executive summary"
        ),
        quality_checks=[
            "Verify numeric values are present in the tool result",
            "Confirm project scope matches active follow-up context",
        ],
        estimated_duration_ms=3000,
    )


def _revenue_by_client_step(
    *,
    step_number: int,
    parallel_with: list[int],
    date_from: str,
    date_to: str,
    limit: int,
    description: str,
) -> ExecutionStep:
    return ExecutionStep(
        step_number=step_number,
        description=description,
        tool="group_and_aggregate",
        tool_input={
            "model": "account.move",
            "domain": [
                ["move_type", "=", "out_invoice"],
                ["state", "=", "posted"],
            ],
            "date_from": date_from,
            "date_to": date_to,
            "group_by": ["partner_id"],
            "aggregates": ["amount_total:sum"],
            "limit": limit,
            "order_by": "amount_total:sum desc",
        },
        depends_on=[],
        parallel_with=parallel_with,
        expected_output="table",
        fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
    )


def build_revenue_comparison_strategy(
    *,
    period_1: tuple[str, str] = ("2026-01-01", "2026-03-31"),
    period_2: tuple[str, str] = ("2025-01-01", "2025-03-31"),
    limit: int = 5,
) -> Strategy:
    """Two-step revenue comparison with parallel period fetches."""
    return Strategy(
        steps=[
            _revenue_by_client_step(
                step_number=1,
                parallel_with=[2],
                date_from=period_1[0],
                date_to=period_1[1],
                limit=limit,
                description=f"Fetch revenue by client for {period_1[0]} to {period_1[1]}",
            ),
            _revenue_by_client_step(
                step_number=2,
                parallel_with=[1],
                date_from=period_2[0],
                date_to=period_2[1],
                limit=limit,
                description=f"Fetch revenue by client for {period_2[0]} to {period_2[1]}",
            ),
        ],
        synthesis_approach="Compare top clients by revenue across both Q1 periods",
        quality_checks=[
            "Top clients identified in both quarters",
            "Revenue values are present for both periods",
        ],
        estimated_duration_ms=8000,
    )


def build_revenue_by_client_strategy(
    *,
    date_from: str,
    date_to: str,
    limit: int = 10,
) -> Strategy:
    """Single-step revenue-by-client fetch for one period."""
    return Strategy(
        steps=[
            ExecutionStep(
                step_number=1,
                description=f"Fetch revenue by client for {date_from} to {date_to}",
                tool="group_and_aggregate",
                tool_input={
                    "model": "account.move",
                    "domain": [
                        ["move_type", "=", "out_invoice"],
                        ["state", "=", "posted"],
                    ],
                    "date_from": date_from,
                    "date_to": date_to,
                    "group_by": ["partner_id"],
                    "aggregates": ["amount_total:sum"],
                    "limit": limit,
                    "order_by": "amount_total:sum desc",
                },
                depends_on=[],
                parallel_with=[],
                expected_output="table",
                fallback_if_fails="use_tool:search_odoo:{'model': 'account.move'}",
            ),
        ],
        synthesis_approach="Summarize top clients by posted invoice revenue for the period",
        quality_checks=[
            "Client names are human-readable",
            "Revenue values come from posted invoices",
        ],
        estimated_duration_ms=6000,
    )
