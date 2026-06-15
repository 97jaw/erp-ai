"""Reports agent tools — definitions and execution for the unified agent loop."""

from __future__ import annotations

import logging
from typing import Any

from gateway.reports.ui_blocks import FileReadyBlock

logger = logging.getLogger(__name__)

REPORTS_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "show_ui_block",
        "description": (
            "Emit an interactive UI block to the user. Use this to show report pickers, "
            "date selectors, format selectors, or file-ready cards."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "block_type": {
                    "type": "string",
                    "enum": ["pill_select", "date_quick", "format_select"],
                    "description": "The type of UI block to show.",
                },
                "options": {
                    "type": "array",
                    "description": "For pill_select: list of {id, label} objects.",
                    "items": {"type": "object"},
                },
                "mode": {
                    "type": "string",
                    "enum": ["single", "multi"],
                    "description": "For pill_select: selection mode.",
                },
                "allow_typed_input": {
                    "type": "boolean",
                    "description": "For pill_select: whether to show a text input below pills.",
                },
                "prompt": {
                    "type": "string",
                    "description": "Label/prompt shown above the block.",
                },
            },
            "required": ["block_type"],
        },
    },
    {
        "name": "get_financial_report",
        "description": (
            "Get financial reports: Profit & Loss (pandl), Balance Sheet, or Cash Flow. "
            "Use for company-wide financial data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "enum": ["pandl", "balance_sheet", "cash_flow"],
                },
                "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["report_type"],
        },
    },
    {
        "name": "get_trial_balance",
        "description": "Get Trial Balance — summary of all accounts with debit, credit, balance totals.",
        "input_schema": {
            "type": "object",
            "properties": {
                "date_from": {"type": "string", "description": "YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["date_from", "date_to"],
        },
    },
    {
        "name": "get_project_expense_summary",
        "description": "Get expense summary for a single project by project_id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {
                    "type": "integer",
                    "description": "Odoo project.project ID.",
                },
                "project_name": {
                    "type": "string",
                    "description": "Project name (used if project_id is not known).",
                },
            },
        },
    },
    {
        "name": "generate_report",
        "description": (
            "Generate the report file after all parameters are collected. "
            "Calls the appropriate data tool then produces PDF/Excel output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "template": {
                    "type": "string",
                    "enum": ["pandl", "trial_balance", "project_expense"],
                    "description": "Which report template to use.",
                },
                "params": {
                    "type": "object",
                    "description": "Parameters: date_from, date_to, project_id, project_name, report_type.",
                },
                "format": {
                    "type": "string",
                    "enum": ["pdf", "excel", "both"],
                },
            },
            "required": ["template", "params", "format"],
        },
    },
]

REPORTS_TOOL_NAMES = frozenset(t["name"] for t in REPORTS_TOOL_DEFINITIONS)


async def execute_reports_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    *,
    adapter: Any,
    session_id: str | None = None,
) -> Any:
    """Execute a reports-specific data tool."""
    tool_input = dict(tool_input or {})

    if tool_name == "show_ui_block":
        return {"status": "ui_directive", "tool": tool_name, "data": tool_input}

    if tool_name == "get_financial_report":
        return adapter.accounting.get_financial_report(
            report_type=tool_input.get("report_type", "pandl"),
            date_from=tool_input.get("date_from"),
            date_to=tool_input.get("date_to"),
        )

    if tool_name == "get_trial_balance":
        return adapter.accounting.get_trial_balance(
            date_from=tool_input.get("date_from"),
            date_to=tool_input.get("date_to"),
        )

    if tool_name == "get_project_expense_summary":
        return await _handle_project_expense(adapter, tool_input)

    if tool_name == "generate_report":
        return await execute_generate_report(adapter, tool_input, session_id=session_id)

    raise ValueError(f"Unknown reports tool: {tool_name}")


async def _handle_project_expense(adapter: Any, tool_input: dict[str, Any]) -> Any:
    from gateway.tools.project_expense import execute_project_expense_tool

    project_id = tool_input.get("project_id")
    if not project_id and tool_input.get("project_name"):
        try:
            records = adapter.safe_search_read(
                "project.project",
                [["name", "ilike", tool_input["project_name"]]],
                fields=["id", "name"],
                limit=1,
            )
            if records:
                project_id = records[0]["id"]
        except Exception:
            logger.warning("[reports_tools] project name resolve failed", exc_info=True)

    if not project_id:
        return {
            "status": "error",
            "message": "Could not resolve project. Please provide the exact project name or ID.",
        }

    return await execute_project_expense_tool(
        "get_project_expense_summary",
        {"project_id": int(project_id)},
        adapter,
    )


