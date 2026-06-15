"""Shared preflight UI block helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PreflightResult:
    text: str
    ui_blocks: list[dict[str, Any]]
    suggestions: list[str]


def pill_block(
    prompt: str,
    options: list[dict[str, Any]],
    *,
    allow_typed_input: bool = True,
) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    for option in options:
        entry: dict[str, Any] = {"id": option["id"], "label": option["label"]}
        if option.get("icon"):
            entry["icon"] = option["icon"]
        normalized.append(entry)
    return {
        "type": "pill_select",
        "prompt": prompt,
        "options": normalized,
        "mode": "single",
        "allow_typed_input": allow_typed_input,
    }


def date_quick_block(prompt: str) -> dict[str, Any]:
    from gateway.agent.ui_blocks import normalize_ui_block

    return normalize_ui_block(
        {
            "block_type": "date_quick",
            "prompt": prompt,
        }
    ) or {"type": "date_quick", "prompt": prompt}
