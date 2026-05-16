from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from uuid import uuid4

from fpdf import FPDF

try:
    from jinja2 import Template
except ImportError:  # pragma: no cover
    Template = None  # type: ignore[assignment,misc]

try:
    from weasyprint import HTML
except ImportError:  # pragma: no cover
    HTML = None  # type: ignore[assignment,misc]

REPORTS_DIR = Path(__file__).resolve().parent.parent / "static" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

PDF_THEMES = {
    "light": {
        "background": (255, 255, 255),
        "text": (26, 31, 58),
        "accent": (201, 168, 76),
        "muted": (90, 99, 120),
        "css": {
            "background": "#ffffff",
            "text": "#1a1f3a",
            "accent": "#c9a84c",
            "muted": "#5a6378",
            "section_bg": "#f4f7fc",
        },
        "chart_colors": ["#c9a84c", "#4ecdc4", "#5b6fe6", "#ff6b6b"],
    },
    "dark": {
        "background": (10, 15, 30),
        "text": (232, 234, 246),
        "accent": (212, 175, 55),
        "muted": (160, 168, 190),
        "css": {
            "background": "#0a0f1e",
            "text": "#e8eaf6",
            "accent": "#d4af37",
            "muted": "#a0a8be",
            "section_bg": "#141b2e",
        },
        "chart_colors": ["#d4af37", "#4ecdc4", "#8b5cf6", "#ff6b6b"],
    },
}

