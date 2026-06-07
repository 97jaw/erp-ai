"""Map Layer 1 brain output + UI options → PDF/Excel generation specs (Layer 2)."""

from __future__ import annotations

from typing import Any

from visualize.data_resolver import collect_tables_from_items, enrich_pdf_sections

_LAYOUT_MAP = {
    "executive_summary": "executive",
    "detailed_analytical": "detailed",
    "comparative": "comparative",
    "standard_report": "executive",
    "boardroom": "presentation",
    "single_sheet": "executive",
    "multi_sheet": "detailed",
    "pivot_ready": "detailed",
}

_CHART_TYPE_MAP = {
    "line_chart": "line_chart",
    "donut_chart": "pie_chart",
    "grouped_bar": "comparison_chart",
    "horizontal_bar": "bar_chart",
    "kpi_grid": "kpi_grid",
}


def map_recommendation_layout(layout: str | None) -> str:
    if not layout:
        return "executive"
    key = layout.strip().lower().replace(" ", "_")
    if key in {"executive", "detailed", "comparative", "presentation"}:
        return key
    return _LAYOUT_MAP.get(key, "executive")


def _finding_lines(analysis: dict[str, Any], limit: int = 5) -> str:
    findings = analysis.get("findings") or []
    lines = []
    for item in findings[:limit]:
        if isinstance(item, dict):
            lines.append(str(item.get("text") or item.get("message") or ""))
        else:
            lines.append(str(item))
    return "\n".join(line for line in lines if line.strip())


def recommendation_to_pdf_sections(
    *,
    inspection: dict[str, Any],
    analysis: dict[str, Any],
    recommendation: dict[str, Any],
    dropped_items: list[dict[str, Any]],
    title: str,
) -> list[dict[str, Any]]:
    """Convert brain recommendation sections into PDF generator section dicts."""
    sections: list[dict[str, Any]] = []
    rec_sections = recommendation.get("sections") or []

    for rec in sorted(rec_sections, key=lambda s: s.get("order", 99)):
        stype = str(rec.get("type") or "")
        config = rec.get("config") if isinstance(rec.get("config"), dict) else {}
        label = str(rec.get("label") or stype.replace("_", " ").title())

        if stype == "cover":
            sections.append({
                "type": "cover",
                "title": config.get("title") or inspection.get("report_subject") or title,
                "content": config.get("period") or inspection.get("date_range") or "",
            })
            continue

        if stype == "executive_summary":
            findings = config.get("findings") or analysis.get("findings") or []
            text_parts = []
            for f in findings[:5]:
                if isinstance(f, dict):
                    text_parts.append(str(f.get("text") or ""))
                else:
                    text_parts.append(str(f))
            body = "\n".join(p for p in text_parts if p.strip())
            if not body:
                body = _finding_lines(analysis) or recommendation.get("reasoning", "")
            sections.append({
                "type": "executive_summary",
                "title": label,
                "content": body[:8000],
            })
            continue

        if stype == "kpi_dashboard":
            metrics = config.get("metrics") or inspection.get("metrics") or []
            kpis = []
            for m in metrics:
                if isinstance(m, dict):
                    kpis.append({
                        "label": m.get("label") or m.get("name", "Metric"),
                        "value": m.get("value", 0),
                        "unit": m.get("unit", ""),
                        "trend": m.get("trend", ""),
                    })
            if not kpis:
                for item in dropped_items:
                    viz = item.get("visualization") or {}
                    data = viz.get("data") if isinstance(viz, dict) else {}
                    raw_kpis = (viz.get("kpis") or data.get("kpis") or {}) if isinstance(data, dict) else {}
                    if isinstance(raw_kpis, dict):
                        for key, val in raw_kpis.items():
                            kpis.append({
                                "label": key.replace("_", " ").title(),
                                "value": val,
                                "unit": inspection.get("currency", ""),
                            })
                        break
            if kpis:
                sections.append({
                    "type": "kpi_grid",
                    "title": label,
                    "data": {"kpis": kpis},
                })
            continue

        if stype == "primary_chart":
            chart_type = str(config.get("type") or "bar_chart")
            pdf_chart = _CHART_TYPE_MAP.get(chart_type, "bar_chart")
            chart_data = _chart_data_from_items(dropped_items, inspection)
            if chart_data:
                sections.append({
                    "type": pdf_chart,
                    "title": label,
                    "data": chart_data,
                })
            continue

        if stype == "insights":
            parts = []
            for key in ("concentrations", "outliers", "thresholds"):
                for entry in (analysis.get(key) or config.get(key) or []):
                    if isinstance(entry, dict):
                        parts.append(str(entry.get("text") or entry.get("message") or entry))
                    else:
                        parts.append(str(entry))
            if parts:
                sections.append({
                    "type": "insights_callout",
                    "title": label,
                    "content": "\n".join(parts[:12])[:4000],
                })
            continue

        if stype == "data_table":
            tables = collect_tables_from_items(dropped_items)
            if tables:
                table = tables[0]
                rows = list(table.get("rows") or [])
                top_n = config.get("show_top_n")
                if top_n and len(rows) > top_n:
                    rows = rows[:top_n]
                sections.append({
                    "type": "table",
                    "title": table.get("title") or label,
                    "data": {
                        "headers": table.get("headers") or [],
                        "rows": rows,
                    },
                })
            continue

        if stype == "recommendations":
            items = config.get("items") or []
            text = "\n".join(f"• {i}" if isinstance(i, str) else str(i) for i in items[:10])
            if text:
                sections.append({
                    "type": "text_block",
                    "title": label,
                    "content": text,
                })

    if not sections:
        sections = [{"type": "cover", "title": title, "content": inspection.get("date_range") or ""}]

    return enrich_pdf_sections(sections, dropped_items)


