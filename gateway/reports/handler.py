"""Reports agent handler — /reports/stream endpoint."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from calendar import monthrange
from datetime import date, timedelta
from typing import Any, AsyncIterator

import anthropic

from gateway.reports.prompt import REPORTS_SYSTEM_PROMPT
from gateway.reports.ui_blocks import (
    DatePreset,
    DateQuickBlock,
    FileReadyBlock,
    FormatSelectBlock,
    PillOption,
    PillSelectBlock,
)

logger = logging.getLogger(__name__)

AGENT_MODEL = "claude-sonnet-4-20250514"
MAX_AGENT_TOKENS = 4096
MAX_TOOL_ROUNDS = 8

# ---------------------------------------------------------------------------
# Per-session store
# ---------------------------------------------------------------------------
_sessions: dict[str, "ReportsHandler"] = {}


def get_or_create_handler(session_id: str, adapter: Any) -> "ReportsHandler":
    if session_id not in _sessions:
        _sessions[session_id] = ReportsHandler(adapter)
    else:
        # Refresh adapter in case connection was re-established
        _sessions[session_id].adapter = adapter
    return _sessions[session_id]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_async_client: anthropic.AsyncAnthropic | None = None


def _get_async_client() -> anthropic.AsyncAnthropic:
    global _async_client
    if _async_client is None:
        _async_client = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _async_client


def _sse(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, default=str)}\n\n"


def _date_presets() -> list[DatePreset]:
    today = date.today()
    # This Month
    first_this = today.replace(day=1)
    last_this = today.replace(day=monthrange(today.year, today.month)[1])
    # Last Month
    last_month_end = first_this - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    # This Quarter
    q = (today.month - 1) // 3
    q_start = date(today.year, q * 3 + 1, 1)
    q_end_month = q_start.month + 2
    q_end = date(today.year, q_end_month, monthrange(today.year, q_end_month)[1])
    # Last Quarter
    lq_end = q_start - timedelta(days=1)
    lq_start = lq_end.replace(day=1)
    lq_start = date(lq_start.year, ((lq_start.month - 1) // 3) * 3 + 1, 1)
    # This Year
    year_start = date(today.year, 1, 1)
    year_end = date(today.year, 12, 31)
    # Last Year
    last_year_start = date(today.year - 1, 1, 1)
    last_year_end = date(today.year - 1, 12, 31)

    def iso(d: date) -> str:
        return d.isoformat()

    return [
        DatePreset("this_month", "This Month", iso(first_this), iso(last_this)),
        DatePreset("last_month", "Last Month", iso(last_month_start), iso(last_month_end)),
        DatePreset("this_quarter", "This Quarter", iso(q_start), iso(q_end)),
        DatePreset("last_quarter", "Last Quarter", iso(lq_start), iso(lq_end)),
        DatePreset("this_year", "This Year", iso(year_start), iso(year_end)),
        DatePreset("last_year", "Last Year", iso(last_year_start), iso(last_year_end)),
    ]


# ---------------------------------------------------------------------------
# Tool definitions exposed to Claude
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# ReportsHandler
# ---------------------------------------------------------------------------


class ReportsHandler:
    """Handles reports queries via a Claude tool-use loop."""

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self.history: list[dict[str, Any]] = []

    async def handle_stream(
        self,
        message: str,
        user: Any | None,
        session_id: str,
    ) -> AsyncIterator[str]:
        """Stream SSE events."""
        system_prompt = REPORTS_SYSTEM_PROMPT.replace("{today}", date.today().isoformat())

        # Append user turn to history
        self.history.append({"role": "user", "content": message})
        messages = list(self.history)

        full_text_parts: list[str] = []

        try:
            for _round in range(MAX_TOOL_ROUNDS):
                stream_started = time.perf_counter()
                async with _get_async_client().messages.stream(
                    model=AGENT_MODEL,
                    max_tokens=MAX_AGENT_TOKENS,
                    system=system_prompt,
                    tools=REPORTS_TOOL_DEFINITIONS,
                    messages=messages,
                ) as stream:
                    async for text in stream.text_stream:
                        if not text:
                            continue
                        full_text_parts.append(text)
                        yield _sse({"type": "text", "chunk": text})

                    response = await stream.get_final_message()

                if response.stop_reason == "end_turn":
                    # Save assistant turn to history
                    assistant_text = "".join(full_text_parts).strip()
                    if assistant_text:
                        self.history.append({"role": "assistant", "content": assistant_text})
                    break

                if response.stop_reason != "tool_use":
                    break

                messages.append({"role": "assistant", "content": response.content})
                tool_blocks = [b for b in response.content if b.type == "tool_use"]
                tool_results = []

                for block in tool_blocks:
                    tool_name = block.name
                    tool_input = dict(block.input or {})

                    status_msg = {
                        "generate_report": "Fetching financial data from Odoo...",
                        "get_financial_report": "Querying financial data from Odoo...",
                        "get_trial_balance": "Fetching trial balance from Odoo...",
                        "get_project_expense_summary": "Loading project expense data...",
                    }.get(tool_name, f"Processing {tool_name}...")
                    yield _sse({"type": "status", "message": status_msg})

                    result, ui_event = await self._execute_tool(
                        tool_name, tool_input, user=user, session_id=session_id
                    )

                    if ui_event is not None:
                        yield _sse(ui_event)

                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str)[:8000],
                        }
                    )

                messages.append({"role": "user", "content": tool_results})

            clean_text = "".join(full_text_parts).strip()
            yield _sse(
                {
                    "type": "done",
                    "text": clean_text,
                    "session_id": session_id,
                    "agent": "reports",
                }
            )

        except Exception as exc:
            logger.exception("[ReportsHandler] stream error: %s", exc)
            yield _sse({"type": "error", "message": str(exc)})
            yield _sse({"type": "done", "text": "", "session_id": session_id, "agent": "reports"})

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        *,
        user: Any | None,
        session_id: str,
    ) -> tuple[Any, dict[str, Any] | None]:
        """
        Execute a tool call.

        Returns (tool_result, optional_sse_event).
        """
        try:
            if tool_name == "show_ui_block":
                return self._handle_show_ui_block(tool_input)

            if tool_name == "get_financial_report":
                result = self.adapter.accounting.get_financial_report(
                    report_type=tool_input.get("report_type", "pandl"),
                    date_from=tool_input.get("date_from"),
                    date_to=tool_input.get("date_to"),
                )
                return result, None

            if tool_name == "get_trial_balance":
                result = self.adapter.accounting.get_trial_balance(
                    date_from=tool_input.get("date_from"),
                    date_to=tool_input.get("date_to"),
                )
                return result, None

            if tool_name == "get_project_expense_summary":
                return await self._handle_project_expense(tool_input)

            if tool_name == "generate_report":
                return await self._handle_generate_report(tool_input, session_id)

            return {"status": "error", "message": f"Unknown tool: {tool_name}"}, None

        except Exception as exc:
            logger.warning("[ReportsHandler] tool %s failed: %s", tool_name, exc)
            return {"status": "error", "message": str(exc)}, None

    def _handle_show_ui_block(
        self, tool_input: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        block_type = tool_input.get("block_type", "")
        prompt = tool_input.get("prompt", "")

        if block_type == "pill_select":
            raw_options = tool_input.get("options") or []
            options = [
                PillOption(id=o.get("id", ""), label=o.get("label", ""))
                for o in raw_options
            ]
            block = PillSelectBlock(
                options=options,
                mode=tool_input.get("mode", "single"),
                allow_typed_input=bool(tool_input.get("allow_typed_input", False)),
                prompt=prompt,
            )

        elif block_type == "date_quick":
            block = DateQuickBlock(presets=_date_presets(), prompt=prompt)

        elif block_type == "format_select":
            block = FormatSelectBlock(
                options=tool_input.get("options", ["pdf", "excel", "both"]),
                prompt=prompt,
            )
        else:
            block = {"type": "unknown", "raw": tool_input}
            return {"status": "ok", "block_shown": True}, {
                "type": "ui_block", "block": block
            }

        block_dict = block.to_dict()
        sse_event = {"type": "ui_block", "block": block_dict}
        return {"status": "ok", "block_shown": True, "block_type": block_type}, sse_event

    async def _handle_project_expense(
        self, tool_input: dict[str, Any]
    ) -> tuple[Any, None]:
        from gateway.tools.project_expense import execute_project_expense_tool

        project_id = tool_input.get("project_id")
        if not project_id and tool_input.get("project_name"):
            # Try to resolve by name
            try:
                records = self.adapter.env["project.project"].search_read(
                    [["name", "ilike", tool_input["project_name"]]],
                    fields=["id", "name"],
                    limit=1,
                )
                if records:
                    project_id = records[0]["id"]
            except Exception:
                pass

        if not project_id:
            return {
                "status": "error",
                "message": "Could not resolve project. Please provide the exact project name or ID.",
            }, None

        result = await execute_project_expense_tool(
            "get_project_expense_summary",
            {"project_id": int(project_id)},
            self.adapter,
        )
        return result, None

    async def _handle_generate_report(
        self, tool_input: dict[str, Any], session_id: str
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        template = tool_input.get("template", "pandl")
        params = tool_input.get("params") or {}
        fmt = tool_input.get("format", "pdf")

        # --- Fetch data from Odoo ---
        data: dict[str, Any] = {}
        report_type_for_file = template

        if template == "pandl":
            raw = self.adapter.accounting.get_financial_report(
                report_type=params.get("report_type", "pandl"),
                date_from=params.get("date_from"),
                date_to=params.get("date_to"),
                target_move=params.get("target_move", "posted"),
            )
            # Normalized output has: report_lines (list), kpis, income_lines, expense_lines
            # Extract rows for generators: list of {account, amount, level, highlight}
            data = _extract_generator_data(raw, template)
            report_type_for_file = params.get("report_type", "pandl")

        elif template == "trial_balance":
            raw = self.adapter.accounting.get_trial_balance(
                date_from=params.get("date_from"),
                date_to=params.get("date_to"),
                target_moves=params.get("target_move", "posted"),
                display_accounts=params.get("display_accounts", "all"),
                show_hierarchy=bool(params.get("show_hierarchy", False)),
            )
            data = _extract_generator_data(raw, template)
            report_type_for_file = "trial_balance"

        elif template == "project_expense":
            from gateway.tools.project_expense import execute_project_expense_tool

            project_id = params.get("project_id")
            if not project_id and params.get("project_name"):
                try:
                    records = self.adapter.env["project.project"].search_read(
                        [["name", "ilike", params["project_name"]]],
                        fields=["id", "name"],
                        limit=1,
                    )
                    if records:
                        project_id = records[0]["id"]
                except Exception:
                    pass
            if project_id:
                raw = await execute_project_expense_tool(
                    "get_project_expense_summary",
                    {"project_id": int(project_id)},
                    self.adapter,
                )
                data = _extract_generator_data(raw, template)
            report_type_for_file = "project_expense"

        if not isinstance(data, dict):
            data = {"raw": data}

        # --- Generate file(s) ---
        results: list[dict[str, Any]] = []

        if fmt in ("pdf", "both"):
            from gateway.reports.generators.pdf import PDFGenerator

            report_id, filepath = PDFGenerator().generate(report_type_for_file, data, params)
            filename = _make_filename(template, params, "pdf")
            file_block = FileReadyBlock(
                report_id=report_id,
                filename=filename,
                format="pdf",
                url=f"/reports/download/{report_id}",
            )
            results.append(file_block.to_dict())

        if fmt in ("excel", "both"):
            from gateway.reports.generators.excel import ExcelGenerator

            report_id, filepath = ExcelGenerator().generate(report_type_for_file, data, params)
            filename = _make_filename(template, params, "xlsx")
            file_block = FileReadyBlock(
                report_id=report_id,
                filename=filename,
                format="excel",
                url=f"/reports/download/{report_id}",
            )
            results.append(file_block.to_dict())

        # Build SSE events: emit file_ready blocks and return summary to Claude
        sse_events = {"type": "file_ready_list", "files": results}

        # We return the list as the tool result AND emit via a special key
        tool_result = {
            "status": "success",
            "files": results,
            "message": f"Generated {len(results)} file(s) successfully.",
        }
        # Emit each file as a ui_block file_ready
        return tool_result, {"type": "file_ready_list", "files": results}


def _extract_generator_data(raw: dict[str, Any], template: str) -> dict[str, Any]:
    """
    Convert normalized Odoo API response into generator-friendly structure.

    Generators expect:
      - data["rows"] = list of {account, amount, level, highlight}
      - data["kpis"] = summary dict
      - all original keys passed through for _extract_summary / _extract_lines fallback
    """
    if not isinstance(raw, dict):
        return {}

    # Pass raw data through so existing _extract_lines / _extract_summary in generators still work
    result = dict(raw)

    # Build unified rows from report_lines (financial reports) or expense_lines (project expense)
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
            rows.append({
                "account": name,
                "amount": balance,
                "debit": debit,
                "credit": credit,
                "level": level,
                "highlight": highlight,
            })

    elif template == "project_expense":
        # expense_lines: [{label, amount}], top_expenses: [{name, amount, percent}]
        expense_lines = raw.get("expense_lines") or []
        for line in expense_lines:
            label = line.get("label") or line.get("name") or ""
            amount = float(line.get("amount") or 0)
            rows.append({
                "account": label,
                "amount": amount,
                "level": 0,
                "highlight": False,
            })
        # Also expose top-level KPIs as rows if no expense_lines
        if not rows:
            for key in ("total_expenses", "wo_amount", "variance_amount"):
                if raw.get(key) is not None:
                    rows.append({
                        "account": key.replace("_", " ").title(),
                        "amount": float(raw[key] or 0),
                        "level": 0,
                        "highlight": True,
                    })

    result["rows"] = rows

    # Ensure kpis exists for summary section
    if "kpis" not in result:
        kpis: dict[str, Any] = {}
        for key in ("total_income", "total_expense", "net_profit", "margin",
                    "total_debit", "total_credit", "balance",
                    "total_expenses", "wo_amount", "spend_percent_of_wo"):
            if raw.get(key) is not None:
                kpis[key] = raw[key]
        if kpis:
            result["kpis"] = kpis

    return result


def _make_filename(template: str, params: dict[str, Any], ext: str) -> str:
    date_from = params.get("date_from", "")
    date_to = params.get("date_to", "")
    slug = template.replace("_", "-")
    if date_from:
        slug += f"_{date_from}"
    if date_to:
        slug += f"_{date_to}"
    return f"{slug}.{ext}"
