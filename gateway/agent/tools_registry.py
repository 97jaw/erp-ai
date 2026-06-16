"""Single source of truth for agent tools and dispatch."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from gateway.agent.permissions import filter_tools_for_user
from gateway.agent.ui_block_tools import UI_INTERACTION_TOOLS, UI_TOOL_NAMES
from gateway.audit.tools import AUDIT_TOOL_DEFINITIONS
from gateway.agent.reports_tools import REPORTS_TOOL_DEFINITIONS, REPORTS_TOOL_NAMES, execute_reports_tool
from gateway.tools.project_expense import PROJECT_EXPENSE_TOOL_DEFINITIONS
from gateway.tools.universal_odoo import (
    UNIVERSAL_ODOO_EXECUTORS,
    UNIVERSAL_ODOO_TOOL_DEFINITIONS,
    build_universal_context,
)

logger = logging.getLogger(__name__)

CHAT_FINANCIAL_TOOL_NAMES = frozenset(
    {
        "get_financial_report",
        "get_trial_balance",
        "get_general_ledger",
        "get_partner_ageing",
        "query_accounting",
        "get_project_financial_data",
    }
)

CHAT_SEARCH_TOOL_NAMES = frozenset(
    {
        "search_entities",
        "search_fleet_vehicles",
        "search_odoo",
    }
)

CHAT_HR_TOOL_NAMES = frozenset(
    {
        "get_employee_payslips",
        "get_payslip_detail",
        "get_my_payslips",
        "list_employee_requests",
    }
)

CHAT_PROCUREMENT_TOOL_NAMES = frozenset(
    {
        "get_purchase_orders",
        "get_project_records",
        "list_attachments",
        "get_project_activity",
    }
)

AUDIT_UNIVERSAL_NAMES = frozenset({"query_odoo", "aggregate_odoo"})


def _main_tools_by_names(names: frozenset[str]) -> list[dict[str, Any]]:
    """Lazy import to avoid circular dependency at module load."""
    from gateway.main import TOOLS

    return [tool for tool in TOOLS if tool.get("name") in names]


def get_all_tools(agent_type: str, user: Any | None) -> list[dict[str, Any]]:
    """Return Claude tool definitions for this agent type and user."""
    tools: list[dict[str, Any]] = []

    if agent_type == "chat":
        tools.extend(UNIVERSAL_ODOO_TOOL_DEFINITIONS)
        tools.extend(_main_tools_by_names(CHAT_FINANCIAL_TOOL_NAMES))
        tools.extend(PROJECT_EXPENSE_TOOL_DEFINITIONS)
        tools.extend(_main_tools_by_names(CHAT_SEARCH_TOOL_NAMES))
        tools.extend(_main_tools_by_names(CHAT_HR_TOOL_NAMES))
        tools.extend(_main_tools_by_names(CHAT_PROCUREMENT_TOOL_NAMES))
        tools.extend(UI_INTERACTION_TOOLS)
    elif agent_type == "audit":
        tools.extend(AUDIT_TOOL_DEFINITIONS)
        tools.extend(
            tool
            for tool in UNIVERSAL_ODOO_TOOL_DEFINITIONS
            if tool["name"] in AUDIT_UNIVERSAL_NAMES
        )
        tools.extend(UI_INTERACTION_TOOLS)
    elif agent_type == "reports":
        from gateway.agent.ui_block_tools import show_ui_block_tool

        tools.extend(
            tool for tool in REPORTS_TOOL_DEFINITIONS if tool["name"] != "show_ui_block"
        )
        tools.append(show_ui_block_tool)
        tools.extend(
            tool
            for tool in UI_INTERACTION_TOOLS
            if tool["name"] in {"add_suggestions", "render_visualization"}
        )
    else:
        tools.extend(UNIVERSAL_ODOO_TOOL_DEFINITIONS)
        tools.extend(UI_INTERACTION_TOOLS)

    return filter_tools_for_user(tools, user)


async def execute_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    *,
    adapter: Any,
    user: Any | None,
    session_id: str | None = None,
    user_message: str = "",
) -> Any:
    """Execute a tool by name. UI tools return directives; data tools delegate to gateway."""
    tool_input = dict(tool_input or {})

    if session_id:
        from gateway.agent.session_entities import (
            enrich_financial_tool_input,
            enrich_fleet_tool_input,
            enrich_payroll_tool_input,
            enrich_procurement_tool_input,
            enrich_project_tool_input,
            enrich_attachment_tool_input,
        )

        tool_input = enrich_payroll_tool_input(session_id, tool_name, tool_input)
        tool_input = enrich_project_tool_input(session_id, tool_name, tool_input)
        tool_input = enrich_fleet_tool_input(session_id, tool_name, tool_input)
        tool_input = enrich_procurement_tool_input(session_id, tool_name, tool_input)
        tool_input = enrich_attachment_tool_input(session_id, tool_name, tool_input)
        tool_input = enrich_financial_tool_input(session_id, tool_name, tool_input)

    if tool_name == "query_odoo" and tool_input.get("model") == "hr.payslip":
        from gateway.agent.session_entities import domain_has_employee_filter

        domain = tool_input.get("domain") or []
        if not domain_has_employee_filter(domain):
            return {
                "status": "error",
                "error_type": "missing_employee_filter",
                "message": "Refusing unfiltered hr.payslip query.",
                "hint": (
                    "Use get_payslip_detail or get_employee_payslips with employee_file_id "
                    "and date_from/date_to for the requested month."
                ),
            }

    from gateway.audit.tools import AUDIT_TOOL_EXECUTORS

    if tool_name in UI_TOOL_NAMES:
        return {"status": "ui_directive", "tool": tool_name, "data": tool_input}

    result: Any
    if tool_name in UNIVERSAL_ODOO_EXECUTORS:
        context = build_universal_context(user_message=user_message, user=user)
        result = await UNIVERSAL_ODOO_EXECUTORS[tool_name](adapter, tool_input, context)
    elif tool_name in AUDIT_TOOL_EXECUTORS:
        executor = AUDIT_TOOL_EXECUTORS[tool_name]
        if executor is None:
            return {"status": "error", "message": f"Tool not wired: {tool_name}"}
        result = await executor(adapter, tool_input, context=None)
    elif tool_name in REPORTS_TOOL_NAMES:
        result = await execute_reports_tool(
            tool_name,
            tool_input,
            adapter=adapter,
            session_id=session_id,
        )
    else:
        from gateway.main import execute_tool as main_execute_tool

        result = await asyncio.to_thread(
            main_execute_tool,
            tool_name,
            tool_input,
            adapter,
            session_id,
            user_message,
            user,
        )

    if session_id:
        from gateway.agent.session_entities import update_entities_from_tool

        update_entities_from_tool(session_id, tool_name, tool_input, result)

    if (
        session_id
        and tool_name == "list_attachments"
        and isinstance(result, dict)
        and result.get("status") == "success"
    ):
        from gateway.attachments.visualization import build_file_list_visualization

        built = build_file_list_visualization(result, session_id=session_id)
        if built:
            result = dict(result)
            result["_visualization"] = built

    return result


def format_tool_result(result: Any, *, limit: int = 12000, agent_type: str = "chat") -> str:
    """Serialize tool output for Claude, truncating large payloads."""
    if isinstance(result, dict) and "_sse_events" in result:
        result = {key: value for key, value in result.items() if key != "_sse_events"}
    if agent_type == "audit" and isinstance(result, dict):
        from gateway.agent.audit_helpers import prepare_audit_tool_result

        return prepare_audit_tool_result(result)
    if isinstance(result, str):
        text = result
    else:
        text = json.dumps(result, default=str)
    if len(text) > limit:
        return text[:limit] + "..."
    return text
