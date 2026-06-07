"""Role-aware Odoo search limits and transparent pagination metadata."""

from __future__ import annotations

import logging
import os
from typing import Any

from admin.auth.principal import CurrentUser
from adapters.v14.connector import OdooV14Adapter

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_LIMIT = int(os.environ.get("OOA_DEFAULT_SEARCH_LIMIT", "100"))
POWER_USER_SEARCH_LIMIT = int(os.environ.get("OOA_POWER_USER_SEARCH_LIMIT", "200"))
SUPER_ADMIN_SEARCH_LIMIT = int(os.environ.get("OOA_SUPER_ADMIN_SEARCH_LIMIT", "2000"))
ABSOLUTE_MAX_LIMIT = int(os.environ.get("OOA_ABSOLUTE_SEARCH_LIMIT", "5000"))
SEARCH_PAGE_SIZE = int(os.environ.get("OOA_SEARCH_PAGE_SIZE", "80"))


def is_elevated_query_user(user: CurrentUser | None) -> bool:
    if user is None:
        return False
    return user.is_super_admin or user.has_permission("odoo.full_access")


def max_limit_for_user(user: CurrentUser | None) -> int:
    if is_elevated_query_user(user):
        return min(SUPER_ADMIN_SEARCH_LIMIT, ABSOLUTE_MAX_LIMIT)
    if user and user.has_permission("data.all_projects"):
        return min(POWER_USER_SEARCH_LIMIT, ABSOLUTE_MAX_LIMIT)
    return min(DEFAULT_SEARCH_LIMIT, ABSOLUTE_MAX_LIMIT)


def default_limit_for_user(user: CurrentUser | None) -> int:
    """Limit applied when the agent omits `limit` on list/search tools."""
    return max_limit_for_user(user)


def resolve_tool_limit(
    user: CurrentUser | None,
    tool_input: dict[str, Any],
    *,
    tool_name: str,
) -> tuple[int, dict[str, Any]]:
    """
    Normalize `limit` on tool_input.
    Returns (effective_limit, limit_meta for transparency).
    """
    scoped = dict(tool_input)
    raw = scoped.get("limit")
    requested: int | None = None
    if raw is not None and raw != "":
        try:
            requested = int(raw)
        except (TypeError, ValueError):
            requested = None

    ceiling = max_limit_for_user(user)
    if requested is None:
        effective = default_limit_for_user(user)
        meta = {
            "limit_requested": None,
            "limit_applied": effective,
            "limit_defaulted": True,
            "limit_ceiling": ceiling,
        }
    else:
        effective = min(max(requested, 1), ceiling)
        meta = {
            "limit_requested": requested,
            "limit_applied": effective,
            "limit_defaulted": False,
            "limit_ceiling": ceiling,
            "limit_capped": requested > ceiling,
        }

    scoped["limit"] = effective
    scoped["_limit_meta"] = meta
    return effective, meta


def apply_query_limits_to_tool_input(
    tool_name: str,
    tool_input: dict[str, Any],
    user: CurrentUser | None,
) -> dict[str, Any]:
    """Inject role-based defaults for tools that accept `limit`."""
    if tool_name not in {
        "search_odoo",
        "get_projects_summary",
        "get_purchase_orders",
        "group_and_aggregate",
        "get_top_projects_by_metric",
        "get_projects_by_client",
        "get_projects_with_overrun",
        "list_recent_payslips",
        "get_my_payslips",
        "get_employee_payslips",
    }:
        return tool_input

    effective, meta = resolve_tool_limit(user, tool_input, tool_name=tool_name)
    scoped = dict(tool_input)
    scoped["limit"] = effective
    scoped["_limit_meta"] = meta
    return scoped


def _search_count_safe(adapter: OdooV14Adapter, model: str, domain: list[Any]) -> int | None:
    try:
        return int(adapter.search_count(model, domain))
    except Exception as exc:
        logger.warning("[QueryLimits] search_count failed for %s: %s", model, exc)
        return None


