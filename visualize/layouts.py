"""PDF layout templates for Visualize exports."""

from __future__ import annotations

from typing import Any

LAYOUTS: list[dict[str, str]] = [
    {
        "id": "executive",
        "name": "Executive Summary",
        "description": "Cover plus KPI dashboard — 1–2 pages, leadership focus",
    },
    {
        "id": "detailed",
        "name": "Detailed Report",
        "description": "Multi-section breakdown with page breaks between topics",
    },
    {
        "id": "comparative",
        "name": "Comparative",
        "description": "Period comparison tables and charts emphasized",
    },
    {
        "id": "presentation",
        "name": "Presentation",
        "description": "Large type, fewer tables — slide-deck feel",
    },
]

_SECTION_ORDER = {
    "cover": 0,
    "section_header": 10,
    "executive_summary": 20,
    "insights_callout": 25,
    "kpi_grid": 30,
    "bar_chart": 40,
    "line_chart": 41,
    "pie_chart": 42,
    "comparison_chart": 35,
    "table": 50,
    "analysis": 55,
    "text_block": 56,
    "footer": 90,
    "page_break": 80,
    "appendix": 85,
}


def list_layouts() -> list[dict[str, str]]:
    return list(LAYOUTS)


def resolve_layout(layout_id: str | None) -> str:
    if not layout_id:
        return "executive"
    normalized = layout_id.strip().lower().replace(" ", "_")
    if any(layout["id"] == normalized for layout in LAYOUTS):
        return normalized
    return "executive"


def _sort_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        sections,
        key=lambda section: _SECTION_ORDER.get(str(section.get("type") or ""), 60),
    )


def apply_layout(
    sections: list[dict[str, Any]],
    layout_id: str | None,
    meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Reorder sections and inject page breaks per layout template."""
    layout = resolve_layout(layout_id)
    ordered = _sort_sections([dict(section) for section in sections if isinstance(section, dict)])

    if layout == "executive":
        return _apply_executive_layout(ordered, meta or {})

    if layout == "detailed":
        return _apply_detailed_layout(ordered, meta or {})

    if layout == "comparative":
        return _apply_comparative_layout(ordered, meta or {})

    if layout == "presentation":
        return _apply_presentation_layout(ordered, meta or {})

    return ordered


def _apply_executive_layout(
    sections: list[dict[str, Any]],
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    cover_done = False
    for section in sections:
        stype = section.get("type")
        if stype == "cover":
            item = dict(section)
            item["layout_class"] = "cover-executive"
            result.append(item)
            cover_done = True
            continue
        if not cover_done and stype != "page_break":
            result.append({
                "type": "cover",
                "title": meta.get("title") or "Elrace Report",
                "content": meta.get("subtitle") or "Executive Summary",
                "layout_class": "cover-executive",
            })
            cover_done = True
        if stype == "kpi_grid":
            item = dict(section)
            item["layout_class"] = "kpi-executive"
            result.append(item)
            continue
        result.append(section)
    return result


def _apply_detailed_layout(
    sections: list[dict[str, Any]],
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    last_type: str | None = None
    for section in sections:
        stype = str(section.get("type") or "")
        if last_type and stype in {
            "section_header",
            "executive_summary",
            "kpi_grid",
            "table",
            "comparison_chart",
        } and stype != last_type:
            result.append({"type": "page_break"})
        item = dict(section)
        item["layout_class"] = "section-detailed"
        result.append(item)
        last_type = stype
    return result


def _apply_comparative_layout(
    sections: list[dict[str, Any]],
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    charts = [s for s in sections if s.get("type") == "comparison_chart"]
    others = [s for s in sections if s.get("type") != "comparison_chart"]
    result: list[dict[str, Any]] = []
    for section in _sort_sections(others):
        if section.get("type") == "cover":
            item = dict(section)
            item["layout_class"] = "cover-comparative"
            result.append(item)
        else:
            result.append(section)
    for chart in charts:
        item = dict(chart)
        item["layout_class"] = "chart-comparative"
        result.append(item)
    if not charts and meta.get("title"):
        result.append({
            "type": "section_header",
            "title": "Period Comparison",
            "layout_class": "chart-comparative",
        })
    return result


def _apply_presentation_layout(
    sections: list[dict[str, Any]],
    meta: dict[str, Any],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for section in sections:
        item = dict(section)
        item["layout_class"] = f"presentation-{section.get('type', 'block')}"
        result.append(item)
    return result
