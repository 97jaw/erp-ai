"""Fast path for attachment / document listing with ephemeral downloads."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from gateway.core.project_activity_routing import (
    _AGREEMENT_CONTEXT_RE,
    derive_activity_type,
    extract_activity_project_hint,
)
from gateway.core.project_query_utils import extract_project_name_hint

logger = logging.getLogger(__name__)

_RFQ_RE = re.compile(r"\brfq\b|request\s+for\s+quotation", re.I)
_RFQ_ID_RE = re.compile(r"\b(?:rfq|requisition)\s*#?\s*(\d+)\b", re.I)
_RECORD_MODEL_RE = re.compile(
    r"\b(?:on|for|of)\s+(?:model\s+)?([a-z][a-z0-9_.]+)\s+(?:id\s+)?(\d+)\b",
    re.I,
)
_GENERIC_ATTACHMENT_RE = re.compile(
    r"\battachments?|documents?|files?|uploads?\b|مرفق|مرفقات|مستند",
    re.I,
)


@dataclass
class AttachmentFastPathResult:
    text: str
    visualization: dict[str, Any] | None
    suggestions: list[str]
    tool_names: list[str]


def is_attachment_list_query(message: str) -> bool:
    text = (message or "").strip()
    if len(text) < 3:
        return False
    from gateway.agent.documents_flow import detect_scope_pick, is_documents_category_pick

    if is_documents_category_pick(text):
        return False
    if detect_scope_pick(text):
        return False
    if derive_activity_type(text) == "attachments":
        return True
    if _GENERIC_ATTACHMENT_RE.search(text) and (
        _AGREEMENT_CONTEXT_RE.search(text)
        or _RFQ_RE.search(text)
        or _RECORD_MODEL_RE.search(text)
        or extract_activity_project_hint(text)
        or extract_project_name_hint(text)
        or re.search(r"\(ID:\s*\d+\)", text, re.I)
    ):
        return True
    return False


def _parse_tool_input(
    message: str,
    *,
    session_id: str | None,
    project_row: dict[str, Any] | None,
) -> dict[str, Any]:
    from gateway.agent.documents_flow import resolve_documents_project_id
    from gateway.agent.project_resolve import agreement_id_from_project, project_id_from_row
    from gateway.agent.session_entities import get_entities

    entities = get_entities(session_id) if session_id else {}
    tool_input: dict[str, Any] = {"limit": 50}

    record_match = _RECORD_MODEL_RE.search(message or "")
    if record_match:
        tool_input["res_model"] = record_match.group(1)
        tool_input["res_id"] = int(record_match.group(2))
        return tool_input

    rfq_match = _RFQ_ID_RE.search(message or "")
    if rfq_match:
        tool_input["rfq_id"] = int(rfq_match.group(1))
        return tool_input
    if _RFQ_RE.search(message or "") and entities.get("rfq_id"):
        tool_input["rfq_id"] = int(entities["rfq_id"])

    if _AGREEMENT_CONTEXT_RE.search(message or ""):
        agreement_id = entities.get("agreement_id")
        if agreement_id:
            tool_input["agreement_id"] = int(agreement_id)
            return tool_input

    project_id = resolve_documents_project_id(message, entities)
    if project_row and not project_id:
        project_id = project_id_from_row(project_row)
    if project_id:
        tool_input["project_id"] = int(project_id)
        if _AGREEMENT_CONTEXT_RE.search(message or ""):
            tool_input["include_agreement"] = True
        elif project_row and agreement_id_from_project(project_row):
            tool_input["include_agreement"] = True
        return tool_input

    return tool_input


async def try_attachment_fast_path(
    *,
    message: str,
    user: Any | None,
    adapter: Any,
    session_id: str | None,
    language: str = "en",
) -> AttachmentFastPathResult | None:
    if not is_attachment_list_query(message):
        return None

    from gateway.agent.documents_flow import has_resolved_attachment_target
    from gateway.agent.project_resolve import extract_project_id_from_message
    from gateway.agent.session_entities import get_entities

    entities = get_entities(session_id) if session_id else {}
    if not has_resolved_attachment_target(entities, message) and not extract_project_id_from_message(message):
        return None

    from gateway.agent.project_resolve import (
        find_project,
        project_name_from_row,
    )
    from gateway.agent.response_finalize import finalize_chat_response
    from gateway.agent.session_entities import get_entities, update_entities
    from gateway.agent.tools_registry import execute_tool
    from gateway.attachments.visualization import build_file_list_visualization

    entities = get_entities(session_id) if session_id else {}
    from gateway.agent.documents_flow import resolve_documents_project_id

    project_id = resolve_documents_project_id(message, entities)
    project_row = None
    if project_id:
        project_row = await find_project(
            adapter=adapter,
            user=user,
            project_id=int(project_id),
        )

    tool_input = _parse_tool_input(message, session_id=session_id, project_row=project_row)
    if not any(
        key in tool_input
        for key in ("project_id", "agreement_id", "rfq_id", "res_model", "res_id")
    ):
        return None

    tool_name = "list_attachments"
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
        logger.warning("[AttachmentFastPath] %s failed: %s", tool_name, exc)
        return None

    if not isinstance(result, dict) or result.get("error") or result.get("status") != "success":
        return None

    files = result.get("files") or []
    label = str(result.get("label") or "Documents")
    if not files:
        scope = project_name_from_row(project_row) if project_row else label
        text = (
            f"No downloadable files found for **{scope}**."
            if language != "ar"
            else f"لا توجد ملفات قابلة للتنزيل لـ **{scope}**."
        )
        return AttachmentFastPathResult(
            text=text,
            visualization=None,
            suggestions=[
                "List all departments",
                "Project expense breakdown",
                "Show purchase orders",
            ],
            tool_names=[tool_name],
        )

    visualization = build_file_list_visualization(result, session_id=session_id)
    if project_row and session_id:
        from gateway.agent.project_resolve import project_id_from_row

        pid = project_id_from_row(project_row)
        if pid:
            update_entities(
                session_id,
                project_id=pid,
                project_name=project_name_from_row(project_row),
                intent="attachments",
            )

    from gateway.attachments.visualization import file_list_summary_text

    text = file_list_summary_text(label, len(files), language=language)
    suggestions = [
        "Project expense breakdown",
        "Show purchase orders",
        "Chatter summary",
    ]

    clean_text, built_visual, suggestion_labels, _meta = finalize_chat_response(
        text,
        visualization,
        suggestions,
        [tool_name],
        [result],
        language,
        message,
        session_id,
    )
    return AttachmentFastPathResult(
        text=clean_text,
        visualization=built_visual or visualization,
        suggestions=suggestion_labels,
        tool_names=[tool_name],
    )