def _chart_data_from_items(
    items: list[dict[str, Any]],
    inspection: dict[str, Any],
) -> dict[str, Any] | None:
    for item in items:
        viz = item.get("visualization")
        if not isinstance(viz, dict):
            continue
        data = viz.get("data") if isinstance(viz.get("data"), dict) else {}
        if data.get("summary_chart"):
            return data["summary_chart"]
        labels = data.get("labels")
        values = data.get("values")
        if isinstance(labels, list) and isinstance(values, list) and labels:
            return {"labels": labels, "values": values, "title": viz.get("label") or ""}
        rows = data.get("rows") or data.get("all_rows") or []
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            first = rows[0]
            keys = [k for k in first if k not in ("id",)]
            if len(keys) >= 2:
                label_key, value_key = keys[0], keys[1]
                return {
                    "labels": [str(r.get(label_key, "")) for r in rows[:20]],
                    "values": [float(r.get(value_key, 0) or 0) for r in rows[:20]],
                }
    return None


def build_pdf_spec_from_brain(
    *,
    inspection: dict[str, Any],
    analysis: dict[str, Any],
    recommendation: dict[str, Any],
    dropped_items: list[dict[str, Any]],
    theme: str,
    layout: str,
    include_logo: bool = True,
    page_numbers: bool = True,
    watermark: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    report_title = (
        title
        or inspection.get("report_subject")
        or inspection.get("display_type")
        or "Elrace Report"
    )
    sections = recommendation_to_pdf_sections(
        inspection=inspection,
        analysis=analysis,
        recommendation=recommendation,
        dropped_items=dropped_items,
        title=str(report_title),
    )
    return {
        "title": str(report_title),
        "subtitle": inspection.get("display_type"),
        "date_range": inspection.get("date_range"),
        "language": recommendation.get("language") or inspection.get("language", "en"),
        "theme": theme,
        "visualize_theme": theme,
        "layout": map_recommendation_layout(layout or recommendation.get("layout")),
        "include_logo": include_logo,
        "page_numbers": page_numbers,
        "watermark": watermark if watermark and watermark != "none" else None,
        "sections": sections,
    }


def build_excel_spec_from_brain(
    *,
    inspection: dict[str, Any],
    recommendation: dict[str, Any],
    dropped_items: list[dict[str, Any]],
    title: str | None = None,
) -> dict[str, Any]:
    tables = collect_tables_from_items(dropped_items)
    headers: list[str] = []
    rows: list[Any] = []
    if tables:
        headers = list(tables[0].get("headers") or [])
        rows = list(tables[0].get("rows") or [])

    layout = str(recommendation.get("layout") or "single_sheet")
    structure = "pivot_ready" if "pivot" in layout else (
        "multi_sheet" if "multi" in layout else "single_sheet"
    )

    return {
        "title": title or inspection.get("report_subject") or "Elrace Export",
        "structure": structure,
        "columns": headers,
        "rows": rows,
        "data_context": {"headers": headers, "rows": rows},
        "formatting": {"highlight_negatives": True},
    }