async def execute_generate_report(
    adapter: Any,
    tool_input: dict[str, Any],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    template = tool_input.get("template", "pandl")
    params = tool_input.get("params") or {}
    fmt = tool_input.get("format", "pdf")

    data: dict[str, Any] = {}
    report_type_for_file = template

    if template == "pandl":
        raw = adapter.accounting.get_financial_report(
            report_type=params.get("report_type", "pandl"),
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            target_move=params.get("target_move", "posted"),
        )
        data = extract_generator_data(raw, template)
        report_type_for_file = params.get("report_type", "pandl")

    elif template == "trial_balance":
        raw = adapter.accounting.get_trial_balance(
            date_from=params.get("date_from"),
            date_to=params.get("date_to"),
            target_moves=params.get("target_move", "posted"),
            display_accounts=params.get("display_accounts", "all"),
            show_hierarchy=bool(params.get("show_hierarchy", False)),
        )
        data = extract_generator_data(raw, template)
        report_type_for_file = "trial_balance"

    elif template == "project_expense":
        project_id = params.get("project_id")
        if not project_id and params.get("project_name"):
            try:
                records = adapter.safe_search_read(
                    "project.project",
                    [["name", "ilike", params["project_name"]]],
                    fields=["id", "name"],
                    limit=1,
                )
                if records:
                    project_id = records[0]["id"]
            except Exception:
                logger.warning("[reports_tools] project resolve failed", exc_info=True)
        if project_id:
            from gateway.tools.project_expense import execute_project_expense_tool

            raw = await execute_project_expense_tool(
                "get_project_expense_summary",
                {"project_id": int(project_id)},
                adapter,
            )
            data = extract_generator_data(raw, template)
        report_type_for_file = "project_expense"

    if not isinstance(data, dict):
        data = {"raw": data}

    results: list[dict[str, Any]] = []

    if fmt in ("pdf", "both"):
        from gateway.reports.generators.pdf import PDFGenerator

        report_id, _filepath = PDFGenerator().generate(report_type_for_file, data, params)
        filename = make_filename(template, params, "pdf")
        results.append(
            FileReadyBlock(
                report_id=report_id,
                filename=filename,
                format="pdf",
                url=f"/reports/download/{report_id}",
            ).to_dict()
        )

    if fmt in ("excel", "both"):
        from gateway.reports.generators.excel import ExcelGenerator

        report_id, _filepath = ExcelGenerator().generate(report_type_for_file, data, params)
        filename = make_filename(template, params, "xlsx")
        results.append(
            FileReadyBlock(
                report_id=report_id,
                filename=filename,
                format="excel",
                url=f"/reports/download/{report_id}",
            ).to_dict()
        )

    return {
        "status": "success",
        "files": results,
        "message": f"Generated {len(results)} file(s) successfully.",
        "_sse_events": [{"type": "file_ready_list", "files": results}],
    }


def extract_generator_data(raw: dict[str, Any], template: str) -> dict[str, Any]:
    """Convert normalized Odoo API response into generator-friendly structure."""
    if not isinstance(raw, dict):
        return {}

    result = dict(raw)
    rows: list[dict[str, Any]] = []

    if template in ("pandl", "balance_sheet", "cash_flow", "trial_balance"):
        report_lines = raw.get("report_lines") or []
        for line in report_lines:
            name = line.get("name") or ""
            balance = float(line.get("balance") or 0)
            debit = float(line.get("debit") or 0)
            credit = float(line.get("credit") or 0)
            level = int(line.get("level") or 0)
            style = line.get("style") or line.get("style_type") or "main"
            highlight = style in ("main", "bold", "total") or level <= 1
            rows.append(
                {
                    "account": name,
                    "amount": balance,
                    "debit": debit,
                    "credit": credit,
                    "level": level,
                    "highlight": highlight,
                }
            )

    elif template == "project_expense":
        expense_lines = raw.get("expense_lines") or []
        for line in expense_lines:
            label = line.get("label") or line.get("name") or ""
            amount = float(line.get("amount") or 0)
            rows.append(
                {
                    "account": label,
                    "amount": amount,
                    "level": 0,
                    "highlight": False,
                }
            )
        if not rows:
            for key in ("total_expenses", "wo_amount", "variance_amount"):
                if raw.get(key) is not None:
                    rows.append(
                        {
                            "account": key.replace("_", " ").title(),
                            "amount": float(raw[key] or 0),
                            "level": 0,
                            "highlight": True,
                        }
                    )

    result["rows"] = rows

    if "kpis" not in result:
        kpis: dict[str, Any] = {}
        for key in (
            "total_income",
            "total_expense",
            "net_profit",
            "margin",
            "total_debit",
            "total_credit",
            "balance",
            "total_expenses",
            "wo_amount",
            "spend_percent_of_wo",
        ):
            if raw.get(key) is not None:
                kpis[key] = raw[key]
        if kpis:
            result["kpis"] = kpis

    return result


def make_filename(template: str, params: dict[str, Any], ext: str) -> str:
    date_from = params.get("date_from", "")
    date_to = params.get("date_to", "")
    slug = template.replace("_", "-")
    if date_from:
        slug += f"_{date_from}"
    if date_to:
        slug += f"_{date_to}"
    return f"{slug}.{ext}"
