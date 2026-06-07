"""Visualize agent Claude streaming loop."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncIterator

from visualize.context import build_system_prompt
from visualize.message_utils import prepare_messages_for_api, serialize_content
from visualize.prompt import DEFAULT_OUTPUT_ACTIONS, VISUALIZE_AGENT_PROMPT
from visualize.sessions import VisualizeSession, append_message, get_session
from visualize.tool_runner import execute_visualize_tool
from visualize.tools import TOOL_STATUS_LABELS, VISUALIZE_TOOLS

logger = logging.getLogger(__name__)

AGENT_MODEL = "claude-sonnet-4-20250514"
MAX_AGENT_TOKENS = 2048
TOOL_RESULT_CHAR_LIMIT = 10000


def _prepare_tool_result(result: Any) -> str:
    payload = json.dumps(result, default=str)
    if len(payload) > TOOL_RESULT_CHAR_LIMIT:
        payload = payload[: TOOL_RESULT_CHAR_LIMIT - 3] + "..."
    return payload


def _progress_steps(tool_blocks: list[Any]) -> list[dict[str, str]]:
    return [
        {
            "id": block.id,
            "tool": block.name,
            "label": TOOL_STATUS_LABELS.get(block.name, block.name),
            "status": "queued",
        }
        for block in tool_blocks
    ]


async def stream_visualize_chat(
    session: VisualizeSession,
    user_message: str,
) -> AsyncIterator[str]:
    """Yield SSE `data: {...}\\n\\n` lines."""
    from gateway.main import get_agent_client

    client = get_agent_client()
    append_message(session.session_id, "user", user_message)
    session = get_session(session.session_id) or session
    messages = prepare_messages_for_api(list(session.messages))
    brain = None
    if session.brain_recommendation:
        brain = {
            "inspection": session.brain_inspection,
            "analysis": session.brain_analysis,
            "recommendation": session.brain_recommendation,
        }
    system = build_system_prompt(VISUALIZE_AGENT_PROMPT, session.dropped_items, brain=brain)
    full_text = ""

    try:
        while True:
            with client.messages.stream(
                model=AGENT_MODEL,
                max_tokens=MAX_AGENT_TOKENS,
                system=system,
                tools=VISUALIZE_TOOLS,
                messages=messages,
            ) as stream:
                for event in stream:
                    if hasattr(event, "type") and event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            chunk = event.delta.text
                            full_text += chunk
                            yield f"data: {json.dumps({'type': 'text', 'chunk': chunk})}\n\n"

                final_message = stream.get_final_message()

                if final_message.stop_reason == "tool_use":
                    assistant_content = serialize_content(final_message.content)
                    messages.append({"role": "assistant", "content": assistant_content})
                    append_message(session.session_id, "assistant", assistant_content)

                    tool_blocks = [b for b in final_message.content if b.type == "tool_use"]
                    progress = _progress_steps(tool_blocks)
                    if progress:
                        yield f"data: {json.dumps({'type': 'progress', 'steps': progress})}\n\n"

                    tool_messages: list[dict[str, Any]] = []
                    last_output: dict[str, Any] | None = None

                    for index, block in enumerate(tool_blocks):
                        progress[index]["status"] = "running"
                        status = TOOL_STATUS_LABELS.get(block.name, block.name)
                        yield f"data: {json.dumps({'type': 'status', 'message': status})}\n\n"
                        yield f"data: {json.dumps({'type': 'progress', 'steps': progress})}\n\n"

                        result = await asyncio.to_thread(
                            execute_visualize_tool,
                            block.name,
                            block.input,
                            session,
                        )
                        if isinstance(result, dict) and "error" not in result:
                            if result.get("pdf_url") or result.get("excel_url"):
                                last_output = result
                        progress[index]["status"] = (
                            "failed"
                            if isinstance(result, dict) and result.get("error")
                            else "done"
                        )
                        yield f"data: {json.dumps({'type': 'progress', 'steps': progress})}\n\n"

                        tool_messages.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": _prepare_tool_result(result),
                        })

                    messages.append({"role": "user", "content": tool_messages})
                    append_message(session.session_id, "user", tool_messages)
                    full_text = ""
                    continue

                break

        append_message(session.session_id, "assistant", full_text)
        done_payload: dict[str, Any] = {
            "type": "done",
            "text": full_text.strip(),
            "session_id": session.session_id,
            "actions": DEFAULT_OUTPUT_ACTIONS,
        }
        if session.last_output:
            done_payload["output"] = session.last_output
        refreshed = get_session(session.session_id)
        if refreshed and refreshed.last_output:
            done_payload["output"] = refreshed.last_output
        yield f"data: {json.dumps(done_payload)}\n\n"

    except Exception as exc:
        logger.exception("[visualize] stream failed")
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
