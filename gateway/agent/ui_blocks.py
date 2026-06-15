"""Normalize agent UI block tool input to frontend-compatible payloads."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from typing import Any

from gateway.reports.ui_blocks import (
    DatePreset,
    DateQuickBlock,
    FormatSelectBlock,
    PillOption,
    PillSelectBlock,
)


def _date_presets() -> list[DatePreset]:
    today = date.today()
    first_this = today.replace(day=1)
    last_this = today.replace(day=monthrange(today.year, today.month)[1])
    last_month_end = first_this - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    q = (today.month - 1) // 3
    q_start = date(today.year, q * 3 + 1, 1)
    q_end_month = q_start.month + 2
    q_end = date(today.year, q_end_month, monthrange(today.year, q_end_month)[1])
    lq_end = q_start - timedelta(days=1)
    lq_start = date(lq_end.year, ((lq_end.month - 1) // 3) * 3 + 1, 1)
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)
    last_year_start = date(today.year - 1, 1, 1)
    last_year_end = date(today.year - 1, 12, 31)

    def iso(d: date) -> str:
        return d.isoformat()

    return [
        DatePreset("this_month", "This Month", iso(first_this), iso(last_this)),
        DatePreset("last_month", "Last Month", iso(last_month_start), iso(last_month_end)),
        DatePreset("this_quarter", "This Quarter", iso(q_start), iso(q_end)),
        DatePreset("last_quarter", "Last Quarter", iso(lq_start), iso(lq_end)),
        DatePreset("this_year", "This Year", iso(year_start), iso(year_end)),
        DatePreset("last_year", "Last Year", iso(last_year_start), iso(last_year_end)),
    ]


def normalize_ui_block(tool_input: dict[str, Any]) -> dict[str, Any] | None:
    """Convert show_ui_block tool input to SSE ui_block payload."""
    block_type = (
        tool_input.get("block_type")
        or tool_input.get("type")
        or ""
    ).strip()
    prompt = str(tool_input.get("prompt") or tool_input.get("label") or "").strip()

    if block_type == "pill_select":
        raw_options = tool_input.get("options") or []
        options = [
            PillOption(id=str(o.get("id", "")), label=str(o.get("label", "")))
            for o in raw_options
            if isinstance(o, dict)
        ]
        block = PillSelectBlock(
            options=options,
            mode=str(tool_input.get("mode") or "single"),
            allow_typed_input=bool(tool_input.get("allow_typed_input", True)),
            prompt=prompt,
        )
        return block.to_dict()

    if block_type == "date_quick":
        return DateQuickBlock(presets=_date_presets(), prompt=prompt).to_dict()

    if block_type == "format_select":
        return FormatSelectBlock(
            options=list(tool_input.get("options") or ["pdf", "excel", "both"]),
            prompt=prompt,
        ).to_dict()

    if block_type == "toggle":
        return {
            "type": "toggle",
            "prompt": prompt,
            "options": tool_input.get("options")
            or [{"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}],
        }

    if block_type == "text_input":
        return {"type": "text_input", "prompt": prompt}

    if block_type == "search_picker":
        return {
            "type": "search_picker",
            "prompt": prompt,
            "model": tool_input.get("model"),
            "placeholder": tool_input.get("placeholder", "Search..."),
        }

    if block_type:
        return {"type": block_type, "prompt": prompt, "raw": tool_input}

    return None
