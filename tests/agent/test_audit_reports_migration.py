"""Tests for audit/reports migration to unified AgentHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.agent.audit_helpers import audit_visualization_payload
from gateway.agent.handler import AgentHandler
from gateway.agent.reports_session import append_reports_message, clear_reports_session, get_reports_history
from gateway.agent.reports_tools import REPORTS_TOOL_NAMES
from gateway.audit.handler import AuditHandler
from gateway.reports.handler import ReportsHandler, get_or_create_handler


def test_audit_handler_is_agent_handler() -> None:
    handler = AuditHandler(MagicMock())
    assert handler.agent_type == "audit"
    assert handler.max_rounds == 6


def test_reports_handler_is_agent_handler() -> None:
    handler = get_or_create_handler("sess-1", MagicMock())
    assert isinstance(handler, ReportsHandler)
    assert handler.agent_type == "reports"
    assert handler.max_rounds == 8


def test_reports_session_history() -> None:
    clear_reports_session("rpt-1")
    append_reports_message("rpt-1", "user", "hello")
    append_reports_message("rpt-1", "assistant", "hi")
    history = get_reports_history("rpt-1")
    assert len(history) == 2
    clear_reports_session("rpt-1")


def test_audit_visualization_payload_prefers_trail() -> None:
    payloads = [
        {"tool": "get_user_activity", "data": {"status": "success", "by_model": []}},
        {
            "tool": "get_audit_trail",
            "data": {"status": "success", "timeline": [{"id": 1}]},
        },
    ]
    viz = audit_visualization_payload(payloads)
    assert viz is not None
    assert viz["view"] == "timeline"


def test_reports_tool_names_include_generate() -> None:
    assert "generate_report" in REPORTS_TOOL_NAMES
    assert "show_ui_block" in REPORTS_TOOL_NAMES


@pytest.mark.asyncio
async def test_reports_handler_emits_file_ready_on_generate() -> None:
    """generate_report side effects surface as file_ready_list SSE events."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_gen"
    tool_block.name = "generate_report"
    tool_block.input = {
        "template": "pandl",
        "params": {"date_from": "2026-01-01", "date_to": "2026-03-31"},
        "format": "pdf",
    }

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Your report is ready."
    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    mock_client = MagicMock()
    mock_stream = MagicMock()
    mock_stream.text_stream = _async_iter([])
    mock_stream.get_final_message = AsyncMock(side_effect=[tool_response, final_response])
    mock_client.messages.stream.return_value.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_client.messages.stream.return_value.__aexit__ = AsyncMock(return_value=False)

    handler = ReportsHandler(MagicMock())
    handler.client = mock_client

    generate_result = {
        "status": "success",
        "files": [
            {
                "type": "file_ready",
                "report_id": "abc",
                "filename": "pandl.pdf",
                "format": "pdf",
                "url": "/reports/download/abc",
            }
        ],
        "message": "Generated 1 file(s) successfully.",
        "_sse_events": [
            {
                "type": "file_ready_list",
                "files": [
                    {
                        "type": "file_ready",
                        "report_id": "abc",
                        "filename": "pandl.pdf",
                        "format": "pdf",
                        "url": "/reports/download/abc",
                    }
                ],
            }
        ],
    }

    events: list[dict] = []
    with patch("gateway.agent.handler.execute_tool", AsyncMock(return_value=generate_result)):
        async for chunk in handler.handle_stream("generate P&L", None, "reports-test-session"):
            if chunk.startswith("data: "):
                import json

                events.append(json.loads(chunk[6:]))

    file_events = [e for e in events if e.get("type") == "file_ready_list"]
    assert file_events
    done = next(e for e in events if e.get("type") == "done")
    assert done.get("agent") == "reports"
    assert done.get("files")


async def _async_iter(items):
    for item in items:
        yield item
