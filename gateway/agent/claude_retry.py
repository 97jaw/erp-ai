"""Retry helpers for transient Anthropic API failures."""

from __future__ import annotations

import logging
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

_TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 529})


def is_transient_claude_error(exc: BaseException) -> bool:
    """Return True when a Claude call is worth retrying."""
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.RateLimitError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code in _TRANSIENT_STATUS_CODES:
            return True
        body: Any = getattr(exc, "body", None)
        if isinstance(body, dict):
            err = body.get("error") or {}
            if isinstance(err, dict) and err.get("type") in {
                "api_error",
                "overloaded_error",
            }:
                return True
            message = str(err.get("message") or "").lower()
            if "internal server error" in message:
                return True
    return False


def log_claude_retry(agent_type: str, attempt: int, exc: BaseException) -> None:
    logger.warning(
        "[ClaudeRetry] attempt=%s agent=%s error=%s",
        attempt,
        agent_type,
        exc,
    )