def search_read_pages(
    adapter: OdooV14Adapter,
    *,
    model: str,
    domain: list[Any],
    fields: list[str],
    limit: int,
    order: str | None = None,
) -> list[dict[str, Any]]:
    """Fetch up to `limit` rows using offset pagination (Odoo XML-RPC safe page size)."""
    if limit <= 0:
        return []

    page_size = min(max(SEARCH_PAGE_SIZE, 1), limit)
    rows: list[dict[str, Any]] = []
    offset = 0

    while len(rows) < limit:
        batch_limit = min(page_size, limit - len(rows))
        batch = adapter.search_read(
            model=model,
            domain=domain,
            fields=fields,
            limit=batch_limit,
            offset=offset,
            order=order,
        )
        if not batch:
            break
        rows.extend(batch)
        offset += len(batch)
        if len(batch) < batch_limit:
            break

    return rows[:limit]


def build_query_meta(
    *,
    returned_count: int,
    limit_applied: int,
    total_matching: int | None,
    limit_meta: dict[str, Any] | None,
    user: CurrentUser | None,
    model: str | None = None,
) -> dict[str, Any]:
    truncated = False
    if total_matching is not None:
        truncated = total_matching > returned_count
    else:
        truncated = returned_count >= limit_applied

    parts = [f"Returned {returned_count} row(s)"]
    if total_matching is not None:
        parts.append(f"{total_matching} match this query in Odoo")
    parts.append(f"limit applied: {limit_applied}")

    meta: dict[str, Any] = {
        "returned_count": returned_count,
        "total_matching": total_matching,
        "limit_applied": limit_applied,
        "truncated": truncated,
        "summary": " — ".join(parts) + ".",
        "pagination": (
            "Results use Odoo search_read with a row limit (not necessarily every "
            "matching record in one response)."
        ),
    }
    if limit_meta:
        meta.update(limit_meta)
    if truncated:
        meta["hint"] = (
            "More records exist in Odoo than were returned. "
            "Narrow filters, raise `limit`, or ask to export/report for the full set."
        )
    if is_elevated_query_user(user):
        meta["elevated_access"] = True
        if model:
            meta["model"] = model
        if truncated and total_matching is not None:
            meta["super_admin_note"] = (
                f"Database has {total_matching} matching `{model or 'records'}`; "
                f"this response includes {returned_count} (limit {limit_applied})."
            )
    return meta


def wrap_search_odoo_result(
    rows: list[dict[str, Any]],
    *,
    adapter: OdooV14Adapter,
    model: str,
    domain: list[Any],
    limit_applied: int,
    limit_meta: dict[str, Any] | None,
    user: CurrentUser | None,
) -> dict[str, Any]:
    total = _search_count_safe(adapter, model, domain)
    return {
        "records": rows,
        "_query_meta": build_query_meta(
            returned_count=len(rows),
            limit_applied=limit_applied,
            total_matching=total,
            limit_meta=limit_meta,
            user=user,
            model=model,
        ),
    }


def execute_search_odoo(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
    user: CurrentUser | None,
) -> dict[str, Any]:
    model = tool_input["model"]
    domain = tool_input.get("filters") or []
    fields = tool_input.get("fields") or ["id", "name"]
    limit_applied = int(tool_input.get("limit") or default_limit_for_user(user))
    order = tool_input.get("order")
    limit_meta = tool_input.get("_limit_meta")

    rows = search_read_pages(
        adapter,
        model=model,
        domain=domain,
        fields=fields,
        limit=limit_applied,
        order=order,
    )
    return wrap_search_odoo_result(
        rows,
        adapter=adapter,
        model=model,
        domain=domain,
        limit_applied=limit_applied,
        limit_meta=limit_meta if isinstance(limit_meta, dict) else None,
        user=user,
    )
