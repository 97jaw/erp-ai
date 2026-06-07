"""Excel export for Visualize agent (Phase 2 baseline)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from gateway.pdf_reports import REPORTS_DIR
from visualize.data_resolver import resolve_table_from_visualization

THEME_COLORS = {
    "header_bg": "#1a2744",
    "header_fg": "#ffffff",
    "accent": "#c9a84c",
}


def generate_excel_workbook(spec: dict[str, Any], session_id: str | None = None) -> dict[str, Any]:
    try:
        import xlsxwriter
    except ImportError as exc:  # pragma: no cover
        return {"error": "excel_unavailable", "message": str(exc)}

    title = str(spec.get("title") or "Elrace Export").strip() or "Elrace Export"
    rows = spec.get("rows") or []
    columns = [str(c) for c in (spec.get("columns") or [])]
    if not columns and rows and isinstance(rows[0], dict):
        columns = [str(k) for k in rows[0].keys()]

    if not rows:
        data = spec.get("data_context") or {}
        if isinstance(data, dict):
            if data.get("rows"):
                columns = [str(h) for h in (data.get("headers") or columns)]
                rows = data.get("rows") or rows
            else:
                resolved = resolve_table_from_visualization({"visual_type": "DATA_TABLE", "data": data})
                columns = [str(h) for h in (resolved.get("headers") or columns)]
                rows = resolved.get("rows") or rows

    output_id = uuid4().hex
    output_path = REPORTS_DIR / f"{output_id}.xlsx"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    workbook = xlsxwriter.Workbook(str(output_path))
    sheet_name = "Summary" if spec.get("structure") != "pivot_ready" else "Data"
    sheet = workbook.add_worksheet(sheet_name[:31])

    header_fmt = workbook.add_format({
        "bold": True,
        "bg_color": THEME_COLORS["header_bg"],
        "font_color": THEME_COLORS["header_fg"],
        "border": 1,
    })
    currency_fmt = workbook.add_format({"num_format": '"AED" #,##0'})
    neg_fmt = workbook.add_format({"num_format": '"AED" #,##0;[Red]"AED" -#,##0'})

    sheet.merge_range(0, 0, 0, max(len(columns), 3), title, header_fmt)
    sheet.set_row(0, 28)

    start_row = 2
    if columns:
        for col, header in enumerate(columns):
            sheet.write(start_row, col, header, header_fmt)
        for row_idx, row in enumerate(rows[:500], start=start_row + 1):
            if isinstance(row, dict):
                values = [row.get(col) for col in columns]
            else:
                values = list(row) if isinstance(row, (list, tuple)) else [row]
            for col_idx, value in enumerate(values):
                if isinstance(value, (int, float)):
                    fmt = neg_fmt if spec.get("formatting", {}).get("highlight_negatives") and value < 0 else currency_fmt
                    sheet.write(row_idx, col_idx, value, fmt)
                else:
                    sheet.write(row_idx, col_idx, value)
        sheet.freeze_panes(start_row + 1, 0)
        sheet.autofilter(start_row, 0, start_row + len(rows), len(columns) - 1)
    else:
        sheet.write(start_row, 0, "No tabular rows in context — add table data or text in dropped item.")

    workbook.close()

    return {
        "output_id": output_id,
        "excel_url": f"/reports/{output_id}.xlsx",
        "download_url": f"/reports/{output_id}.xlsx",
        "size_bytes": output_path.stat().st_size,
        "title": title,
        "session_id": session_id,
        "format": "xlsx",
    }
