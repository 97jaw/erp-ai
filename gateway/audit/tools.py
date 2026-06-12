"""Audit tools — mail.message + mail.tracking.value composition."""

from __future__ import annotations

import asyncio
import html
import logging
import re
from typing import Any

from gateway.tools.universal_odoo import FORBIDDEN_MODELS

logger = logging.getLogger(__name__)

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_DEFAULT_AUDIT_TRAIL_LIMIT = 50
_DEFAULT_USER_ACTIVITY_LIMIT = 100

_MODEL_LABELS: dict[str, str] = {
    "project.project": "Project",
    "project.task": "Task",
    "project.attachment": "Project Attachment",
    "agreement": "Agreement",
    "agreement.attachment": "Agreement Attachment",
    "project.expense": "Project Expense",
}

AUDIT_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_audit_trail",
        "description": (
            "Get the change history (chatter + field tracking) for a single Odoo "
            "record. Returns a chronological timeline with author, message body, "
            "and field-level old→new values from mail.tracking.value.\n\n"
            "USE FOR: 'what changed on project X', 'who modified this agreement', "
            "'timeline for record Y this week'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "model": {
                    "type": "string",
                    "description": "Odoo model technical name, e.g. project.project",
                },
                "record_id": {
                    "type": "integer",
                    "description": "Database id of the record (res_id on mail.message)",
                },
                "date_from": {
                    "type": "string",
                    "description": "Optional ISO date lower bound (inclusive)",
                },
                "date_to": {
                    "type": "string",
                    "description": "Optional ISO date upper bound (inclusive)",
                },
                "limit": {
                    "type": "integer",
                    "default": _DEFAULT_AUDIT_TRAIL_LIMIT,
                    "description": "Max mail.message rows (default 50)",
                },
            },
            "required": ["model", "record_id"],
        },
    },
    {
        "name": "get_user_activity",
        "description": (
            "Summarize what a user changed across Odoo — grouped by model and "
            "record. Resolves user_name to author partner or user_id to res.users "
            "partner. Returns change counts and last-change timestamps.\n\n"
            "USE FOR: 'what did Ahmed do today', 'activity log for user X this month'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {
                    "type": "integer",
                    "description": "res.users id (Odoo uid) — resolved to author partner",
                },
                "user_name": {
                    "type": "string",
                    "description": "Partner/user name fragment — ilike search on res.partner",
                },
                "date_from": {"type": "string"},
                "date_to": {"type": "string"},
                "model_filter": {
                    "type": "string",
                    "description": "Optional model technical name to restrict activity",
                },
                "limit": {
                    "type": "integer",
                    "default": _DEFAULT_USER_ACTIVITY_LIMIT,
                },
            },
        },
    },
]

AUDIT_TOOL_EXECUTORS = {
    "get_audit_trail": None,  # set after function definitions
    "get_user_activity": None,
}


def _model_forbidden(model: str) -> bool:
    return (model or "").strip() in FORBIDDEN_MODELS


def _strip_html(raw: Any) -> str:
    if not raw:
        return ""
    text = html.unescape(str(raw))
    text = _HTML_TAG_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _m2o_label(value: Any, default: str = "") -> str:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1])
    return default


def _m2o_id(value: Any) -> int | None:
    if isinstance(value, (list, tuple)) and value:
        try:
            return int(value[0])
        except (TypeError, ValueError):
            return None
    if isinstance(value, int):
        return value
    return None


def _append_date_filters(
    domain: list[Any],
    *,
    date_from: str | None,
    date_to: str | None,
    field: str = "date",
) -> list[Any]:
    out = list(domain)
    if date_from:
        out.append([field, ">=", date_from])
    if date_to:
        out.append([field, "<=", date_to])
    return out


async def _search_read(
    adapter: Any,
    model: str,
    domain: list[Any],
    fields: list[str],
    *,
    limit: int,
    order: str | None = None,
) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {"limit": limit}
    if order:
        kwargs["order"] = order

    def _call() -> list[dict[str, Any]]:
        return adapter.safe_search_read(model, domain, fields, **kwargs)

    return await asyncio.to_thread(_call)


def _collect_tracking_ids(messages: list[dict[str, Any]]) -> list[int]:
    ids: list[int] = []
    seen: set[int] = set()
    for message in messages:
        raw = message.get("tracking_value_ids")
        if not raw:
            continue
        if isinstance(raw, list):
            for item in raw:
                tid = int(item) if isinstance(item, int) else _m2o_id(item)
                if tid and tid not in seen:
                    seen.add(tid)
                    ids.append(tid)
    return ids


