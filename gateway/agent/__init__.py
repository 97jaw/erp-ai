"""Unified agent-mode architecture — replaces rigid pipeline routing."""

from gateway.agent.core import Agent, AgentResponse
from gateway.agent.handler import AgentHandler

__all__ = ["Agent", "AgentHandler", "AgentResponse"]
