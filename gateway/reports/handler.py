"""Reports agent — unified agent-mode handler (compatibility shim)."""

from __future__ import annotations

from typing import Any

from gateway.agent.handler import AgentHandler
from gateway.agent.reports_tools import REPORTS_TOOL_DEFINITIONS

# Re-export for backward compatibility
__all__ = ["ReportsHandler", "get_or_create_handler", "REPORTS_TOOL_DEFINITIONS"]


class ReportsHandler(AgentHandler):
    """Handles reports queries via the unified agent loop."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter, agent_type="reports")


def get_or_create_handler(session_id: str, adapter: Any) -> ReportsHandler:
    """Return a reports handler (session history is stored in reports_session)."""
    return ReportsHandler(adapter)