PDF_TEXT_REPLACEMENTS = {
    "\u2022": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2026": "...",
    "\u00a0": " ",
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="{{ language }}" dir="{{ direction }}">
<head>
  <meta charset="utf-8" />
  <style>
    @page { size: A4; margin: 18mm; }
    body {
      font-family: Inter, "Noto Naskh Arabic", sans-serif;
      color: {{ theme.text }};
      background: {{ theme.background }};
      line-height: 1.45;
    }
    h1, h2, h3 { color: {{ theme.accent }}; }
    .cover { margin-top: 35mm; }
    .muted { color: {{ theme.muted }}; }
    .callout {
      background: {{ theme.section_bg }};
      border-left: 4px solid {{ theme.accent }};
      padding: 12px 16px;
      margin: 12px 0;
    }
    table { width: 100%; border-collapse: collapse; margin: 12px 0; }
    th, td { border: 1px solid #d8deea; padding: 6px 8px; text-align: {{ text_align }}; }
    th { background: {{ theme.section_bg }}; }
    .chart { margin: 16px 0; text-align: center; }
    .chart img { max-width: 100%; height: auto; }
    .page-break { page-break-before: always; }
  </style>
</head>
<body>
  <section class="cover">
    <h1>{{ title }}</h1>
    {% if subtitle %}<p class="muted">{{ subtitle }}</p>{% endif %}
    {% if date_range %}<p class="muted">{{ date_range }}</p>{% endif %}
  </section>
  {% for block in blocks %}
    {{ block | safe }}
  {% endfor %}
</body>
</html>
"""


def _format_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1000:
        return f"{number:,.0f}"
    return f"{number:,.2f}"


def _sanitize_pdf_text(value: Any) -> str:
    text = str(value or "")
    for source, replacement in PDF_TEXT_REPLACEMENTS.items():
        text = text.replace(source, replacement)
    text = re.sub(r"^[ \t]*•", "-", text, flags=re.MULTILINE)
    text = text.replace("•", "-")
    sanitized: list[str] = []
    for character in text:
        try:
            character.encode("latin-1")
            sanitized.append(character)
        except UnicodeEncodeError:
            sanitized.append("?")
    return "".join(sanitized)


def _section_data(section: dict[str, Any]) -> Any:
    return section.get("data") or {}


def _comparison_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        rows = data.get("periods") or data.get("rows") or data.get("series") or []
        return [row for row in rows if isinstance(row, dict)]
    return []


def _financial_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("rows") or data.get("accounts") or []
    else:
        rows = []
    return [
        row for row in rows
        if isinstance(row, dict) and ("account" in row or "name" in row)
    ]


def _chart_image_path(
    section_type: str,
    data: dict[str, Any],
    theme_name: str,
    assets_dir: Path,
) -> Path | None:
    labels = data.get("labels") or []
    values = [float(value or 0) for value in (data.get("values") or [])]
    if not labels or not values:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover
        return None

    colors = PDF_THEMES[theme_name]["chart_colors"]
    figure, axis = plt.subplots(figsize=(7.2, 3.6))
    if section_type == "pie_chart":
        axis.pie(values, labels=labels, colors=colors[: len(values)], autopct="%1.0f%%")
    elif section_type == "line_chart":
        axis.plot(labels, values, color=colors[0], linewidth=2.5, marker="o")
        axis.grid(alpha=0.2)
    else:
        axis.bar(labels, values, color=colors[: len(values)])
        axis.grid(axis="y", alpha=0.2)
    axis.set_title(_sanitize_pdf_text(data.get("title") or section_type.replace("_", " ").title()))
    plt.xticks(rotation=20, ha="right")
    plt.tight_layout()

    image_path = assets_dir / f"{uuid4().hex}.png"
    figure.savefig(image_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return image_path


def _comparison_chart_image(
    rows: list[dict[str, Any]],
    theme_name: str,
    assets_dir: Path,
    title: str,
) -> Path | None:
    if not rows:
        return None

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover
        return None

    labels = [str(row.get("period") or row.get("label") or f"Period {index + 1}") for index, row in enumerate(rows)]
    metrics = [
        ("revenue", "Revenue"),
        ("expenses", "Expenses"),
        ("profit", "Profit"),
    ]
    colors = PDF_THEMES[theme_name]["chart_colors"]
    figure, axis = plt.subplots(figsize=(7.2, 3.8))
    positions = list(range(len(labels)))
    width = 0.24
    for index, (key, label) in enumerate(metrics):
        values = [float(row.get(key, 0) or 0) for row in rows]
        offset = (index - 1) * width
        axis.bar([position + offset for position in positions], values, width=width, label=label, color=colors[index % len(colors)])
    axis.set_xticks(positions)
    axis.set_xticklabels(labels, rotation=15, ha="right")
    axis.set_title(_sanitize_pdf_text(title or "Comparison"))
    axis.grid(axis="y", alpha=0.2)
    axis.legend()
    plt.tight_layout()

    image_path = assets_dir / f"{uuid4().hex}.png"
    figure.savefig(image_path, dpi=160, bbox_inches="tight")
    plt.close(figure)
    return image_path


def _render_section_html(
    section: dict[str, Any],
    theme_name: str,
    assets_dir: Path,
    rtl: bool,
) -> str:
    section_type = section.get("type")
    title = escape(str(section.get("title") or ""))
    content = escape(str(section.get("content") or ""))
    data = _section_data(section)

    if section_type == "page_break":
        return '<div class="page-break"></div>'

    if section_type == "cover":
        return f"<section><h2>{title}</h2><p>{content}</p></section>"

    if section_type == "section_header":
        return f"<h2>{title}</h2>"

    if section_type in {"executive_summary", "analysis", "text_block"}:
        heading = title or ("Executive Summary" if section_type == "executive_summary" else "Analysis")
        return f"<section><h3>{heading}</h3><p>{content}</p></section>"

    if section_type == "footer":
        return f'<section class="muted"><p>{content}</p></section>'

    if section_type == "insights_callout":
        return f'<section class="callout"><h3>{title or "Insights"}</h3><p>{content}</p></section>'

    if section_type == "kpi_grid" and isinstance(data, dict):
        rows = []
        for kpi in data.get("kpis") or []:
            label = escape(str(kpi.get("label", "Metric")))
            value = escape(_format_number(kpi.get("value", 0)))
            unit = escape(str(kpi.get("unit", "")))
            trend = escape(str(kpi.get("trend", "")))
            line = f"{label}: {unit} {value}".strip()
            if trend:
                line = f"{line} ({trend})"
            rows.append(f"<li>{line}</li>")
        heading = f"<h3>{title or 'Key Metrics'}</h3>"
        return f"<section>{heading}<ul>{''.join(rows)}</ul></section>"

    financial_rows = _financial_rows(data)
    if financial_rows:
        body_rows = []
        for row in financial_rows[:80]:
            account = escape(str(row.get("account") or row.get("name") or ""))
            amount = escape(_format_number(row.get("amount", 0)))
            body_rows.append(f"<tr><td>{account}</td><td>{amount}</td></tr>")
        heading = f"<h3>{title}</h3>" if title else ""
        return (
            f"<section>{heading}<table><thead><tr><th>Account</th><th>Amount</th></tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody></table></section>"
        )

    if section_type == "table" and isinstance(data, dict):
        headers = data.get("headers") or []
        rows = data.get("rows") or []
        header_html = "".join(f"<th>{escape(str(header))}</th>" for header in headers)
        body_rows = []
        for row in rows[:60]:
            if isinstance(row, dict):
                values = [row.get(header, "") for header in headers]
            else:
                values = list(row)
            body_rows.append(
                "<tr>"
                + "".join(f"<td>{escape(_format_number(value))}</td>" for value in values)
                + "</tr>"
            )
        heading = f"<h3>{title}</h3>" if title else ""
        return (
            f"<section>{heading}<table><thead><tr>{header_html}</tr></thead>"
            f"<tbody>{''.join(body_rows)}</tbody></table></section>"
        )

    if section_type in {"bar_chart", "line_chart", "pie_chart"} and isinstance(data, dict):
        image_path = _chart_image_path(section_type, {**data, "title": section.get("title")}, theme_name, assets_dir)
        if image_path:
            return (
                f'<section class="chart"><h3>{title or section_type.replace("_", " ").title()}</h3>'
                f'<img src="file://{image_path}" alt="{title}" /></section>'
            )

    if section_type == "comparison_chart":
        image_path = _comparison_chart_image(_comparison_rows(data), theme_name, assets_dir, title)
        if image_path:
            return f'<section class="chart"><h3>{title or "Comparison"}</h3><img src="file://{image_path}" alt="{title}" /></section>'

    if section_type == "two_column_split" and isinstance(data, dict):
        left = escape(str(data.get("left") or content))
        right = escape(str(data.get("right") or ""))
        return f"<section><p>{left}</p><p>{right}</p></section>"

    if content:
        return f"<section><p>{content}</p></section>"
    return ""


def _build_report_html(spec: dict[str, Any], assets_dir: Path) -> str:
    theme_name = "dark" if spec.get("theme") == "dark" else "light"
    rtl = spec.get("language") == "ar"
    blocks = [
        _render_section_html(section, theme_name, assets_dir, rtl)
        for section in (spec.get("sections") or [])
    ]
    if Template is None:
        return ""
    template = Template(HTML_TEMPLATE)
    return template.render(
        title=escape(str(spec.get("title") or "Elrace Report")),
        subtitle=escape(str(spec.get("subtitle") or "")),
        date_range=escape(str(spec.get("date_range") or "")),
        language=spec.get("language") or "en",
        direction="rtl" if rtl else "ltr",
        text_align="right" if rtl else "left",
        theme=PDF_THEMES[theme_name]["css"],
        blocks=blocks,
    )


def _render_with_weasyprint(spec: dict[str, Any], output_path: Path, assets_dir: Path) -> bool:
    if HTML is None or Template is None:
        return False
    html = _build_report_html(spec, assets_dir)
    if not html:
        return False
    HTML(string=html, base_url=str(assets_dir)).write_pdf(str(output_path))
    return output_path.exists()


def _pdf_heading(pdf: FPDF, text: str, size: int = 12, style: str = "B") -> None:
    pdf.set_font("Helvetica", style, size)
    pdf.cell(0, 8, _sanitize_pdf_text(text), ln=1)


def _pdf_paragraph(pdf: FPDF, text: str, size: int = 11) -> None:
    pdf.set_font("Helvetica", "", size)
    pdf.multi_cell(0, 6, _sanitize_pdf_text(text))


def _render_financial_rows(
    pdf: FPDF,
    title: str,
    rows: list[dict[str, Any]],
    theme: dict[str, Any],
) -> None:
    if title:
        _pdf_heading(pdf, title, size=13)
    pdf.set_font("Helvetica", "", 10)
    for row in rows[:80]:
        level = int(row.get("level", 0) or 0)
        account = _sanitize_pdf_text(row.get("account") or row.get("name") or "")
        amount = _format_number(row.get("amount", 0))
        line = f"{'  ' * level}{account}: AED {amount}"
        if row.get("highlight"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, line, ln=1)
            pdf.set_font("Helvetica", "", 10)
        else:
            pdf.cell(0, 6, line, ln=1)
    pdf.ln(3)
    pdf.set_text_color(*theme["text"])


def _render_section(
    pdf: FPDF,
    section: dict[str, Any],
    theme: dict[str, Any],
    assets_dir: Path,
    theme_name: str,
) -> None:
    section_type = section.get("type")
    title = section.get("title") or ""
    content = section.get("content") or ""
    data = _section_data(section)

    if section_type == "page_break":
        pdf.add_page()
        return

    if section_type == "cover":
        _pdf_heading(pdf, title or "Elrace Report", size=24)
        pdf.set_text_color(*theme["text"])
        _pdf_paragraph(pdf, content or "Generated by Odoo Omni-Agent", size=14)
        pdf.ln(8)
        return

    if section_type == "section_header":
        pdf.set_text_color(*theme["accent"])
        _pdf_heading(pdf, title, size=16)
        pdf.set_text_color(*theme["text"])
        return

    if section_type in {"executive_summary", "analysis", "text_block"}:
        heading = title or ("Executive Summary" if section_type == "executive_summary" else "Analysis")
        _pdf_heading(pdf, heading, size=14)
        _pdf_paragraph(pdf, content)
        pdf.ln(4)
        return

    if section_type == "footer":
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*theme["muted"])
        _pdf_paragraph(pdf, content, size=9)
        pdf.set_text_color(*theme["text"])
        pdf.ln(2)
        return

    if section_type == "insights_callout":
        pdf.set_fill_color(244, 247, 252)
        _pdf_heading(pdf, title or "Insights", size=12)
        _pdf_paragraph(pdf, content)
        pdf.ln(4)
        return

    if section_type == "kpi_grid" and isinstance(data, dict):
        _pdf_heading(pdf, title or "Key Metrics", size=13)
        for kpi in data.get("kpis") or []:
            label = _sanitize_pdf_text(kpi.get("label", "Metric"))
            value = _format_number(kpi.get("value", 0))
            unit = _sanitize_pdf_text(kpi.get("unit", ""))
            trend = _sanitize_pdf_text(kpi.get("trend", ""))
            line = f"{label}: {unit} {value}".strip()
            if trend:
                line = f"{line} ({trend})"
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(0, 7, line, ln=1)
        pdf.ln(3)
        return

    financial_rows = _financial_rows(data)
    if financial_rows:
        _render_financial_rows(pdf, title, financial_rows, theme)
        return

    if section_type == "table" and isinstance(data, dict):
        headers = data.get("headers") or []
        rows = data.get("rows") or []
        if title:
            _pdf_heading(pdf, title, size=13)
        if headers:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 7, _sanitize_pdf_text(" | ".join(str(header) for header in headers)), ln=1)
        pdf.set_font("Helvetica", "", 10)
        for row in rows[:40]:
            if isinstance(row, dict):
                values = [str(row.get(header, "")) for header in headers]
            else:
                values = [str(value) for value in row]
            pdf.cell(0, 6, _sanitize_pdf_text(" | ".join(values)), ln=1)
        pdf.ln(3)
        return

    if section_type in {"bar_chart", "line_chart", "pie_chart"} and isinstance(data, dict):
        image_path = _chart_image_path(section_type, data, theme_name, assets_dir)
        if image_path:
            _pdf_heading(pdf, title or section_type.replace("_", " ").title(), size=12)
            pdf.image(str(image_path), w=170)
            pdf.ln(6)
            return
        _pdf_heading(pdf, title or section_type.replace("_", " ").title(), size=12)
        for label, value in zip(data.get("labels") or [], data.get("values") or []):
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, _sanitize_pdf_text(f"{label}: {_format_number(value)}"), ln=1)
        pdf.ln(3)
        return

    if section_type == "comparison_chart":
        image_path = _comparison_chart_image(_comparison_rows(data), theme_name, assets_dir, title)
        if image_path:
            _pdf_heading(pdf, title or "Comparison", size=12)
            pdf.image(str(image_path), w=170)
            pdf.ln(6)
            return
        _pdf_heading(pdf, title or "Comparison", size=12)
        for row in _comparison_rows(data):
            period = _sanitize_pdf_text(row.get("period") or row.get("label") or "Period")
            revenue = _format_number(row.get("revenue", 0))
            expenses = _format_number(row.get("expenses", 0))
            profit = _format_number(row.get("profit", 0))
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, f"{period}: revenue {revenue}, expenses {expenses}, profit {profit}", ln=1)
        pdf.ln(3)
        return

    if section_type == "two_column_split" and isinstance(data, dict):
        left = data.get("left") or content
        right = data.get("right") or ""
        _pdf_paragraph(pdf, str(left), size=10)
        pdf.ln(2)
        _pdf_paragraph(pdf, str(right), size=10)
        pdf.ln(3)
        return

    if content:
        _pdf_paragraph(pdf, content)
        return

    if isinstance(data, dict) and data.get("headers") and data.get("rows"):
        _pdf_heading(pdf, title or "Report", size=13)
        headers = data.get("headers") or []
        rows = data.get("rows") or []
        if headers:
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 7, _sanitize_pdf_text(" | ".join(str(header) for header in headers)), ln=1)
        pdf.set_font("Helvetica", "", 10)
        for row in rows[:40]:
            if isinstance(row, dict):
                values = [str(row.get(header, "")) for header in headers]
            else:
                values = [str(value) for value in row]
            pdf.cell(0, 6, _sanitize_pdf_text(" | ".join(values)), ln=1)
        pdf.ln(3)
        return

    if title:
        _pdf_heading(pdf, title, size=12)
        return

    if section_type:
        _pdf_paragraph(pdf, f"Section: {section_type}")


def _build_preview_image(spec: dict[str, Any], preview_path: Path, theme_name: str) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:  # pragma: no cover
        return False

    theme = PDF_THEMES[theme_name]["css"]
    figure, axis = plt.subplots(figsize=(4.2, 5.8))
    figure.patch.set_facecolor(theme["background"])
    axis.set_facecolor(theme["section_bg"])
    axis.axis("off")
    axis.text(
        0.08,
        0.82,
        _sanitize_pdf_text(spec.get("title") or "Elrace Report"),
        color=theme["accent"],
        fontsize=16,
        fontweight="bold",
        ha="left",
        va="top",
    )
    subtitle = spec.get("subtitle") or spec.get("date_range") or "Generated by Odoo Omni-Agent"
    axis.text(0.08, 0.72, _sanitize_pdf_text(subtitle), color=theme["text"], fontsize=10, ha="left", va="top")
    axis.text(0.08, 0.12, "PDF preview", color=theme["muted"], fontsize=9, ha="left", va="bottom")
    plt.savefig(preview_path, dpi=140, bbox_inches="tight")
    plt.close(figure)
    return preview_path.exists()


def _normalize_pdf_spec(spec: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(spec)
    title = str(normalized.get("title") or "Elrace Report").strip() or "Elrace Report"
    normalized["title"] = title

    sections: list[dict[str, Any]] = []
    for section in spec.get("sections") or []:
        if not isinstance(section, dict):
            continue
        item = dict(section)
        item["type"] = str(item.get("type") or "").strip().lower().replace(" ", "_")
        sections.append(item)

    data = spec.get("data")
    if not sections and isinstance(data, dict) and data.get("headers") and data.get("rows"):
        sections.append({
            "type": "table",
            "title": title,
            "data": data,
        })

    rows = spec.get("rows") or []
    columns = [str(column) for column in (spec.get("columns") or [])]
    if not sections and rows:
        if not columns and isinstance(rows[0], dict):
            columns = [str(key) for key in rows[0].keys()]
        if columns:
            sections.append({
                "type": "table",
                "title": title,
                "data": {
                    "headers": columns,
                    "rows": [
                        [row.get(column) for column in columns] if isinstance(row, dict) else row
                        for row in rows
                    ],
                },
            })

    if not sections:
        summary = spec.get("content") or spec.get("summary") or spec.get("notes")
        sections.append({
            "type": "executive_summary",
            "title": "Summary",
            "content": summary or "Report generated by Odoo Omni-Agent.",
        })

    if not any(section.get("type") == "cover" for section in sections):
        sections.insert(0, {
            "type": "cover",
            "title": title,
            "content": (
                normalized.get("subtitle")
                or normalized.get("date_range")
                or "Generated by Odoo Omni-Agent"
            ),
        })

    normalized["sections"] = sections
    return normalized


def _render_with_fpdf(spec: dict[str, Any], output_path: Path, assets_dir: Path, theme_name: str) -> int:
    spec = _normalize_pdf_spec(spec)
    theme = PDF_THEMES[theme_name]
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_fill_color(*theme["background"])
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")
    pdf.set_text_color(*theme["text"])

    for section in spec.get("sections") or []:
        _render_section(pdf, section, theme, assets_dir, theme_name)

    pdf.output(str(output_path))
    return max(1, pdf.page_no())


def generate_pdf_report(
    spec: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    spec = _normalize_pdf_spec(spec)
    theme_name = "dark" if spec.get("theme") == "dark" else "light"
    stem = uuid4().hex
    output_path = REPORTS_DIR / f"{stem}.pdf"
    preview_path = REPORTS_DIR / f"{stem}-preview.png"
    assets_dir = REPORTS_DIR / f"{stem}-assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    try:
        page_count = 1
        if not _render_with_weasyprint(spec, output_path, assets_dir):
            page_count = _render_with_fpdf(spec, output_path, assets_dir, theme_name)

        preview_url = None
        if _build_preview_image(spec, preview_path, theme_name):
            preview_url = f"/reports/{preview_path.name}"

        return {
            "pdf_url": f"/reports/{output_path.name}",
            "preview_image": preview_url,
            "size_bytes": output_path.stat().st_size,
            "generated_at": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "title": spec.get("title"),
            "page_count": page_count,
            "language": spec.get("language", "en"),
            "theme": theme_name,
            "spec_preview": json.dumps(spec, default=str)[:500],
        }
    except Exception as exc:  # pragma: no cover - exercised via integration
        return {
            "error": "pdf_generation_failed",
            "message": str(exc),
            "session_id": session_id,
            "title": spec.get("title"),
        }
