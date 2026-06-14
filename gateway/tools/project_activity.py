"""Project activity tool — attachments, chatter summary, progress, audit (no Deep Think).

Project Model Phase 3.
"""

from __future__ import annotations

import logging
import os
import re
from html import unescape
from typing import Any

from gateway.core.context_stack import ContextStack

logger = logging.getLogger(__name__)

ACTIVITY_SOURCE = "project_activity"

PROJECT_ACTIVITY_TOOL_NAMES = frozenset({"get_project_activity"})

ACTIVITY_TYPE_VALUES = (
    "attachments",
    "chatter_summary",
    "progress",
    "audit",
)

ACTIVITY_TYPE_LABELS = {
    "attachments": "attachments",
    "chatter_summary": "chatter summary",
    "progress": "progress",
    "audit": "audit trail",
}

CHATTER_SUMMARY_MODEL = os.environ.get(
    "OOA_CHATTER_SUMMARY_MODEL",
    "claude-sonnet-4-20250514",
)

PROJECT_ACTIVITY_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_project_activity",
        "description": (
            "Project or Agreement ACTIVITY data: attachments/documents, chatter/message summary, "
            "progress %, audit trail (created/last updated by).\n\n"
            "USE for: 'attachments of project X', 'documents for agreement Y', "
            "'chatter summary of X', 'project progress of X', 'last updated by for X'.\n\n"
            "Pass project_id for project attachments (reads project.attachment Elrace model). "
            "Pass agreement_id instead for agreement attachments (reads agreement.attachment). "
            "NOT for invoices/POs/timesheets (get_project_records) or engineer "
            "amounts/PM/schedule (get_project_profile) or expenses (Deep Think)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "ID of the project (for project attachments/chatter/progress)"},
                "agreement_id": {"type": "integer", "description": "ID of the agreement (for agreement.attachment docs)"},
                "activity_type": {
                    "type": "string",
                    "enum": list(ACTIVITY_TYPE_VALUES),
                },
                "limit": {"type": "integer", "default": 20},
                "language": {"type": "string", "default": "en"},
            },
            "required": ["activity_type"],
        },
    },
]


def _m2o_name(value: Any) -> str | None:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[1])
    return None


def _text(value: Any) -> str | None:
    if value is None or value is False:
        return None
    text = str(value).strip()
    return text or None


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = unescape(text)
    return " ".join(text.split())


def _normalize_attachment(row: dict[str, Any]) -> dict[str, Any]:
    # project.attachment (Elrace custom) vs ir.attachment (standard)
    if "lead_attachment_type" in row or "file_count" in row:
        folder = _m2o_name(row.get("x_folder_id"))
        return {
            "name": _text(row.get("name")),
            "type": _text(row.get("lead_attachment_type")),
            "folder": folder,
            "file_count": row.get("file_count"),
            "uploaded_at": _text(row.get("create_date")),
            "uploaded_by": _m2o_name(row.get("create_uid")),
        }
    # agreement.attachment
    if "attachment_type" in row or "file_type" in row:
        return {
            "name": _text(row.get("name")),
            "type": _text(row.get("attachment_type")),
            "file_type": _text(row.get("file_type")),
            "file_count": row.get("file_count"),
            "uploaded_at": _text(row.get("create_date")),
            "uploaded_by": _m2o_name(row.get("create_uid")),
        }
    # ir.attachment fallback
    size = row.get("file_size")
    return {
        "name": _text(row.get("name")),
        "mimetype": _text(row.get("mimetype")),
        "size_bytes": int(size) if isinstance(size, (int, float)) else None,
        "uploaded_at": _text(row.get("create_date")),
        "uploaded_by": _m2o_name(row.get("create_uid")),
        "description": _text(row.get("description")),
    }


def _normalize_message(row: dict[str, Any]) -> dict[str, Any]:
    body = _strip_html(str(row.get("body") or ""))
    if len(body) > 500:
        body = body[:497] + "..."
    subject = _text(row.get("subject"))
    return {
        "date": _text(row.get("date")),
        "author": _m2o_name(row.get("author_id")) or _text(row.get("email_from")),
        "subject": subject,
        "body": body,
        "message_type": _text(row.get("message_type")),
        "subtype": _m2o_name(row.get("subtype_id")),
    }


def _normalize_progress_audit(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "progress_percent": raw.get("progress_overall_percent"),
        "progress_last_update": _text(raw.get("progress_last_update")),
        "delayed_weeks": raw.get("progress_delayed_weeks"),
        "on_time_weeks": raw.get("progress_on_time_weeks"),
        "project_status": _m2o_name(raw.get("project_status")),
        "project_status_compute": _text(raw.get("project_status_compute")),
        "state": _text(raw.get("state")),
        "created_by": _m2o_name(raw.get("create_uid")),
        "created_on": _text(raw.get("create_date")),
        "last_updated_by": _m2o_name(raw.get("write_uid")),
        "last_updated_on": _text(raw.get("write_date")),
    }


