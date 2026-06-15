"""Resolve project references from session context or natural-language hints."""

from __future__ import annotations

import asyncio
import logging
import re
from difflib import SequenceMatcher
from typing import Any

logger = logging.getLogger(__name__)

FAST_PROJECT_SEARCH_TIMEOUT_S = 5.0
FAST_PROJECT_SEARCH_LIMIT = 8

_PROJECT_ID_RE = re.compile(r"\(ID:\s*(\d+)\)", re.I)


def extract_project_id_from_message(message: str) -> int | None:
    match = _PROJECT_ID_RE.search(message or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _row_id(row: dict[str, Any]) -> int | None:
    raw = row.get("id")
    if isinstance(raw, (list, tuple)) and raw:
        raw = raw[0]
    try:
        return int(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _row_name(row: dict[str, Any]) -> str:
    name = row.get("name")
    if isinstance(name, (list, tuple)) and len(name) > 1:
        return str(name[1])
    return str(name or "")


def _row_search_text(row: dict[str, Any]) -> str:
    parts = [_row_name(row)]
    wo = row.get("wo_ref_no")
    if wo:
        parts.append(str(wo))
    arabic = row.get("project_name_arabic")
    if arabic:
        parts.append(str(arabic))
    return " ".join(parts)


def _build_fast_search_domains(token: str) -> list[list[Any]]:
    """Ordered Odoo domains — phrase and all-words AND before loose OR."""
    from gateway.core.entity_resolver import ACRONYM_MAP, ARABIC_EQUIVALENTS
    from gateway.core.project_query_utils import normalize_project_search_tokens

    cleaned = (token or "").strip()
    if not cleaned:
        return []

    domains: list[list[Any]] = [[["name", "ilike", cleaned]]]

    words = normalize_project_search_tokens(cleaned)
    if len(words) > 1:
        and_clauses = [["name", "ilike", word] for word in words]
        domains.append(["&"] * (len(words) - 1) + and_clauses)
        if len(words) > 2:
            core_words = words[:2]
            core_clauses = [["name", "ilike", word] for word in core_words]
            domains.insert(1, ["&"] + core_clauses)

    lowered = cleaned.lower()
    for arabic_phrase in ARABIC_EQUIVALENTS.get(lowered, []):
        domains.append([["name", "ilike", arabic_phrase]])

    for word in words:
        expansion = ACRONYM_MAP.get(word.lower())
        if expansion:
            domains.append([["name", "ilike", expansion]])

    if len(words) > 1:
        or_clauses = [["name", "ilike", word] for word in words]
        domains.append(["|"] * (len(words) - 1) + or_clauses)

    return domains


def score_project_row(row: dict[str, Any], query: str) -> float:
    """Rank project rows for picker display — prefer phrase and all-word matches."""
    from gateway.core.project_query_utils import (
        extract_project_number_hint,
        project_record_matches_number,
    )

    query_lower = (query or "").strip().lower()
    if not query_lower:
        return 0.0

    query_words = {word for word in re.split(r"\s+", query_lower) if word}
    best = 0.0
    for blob in {_row_search_text(row).lower()}:
        if blob == query_lower:
            best = max(best, 1.0)
        elif blob.startswith(query_lower):
            best = max(best, 0.92)
        elif query_lower in blob:
            best = max(best, 0.88)
        elif query_words and all(word in blob for word in query_words):
            best = max(best, 0.82)
        else:
            overlap = len(query_words & {word for word in blob.split() if word})
            if query_words:
                best = max(best, (overlap / len(query_words)) * 0.55)
        best = max(best, SequenceMatcher(None, query_lower, blob).ratio() * 0.7)

    number_hint = extract_project_number_hint(query)
    if number_hint and project_record_matches_number(row, number_hint):
        best = max(best, 0.93)
    return best


def rank_project_rows(rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    """Deduplicate by id and sort by relevance to the user's hint."""
    by_id: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid = _row_id(row)
        if pid is None:
            continue
        by_id[pid] = row
    ranked = sorted(by_id.values(), key=lambda row: (-score_project_row(row, query), _row_name(row).lower()))
    return ranked


async def search_projects_fast(
    adapter: Any,
    name_hint: str,
    *,
    limit: int = FAST_PROJECT_SEARCH_LIMIT,
) -> list[dict[str, Any]]:
    """Quick project lookup — phrase/all-word domains, relevance ranking, 5s cap."""
    token = (name_hint or "").strip()
    if not token or len(token) < 2:
        return []

    domains = _build_fast_search_domains(token)
    collected: list[dict[str, Any]] = []
    seen_ids: set[int] = set()

    def _search(domain: list[Any]) -> list[dict[str, Any]]:
        return adapter.safe_search_read(
            "project.project",
            domain,
            ["name", "agreement_id", "wo_ref_no", "project_name_arabic"],
            limit=max(limit * 3, 20),
            order="name asc",
        )

    for domain in domains:
        if len(collected) >= limit * 3:
            break
        try:
            rows = await asyncio.wait_for(
                asyncio.to_thread(_search, domain),
                timeout=FAST_PROJECT_SEARCH_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            logger.warning("[ProjectResolve] fast search timed out hint=%r domain=%r", token, domain)
            continue
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ProjectResolve] fast search failed hint=%r: %s", token, exc)
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            pid = _row_id(row)
            if pid is None or pid in seen_ids:
                continue
            seen_ids.add(pid)
            collected.append(row)

    if not collected:
        return []

    ranked = rank_project_rows(collected, token)
    return ranked[:limit]


async def find_project(
    *,
    adapter: Any,
    user: Any | None,
    name_hint: str | None = None,
    project_id: int | None = None,
) -> dict[str, Any] | None:
    """Best-match project.project row by id or name hint."""
    from gateway.agent.tools_registry import execute_tool

    if project_id:
        result = await execute_tool(
            "query_odoo",
            {
                "model": "project.project",
                "domain": [["id", "=", int(project_id)]],
                "fields": ["name", "agreement_id"],
                "limit": 1,
            },
            adapter=adapter,
            user=user,
            session_id=None,
            user_message="",
        )
        rows = _records_from_result(result)
        return rows[0] if rows else None

    token = (name_hint or "").strip()
    if not token:
        return None

    rows = await search_projects_fast(adapter, token, limit=10)
    if not rows:
        return None

    if len(rows) == 1:
        return rows[0]

    top_score = score_project_row(rows[0], token)
    second_score = score_project_row(rows[1], token) if len(rows) > 1 else 0.0
    if top_score >= 0.82 and top_score - second_score >= 0.12:
        return rows[0]

    lowered = token.lower()
    for row in rows:
        if _row_name(row).lower() == lowered:
            return row
    for row in rows:
        if lowered in _row_name(row).lower():
            return row
    return rows[0]


def agreement_id_from_project(row: dict[str, Any]) -> int | None:
    value = row.get("agreement_id")
    if isinstance(value, (list, tuple)) and value:
        try:
            return int(value[0])
        except (TypeError, ValueError):
            return None
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def project_id_from_row(row: dict[str, Any]) -> int | None:
    return _row_id(row)


def project_name_from_row(row: dict[str, Any]) -> str:
    return _row_name(row)


def _records_from_result(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        rows = result.get("records") or result.get("rows") or []
        return [row for row in rows if isinstance(row, dict)]
    if isinstance(result, list):
        return [row for row in result if isinstance(row, dict)]
    return []