def _tracking_change_row(tv: dict[str, Any]) -> dict[str, str]:
    field = str(tv.get("field_desc") or "Field")
    for old_key, new_key in (
        ("old_value_char", "new_value_char"),
        ("old_value_integer", "new_value_integer"),
        ("old_value_float", "new_value_float"),
        ("old_value_datetime", "new_value_datetime"),
    ):
        old_val = tv.get(old_key)
        new_val = tv.get(new_key)
        if old_val is not False or new_val is not False:
            if old_val not in (False, None) or new_val not in (False, None):
                return {
                    "field": field,
                    "old": "" if old_val in (False, None) else str(old_val),
                    "new": "" if new_val in (False, None) else str(new_val),
                }
    return {"field": field, "old": "", "new": ""}


async def _load_tracking_map(
    adapter: Any,
    tracking_ids: list[int],
) -> dict[int, list[dict[str, str]]]:
    if not tracking_ids:
        return {}
    rows = await _search_read(
        adapter,
        "mail.tracking.value",
        [["id", "in", tracking_ids]],
        [
            "mail_message_id",
            "field_desc",
            "old_value_char",
            "new_value_char",
            "old_value_integer",
            "new_value_integer",
            "old_value_float",
            "new_value_float",
            "old_value_datetime",
            "new_value_datetime",
        ],
        limit=len(tracking_ids),
    )
    by_message: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        message_id = _m2o_id(row.get("mail_message_id"))
        if not message_id:
            continue
        by_message.setdefault(message_id, []).append(_tracking_change_row(row))
    return by_message


async def execute_get_audit_trail(
    adapter: Any,
    tool_input: dict[str, Any],
    context: Any | None = None,
) -> dict[str, Any]:
    """Change history for one record."""
    del context
    model = (tool_input.get("model") or "").strip()
    record_id = int(tool_input.get("record_id") or 0)
    date_from = tool_input.get("date_from")
    date_to = tool_input.get("date_to")
    limit = min(int(tool_input.get("limit") or _DEFAULT_AUDIT_TRAIL_LIMIT), 200)

    if not model or record_id <= 0:
        return {"status": "error", "message": "model and record_id are required"}
    if _model_forbidden(model):
        return {
            "status": "error",
            "error_code": "model_forbidden",
            "message": f"Audit not permitted for restricted model '{model}'.",
        }

    domain = _append_date_filters(
        [["model", "=", model], ["res_id", "=", record_id]],
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
    )
    try:
        messages = await _search_read(
            adapter,
            "mail.message",
            domain,
            [
                "id",
                "date",
                "author_id",
                "body",
                "message_type",
                "subtype_id",
                "tracking_value_ids",
            ],
            limit=limit,
            order="date desc",
        )
        tracking_map = await _load_tracking_map(
            adapter,
            _collect_tracking_ids(messages),
        )
    except Exception as exc:
        logger.warning("[get_audit_trail] query failed: %s", exc)
        return {"status": "error", "message": str(exc)}

    timeline: list[dict[str, Any]] = []
    for message in messages:
        message_id = int(message.get("id") or 0)
        timeline.append(
            {
                "date": str(message.get("date") or ""),
                "author": _m2o_label(message.get("author_id"), "Unknown"),
                "message_type": str(message.get("message_type") or ""),
                "subtype": _m2o_label(message.get("subtype_id")),
                "body_text": _strip_html(message.get("body")),
                "field_changes": tracking_map.get(message_id, []),
            }
        )

    changes_count = sum(
        1
        for entry in timeline
        if entry.get("field_changes") or entry.get("body_text")
    )
    return {
        "status": "success",
        "model": model,
        "record_id": record_id,
        "changes_count": changes_count,
        "timeline": timeline,
        "_source": "audit_trail",
    }


async def _resolve_author_partner_id(
    adapter: Any,
    *,
    user_id: int | None,
    user_name: str | None,
) -> tuple[int | None, str]:
    """Map user_id (res.users) or user_name to mail.message author partner id."""
    if user_id:
        users = await _search_read(
            adapter,
            "res.users",
            [["id", "=", int(user_id)]],
            ["id", "name", "partner_id"],
            limit=1,
        )
        if users:
            partner_id = _m2o_id(users[0].get("partner_id"))
            label = _m2o_label(users[0].get("partner_id"), str(users[0].get("name") or ""))
            if partner_id:
                return partner_id, label or str(users[0].get("name") or "")

    if user_name:
        partners = await _search_read(
            adapter,
            "res.partner",
            [["name", "ilike", user_name.strip()]],
            ["id", "name"],
            limit=5,
        )
        if partners:
            pid = int(partners[0]["id"])
            return pid, str(partners[0].get("name") or user_name)

    return None, ""


