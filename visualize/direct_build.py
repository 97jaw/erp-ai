"""Direct report build without Claude chat loop (Layer 2)."""

from __future__ import annotations

import logging
from typing import Any

from visualize.brain import run_full_brain
from visualize.build_spec import build_excel_spec_from_brain, build_pdf_spec_from_brain
from visualize.excel_generator import generate_excel_workbook
from visualize.pdf_generator import generate_visualize_pdf
from visualize.sessions import VisualizeSession, update_session

logger = logging.getLogger(__name__)


def _normalize_format(fmt: str | None) -> str:
    key = (fmt or "pdf").strip().lower()
    if key in ("xlsx", "excel", "spreadsheet"):
        return "excel"
    return "pdf"


def ensure_session_brain(session: VisualizeSession) -> dict[str, Any]:
    """Return cached brain or compute and store on session."""
    if session.brain_inspection and session.brain_recommendation:
        return {
            "inspection": session.brain_inspection,
            "analysis": session.brain_analysis or {},
            "recommendation": session.brain_recommendation,
        }
    brain = run_full_brain(session.dropped_items)
    update_session(
        session.session_id,
        brain_inspection=brain.get("inspection"),
        brain_analysis=brain.get("analysis"),
        brain_recommendation=brain.get("recommendation"),
    )
    return brain


def execute_direct_build(
    session: VisualizeSession,
    *,
    output_format: str | None = None,
    theme: str | None = None,
    layout: str | None = None,
    include_logo: bool = True,
    page_numbers: bool = True,
    watermark: str | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    if not session.dropped_items:
        return {"error": "no_items", "message": "Drop chat data before building."}

    brain = ensure_session_brain(session)
    inspection = brain["inspection"]
    analysis = brain["analysis"]
    recommendation = brain["recommendation"]

    fmt = _normalize_format(output_format or recommendation.get("format"))
    resolved_theme = theme or recommendation.get("theme") or "elegant_gold"
    resolved_layout = layout or recommendation.get("layout")

    if fmt == "excel":
        spec = build_excel_spec_from_brain(
            inspection=inspection,
            recommendation=recommendation,
            dropped_items=session.dropped_items,
            title=title,
        )
        result = generate_excel_workbook(spec, session_id=session.session_id)
        if "error" not in result:
            update_session(session.session_id, output_type="excel", last_output=result)
        return result

    spec = build_pdf_spec_from_brain(
        inspection=inspection,
        analysis=analysis,
        recommendation=recommendation,
        dropped_items=session.dropped_items,
        theme=resolved_theme,
        layout=resolved_layout,
        include_logo=include_logo,
        page_numbers=page_numbers,
        watermark=watermark,
        title=title,
    )
    result = generate_visualize_pdf(spec, session_id=session.session_id)
    if "error" not in result:
        update_session(
            session.session_id,
            output_type="pdf",
            theme=resolved_theme,
            layout=resolved_layout,
            last_output=result,
        )
    return result
