"""Deterministic fleet vehicle query routing."""

from __future__ import annotations

import re
from typing import Any

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent
from gateway.core.hr_payroll_composer import extract_employee_name, extract_inline_file_id
from gateway.fleet_tools import extract_license_plate


def is_fleet_orchestration_query(message: str, intent: Intent) -> bool:
    """True when the user asks about assigned vehicles or fleet records."""
    blob = f"{message} {intent.specific_intent} {intent.subject_area}".lower()
    if any(
        token in blob
        for token in (
            "fleet",
            "vehicle",
            "vehicles",
            "assigned car",
            "assigned vehicle",
            "license plate",
            "plate number",
            "car for",
            "car assigned",
            "vehicle assigned",
        )
    ):
        return True
    if re.search(r".+'s (car|vehicle)", blob):
        return True
    if extract_license_plate(message):
        return True
    return False


def resolve_fleet_tool(
    message: str,
    intent: Intent,
    context: ContextStack | None = None,
) -> tuple[str, dict[str, Any]] | None:
    """Return (tool_name, payload) for fleet queries."""
    if not is_fleet_orchestration_query(message, intent):
        return None

    from gateway.core.hr_payroll_composer import get_pending_hr_context, merge_pending_hr_context

    pending = merge_pending_hr_context(context, message)
    resolved = pending.get("resolved") or {}
    payload: dict[str, Any] = {"limit": 20}

    file_id = extract_inline_file_id(message) or resolved.get("employee_file_id")
    name_hint = extract_employee_name(message) or resolved.get("employee_name_hint")
    if not name_hint and "'s" in message:
        name_hint = message.split("'s", 1)[0].strip()
    if not name_hint:
        assigned_match = re.search(
            r"(?:\b(?:show|get|list|find)\s+)?([A-Za-z][A-Za-z\s'.-]{1,40}?)\s+assigned\s+(?:vehicle|car)\b",
            message,
            re.I,
        )
        if assigned_match:
            name_hint = assigned_match.group(1).strip()
    if name_hint:
        from gateway.core.hr_payroll_composer import strip_conversational_filler

        name_hint = strip_conversational_filler(name_hint)

    plate = extract_license_plate(message)
    if file_id:
        payload["employee_file_id"] = str(file_id)
    if name_hint:
        payload["employee_name"] = name_hint
    if plate:
        payload["license_plate"] = plate

    project_match = re.search(
        r"\b(?:project|on)\s+([A-Za-z0-9][A-Za-z0-9\s'.-]{2,60}?)(?:\s*$|\s+vehicle|\s+car|\s+fleet)",
        message,
        re.I,
    )
    if project_match:
        payload["project_name"] = project_match.group(1).strip()

    if not any(key in payload for key in ("employee_file_id", "employee_name", "license_plate", "project_name")):
        pending_ctx = get_pending_hr_context(context)
        if pending_ctx.get("domain") == "fleet":
            if resolved.get("employee_file_id"):
                payload["employee_file_id"] = str(resolved["employee_file_id"])
            if resolved.get("employee_name_hint"):
                payload["employee_name"] = str(resolved["employee_name_hint"])

    return "search_fleet_vehicles", payload
