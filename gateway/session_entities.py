from __future__ import annotations

import json
from typing import Any

from gateway.session_scope import SessionScopeStore
from gateway.tool_validation import extract_project_id_from_text


PROJECT_FOLLOW_UP_TOOLS = {
    "get_project_expenses",
    "get_project_financial_data",
    "get_project_cost_categories",
}


def enrich_tool_input(
    tool_name: str,
    tool_input: dict[str, Any],
    session_id: str | None,
) -> dict[str, Any]:
    enriched = dict(tool_input or {})
    if not session_id:
        return enriched

    scope = SessionScopeStore.get(session_id)
    confirmed = scope.get("confirmed_entities") or {}
    if tool_name in PROJECT_FOLLOW_UP_TOOLS:
        project = confirmed.get("project")
        if project and project.get("id"):
            enriched["project_id"] = int(project["id"])
            if project.get("name"):
                enriched["project_name"] = str(project["name"])
        else:
            if not enriched.get("project_id") and scope.get("project_id"):
                enriched["project_id"] = scope["project_id"]
            if not enriched.get("project_name") and scope.get("project_name"):
                enriched["project_name"] = scope["project_name"]
    if tool_name == "get_purchase_orders":
        if not enriched.get("client_name") and scope.get("client_name"):
            enriched["client_name"] = scope["client_name"]
        if not enriched.get("partner_ids") and scope.get("partner_ids"):
            enriched["partner_ids"] = scope["partner_ids"]
        if not enriched.get("project_id") and scope.get("project_id"):
            enriched["project_id"] = scope["project_id"]
    return enriched


def update_scope_from_tool_result(
    session_id: str | None,
    tool_name: str,
    tool_input: dict[str, Any],
    result: Any,
) -> None:
    if not session_id or not isinstance(result, dict) or result.get("error"):
        return

    updates: dict[str, Any] = {}
    project_id = result.get("project_id")
    project_name = result.get("project_name") or result.get("project")
    if not project_id:
        project_id = tool_input.get("project_id")
    if not project_name:
        project_name = tool_input.get("project_name")

    if tool_name in PROJECT_FOLLOW_UP_TOOLS:
        if project_id:
            updates["project_id"] = int(project_id)
        if project_name:
            updates["project_name"] = str(project_name)

    if tool_name == "get_purchase_orders":
        request = result.get("request") or {}
        if request.get("client_name"):
            updates["client_name"] = request["client_name"]
        matched_clients = result.get("matched_clients") or []
        if matched_clients:
            updates["partner_ids"] = [int(client["id"]) for client in matched_clients]
        if result.get("project_ids"):
            updates["project_ids"] = result["project_ids"]

    if updates:
        SessionScopeStore.update(session_id, **updates)


def build_session_context_prompt(session_id: str | None) -> str:
    if not session_id:
        return ""

    scope = SessionScopeStore.get(session_id)
    lines: list[str] = []
    if scope.get("project_id"):
        label = scope.get("project_name") or "the last project"
        lines.append(
            f"- Last project discussed: {label} (ID: {scope['project_id']})"
        )
    if scope.get("client_name"):
        lines.append(f"- Last client discussed: {scope['client_name']}")
    if scope.get("partner_ids"):
        lines.append(f"- Known client partner IDs: {scope['partner_ids']}")

    if not lines:
        return ""

    return (
        "\n\nCONVERSATION CONTEXT:\n"
        + "\n".join(lines)
        + "\n- When the user says this project, the expenses, categorize them, or drill down, "
        "reuse the last project ID instead of repeating the previous dashboard.\n"
        + "- For category breakdowns, call get_project_cost_categories.\n"
        + "- Never invent project names or financial numbers.\n"
    )


def infer_scope_from_messages(messages: list[dict[str, Any]]) -> dict[str, Any]:
    inferred: dict[str, Any] = {}
    for message in reversed(messages[-8:]):
        content = message.get("content")
        if isinstance(content, list):
            content = json.dumps(content, default=str)
        if not isinstance(content, str):
            continue
        project_id = extract_project_id_from_text(content)
        if project_id and not inferred.get("project_id"):
            inferred["project_id"] = project_id
    return inferred
