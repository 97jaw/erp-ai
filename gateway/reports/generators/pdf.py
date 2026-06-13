"""PDF report generator using ReportLab."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import date
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

logger = logging.getLogger(__name__)

# Brand colours
HEADER_BG = colors.HexColor("#1a1a2e")
HEADER_FG = colors.white
ACCENT = colors.HexColor("#4a90d9")
ALT_ROW = colors.HexColor("#f5f7fa")
BORDER = colors.HexColor("#dee2e6")


def _reports_dir() -> str:
    base = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "static", "reports"
    )
    path = os.path.abspath(base)
    os.makedirs(path, exist_ok=True)
    return path


def _fmt_currency(value: Any) -> str:
    try:
        num = float(value)
        return f"AED {num:,.2f}"
    except (TypeError, ValueError):
        return str(value) if value is not None else ""


def _report_title(report_type: str) -> str:
    titles = {
        "pandl": "Profit & Loss Statement",
        "balance_sheet": "Balance Sheet",
        "cash_flow": "Cash Flow Statement",
        "trial_balance": "Trial Balance",
        "project_expense": "Project Expense Summary",
    }
    return titles.get(report_type, report_type.replace("_", " ").title())


def _extract_lines(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort extraction of line items from various API response shapes."""
    # Try common shapes
    for key in ("lines", "line_ids", "accounts", "items", "rows", "data"):
        val = data.get(key)
        if isinstance(val, list) and val:
            return val
    # Flatten nested sections
    sections = data.get("sections") or data.get("groups") or []
    if isinstance(sections, list):
        lines = []
        for section in sections:
            if isinstance(section, dict):
                sub = section.get("lines") or section.get("children") or []
                lines.extend(sub if isinstance(sub, list) else [])
        if lines:
            return lines
    return []


def _extract_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Pull top-level summary metrics."""
    summary = {}
    for key in (
        "total_income", "total_expense", "net_profit", "net_loss",
        "total_debit", "total_credit", "balance",
        "total_expenses", "wo_amount", "spend_percentage",
    ):
        if key in data:
            summary[key] = data[key]
    # Also pull any top-level numeric scalars not in sub-lists
    for k, v in data.items():
        if isinstance(v, (int, float)) and k not in summary:
            summary[k] = v
    return summary


class PDFGenerator:
    """Generate a styled PDF report using ReportLab."""

    def generate(
        self,
        report_type: str,
        data: dict[str, Any],
        params: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Build the PDF.

        Returns (report_id, filepath).
        """
        report_id = uuid.uuid4().hex
        filename = f"{report_id}.pdf"
        filepath = os.path.join(_reports_dir(), filename)

        doc = SimpleDocTemplate(
            filepath,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        story = []

        # --- Header banner ---
        header_data = [
            [
                Paragraph(
                    f'<font color="white"><b>Elrace</b></font>',
                    ParagraphStyle("hdr", fontSize=14, textColor=colors.white),
                ),
                Paragraph(
                    f'<font color="white">{_report_title(report_type)}</font>',
                    ParagraphStyle(
                        "hdr2", fontSize=14, textColor=colors.white, alignment=TA_RIGHT
                    ),
                ),
            ]
        ]
        header_table = Table(header_data, colWidths=["50%", "50%"])
        header_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HEADER_BG),
                    ("TOPPADDING", (0, 0), (-1, -1), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 0.4 * cm))

        # --- Period & generated date ---
        date_from = params.get("date_from", "")
        date_to = params.get("date_to", "")
        period_text = (
            f"Period: {date_from} to {date_to}" if date_from and date_to else ""
        )
        gen_text = f"Generated: {date.today().isoformat()}"
        meta_data = [[period_text, gen_text]]
        meta_table = Table(meta_data, colWidths=["60%", "40%"])
        meta_table.setStyle(
            TableStyle(
                [
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#555555")),
                    ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(meta_table)
        story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
        story.append(Spacer(1, 0.3 * cm))

        # --- Summary table ---
        summary = _extract_summary(data)
        if summary:
            story.append(
                Paragraph(
                    "Summary",
                    ParagraphStyle(
                        "section", fontSize=11, textColor=HEADER_BG, spaceAfter=6,
                        fontName="Helvetica-Bold"
                    ),
                )
            )
            sum_rows = [["Metric", "Value"]]
            for k, v in summary.items():
                label = k.replace("_", " ").title()
                value = _fmt_currency(v) if isinstance(v, (int, float)) else str(v)
                sum_rows.append([label, value])

            sum_table = Table(sum_rows, colWidths=["55%", "45%"])
            sum_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW]),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            story.append(sum_table)
            story.append(Spacer(1, 0.5 * cm))

        # --- Line items table ---
        lines = _extract_lines(data)
        if lines:
            story.append(
                Paragraph(
                    "Detail",
                    ParagraphStyle(
                        "section2", fontSize=11, textColor=HEADER_BG, spaceAfter=6,
                        fontName="Helvetica-Bold"
                    ),
                )
            )
            # Determine columns from first row
            if isinstance(lines[0], dict):
                cols = list(lines[0].keys())[:6]  # max 6 cols
                col_headers = [c.replace("_", " ").title() for c in cols]
                detail_rows = [col_headers]
                for line in lines[:200]:  # cap at 200 rows
                    row = []
                    for col in cols:
                        val = line.get(col, "")
                        if isinstance(val, (int, float)):
                            val = _fmt_currency(val)
                        row.append(str(val) if val is not None else "")
                    detail_rows.append(row)

                col_width = 15.5 * cm / len(cols)
                detail_table = Table(
                    detail_rows, colWidths=[col_width] * len(cols), repeatRows=1
                )
                detail_table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW]),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                            ("LEFTPADDING", (0, 0), (-1, -1), 6),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                        ]
                    )
                )
                story.append(detail_table)

        if not summary and not lines:
            story.append(
                Paragraph(
                    "No data available for the selected period.",
                    styles["Normal"],
                )
            )

        # --- Footer ---
        story.append(Spacer(1, 0.5 * cm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
        story.append(
            Paragraph(
                "Elrace ERP — Confidential",
                ParagraphStyle(
                    "footer", fontSize=7, textColor=colors.HexColor("#999999"),
                    alignment=TA_CENTER, spaceBefore=4
                ),
            )
        )

        doc.build(story)
        logger.info("[PDFGenerator] Generated %s → %s", report_type, filepath)
        return report_id, filepath
