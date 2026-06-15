"""Resolve user department tokens to hr.department records."""

from __future__ import annotations

from typing import Any

_DEPT_ALIASES: dict[str, list[str]] = {
    "ict": ["it", "information technology", "i.t."],
    "i.t.": ["it", "information technology"],
    "i t": ["it", "information technology"],
    "info tech": ["information technology", "it"],
    "human resources": ["hr"],
    "hse": ["health safety environment", "health & safety"],
}


def row_name(row: dict[str, Any]) -> str:
    return _row_name(row)


def row_id(row: dict[str, Any]) -> int | None:
    return _row_id(row)


def _row_name(row: dict[str, Any]) -> str:
    name = row.get("name")
    if isinstance(name, (list, tuple)) and len(name) > 1:
        return str(name[1])
    return str(name or "")


def _row_id(row: dict[str, Any]) -> int | None:
    raw = row.get("id")
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _records_from_result(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        rows = result.get("records") or result.get("rows") or []
        return [row for row in rows if isinstance(row, dict)]
    if isinstance(result, list):
        return [row for row in result if isinstance(row, dict)]
    return []


async def find_hr_department(
    *,
    adapter: Any,
    user: Any | None,
    name_token: str,
) -> dict[str, Any] | None:
    """Best-match hr.department for a user token (e.g. ICT → IT)."""
    token = (name_token or "").strip()
    if not token:
        return None

    from gateway.agent.tools_registry import execute_tool

    search_terms = [token]
    search_terms.extend(_DEPT_ALIASES.get(token.lower(), []))

    seen_ids: set[int] = set()
    matches: list[dict[str, Any]] = []
    for term in search_terms:
        if not term:
            continue
        try:
            result = await execute_tool(
                "query_odoo",
                {
                    "model": "hr.department",
                    "domain": [["name", "ilike", term]],
                    "fields": ["name", "manager_id", "total_employee"],
                    "limit": 25,
                    "order": "name asc",
                },
                adapter=adapter,
                user=user,
                session_id=None,
                user_message=token,
            )
        except Exception:
            continue
        for row in _records_from_result(result):
            dept_id = _row_id(row)
            if dept_id is None or dept_id in seen_ids:
                continue
            seen_ids.add(dept_id)
            matches.append(row)

    if not matches:
        return None

    token_l = token.lower()
    for row in matches:
        if _row_name(row).lower() == token_l:
            return row

    if len(matches) == 1:
        return matches[0]

    containing = [row for row in matches if token_l in _row_name(row).lower()]
    if len(containing) == 1:
        return containing[0]

    return matches[0]
