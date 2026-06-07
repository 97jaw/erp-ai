"""Serialize and repair Visualize agent conversation messages for the Claude API."""

from __future__ import annotations

import json
from typing import Any


def _block_to_dict(block: Any) -> dict[str, Any]:
    if isinstance(block, dict):
        return dict(block)
    if hasattr(block, "model_dump"):
        return block.model_dump()
    data: dict[str, Any] = {"type": getattr(block, "type", None)}
    for key in ("id", "name", "input", "text", "tool_use_id", "content"):
        value = getattr(block, key, None)
        if value is not None:
            data[key] = value
    return data


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if isinstance(value.get("text"), str):
            return value["text"]
        return json.dumps(value, default=str)
    return str(value)


def _sanitize_block(block: Any) -> dict[str, Any] | None:
    """Keep only fields the Claude Messages API accepts per block type."""
    raw = _block_to_dict(block)
    block_type = raw.get("type")

    if block_type == "text":
        return {"type": "text", "text": _coerce_text(raw.get("text"))}

    if block_type == "tool_use":
        tool_id = raw.get("id")
        name = raw.get("name")
        if not tool_id or not name:
            return None
        tool_input = raw.get("input")
        if tool_input is None:
            tool_input = {}
        if not isinstance(tool_input, dict):
            tool_input = {"value": tool_input}
        return {
            "type": "tool_use",
            "id": str(tool_id),
            "name": str(name),
            "input": tool_input,
        }

    if block_type == "tool_result":
        tool_use_id = raw.get("tool_use_id")
        if not tool_use_id:
            return None
        content = raw.get("content")
        if not isinstance(content, str):
            content = json.dumps(content, default=str) if content is not None else ""
        return {
            "type": "tool_result",
            "tool_use_id": str(tool_use_id),
            "content": content,
        }

    return None


def sanitize_content_for_api(content: str | list[Any]) -> str | list[dict[str, Any]]:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    sanitized: list[dict[str, Any]] = []
    for block in content:
        clean = _sanitize_block(block)
        if clean:
            sanitized.append(clean)
    return sanitized


def serialize_content(content: str | list[Any]) -> str | list[dict[str, Any]]:
    """Persist-safe serialization (API-compatible, no SDK extras)."""
    return sanitize_content_for_api(content)


def _tool_use_ids(content: Any) -> list[str]:
    if not isinstance(content, list):
        return []
    ids: list[str] = []
    for block in content:
        clean = _sanitize_block(block)
        if clean and clean.get("type") == "tool_use" and clean.get("id"):
            ids.append(str(clean["id"]))
    return ids


def _tool_result_ids(content: Any) -> set[str]:
    if not isinstance(content, list):
        return set()
    ids: set[str] = set()
    for block in content:
        clean = _sanitize_block(block)
        if clean and clean.get("type") == "tool_result" and clean.get("tool_use_id"):
            ids.add(str(clean["tool_use_id"]))
    return ids


def _synthetic_tool_results(tool_use_ids: list[str], reason: str = "interrupted") -> list[dict[str, Any]]:
    payload = json.dumps({"status": reason, "note": "Recovered missing tool result from session history."})
    return [
        {
            "type": "tool_result",
            "tool_use_id": tool_id,
            "content": payload,
        }
        for tool_id in tool_use_ids
    ]


def prepare_messages_for_api(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Normalize stored messages and ensure every assistant tool_use turn is
    immediately followed by a user message containing matching tool_result blocks.
    """
    prepared: list[dict[str, Any]] = []

    for index, message in enumerate(messages):
        role = message.get("role")
        content = sanitize_content_for_api(message.get("content", ""))
        prepared.append({"role": role, "content": content})

        if role != "assistant":
            continue

        tool_ids = _tool_use_ids(content)
        if not tool_ids:
            continue

        next_message = messages[index + 1] if index + 1 < len(messages) else None
        next_results = (
            _tool_result_ids(next_message.get("content"))
            if next_message and next_message.get("role") == "user"
            else set()
        )

        if set(tool_ids).issubset(next_results):
            continue

        prepared.append({
            "role": "user",
            "content": _synthetic_tool_results(tool_ids),
        })

    return prepared
