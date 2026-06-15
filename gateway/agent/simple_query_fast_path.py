"""Direct answers for simple factual queries — skip vague HR/finance menus."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

LIST_PAGE_SIZE = 30
TEXT_PREVIEW_COUNT = 8

_DEPT_COUNT_RE = re.compile(
    r"\b(?:how\s+many|number\s+of|count\s+of|total)\s+departments?\b|"
    r"\bdepartments?\s+(?:do\s+we\s+have|count|total)\b|"
    r"كم\s+عدد\s+(?:ال)?أ?قسام|عدد\s+(?:ال)?أ?قسام",
    re.I | re.UNICODE,
)
_DEPT_LIST_RE = re.compile(
    r"\b(?:list|show|name)\s+(?:all\s+)?(?:departments?|sections?)"
    r"(?:\s+and\s+(?:departments?|sections?))?\b|"
    r"\b(?:departments?|sections?)\s+and\s+(?:departments?|sections?)\b|"
    r"\bdepartment\s+list\b|"
    r"^(?:departments|all departments|sections|all sections)$|"
    r"(?:اعرض|أرني|قائمة)\s+(?:ال)?أ?قسام",
    re.I | re.UNICODE,
)
_EMP_COUNT_BY_DEPT_RE = re.compile(
    r"\bemployee\s+count\s+by\s+department\b|"
    r"\bhead\s*count\s+by\s+department\b|"
    r"\bemployees?\s+per\s+department\b|"
    r"\bdepartment[-\s]wise\s+employee\s+count\b|"
    r"\bheadcount\s+by\s+department\b",
    re.I,
)
_VAGUE_HR_MENU_RE = re.compile(
    r"^(?:hr|human resources|payroll|employees?)\s*(?:info|information|data)?$|"
    r"^(?:معلومات|بيانات)\s+(?:الموارد|الموظفين|الموارد البشرية)",
    re.I | re.UNICODE,
)
_EMPLOYEE_OF_DEPT_RE = re.compile(
    r"(?:show|list|get|find|display|give)\s+(?:me\s+)?(?:the\s+)?(?:all\s+)?"
    r"employees?\s+(?:of|in|from|for)\s+(?:the\s+)?(.+?)\s*$",
    re.I,
)
_EMPLOYEES_IN_DEPT_RE = re.compile(
    r"employees?\s+in\s+(?:the\s+)?(.+?)(?:\s+department)?\s*$",
    re.I,
)


def _extract_department_name(message: str) -> str | None:
    text = (message or "").strip()
    for pattern in (_EMPLOYEE_OF_DEPT_RE, _EMPLOYEES_IN_DEPT_RE):
        match = pattern.search(text)
        if match:
            dept = match.group(1).strip(" .?!")
            if dept and len(dept) >= 2:
                return dept
    return None


def _is_employee_roster_query(message: str) -> bool:
    return _extract_department_name(message) is not None


@dataclass
class SimpleQueryResult:
    text: str
    visualization: dict[str, Any] | None
    suggestions: list[str]
    tool_names: list[str]


def _wants_department_list(message: str) -> bool:
    text = (message or "").lower()
    return "department" in text or "قسم" in text or "أقسام" in text


def _wants_section_list(message: str) -> bool:
    text = (message or "").lower()
    return "section" in text


def _is_org_directory_query(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if _DEPT_LIST_RE.search(text):
        return True
    if _wants_department_list(text) and _wants_section_list(text):
        return True
    return bool(
        re.search(r"\b(?:list|show|name)\s+all\s+(?:departments?|sections?)", text, re.I)
    )


def _is_simple_factual_query(message: str) -> bool:
    text = (message or "").strip()
    if not text or _VAGUE_HR_MENU_RE.match(text):
        return False
    if _is_employee_roster_query(text):
        return True
    if _EMP_COUNT_BY_DEPT_RE.search(text):
        return True
    if _DEPT_COUNT_RE.search(text):
        return True
    if _is_org_directory_query(text):
        return True
    return False


async def try_simple_query_fast_path(
    *,
    message: str,
    user: Any | None,
    adapter: Any,
    language: str = "en",
) -> SimpleQueryResult | None:
    """Answer department count/list directly without HR submenu."""
    if not _is_simple_factual_query(message):
        return None

    dept_token = _extract_department_name(message)
    if dept_token:
        return await _handle_employee_roster(
            message=message,
            user=user,
            adapter=adapter,
            language=language,
            dept_token=dept_token,
        )
    if _EMP_COUNT_BY_DEPT_RE.search(message or ""):
        return await _handle_employee_count_by_department(
            message=message,
            user=user,
            adapter=adapter,
            language=language,
        )
    if _DEPT_COUNT_RE.search(message or ""):
        return await _handle_department_count(
            message=message,
            user=user,
            adapter=adapter,
            language=language,
        )
    if _is_org_directory_query(message):
        return await _handle_org_directory(
            message=message,
            user=user,
            adapter=adapter,
            language=language,
        )
    return None


async def _handle_employee_roster(
    *,
    message: str,
    user: Any | None,
    adapter: Any,
    language: str,
    dept_token: str,
) -> SimpleQueryResult | None:
    from gateway.agent.department_resolve import find_hr_department, row_id, row_name
    from gateway.agent.response_finalize import finalize_chat_response
    from gateway.agent.tools_registry import execute_tool

    resolved_dept = await find_hr_department(
        adapter=adapter,
        user=user,
        name_token=dept_token,
    )
    if not resolved_dept:
        text = (
            f"I could not find a department named **{dept_token}**. "
            "Try **IT**, **HR**, **Civil**, or ask for the full department list."
            if language != "ar"
            else f"لم أجد قسمًا باسم **{dept_token}**. جرّب **IT** أو **HR** أو اطلب قائمة الأقسام."
        )
        return SimpleQueryResult(
            text=text,
            visualization=None,
            suggestions=[
                "List all departments",
                "How many departments do we have?",
                "Show employees in IT",
            ],
            tool_names=[],
        )

    dept_id = row_id(resolved_dept)
    tool_name = "query_odoo"
    try:
        result = await execute_tool(
            tool_name,
            {
                "model": "hr.employee",
                "domain": [
                    ["active", "=", True],
                    ["department_id", "=", dept_id],
                ],
                "fields": ["name", "emp_id", "job_id", "department_id", "work_email"],
                "limit": 500,
                "order": "name asc",
            },
            adapter=adapter,
            user=user,
            session_id=None,
            user_message=message,
        )
    except Exception as exc:
        logger.warning("[SimpleQueryFastPath] %s failed: %s", tool_name, exc)
        return None

    if isinstance(result, dict) and result.get("error"):
        return None

    resolved_name = row_name(resolved_dept)
    employee_rows = _employee_table_rows(result)
    visualization: dict[str, Any] | None = None
    if not employee_rows:
        text = (
            f"No active employees found in **{resolved_name}**"
            + (f" (searched as “{dept_token}”)." if resolved_name.lower() != dept_token.lower() else ".")
            if language != "ar"
            else f"لا يوجد موظفون نشطون في **{resolved_name}**."
        )
        suggestions = [
            "List all departments",
            "How many departments do we have?",
            "Show employees in HR",
        ]
    else:
        preview = ", ".join(row[0] for row in employee_rows[:TEXT_PREVIEW_COUNT])
        more = len(employee_rows) - TEXT_PREVIEW_COUNT
        suffix = f" — **{more} more** in the paginated table below." if more > 0 else "."
        text = (
            f"Found **{len(employee_rows)}** active employees in **{resolved_name}**: "
            f"{preview}{suffix}"
            if language != "ar"
            else f"**{len(employee_rows)}** موظفًا نشطًا في **{resolved_name}**: {preview}{suffix}"
        )
        visualization = _build_paginated_table_visual(
            label=f"Employees — {resolved_name}",
            headers=["Name", "File ID", "Job", "Email"],
            rows=employee_rows,
            unit="employees",
        )
        suggestions = [
            "Show employee count by department",
            "List all departments",
            "How many departments do we have?",
        ]

    clean_text, built_visual, suggestion_labels, _meta = finalize_chat_response(
        text,
        visualization,
        suggestions,
        [tool_name],
        [result],
        language,
        message,
        None,
    )
    return SimpleQueryResult(
        text=clean_text,
        visualization=built_visual or visualization,
        suggestions=suggestion_labels,
        tool_names=[tool_name],
    )


async def _handle_employee_count_by_department(
    *,
    message: str,
    user: Any | None,
    adapter: Any,
    language: str,
) -> SimpleQueryResult | None:
    from gateway.agent.response_finalize import finalize_chat_response
    from gateway.agent.tools_registry import execute_tool

    tool_name = "aggregate_odoo"
    try:
        result = await execute_tool(
            tool_name,
            {
                "model": "hr.employee",
                "domain": [["active", "=", True]],
                "group_by": ["department_id"],
                "aggregates": ["id:count"],
                "limit": 100,
                "order": "department_id",
            },
            adapter=adapter,
            user=user,
            session_id=None,
            user_message=message,
        )
    except Exception as exc:
        logger.warning("[SimpleQueryFastPath] %s failed: %s", tool_name, exc)
        return None

    if isinstance(result, dict) and result.get("error"):
        return None

    chart_rows = _aggregate_group_rows(result, "department_id")
    if not chart_rows:
        return None

    total_employees = sum(int(row[2]) for row in chart_rows)
    top = sorted(chart_rows, key=lambda row: int(row[2]), reverse=True)[:TEXT_PREVIEW_COUNT]
    preview = ", ".join(f"**{row[0]}** ({row[2]})" for row in top)
    text = (
        f"**{total_employees}** active employees across **{len(chart_rows)}** departments. "
        f"Top: {preview}. Full breakdown in the chart below."
        if language != "ar"
        else f"**{total_employees}** موظفًا نشطًا في **{len(chart_rows)}** قسمًا. الأعلى: {preview}."
    )
    visualization = _build_headcount_chart_visual(chart_rows)
    suggestions = [
        "List all departments",
        "How many departments do we have?",
        "Show employees in IT",
    ]

    clean_text, built_visual, suggestion_labels, _meta = finalize_chat_response(
        text,
        visualization,
        suggestions,
        [tool_name],
        [result],
        language,
        message,
        None,
    )
    return SimpleQueryResult(
        text=clean_text,
        visualization=built_visual or visualization,
        suggestions=suggestion_labels,
        tool_names=[tool_name],
    )


async def _handle_department_count(
    *,
    message: str,
    user: Any | None,
    adapter: Any,
    language: str,
) -> SimpleQueryResult | None:
    from gateway.agent.response_finalize import finalize_chat_response
    from gateway.agent.tools_registry import execute_tool

    tool_name = "aggregate_odoo"
    try:
        result = await execute_tool(
            tool_name,
            {
                "model": "hr.department",
                "domain": [],
                "aggregates": ["id:count"],
            },
            adapter=adapter,
            user=user,
            session_id=None,
            user_message=message,
        )
    except Exception as exc:
        logger.warning("[SimpleQueryFastPath] %s failed: %s", tool_name, exc)
        return None

    if isinstance(result, dict) and result.get("error"):
        return None

    total = _extract_department_count(result)
    if total is None:
        return None

    text = (
        f"Elrace has **{total}** departments in Odoo."
        if language != "ar"
        else f"لدى Elrace **{total}** قسمًا في أودو."
    )
    suggestions = [
        "Show employee count by department",
        "Department managers list",
        "List all departments",
    ]

    clean_text, built_visual, suggestion_labels, _meta = finalize_chat_response(
        text,
        None,
        suggestions,
        [tool_name],
        [result],
        language,
        message,
        None,
    )
    return SimpleQueryResult(
        text=clean_text,
        visualization=built_visual,
        suggestions=suggestion_labels,
        tool_names=[tool_name],
    )


async def _handle_org_directory(
    *,
    message: str,
    user: Any | None,
    adapter: Any,
    language: str,
) -> SimpleQueryResult | None:
    from gateway.agent.response_finalize import finalize_chat_response
    from gateway.agent.tools_registry import execute_tool

    wants_depts = _wants_department_list(message)
    wants_sections = _wants_section_list(message)
    tool_names: list[str] = []
    tool_results: list[Any] = []
    dept_rows: list[list[Any]] = []
    section_rows: list[list[Any]] = []

    if wants_depts:
        tool_name = "query_odoo"
        try:
            result = await execute_tool(
                tool_name,
                {
                    "model": "hr.department",
                    "domain": [],
                    "fields": ["name", "manager_id", "total_employee"],
                    "limit": 100,
                    "order": "name asc",
                },
                adapter=adapter,
                user=user,
                session_id=None,
                user_message=message,
            )
        except Exception as exc:
            logger.warning("[SimpleQueryFastPath] %s failed: %s", tool_name, exc)
            return None
        if isinstance(result, dict) and result.get("error"):
            return None
        dept_rows = _department_table_rows(result)
        tool_names.append(tool_name)
        tool_results.append(result)

    if wants_sections:
        section_rows = await _fetch_section_rows(
            adapter=adapter,
            user=user,
            message=message,
        )
        if section_rows:
            tool_names.append("aggregate_odoo")

    if not dept_rows and not section_rows:
        return None

    combined_rows = _merge_org_directory_rows(dept_rows, section_rows)
    parts: list[str] = []
    if dept_rows:
        parts.append(f"**{len(dept_rows)}** departments")
    if section_rows:
        parts.append(f"**{len(section_rows)}** sections")
    summary = " and ".join(parts)
    preview_names = [row[1] for row in combined_rows[:TEXT_PREVIEW_COUNT]]
    preview = ", ".join(preview_names)
    more = len(combined_rows) - TEXT_PREVIEW_COUNT
    suffix = f" — **{more} more** in the paginated table below." if more > 0 else "."
    text = (
        f"Elrace has {summary}: {preview}{suffix}"
        if language != "ar"
        else f"لدى Elrace {summary}: {preview}{suffix}"
    )

    label = "Company departments and sections"
    if dept_rows and not section_rows:
        label = "Company departments"
        visualization = _build_paginated_table_visual(
            label=label,
            headers=["Department", "Manager", "Employees"],
            rows=dept_rows,
            unit="departments",
        )
    elif section_rows and not dept_rows:
        label = "Company sections"
        visualization = _build_paginated_table_visual(
            label=label,
            headers=["Section", "Head", "Employees"],
            rows=section_rows,
            unit="sections",
        )
    else:
        visualization = _build_paginated_table_visual(
            label=label,
            headers=["Type", "Name", "Manager / Head", "Headcount"],
            rows=combined_rows,
            unit="records",
        )
    suggestions = [
        "Show employee count by department",
        "How many departments do we have?",
        "Show employees in IT",
    ]

    clean_text, built_visual, suggestion_labels, _meta = finalize_chat_response(
        text,
        visualization,
        suggestions,
        tool_names,
        tool_results,
        language,
        message,
        None,
    )
    return SimpleQueryResult(
        text=clean_text,
        visualization=built_visual or visualization,
        suggestions=suggestion_labels,
        tool_names=tool_names,
    )


async def _fetch_section_rows(
    *,
    adapter: Any,
    user: Any | None,
    message: str,
) -> list[list[Any]]:
    from gateway.agent.tools_registry import execute_tool

    try:
        result = await execute_tool(
            "aggregate_odoo",
            {
                "model": "hr.employee",
                "domain": [["active", "=", True]],
                "group_by": ["section_id"],
                "aggregates": ["id:count"],
                "limit": 200,
                "order": "section_id",
            },
            adapter=adapter,
            user=user,
            session_id=None,
            user_message=message,
        )
        rows = _aggregate_group_rows(result, "section_id")
        if rows:
            return rows
    except Exception as exc:
        logger.warning("[SimpleQueryFastPath] section aggregate failed: %s", exc)

    for model in ("hr.section", "employee.section", "hr.employee.section"):
        try:
            result = await execute_tool(
                "query_odoo",
                {
                    "model": model,
                    "domain": [],
                    "fields": ["name"],
                    "limit": 200,
                    "order": "name asc",
                },
                adapter=adapter,
                user=user,
                session_id=None,
                user_message=message,
            )
        except Exception:
            continue
        if isinstance(result, dict) and result.get("error"):
            continue
        records = result.get("records") or result.get("rows") or [] if isinstance(result, dict) else []
        if records:
            return [[_field_label(row.get("name")), "", ""] for row in records if isinstance(row, dict)]
    return []


def _merge_org_directory_rows(
    dept_rows: list[list[Any]],
    section_rows: list[list[Any]],
) -> list[list[Any]]:
    combined: list[list[Any]] = []
    for name, manager, count in dept_rows:
        combined.append(["Department", name, manager, count])
    for name, manager, count in section_rows:
        combined.append(["Section", name, manager, count])
    return combined


def _aggregate_group_rows(result: Any, group_field: str) -> list[list[Any]]:
    groups: list[Any] = []
    if isinstance(result, dict):
        groups = list(result.get("groups") or result.get("rows") or [])
    elif isinstance(result, list):
        groups = result

    table: list[list[Any]] = []
    for row in groups:
        if not isinstance(row, dict):
            continue
        label = str(row.get("group_label") or _field_label(row.get(group_field)) or "").strip()
        if not label or label.lower() in {"false", "none", "unassigned"}:
            continue
        count = row.get("id:count") or row.get("__count") or row.get("id_count") or 0
        table.append([label, "", int(count)])
    return sorted(table, key=lambda item: str(item[0]).lower())


def _build_headcount_chart_visual(chart_rows: list[list[Any]]) -> dict[str, Any]:
    ordered = sorted(chart_rows, key=lambda row: int(row[2]), reverse=True)
    labels = [str(row[0]) for row in ordered]
    values = [int(row[2]) for row in ordered]
    return {
        "visual_type": "BAR_CHART",
        "label": "Employee count by department",
        "value": sum(values),
        "unit": "employees",
        "disclosure_exempt": True,
        "scrollable": len(labels) > 6,
        "data": {
            "labels": labels,
            "values": values,
            "rows": [[label, value] for label, value in zip(labels, values)],
        },
    }


def _build_paginated_table_visual(
    *,
    label: str,
    headers: list[str],
    rows: list[list[Any]],
    unit: str,
) -> dict[str, Any]:
    from gateway.query_pagination import QueryPageStore

    total = len(rows)
    query_id = QueryPageStore.register(
        headers=headers,
        rows=rows,
        label=label,
        visual_type="DATA_TABLE",
    )
    page_rows = rows[:LIST_PAGE_SIZE]
    return {
        "visual_type": "DATA_TABLE",
        "label": label,
        "value": total,
        "unit": unit,
        "query_id": query_id,
        "page_size": LIST_PAGE_SIZE,
        "total_records": total,
        "shown_records": len(page_rows),
        "can_expand": total > LIST_PAGE_SIZE,
        "expand_label": f"Browse all {total} {unit}",
        "level": "standard",
        "disclosure_exempt": True,
        "data": {"headers": headers, "rows": page_rows, "all_rows": rows},
    }


def _field_label(value: Any) -> str:
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return str(value[1])
    return str(value or "")


def _department_table_rows(result: Any) -> list[list[Any]]:
    rows: list[Any] = []
    if isinstance(result, dict):
        rows = list(result.get("records") or result.get("rows") or [])
    elif isinstance(result, list):
        rows = result
    table: list[list[Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        table.append(
            [
                _field_label(row.get("name")),
                _field_label(row.get("manager_id")),
                row.get("total_employee") or 0,
            ]
        )
    return table


def _employee_table_rows(result: Any) -> list[list[Any]]:
    rows: list[Any] = []
    if isinstance(result, dict):
        rows = list(result.get("records") or result.get("rows") or [])
    elif isinstance(result, list):
        rows = result
    table: list[list[Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        table.append(
            [
                _field_label(row.get("name")),
                row.get("emp_id") or row.get("employee_code") or "",
                _field_label(row.get("job_id")),
                row.get("work_email") or "",
            ]
        )
    return table


def _extract_department_count(result: Any) -> int | None:
    if isinstance(result, dict):
        if "total_count" in result:
            return int(result["total_count"])
        if "count" in result:
            return int(result["count"])
        rows = result.get("groups") or result.get("rows") or []
        if rows and isinstance(rows[0], dict):
            for key in ("id:count", "__count", "id_count", "count"):
                if key in rows[0]:
                    return int(rows[0][key])
    if isinstance(result, list) and result:
        return len(result)
    return None
