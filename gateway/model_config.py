"""Anthropic model selection — single source of truth for all gateway agents."""

from __future__ import annotations

import os

# Claude Sonnet 4 (20250514) retired 2026-06-15 — use Sonnet 4.6.
DEFAULT_AGENT_MODEL = "claude-sonnet-4-6"


def resolve_agent_model() -> str:
    """Return configured agent model (env override supported)."""
    for key in ("ANTHROPIC_MODEL", "OOA_AGENT_MODEL"):
        value = (os.environ.get(key) or "").strip()
        if value:
            return value
    return DEFAULT_AGENT_MODEL


AGENT_MODEL = resolve_agent_model()
