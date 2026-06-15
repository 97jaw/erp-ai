"""Tests for agent-mode DB conversation persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.agent.conversation_persistence import (
    append_assistant_message,
    append_user_message,
    sync_in_memory_turn,
)
from gateway.agent.handler import AgentHandler


@pytest.mark.asyncio
async def test_append_user_message_calls_conversation_store() -> None:
    user = MagicMock(id=42)
    with patch(
        "gateway.conversation_store.ConversationStore.append",
        new_callable=AsyncMock,
    ) as mock_append:
        await append_user_message("sess-1", user, "hello", language="en")
        mock_append.assert_awaited_once_with(
            "sess-1",
            "user",
            "hello",
            user_id=42,
            language="en",
        )


@pytest.mark.asyncio
async def test_append_assistant_message_stores_ui_blocks() -> None:
    user = MagicMock(id=7)
    blocks = [{"type": "pill_select", "prompt": "Pick one", "options": []}]
    with patch(
        "gateway.conversation_store.ConversationStore.append",
        new_callable=AsyncMock,
    ) as mock_append, patch(
        "gateway.conversation_store.ConversationStore.conversation_id_for_session",
        return_value="conv-uuid",
    ):
        conv_id = await append_assistant_message(
            "sess-3",
            user,
            "",
            ui_blocks=blocks,
        )
        assert conv_id == "conv-uuid"
        kwargs = mock_append.await_args.kwargs
        assert kwargs["tool_calls"] == {"ui_blocks": blocks}


@pytest.mark.asyncio
async def test_append_assistant_message_stores_viz() -> None:
    user = MagicMock(id=7)
    viz = {"visual_type": "DATA_TABLE", "label": "Test"}
    with patch(
        "gateway.conversation_store.ConversationStore.append",
        new_callable=AsyncMock,
    ) as mock_append, patch(
        "gateway.conversation_store.ConversationStore.conversation_id_for_session",
        return_value="conv-uuid",
    ):
        conv_id = await append_assistant_message(
            "sess-2",
            user,
            "Here are the results.",
            visualization=viz,
            suggestions=["Follow up"],
            response_time_ms=1200,
        )
        assert conv_id == "conv-uuid"
        mock_append.assert_awaited_once()
        kwargs = mock_append.await_args.kwargs
        assert kwargs["visualization"] == viz
        assert kwargs["suggestions"] == ["Follow up"]
        assert kwargs["response_time_ms"] == 1200


@pytest.mark.asyncio
async def test_handler_persist_turn_delegates_to_db() -> None:
    handler = AgentHandler(adapter=MagicMock(), agent_type="chat")
    user = MagicMock(id=99)
    with patch(
        "gateway.agent.conversation_persistence.append_assistant_message",
        new_callable=AsyncMock,
        return_value="db-conv-id",
    ) as mock_assistant:
        conv_id = await handler._persist_turn(
            "thread-abc",
            "user question",
            "assistant answer",
            user,
            language="en",
            suggestions=["Next"],
        )
        assert conv_id == "db-conv-id"
        mock_assistant.assert_awaited_once()


def test_sync_in_memory_turn_updates_session_state() -> None:
    from gateway.agent.session_state import clear_session, get_session_history

    clear_session("mem-test")
    sync_in_memory_turn("mem-test", "hi", "hello back")
    history = get_session_history("mem-test", last_n=5)
    assert len(history) == 2
    assert history[0]["content"] == "hi"
    assert history[1]["content"] == "hello back"
    clear_session("mem-test")
