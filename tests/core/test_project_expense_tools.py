"""Unit tests for project expense intelligence tools (Phase E1).

Matches PROJECT_EXPENSE_INTELLIGENCE_PLAN.md minimum test list (9 cases).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from gateway.tools.project_expense import (
    BREAKDOWN_METHOD,
    SERVICE_MODEL,
    SUMMARY_METHOD,
    execute_compare_project_expenses,
    execute_get_project_expense_breakdown,
    execute_get_project_expense_summary,
)


def _summary_odoo_payload(
    *,
    project_name: str = "Zayidia Boys School",
    wo: float = 1_000_000,
    expenses: float = 850_000,
    spend_percent: float = 85.0,
) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "project_name": project_name,
            "agreement_name": "MOE Agreement",
            "partner_name": "Ministry Of Education (MOE)",
            "currency_name": "AED",
            "project_count": wo,
            "total_expenses": expenses,
            "spend_percent_of_wo": spend_percent,
            "estimation_amount": 900_000,
            "top_expenses": [
                {"name": "Civil", "amount": 300_000, "percent": 35.29},
            ],
            "expense_lines": [
                {"label": "LPO", "amount": 400_000},
                {"label": "Labor", "amount": 250_000},
            ],
        },
    }


def _breakdown_odoo_payload() -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "project_name": "Zayidia Boys School",
            "currency_name": "AED",
            "wizard_id": 99,
            "breakdown": {
                "groups": [
                    {
                        "code": "MG01",
                        "name": "Direct Costs",
                        "subgroups": [
                            {
                                "code": "SG01",
                                "name": "Materials",
                                "accounts": [
                                    {"code": "5001", "name": "Steel", "total": 100_000},
                                    {"code": "5002", "name": "Cement", "total": 50_000},
                                ],
                            },
                        ],
                    },
                    {
                        "code": "MG02",
                        "name": "Indirect Costs",
                        "subgroups": [
                            {
                                "code": "SG02",
                                "name": "Admin",
                                "accounts": [
                                    {"code": "6001", "name": "Office", "total": 25_000},
                                ],
                            },
                        ],
                    },
                ],
            },
        },
    }


class MockAdapter:
    def __init__(self, responses: dict[tuple[str, int], Any] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, str, list[Any]]] = []

    def call_method(
        self,
        model: str,
        method: str,
        args: list[Any],
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        del kwargs
        self.calls.append((model, method, args))
        key = (method, int(args[0]))
        if key not in self.responses:
            raise KeyError(f"No mock response for {key}")
        response = self.responses[key]
        if isinstance(response, Exception):
            raise response
        return response


# 1. summary tool returns normalized fields
@pytest.mark.asyncio
async def test_summary_returns_normalized_fields() -> None:
    adapter = MockAdapter(
        {("get_project_expense_summary_mobile", 14549): _summary_odoo_payload()},
    )

    with patch("gateway.tools.project_expense.asyncio.to_thread", new=AsyncMock()) as to_thread:
        to_thread.side_effect = lambda fn, *args: fn(*args)
        result = await execute_get_project_expense_summary(
            {"project_id": 14549},
            adapter,
            None,
        )
        to_thread.assert_awaited_once_with(
            adapter.call_method,
            SERVICE_MODEL,
            SUMMARY_METHOD,
            [14549],
        )

    assert result["status"] == "success"
    assert result["project_id"] == 14549
    assert result["project_name"] == "Zayidia Boys School"
    assert result["wo_amount"] == 1_000_000
    assert result["total_expenses"] == 850_000
    assert result["spend_percent_of_wo"] == 85.0
    assert result["variance_amount"] == 150_000
    assert result["is_over_budget"] is False
    assert result["top_expenses"][0]["name"] == "Civil"
    assert result["expense_lines"][0]["label"] == "LPO"
    assert adapter.calls[0] == (SERVICE_MODEL, SUMMARY_METHOD, [14549])


# 2. summary tool handles Odoo error gracefully
@pytest.mark.asyncio
async def test_summary_handles_odoo_error_gracefully() -> None:
    adapter = MockAdapter(
        {
            ("get_project_expense_summary_mobile", 999): {
                "status": "error",
                "message": "Project not found",
            },
        },
    )

    result = await execute_get_project_expense_summary({"project_id": 999}, adapter, None)

    assert result == {"status": "error", "message": "Project not found"}


# 3. breakdown tool parses hierarchy correctly
@pytest.mark.asyncio
async def test_breakdown_parses_hierarchy_correctly() -> None:
    adapter = MockAdapter(
        {("get_project_expense_breakdown_mobile", 14549): _breakdown_odoo_payload()},
    )

    with patch("gateway.tools.project_expense.asyncio.to_thread", new=AsyncMock()) as to_thread:
        to_thread.side_effect = lambda fn, *args: fn(*args)
        result = await execute_get_project_expense_breakdown(
            {"project_id": 14549},
            adapter,
            None,
        )
        to_thread.assert_awaited_once_with(
            adapter.call_method,
            SERVICE_MODEL,
            BREAKDOWN_METHOD,
            [14549],
        )

    assert result["status"] == "success"
    assert result["group_count"] == 2
    assert result["groups"][0]["code"] == "MG01"
    assert result["groups"][0]["subgroups"][0]["accounts"][0]["code"] == "5001"
    assert result["wizard_id"] == 99


# 4. breakdown tool computes totals at each level
@pytest.mark.asyncio
async def test_breakdown_computes_totals_at_each_level() -> None:
    adapter = MockAdapter(
        {("get_project_expense_breakdown_mobile", 14549): _breakdown_odoo_payload()},
    )

    result = await execute_get_project_expense_breakdown(
        {"project_id": 14549},
        adapter,
        None,
    )

    assert result["grand_total"] == 175_000
    assert result["groups"][0]["total"] == 150_000
    assert result["groups"][0]["subgroups"][0]["total"] == 150_000
    assert result["groups"][1]["total"] == 25_000
    assert result["_truncated"] is False


# 5. compare tool fetches projects in parallel
@pytest.mark.asyncio
async def test_compare_fetches_projects_in_parallel() -> None:
    adapter = MockAdapter(
        {
            ("get_project_expense_summary_mobile", 1): _summary_odoo_payload(
                project_name="Project A",
                expenses=100,
            ),
            ("get_project_expense_summary_mobile", 2): _summary_odoo_payload(
                project_name="Project B",
                expenses=200,
            ),
        },
    )

    async def slow_summary(
        tool_input: dict[str, Any],
        adapter_arg: Any,
        context: Any,
    ) -> dict[str, Any]:
        await asyncio.sleep(0.05)
        return await execute_get_project_expense_summary(tool_input, adapter_arg, context)

    start = time.perf_counter()
    with patch(
        "gateway.tools.project_expense.execute_get_project_expense_summary",
        new=AsyncMock(side_effect=slow_summary),
    ):
        result = await execute_compare_project_expenses(
            {"project_ids": [1, 2]},
            adapter,
            None,
        )
    elapsed = time.perf_counter() - start

    assert result["status"] == "success"
    assert len(result["projects"]) == 2
    assert elapsed < 0.09


# 6. compare tool ranks correctly by total_expenses
@pytest.mark.asyncio
async def test_compare_ranks_by_total_expenses() -> None:
    adapter = MockAdapter(
        {
            ("get_project_expense_summary_mobile", 1): _summary_odoo_payload(
                project_name="Low Spend",
                expenses=100_000,
            ),
            ("get_project_expense_summary_mobile", 2): _summary_odoo_payload(
                project_name="High Spend",
                expenses=500_000,
            ),
        },
    )

    result = await execute_compare_project_expenses(
        {"project_ids": [1, 2], "rank_by": "total_expenses"},
        adapter,
        None,
    )

    assert result["ranking"][0]["project_id"] == 2
    assert result["ranking"][0]["value"] == 500_000
    assert result["ranked_by"] == "total_expenses"
    assert result["totals"]["combined_expenses"] == 600_000


# 7. compare tool ranks correctly by spend_percent
@pytest.mark.asyncio
async def test_compare_ranks_by_spend_percent() -> None:
    adapter = MockAdapter(
        {
            ("get_project_expense_summary_mobile", 1): _summary_odoo_payload(
                expenses=400_000,
                spend_percent=40.0,
            ),
            ("get_project_expense_summary_mobile", 2): _summary_odoo_payload(
                expenses=900_000,
                spend_percent=90.0,
            ),
        },
    )

    result = await execute_compare_project_expenses(
        {"project_ids": [1, 2], "rank_by": "spend_percent"},
        adapter,
        None,
    )

    assert result["ranking"][0]["project_id"] == 2
    assert result["ranking"][0]["value"] == 90.0


# 8. compare tool handles partial failures (one project errors)
@pytest.mark.asyncio
async def test_compare_handles_partial_failures() -> None:
    adapter = MockAdapter(
        {
            ("get_project_expense_summary_mobile", 14549): _summary_odoo_payload(),
            ("get_project_expense_summary_mobile", 999): {
                "status": "error",
                "message": "not found",
            },
        },
    )

    result = await execute_compare_project_expenses(
        {"project_ids": [14549, 999]},
        adapter,
        None,
    )

    assert result["status"] == "success"
    assert len(result["projects"]) == 1
    assert result["projects"][0]["project_id"] == 14549
    assert result["failed"] == [{"project_id": 999, "error": "not found"}]


# 9. all tools include proper _source field for telemetry
@pytest.mark.asyncio
async def test_all_tools_include_source_field_for_telemetry() -> None:
    adapter = MockAdapter(
        {
            ("get_project_expense_summary_mobile", 14549): _summary_odoo_payload(),
            ("get_project_expense_breakdown_mobile", 14549): _breakdown_odoo_payload(),
            ("get_project_expense_summary_mobile", 14610): _summary_odoo_payload(
                project_name="Zayidia Girls School",
                expenses=600_000,
            ),
        },
    )

    summary = await execute_get_project_expense_summary({"project_id": 14549}, adapter, None)
    breakdown = await execute_get_project_expense_breakdown({"project_id": 14549}, adapter, None)
    compare = await execute_compare_project_expenses(
        {"project_ids": [14549, 14610]},
        adapter,
        None,
    )

    assert summary["_source"] == "project_expense_summary_mobile"
    assert breakdown["_source"] == "project_expense_breakdown_mobile"
    assert compare["_source"] == "compare_project_expenses"
