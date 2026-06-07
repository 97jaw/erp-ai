"""Build context blocks from dropped chat items for the Visualize agent."""

from __future__ import annotations

import json
from typing import Any


def _truncate(value: Any, limit: int = 4000) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def summarize_dropped_items(items: list[dict[str, Any]]) -> str:
    if not items:
        return "No items dropped yet."

    blocks: list[str] = []
    for index, item in enumerate(items, start=1):
        question = (item.get("question") or "").strip()
        text = (item.get("text") or "").strip()
        viz = item.get("visualization")
        viz_type = item.get("vizType") or item.get("viz_type")
        if isinstance(viz, dict):
            viz_type = viz_type or viz.get("visual_type")

        block = [f"### Item {index}"]
        if question:
            block.append(f"User question: {question}")
        if text:
            block.append(f"Assistant text:\n{text}")
        if viz_type:
            block.append(f"Visualization type: {viz_type}")
        if viz:
            block.append(f"Visualization JSON:\n{_truncate(viz, 6000)}")
        blocks.append("\n".join(block))

    return "\n\n".join(blocks)


def format_brain_summary(brain: dict[str, Any] | None) -> str:
    if not brain or not brain.get("recommendation"):
        return ""
    inspection = brain.get("inspection") or {}
    recommendation = brain.get("recommendation") or {}
    findings = (brain.get("analysis") or {}).get("findings") or []
    lines = [
        "PRE-COMPUTED ANALYSIS (use this — do not re-run inspect/analyze/recommend unless data changed):",
        f"- Data type: {inspection.get('display_type', 'unknown')}",
        f"- Records: {inspection.get('row_count', 0)}",
        f"- Date range: {inspection.get('date_range') or 'n/a'}",
        f"- Recommended format: {recommendation.get('format_display') or recommendation.get('format')}",
        f"- Recommended layout: {recommendation.get('layout_display') or recommendation.get('layout')}",
        f"- Recommended theme: {recommendation.get('theme_display') or recommendation.get('theme')}",
        f"- Sections: {', '.join(recommendation.get('section_labels') or [])}",
    ]
    if findings:
        lines.append("- Key findings:")
        for f in findings[:5]:
            text = f.get("text") if isinstance(f, dict) else str(f)
            if text:
                lines.append(f"  • {text}")
    if recommendation.get("reasoning"):
        lines.append(f"- Reasoning: {recommendation['reasoning']}")
    lines.append(
        "When the user confirms build, call generate_pdf or generate_excel using these choices."
    )
    return "\n".join(lines)


def build_system_prompt(
    base_prompt: str,
    items: list[dict[str, Any]],
    brain: dict[str, Any] | None = None,
) -> str:
    context = summarize_dropped_items(items)
    brain_block = format_brain_summary(brain)
    parts = [base_prompt.strip(), ""]
    if brain_block:
        parts.extend([
            "═══════════════════════════════════════════════════════════",
            "ANALYSIS BRAIN",
            "═══════════════════════════════════════════════════════════",
            brain_block,
            "",
        ])
    parts.extend([
        "═══════════════════════════════════════════════════════════",
        "CONTEXT (data from main chat — do not re-fetch)",
        "═══════════════════════════════════════════════════════════",
        context,
    ])
    return "\n".join(parts)
