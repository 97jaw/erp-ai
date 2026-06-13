"""HR/Payroll clarification builders for employee disambiguation and slot filling."""

from __future__ import annotations

from typing import Any


def build_employee_disambiguation_clarification(
    *,
    query: str,
    employees: list[dict[str, Any]],
    domain: str = "payroll",
    subtype: str = "payslip_header",
    language: str = "en",
) -> dict[str, Any]:
    """Structured clarification when multiple employees match a name."""
    options = []
    for row in employees[:8]:
        name = str(row.get("name") or "Unknown")
        file_id = str(row.get("emp_id") or row.get("employee_file_id") or "")
        department = row.get("department") or row.get("department_name")
        label = name
        if file_id:
            label = f"{name} (File ID {file_id})"
        if department:
            label = f"{label} — {department}"
        option: dict[str, Any] = {
            "id": row.get("id"),
            "name": name,
            "emp_id": file_id,
            "label": label,
            "type": "employee",
            "entity_type": "employee",
            "entity_id": row.get("id"),
            "action": "confirm_hr_employee",
        }
        if file_id:
            option["query_suffix"] = f" file id {file_id}"
        elif name:
            option["query_suffix"] = f" {name}"
        options.append(option)

    if language == "ar":
        question = (
            f"وجدت أكثر من موظف يطابق \"{query}\".\n\n"
            "أي موظف تقصد؟ (اختر الاسم أو أرسل رقم File ID)"
        )
    else:
        question = (
            f"I found multiple employees matching **{query}**.\n\n"
            "Which employee do you mean? Pick a name below or reply with their File ID."
        )

    return {
        "reason": "employee_disambiguation",
        "question": question,
        "matches": options,
        "options": options,
        "hr_context": {
            "domain": domain,
            "subtype": subtype,
            "prior_query": query,
            "awaiting": ["employee"],
            "resolved": {},
        },
    }


def build_hr_slot_clarification(
    *,
    question: str,
    awaiting: list[str],
    domain: str,
    subtype: str,
    prior_query: str,
    resolved: dict[str, Any] | None = None,
    suggestion_chips: list[str] | None = None,
) -> dict[str, Any]:
    """Ask for a missing HR/payroll slot (employee, period, request type)."""
    return {
        "reason": "hr_slot_clarification",
        "question": question,
        "matches": [],
        "options": [{"label": chip, "type": "suggestion"} for chip in (suggestion_chips or [])],
        "hr_context": {
            "domain": domain,
            "subtype": subtype,
            "prior_query": prior_query,
            "awaiting": awaiting,
            "resolved": dict(resolved or {}),
        },
    }
