"""Direct financial tool execution when menu + period are already resolved."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from gateway.agent.intent_reconcile import message_continues_financial_flow
from gateway.agent.session_entities import get_entities

from gateway.agent.financial_clarification import pl_clarification_complete

logger = logging.getLogger(__name__)

_TOOL_BY_REPORT_TYPE: dict[str, str] = {
    "trial_balance": "get_trial_balance",
    "pl": "get_financial_report",
    "balance_sheet": "get_financial_report",
    "cash_flow": "get_financial_report",
    "general_ledger": "get_general_ledger",
    "partner_ageing": "get_partner_ageing",
}

_REPORT_NAME_BY_TYPE: dict[str, str] = {
    "pl": "profit_and_loss",
    "balance_sheet": "balance_sheet",
    "cash_flow": "cash_flow",
}


@dataclass
class FinancialFastPathResult:
    text: str
    visualization: dict[str, Any] | None
    suggestions: list[str]
    tool_names: list[str]
    tool_results: list[Any]


async def try_financial_fast_path(
    *,
    session_id: str,
    message: str,
    user: Any | None,
    adapter: Any,
    language: str = "en",
) -> FinancialFastPathResult | None:
    """Fetch financial report when session has report type + date range."""
    entities = get_entities(session_id)
    if entities.get("intent") != "financial_reports":
        return None

    if not message_continues_financial_flow(message):
        return None

    report_type = str(entities.get("financial_report_type") or "")
    date_from = entities.get("date_from")
    date_to = entities.get("date_to")
    if not report_type or not date_from or not date_to:
        return None

    if report_type == "pl" and not pl_clarification_complete(session_id):
        return None

    tool_name = _TOOL_BY_REPORT_TYPE.get(report_type)
    if not tool_name:
        return None

    tool_input: dict[str, Any] = {
        "date_from": str(date_from),
        "date_to": str(date_to),
    }
    if tool_name == "get_financial_report":
        report_name = _REPORT_NAME_BY_TYPE.get(report_type)
        if not report_name:
            return None
        tool_input["report_name"] = report_name
        target_move = entities.get("financial_target_move")
        if target_move in {"posted", "all"}:
            tool_input["target_move"] = target_move

    if report_type == "pl" and entities.get("financial_scope") == "project":
        project_id = entities.get("project_id")
        project_name = entities.get("project_name")
        if not project_id and not project_name:
            return None
        tool_name = "get_project_financial_data"
        tool_input = {
            "date_from": str(date_from),
            "date_to": str(date_to),
        }
        if project_id:
            tool_input["project_id"] = int(project_id)
        if project_name:
            tool_input["project_name"] = str(project_name)

    from gateway.agent.tools_registry import execute_tool

    try:
        result = await execute_tool(
            tool_name,
            tool_input,
            adapter=adapter,
            user=user,
            session_id=session_id,
            user_message=message,
        )
    except Exception as exc:
        logger.warning("[FinancialFastPath] tool %s failed: %s", tool_name, exc)
        return None

    if isinstance(result, dict) and result.get("error"):
        return None

    from gateway.agent.response_finalize import finalize_chat_response

    label = report_type.replace("_", " ").title()
    period = f"{date_from} to {date_to}"
    text = (
        f"{label} for {period}."
        if language != "ar"
        else f"{label} للفترة {period}."
    )
    clean_text, visualization, suggestions, _meta = finalize_chat_response(
        text,
        None,
        [],
        [tool_name],
        [result],
        language,
        message,
        session_id,
    )
    return FinancialFastPathResult(
        text=clean_text,
        visualization=visualization,
        suggestions=suggestions,
        tool_names=[tool_name],
        tool_results=[result],
    )
