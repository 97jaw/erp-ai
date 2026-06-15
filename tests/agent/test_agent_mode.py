"""Tests for unified agent-mode architecture (Step 1)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from admin.auth.principal import CurrentUser
from gateway.agent.core import Agent, format_error
from gateway.agent.permissions import filter_tools_for_user, user_role_label
from gateway.agent.session_state import (
    add_to_session,
    clear_session,
    get_session_history,
)
from gateway.agent.system_prompt import build_system_prompt
from gateway.agent.tools_registry import get_all_tools
from gateway.agent.ui_blocks import normalize_ui_block


@pytest.fixture
def super_admin() -> CurrentUser:
    return CurrentUser(
        id=1,
        file_id="TEST001",
        name="Test Admin",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"odoo.full_access"}),
    )


@pytest.fixture
def standard_user() -> CurrentUser:
    return CurrentUser(
        id=2,
        file_id="TEST002",
        name="Standard User",
        language="en",
        is_super_admin=False,
        is_active=True,
        roles=("viewer",),
        permissions=frozenset(),
    )


def test_session_history_roundtrip() -> None:
    clear_session("agent-test")
    add_to_session("agent-test", "user", "hello")
    add_to_session("agent-test", "assistant", "hi")
    history = get_session_history("agent-test", last_n=5)
    assert len(history) == 2
    assert history[0]["content"] == "hello"
    clear_session("agent-test")


def test_build_system_prompt_includes_elrace_context(super_admin: CurrentUser) -> None:
    prompt = build_system_prompt("chat", super_admin, language="en")
    assert "Elrace" in prompt
    assert "THINK BEFORE ACTING" in prompt
    assert "super_admin" in prompt


def test_chat_tools_include_ui_and_universal(super_admin: CurrentUser) -> None:
    names = {t["name"] for t in get_all_tools("chat", super_admin)}
    assert "query_odoo" in names
    assert "show_ui_block" in names
    assert "add_suggestions" in names
    assert "get_financial_report" in names
    assert "search_fleet_vehicles" in names
    assert "get_purchase_orders" in names
    assert "get_project_records" in names


def test_audit_tools_subset(super_admin: CurrentUser) -> None:
    names = {t["name"] for t in get_all_tools("audit", super_admin)}
    assert "get_audit_trail" in names
    assert "query_odoo" in names
    assert "show_ui_block" in names


def test_normalize_ui_block_pill_select() -> None:
    block = normalize_ui_block(
        {
            "block_type": "pill_select",
            "prompt": "What HR info do you need?",
            "options": [
                {"id": "employees", "label": "Employees"},
                {"id": "payroll", "label": "Payroll"},
            ],
        }
    )
    assert block is not None
    assert block["type"] == "pill_select"
    assert len(block["options"]) == 2


def test_format_error_invalid_field() -> None:
    payload = format_error(Exception("Invalid field 'amount_total' on project.project"))
    assert payload["error_type"] == "invalid_field"
    assert "introspect_odoo_schema" in payload["hint"]


def test_user_role_label(standard_user: CurrentUser) -> None:
    assert user_role_label(standard_user) == "viewer"


def test_filter_tools_hides_super_admin_only(standard_user: CurrentUser) -> None:
    tools = [
        {"name": "query_odoo"},
        {"name": "get_partner_ledger"},
    ]
    filtered = filter_tools_for_user(tools, standard_user)
    assert {t["name"] for t in filtered} == {"query_odoo"}


@pytest.mark.asyncio
async def test_agent_handle_end_turn(super_admin: CurrentUser) -> None:
    """Agent returns text when Claude ends without tool use."""
    text_block = SimpleNamespace(type="text", text="Here is your answer.")
    final_response = SimpleNamespace(
        stop_reason="end_turn",
        content=[text_block],
    )

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=final_response)

    agent = Agent(agent_type="chat")
    agent.client = mock_client

    result = await agent.handle(
        "hello",
        user=super_admin,
        adapter=MagicMock(),
        session_id="mock-session",
        language="en",
    )

    assert result.text == "Here is your answer."
    mock_client.messages.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_agent_ui_block_tool_collects_picker(super_admin: CurrentUser) -> None:
    """Smart clarification: show_ui_block is captured in response."""
    tool_block = SimpleNamespace(
        type="tool_use",
        id="toolu_1",
        name="show_ui_block",
        input={
            "block_type": "pill_select",
            "prompt": "What HR info do you need?",
            "options": [
                {"id": "employees", "label": "Employees"},
                {"id": "payroll", "label": "Payroll"},
            ],
        },
    )
    text_block = SimpleNamespace(type="text", text="Which area would you like?")
    tool_response = SimpleNamespace(stop_reason="tool_use", content=[tool_block])
    final_response = SimpleNamespace(stop_reason="end_turn", content=[text_block])

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])

    agent = Agent(agent_type="chat")
    agent.client = mock_client

    clear_session("ui-block-session")
    result = await agent.handle(
        "need HR info",
        user=super_admin,
        adapter=MagicMock(),
        session_id="ui-block-session",
        language="en",
    )

    assert result.ui_blocks
    assert result.ui_blocks[0]["type"] == "pill_select"
    assert any(o["label"] == "Payroll" for o in result.ui_blocks[0]["options"])
    clear_session("ui-block-session")


@pytest.mark.asyncio
async def test_agent_tool_error_returns_to_claude_not_user(super_admin: CurrentUser) -> None:
    """Error recovery: tool failures go back to Claude as structured errors."""
    tool_block = SimpleNamespace(
        type="tool_use",
        id="toolu_err",
        name="query_odoo",
        input={"model": "project.project", "fields": ["bad_field"]},
    )
    text_block = SimpleNamespace(
        type="text",
        text="Let me try a different approach.",
    )
    tool_response = SimpleNamespace(stop_reason="tool_use", content=[tool_block])
    final_response = SimpleNamespace(stop_reason="end_turn", content=[text_block])

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(side_effect=[tool_response, final_response])

    agent = Agent(agent_type="chat")
    agent.client = mock_client

    with patch(
        "gateway.agent.core.execute_tool",
        AsyncMock(side_effect=Exception("Invalid field bad_field")),
    ):
        result = await agent.handle(
            "compare top 5 projects by expense",
            user=super_admin,
            adapter=MagicMock(),
            session_id="err-session",
            language="en",
        )

    assert "different approach" in result.text.lower()
    second_call_messages = mock_client.messages.create.await_args_list[1].kwargs["messages"]
    tool_result_content = second_call_messages[-1]["content"][0]["content"]
    payload = json.loads(tool_result_content)
    assert payload["error_type"] == "invalid_field"