def _summarize_chatter_sync(
    *,
    project_name: str,
    messages: list[dict[str, Any]],
    language: str,
) -> str:
    """LLM narrative of recent project chatter (sync — called from tool executor)."""
    if not messages:
        return (
            "No chatter messages found for this project in Odoo."
            if language != "ar"
            else "لا توجد رسائل في سجل المشروع."
        )

    lines: list[str] = []
    for item in messages[:15]:
        bits = [item.get("date") or "", item.get("author") or "Unknown"]
        if item.get("subject"):
            bits.append(str(item["subject"]))
        if item.get("body"):
            bits.append(str(item["body"]))
        lines.append(" | ".join(part for part in bits if part))

    prompt = (
        f"Project: {project_name}\n\n"
        "Recent Odoo chatter messages (newest first):\n"
        + "\n".join(f"- {line}" for line in lines)
        + "\n\nWrite a concise executive summary (3-6 sentences) of what has "
        "happened recently on this project. Mention key status changes, notes, "
        "and who posted important updates. Use exact dates when visible. "
        "Do not invent facts not present in the messages."
    )
    if language == "ar":
        prompt += "\n\nRespond in Arabic."

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        response = client.messages.create(
            model=CHATTER_SUMMARY_MODEL,
            max_tokens=400,
            system=(
                "You summarize Odoo project chatter for senior management. "
                "Be factual, concise, professional UAE business tone."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        block = response.content[0]
        return getattr(block, "text", str(block)).strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[ProjectActivity] chatter summary LLM failed: %s", exc)
        latest = messages[0]
        fallback = (
            f"Latest activity on {project_name}: "
            f"{latest.get('date', '')} — {latest.get('author', '')}: "
            f"{latest.get('body') or latest.get('subject') or 'update recorded'}."
        )
        return fallback


def execute_get_project_activity(
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None = None,
) -> dict[str, Any]:
    del context
    project_id_raw = tool_input.get("project_id")
    agreement_id_raw = tool_input.get("agreement_id")
    activity_type = str(tool_input.get("activity_type") or "")

    if activity_type not in ACTIVITY_TYPE_VALUES:
        return {
            "status": "error",
            "_source": ACTIVITY_SOURCE,
            "error": f"Unknown activity_type '{activity_type}'.",
        }

    limit = int(tool_input.get("limit") or 20)
    language = str(tool_input.get("language") or "en")

    # --- Agreement attachment branch ---
    if agreement_id_raw and activity_type == "attachments":
        agreement_id = int(agreement_id_raw)
        agr_names = adapter.safe_search_read(
            "sale.contracted.order", [["id", "=", agreement_id]], ["name"], limit=1,
        )
        agr_name = _text(agr_names[0].get("name")) if agr_names else f"Agreement {agreement_id}"
        result = adapter.read_agreement_attachments(agreement_id, limit=limit)
        rows = [_normalize_attachment(row) for row in result.get("rows") or []]
        return {
            "status": "success",
            "_source": ACTIVITY_SOURCE,
            "agreement_id": agreement_id,
            "agreement_name": agr_name,
            "activity_type": "attachments",
            "activity_label": "agreement attachments",
            "source_model": result.get("source_model", "agreement.attachment"),
            "total_count": int(result.get("total_count") or 0),
            "returned_count": len(rows),
            "rows": rows,
        }

    if not project_id_raw:
        return {
            "status": "error",
            "_source": ACTIVITY_SOURCE,
            "error": "project_id is required (or agreement_id for agreement attachments).",
        }

    project_id = int(project_id_raw)
    names = adapter.safe_search_read(
        "project.project", [["id", "=", project_id]], ["name"], limit=1,
    )
    project_name = _text(names[0].get("name")) if names else f"Project {project_id}"

    payload: dict[str, Any] = {
        "status": "success",
        "_source": ACTIVITY_SOURCE,
        "project_id": project_id,
        "project_name": project_name,
        "activity_type": activity_type,
        "activity_label": ACTIVITY_TYPE_LABELS[activity_type],
    }

    if activity_type == "attachments":
        result = adapter.read_project_attachments(project_id, limit=limit)
        rows = [_normalize_attachment(row) for row in result.get("rows") or []]
        payload.update(
            {
                "source_model": result.get("source_model", "project.attachment"),
                "total_count": int(result.get("total_count") or 0),
                "returned_count": len(rows),
                "rows": rows,
            },
        )
    elif activity_type == "chatter_summary":
        result = adapter.read_project_chatter_messages(project_id, limit=25)
        messages = [_normalize_message(row) for row in result.get("rows") or []]
        summary = _summarize_chatter_sync(
            project_name=project_name,
            messages=messages,
            language=language,
        )
        payload.update(
            {
                "total_count": int(result.get("total_count") or 0),
                "message_count": len(messages),
                "summary": summary,
                "recent_messages": messages[:5],
            },
        )
    else:
        raw = adapter.read_project_progress_audit(project_id)
        progress_audit = _normalize_progress_audit(raw)
        payload["progress_audit"] = progress_audit
        if activity_type == "progress":
            payload["focus"] = "progress"
        else:
            payload["focus"] = "audit"

    return payload


def run_project_activity_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    adapter: Any,
    context: ContextStack | None = None,
) -> dict[str, Any]:
    if tool_name == "get_project_activity":
        return execute_get_project_activity(tool_input, adapter, context)
    raise ValueError(f"Unknown project activity tool: {tool_name}")
