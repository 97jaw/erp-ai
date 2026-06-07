"""HTML section renderers for Visualize-themed PDFs."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from gateway.pdf_reports import (
    _format_number,
    _render_section_html,
    _section_data,
)


def render_section_html(
    section: dict[str, Any],
    theme: dict[str, Any],
    assets_dir: Path,
    rtl: bool,
) -> str:
    section_type = section.get("type")
    layout_class = str(section.get("layout_class") or "")
    title = escape(str(section.get("title") or ""))
    content = escape(str(section.get("content") or ""))
    data = _section_data(section)
    css = theme.get("css") or {}
    theme_key = "dark" if css.get("background", "").lower() in {"#0d1428", "#0a0f1e"} else "light"

    if section_type == "cover":
        primary = css.get("primary", "#1a2744")
        return (
            f'<section class="cover {layout_class}">'
            f'<div class="cover-band" style="background:{primary}"></div>'
            f"<h1>{title or 'Elrace Report'}</h1>"
            f'<p class="muted">{content}</p>'
            f"</section>"
        )
