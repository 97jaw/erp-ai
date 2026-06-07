"""Tests for GatewayToolExecutor adapter serialization."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from gateway.core.gateway_tool_executor import GatewayToolExecutor
from tests.core.test_context_stack import _make_context_stack


class _ConcurrencyTrackingExecutor:
    """Mock executor that records peak concurrent executions."""

    def __init__(self, delay_seconds: float = 0.05) -> None:
        self.delay_seconds = delay_seconds
        self.active = 0
        self.peak_active = 0
        self.calls = 0

    async def execute(
        self,
        tool: str,
        tool_input: dict[str, Any],
        context: Any,
    ) -> dict[str, Any]:
        self.calls += 1
        self.active += 1
        self.peak_active = max(self.peak_active, self.active)
        await asyncio.sleep(self.delay_seconds)
        self.active -= 1
        return {"tool": tool, "step": tool_input.get("step")}


class _LockingGatewayToolExecutor(GatewayToolExecutor):
    """GatewayToolExecutor with execute_tool replaced for concurrency testing."""

    def __init__(self, tracker: _ConcurrencyTrackingExecutor) -> None:
        super().__init__(adapter=object())
        self._tracker = tracker

    async def execute(
        self,
        tool: str,
        tool_input: dict[str, Any],
        context: Any,
    ) -> Any:
        async with self._lock:
            return await self._tracker.execute(tool, tool_input, context)


@pytest.mark.asyncio
async def test_gateway_tool_executor_serializes_parallel_calls() -> None:
    tracker = _ConcurrencyTrackingExecutor(delay_seconds=0.05)
    executor = _LockingGatewayToolExecutor(tracker)
    context = _make_context_stack()

    await asyncio.gather(
        executor.execute("group_and_aggregate", {"step": 1}, context),
        executor.execute("group_and_aggregate", {"step": 2}, context),
    )

    assert tracker.calls == 2
    assert tracker.peak_active == 1
