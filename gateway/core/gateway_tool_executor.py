"""Async adapter that routes orchestrator tool calls to gateway.execute_tool."""

from __future__ import annotations

import asyncio
from typing import Any

from gateway.core.context_stack import ContextStack


class GatewayToolExecutor:
    """Execute gateway tools on a worker thread using the live Odoo adapter."""

    def __init__(
        self,
        adapter: Any,
        *,
        session_id: str | None = None,
        user_message: str = "",
    ) -> None:
        self._adapter = adapter
        self._session_id = session_id
        self._user_message = user_message
        # Odoo XML-RPC clients are not thread-safe; parallel orchestration steps
        # must not hit the same adapter concurrently.
        self._lock = asyncio.Lock()

    async def execute(
        self,
        tool: str,
        tool_input: dict[str, Any],
        context: ContextStack,
    ) -> Any:
        """Run one gateway tool through the existing execute_tool pipeline."""
        from gateway.main import execute_tool

        async with self._lock:
            return await asyncio.to_thread(
                execute_tool,
                tool,
                dict(tool_input or {}),
                self._adapter,
                self._session_id,
                self._user_message or context.conversation.message,
            )
