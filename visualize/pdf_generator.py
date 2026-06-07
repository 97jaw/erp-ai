"""Themed PDF generation for the Visualize agent (Phase 3–4)."""

from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fpdf import FPDF

from gateway.pdf_reports import (
    REPORTS_DIR,
    _build_preview_image,
    _normalize_pdf_spec,
    _render_section,
    _sanitize_pdf_text,
)
from visualize.layouts import apply_layout, resolve_layout
from visualize.pdf_options import PdfRenderOptions, parse_pdf_options
from visualize.section_renderers import render_section_html
from visualize.themes import resolve_theme, theme_css_bundle, theme_fpdf_palette

try:
    from jinja2 import Template
except ImportError:  # pragma: no cover
    Template = None  # type: ignore[assignment,misc]

try:
    from weasyprint import HTML
except ImportError:  # pragma: no cover
    HTML = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

VISUALIZE_DIR = Path(__file__).resolve().parent
DEFAULT_LOGO_PATH = VISUALIZE_DIR / "assets" / "elrace_logo.svg"

VISUALIZE_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="{{ language }}" dir="{{ direction }}">
<head>
  <meta charset="utf-8" />
  <style>
    @page {
      size: A4;
      margin: 22mm 16mm 20mm 16mm;
      {% if options.page_numbers %}
      @bottom-right {
        content: "Page " counter(page) " / " counter(pages);
        font-family: {{ theme.body_font }};
        font-size: 9pt;
        color: {{ theme.muted }};
      }
      {% endif %}
      {% if options.include_logo %}
      @top-left {
        content: element(report-header);
      }
      {% endif %}
    }
    body {
      font-family: {{ theme.body_font }};
      color: {{ theme.text }};
      background: {{ theme.background }};
      line-height: 1.45;
      margin: 0;
    }
    {% if options.include_logo %}
    .report-header {
      position: running(report-header);
      display: flex;
      align-items: center;
      gap: 10px;
      padding-bottom: 6px;
      border-bottom: 1px solid color-mix(in srgb, {{ theme.muted }} 35%, transparent);
    }
    .report-header img { height: 28px; width: auto; }
    .report-header .header-title {
      font-size: 11pt;
      font-weight: 600;
      color: {{ theme.primary }};
    }
    {% endif %}
    {% if options.watermark %}
    .watermark-layer {
      position: fixed;
      top: 42%;
      left: 50%;
      width: 100%;
      text-align: center;
      transform: translate(-50%, -50%) rotate(-32deg);
      font-size: 64pt;
      font-weight: 700;
      letter-spacing: 0.2em;
      color: {{ theme.muted }};
      opacity: 0.07;
      z-index: -1;
      pointer-events: none;
    }
    {% endif %}
    h1, h2, h3 { font-family: {{ theme.header_font }}; color: {{ theme.primary }}; }
    .muted { color: {{ theme.muted }}; }
    .cover { margin-top: 4mm; padding-bottom: 12mm; }
    .cover-logo { height: 56px; margin-bottom: 16px; }
    .cover-band { height: 6px; border-radius: 3px; margin-bottom: 18px; }
    .cover h1 { font-size: 28px; margin: 0 0 8px; }
    .kpi-grid-inner {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
      margin-top: 12px;
    }
    .kpi-card {
      background: {{ theme.section_bg }};
      border-left: 4px solid {{ theme.accent }};
      padding: 12px 14px;
      border-radius: 4px;
    }
    .kpi-card.positive { border-left-color: {{ theme.positive }}; }
    .kpi-card.negative { border-left-color: {{ theme.negative }}; }
    .kpi-label { display: block; font-size: 11px; color: {{ theme.muted }}; }
    .kpi-value { display: block; font-size: 18px; font-weight: 600; margin-top: 4px; }
    table { width: 100%; border-collapse: collapse; margin: 12px 0; }
    th, td { border: 1px solid #d8deea; padding: 6px 8px; text-align: {{ text_align }}; }
    th {
      background: {{ theme.table_header_bg }};
      color: {{ theme.table_header_fg }};
    }
    tr:nth-child(even) td { background: {{ theme.table_row_alt }}; }
    .callout {
      background: {{ theme.section_bg }};
      border-left: 4px solid {{ theme.accent }};
      padding: 12px 16px;
      margin: 12px 0;
    }
    .chart { margin: 16px 0; text-align: center; }
    .chart img { max-width: 100%; height: auto; }
    .page-break { page-break-before: always; }
    .cover-executive h1 { font-size: 32px; }
    .presentation-block h2, .presentation-block h3 { font-size: 22px; }
  </style>
</head>
<body>
  {% if options.watermark %}
  <div class="watermark-layer">{{ options.watermark }}</div>
  {% endif %}
  {% if options.include_logo and logo_src %}
  <header class="report-header">
    <img src="{{ logo_src }}" alt="Company logo" />
    <span class="header-title">{{ report_title }}</span>
  </header>
  {% endif %}
  {% for block in blocks %}
    {{ block | safe }}
  {% endfor %}
</body>
</html>
"""


def _chart_theme_key(theme: dict[str, Any]) -> str:
    return "dark" if theme.get("id") == "modern_dark" else "light"


def _fpdf_theme_bundle(theme: dict[str, Any]) -> dict[str, Any]:
    palette = theme_fpdf_palette(theme)
    return {**palette, "css": theme_css_bundle(theme)}


def _prepare_spec(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, PdfRenderOptions]:
    normalized = _normalize_pdf_spec(dict(spec))
    theme = resolve_theme(normalized.get("visualize_theme") or normalized.get("theme"))
    layout_id = resolve_layout(normalized.get("layout"))
    options = parse_pdf_options(normalized)
    meta = {
        "title": normalized.get("title"),
        "subtitle": normalized.get("subtitle"),
        "date_range": normalized.get("date_range"),
    }
    normalized["sections"] = apply_layout(normalized.get("sections") or [], layout_id, meta)
    normalized["visualize_theme"] = theme["id"]
    normalized["layout"] = layout_id
    return normalized, theme, layout_id, options


def _resolve_logo_file(spec: dict[str, Any], options: PdfRenderOptions, assets_dir: Path) -> str | None:
    if not options.include_logo:
        return None

    if options.logo_url:
        source = Path(options.logo_url)
        if not source.is_absolute():
            source = Path.cwd() / source
        if source.is_file():
            dest = assets_dir / f"logo{source.suffix.lower()}"
            shutil.copy(source, dest)
            return dest.name

    if DEFAULT_LOGO_PATH.is_file():
        dest = assets_dir / "elrace_logo.svg"
        shutil.copy(DEFAULT_LOGO_PATH, dest)
        return dest.name

    return None


@dataclass
class _RenderContext:
    spec: dict[str, Any]
    theme: dict[str, Any]
    options: PdfRenderOptions
    assets_dir: Path
    logo_src: str | None


class VisualizeFPDF(FPDF):
    """FPDF with optional header logo, footer page numbers, and watermark."""

    def __init__(
        self,
        fpdf_theme: dict[str, Any],
        options: PdfRenderOptions,
        logo_path: Path | None,
        report_title: str,
        watermark: str | None,
    ) -> None:
        super().__init__()
        self._fpdf_theme = fpdf_theme
        self._options = options
        self._logo_path = logo_path
        self._report_title = report_title
        self._watermark = watermark

    def header(self) -> None:
        if self._watermark:
            self._draw_watermark()
        if self._options.include_logo and self._logo_path and self._logo_path.is_file():
            suffix = self._logo_path.suffix.lower()
            if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg"}:
                try:
                    self.image(str(self._logo_path), x=10, y=8, h=10)
                    self.set_xy(32, 10)
                    self.set_font("Helvetica", "B", 9)
                    self.set_text_color(*self._fpdf_theme["text"])
                    self.cell(0, 6, _sanitize_pdf_text(self._report_title[:60]))
                    self.ln(14)
                except Exception:
                    self.ln(4)
            else:
                self.ln(4)
        elif self._watermark:
            self.ln(2)

    def footer(self) -> None:
        if not self._options.page_numbers:
            return
        self.set_y(-12)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*self._fpdf_theme["muted"])
        self.cell(0, 8, _sanitize_pdf_text(f"Page {self.page_no()}"), align="C")

    def _draw_watermark(self) -> None:
        if not self._watermark:
            return
        self.set_font("Helvetica", "B", 40)
        muted = self._fpdf_theme["muted"]
        self.set_text_color(muted[0], muted[1], muted[2])
        with self.rotation(35, x=self.w / 2, y=self.h / 2):
            self.set_xy(self.w / 2 - 50, self.h / 2 - 10)
            self.cell(100, 10, _sanitize_pdf_text(self._watermark), align="C")


class PDFGenerator:
    """Generates themed Visualize PDFs with logo, page numbers, and watermark."""

    def __init__(self, theme_id: str | None = None) -> None:
        self.theme = resolve_theme(theme_id)

    def generate(
        self,
        spec: dict[str, Any],
        session_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            prepared, theme, layout_id, options = _prepare_spec(spec)
            self.theme = theme

            stem = uuid4().hex
            output_path = REPORTS_DIR / f"{stem}.pdf"
            preview_path = REPORTS_DIR / f"{stem}-preview.png"
            assets_dir = REPORTS_DIR / f"{stem}-assets"
            assets_dir.mkdir(parents=True, exist_ok=True)

            logo_src = _resolve_logo_file(prepared, options, assets_dir)
            ctx = _RenderContext(
                spec=prepared,
                theme=theme,
                options=options,
                assets_dir=assets_dir,
                logo_src=logo_src,
            )

            html = self._build_html(ctx)
            page_count = 1
            if not self._render_weasyprint(html, output_path, assets_dir):
                page_count = self._render_fpdf(ctx, output_path)

            preview_url = None
            if _build_preview_image(prepared, preview_path, _chart_theme_key(theme)):
                preview_url = f"/reports/{preview_path.name}"

            return {
                "pdf_url": f"/reports/{output_path.name}",
                "preview_image": preview_url,
                "size_bytes": output_path.stat().st_size,
                "generated_at": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "title": prepared.get("title"),
                "page_count": page_count,
                "language": prepared.get("language", "en"),
                "theme": theme["id"],
                "layout": layout_id,
                "format": "pdf",
                "include_logo": options.include_logo,
                "page_numbers": options.page_numbers,
                "watermark": options.watermark,
                "spec_preview": json.dumps(
                    {
                        "theme": theme["id"],
                        "layout": layout_id,
                        "sections": len(prepared.get("sections") or []),
                        "include_logo": options.include_logo,
                        "page_numbers": options.page_numbers,
                        "watermark": options.watermark,
                    },
                    default=str,
                )[:500],
            }
        except Exception as exc:  # pragma: no cover
            logger.exception("Visualize PDF generation failed")
            return {
                "error": "pdf_generation_failed",
                "message": str(exc),
                "session_id": session_id,
                "title": spec.get("title"),
            }

    def _build_html(self, ctx: _RenderContext) -> str:
        if Template is None:
            return ""
        css = theme_css_bundle(ctx.theme)
        theme_payload = {**css, "chart_colors": ctx.theme.get("chart_colors") or []}
        rtl = ctx.spec.get("language") == "ar"
        blocks = [
            render_section_html(
                section,
                {"css": css, "id": ctx.theme["id"], "logo_src": ctx.logo_src},
                ctx.assets_dir,
                rtl,
            )
            for section in (ctx.spec.get("sections") or [])
        ]
        template = Template(VISUALIZE_HTML_TEMPLATE)
        return template.render(
            language=ctx.spec.get("language") or "en",
            direction="rtl" if rtl else "ltr",
            text_align="right" if rtl else "left",
            theme=theme_payload,
            options=ctx.options,
            logo_src=ctx.logo_src,
            report_title=ctx.spec.get("title") or "Elrace Report",
            blocks=blocks,
        )

    def _render_weasyprint(self, html: str, output_path: Path, assets_dir: Path) -> bool:
        if HTML is None or not html:
            return False
        try:
            HTML(string=html, base_url=str(assets_dir)).write_pdf(str(output_path))
            return output_path.exists()
        except Exception as exc:  # pragma: no cover
            logger.warning("WeasyPrint visualize PDF failed: %s", exc)
            return False

    def _render_fpdf(self, ctx: _RenderContext, output_path: Path) -> int:
        fpdf_theme = _fpdf_theme_bundle(ctx.theme)
        chart_key = _chart_theme_key(ctx.theme)
        logo_path = ctx.assets_dir / ctx.logo_src if ctx.logo_src else None

        pdf = VisualizeFPDF(
            fpdf_theme=fpdf_theme,
            options=ctx.options,
            logo_path=logo_path,
            report_title=str(ctx.spec.get("title") or "Elrace Report"),
            watermark=ctx.options.watermark,
        )
        pdf.set_auto_page_break(auto=True, margin=18)
        pdf.add_page()
        pdf.set_fill_color(*fpdf_theme["background"])
        pdf.rect(0, 0, pdf.w, pdf.h, style="F")
        pdf.set_text_color(*fpdf_theme["text"])

        top_margin = 22 if ctx.options.include_logo and logo_path else 12
        pdf.set_y(top_margin)

        for section in ctx.spec.get("sections") or []:
            _render_section(pdf, section, fpdf_theme, ctx.assets_dir, chart_key)

        pdf.output(str(output_path))
        return max(1, pdf.page_no())


def generate_visualize_pdf(
    spec: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    """Backward-compatible entry point."""
    theme_id = spec.get("visualize_theme") or spec.get("theme")
    return PDFGenerator(theme_id).generate(spec, session_id=session_id)
