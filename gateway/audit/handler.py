"""Audit agent — unified agent-mode handler (compatibility shim)."""

from __future__ import annotations

from typing import Any

from gateway.agent.handler import AgentHandler


class AuditHandler(AgentHandler):
    """Handles audit/analyze queries via the unified agent loop."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter, agent_type="audit")
