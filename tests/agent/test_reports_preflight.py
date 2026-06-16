from __future__ import annotations

import json
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from gateway.agent.claude_retry import is_transient_claude_error
from gateway.agent.handler import AgentHandler
from gateway.agent.reports_preflight import run_reports_preflight
from gateway.agent.reports_session import clear_reports_session


def test_is_transient_claude_error_api_error_body() -> None:
    exc = anthropic.APIStatusError(
        message="Internal server error",
        response=httpx.Response(500, request=httpx.Request("POST", "https://api.anthropic.com")),
        body={"error": {"type": "api_error", "message": "Internal server error"}},
    )
    assert is_transient_claude_error(exc)


def test_reports_greeting_preflight_shows_report_picker() -> None:
    result = run_reports_preflight("Hi", session_id="rpt-greet", language="en")
    assert result is not None
    assert result.ui_blocks
    option_ids = {opt["id"] for opt in result.ui_blocks[0]["options"]}
    assert "pandl" in option_ids
    assert "trial_balance" in option_ids


def test_reports_template_pick_shows_date_quick() -> None:
    result = run_reports_preflight(
        "Profit & Loss",
        session_id="rpt-pl",
        language="en",
    )
    assert result is not None
    assert result.ui_blocks[0]["type"] == "date_quick"


@pytest.mark.asyncio
async def test_reports_handler_greeting_skips_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = "rpt-no-claude"
    clear_reports_session(session_id)
    mock_client = MagicMock()
    monkeypatch.setattr("gateway.agent.core.get_async_client", lambda: mock_client)
    handler = AgentHandler(MagicMock(), agent_type="reports")

    events: list[dict] = []
    async for chunk in handler.handle_stream("Hello", None, session_id):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))

    handler.client.messages.stream.assert_not_called()
    done = next(e for e in events if e.get("type") == "done")
    assert done.get("agent") == "reports"
    assert done.get("ui_blocks")