async def _record_display_name(
    adapter: Any,
    model: str,
    record_id: int,
) -> str:
    if _model_forbidden(model):
        return str(record_id)
    try:
        rows = await _search_read(adapter, model, [["id", "=", record_id]], ["name"], limit=1)
        if rows and rows[0].get("name"):
            return str(rows[0]["name"])
    except Exception:
        pass
    return str(record_id)


async def execute_get_user_activity(
    adapter: Any,
    tool_input: dict[str, Any],
    context: Any | None = None,
) -> dict[str, Any]:
    """Cross-record activity for one user."""
    del context
    user_id = tool_input.get("user_id")
    user_name = tool_input.get("user_name")
    date_from = tool_input.get("date_from")
    date_to = tool_input.get("date_to")
    model_filter = (tool_input.get("model_filter") or "").strip() or None
    limit = min(int(tool_input.get("limit") or _DEFAULT_USER_ACTIVITY_LIMIT), 500)

    author_id, user_label = await _resolve_author_partner_id(
        adapter,
        user_id=int(user_id) if user_id else None,
        user_name=str(user_name) if user_name else None,
    )
    if not author_id:
        return {
            "status": "error",
            "message": "Could not resolve user — provide user_id or user_name",
        }

    domain: list[Any] = [["author_id", "=", author_id]]
    if model_filter:
        if _model_forbidden(model_filter):
            return {
                "status": "error",
                "error_code": "model_forbidden",
                "message": f"Activity filter model '{model_filter}' is restricted.",
            }
        domain.append(["model", "=", model_filter])
    domain = _append_date_filters(
        domain,
        date_from=str(date_from) if date_from else None,
        date_to=str(date_to) if date_to else None,
    )

    try:
        messages = await _search_read(
            adapter,
            "mail.message",
            domain,
            [
                "id",
                "date",
                "model",
                "res_id",
                "message_type",
                "tracking_value_ids",
                "body",
            ],
            limit=limit,
            order="date desc",
        )
    except Exception as exc:
        logger.warning("[get_user_activity] query failed: %s", exc)
        return {"status": "error", "message": str(exc)}

    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    for message in messages:
        model = str(message.get("model") or "")
        res_id = int(message.get("res_id") or 0)
        if not model or res_id <= 0 or _model_forbidden(model):
            continue
        key = (model, res_id)
        bucket = grouped.setdefault(
            key,
            {
                "id": res_id,
                "name": str(res_id),
                "changes": 0,
                "last_change": "",
                "message_ids": [],
            },
        )
        bucket["changes"] += 1
        msg_date = str(message.get("date") or "")
        if not bucket["last_change"] or msg_date > bucket["last_change"]:
            bucket["last_change"] = msg_date
        mid = int(message.get("id") or 0)
        if mid:
            bucket["message_ids"].append(mid)

    by_model: dict[str, list[dict[str, Any]]] = {}
    for (model, res_id), bucket in grouped.items():
        bucket["name"] = await _record_display_name(adapter, model, res_id)
        by_model.setdefault(model, []).append(bucket)

    by_model_out: list[dict[str, Any]] = []
    for model, records in sorted(by_model.items()):
        records.sort(key=lambda row: row.get("last_change") or "", reverse=True)
        by_model_out.append(
            {
                "model": model,
                "model_label": _MODEL_LABELS.get(model, model.replace(".", " ").title()),
                "records_changed": len(records),
                "records": [
                    {
                        "id": row["id"],
                        "name": row["name"],
                        "changes": row["changes"],
                        "last_change": row["last_change"],
                    }
                    for row in records
                ],
            }
        )

    return {
        "status": "success",
        "user": user_label,
        "author_partner_id": author_id,
        "period": {"from": date_from, "to": date_to},
        "total_changes": len(messages),
        "by_model": by_model_out,
        "_source": "user_activity",
    }


AUDIT_TOOL_EXECUTORS["get_audit_trail"] = execute_get_audit_trail
AUDIT_TOOL_EXECUTORS["get_user_activity"] = execute_get_user_activity
