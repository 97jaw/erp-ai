"""Documents clarification flow — scope picker, fast project lookup, file listing."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from gateway.agent.attachment_fast_path import is_attachment_list_query
from gateway.agent.menu_preflight import normalize_pick_text
from gateway.agent.preflight_blocks import pill_block
from gateway.core.project_activity_routing import (
    _AGREEMENT_CONTEXT_RE,
    derive_activity_type,
    extract_activity_project_hint,
)
from gateway.core.project_query_utils import extract_project_name_hint

logger = logging.getLogger(__name__)

_PROJECT_COST_SUMMARY_RE = re.compile(
    r"\b(?:expense|cost|spend|spending|budget)\s+summary\b|"
    r"\bproject\s+summary\b|"
    r"\bsummary\s+(?:of|for)\s+(?:project|expenses?|costs?)\b|"
    r"\b(?:expense|cost)\s+(?:breakdown|overview)\b",
    re.I,
)


def is_project_cost_query(message: str) -> bool:
    """True when the user is asking about spend/costs — not downloadable files."""
    text = (message or "").strip()
    if not text:
        return False

    from gateway.agent.session_entities import _PROJECT_INTENT_RE
    from gateway.core.project_profile_routing import _SPEND_DISQUALIFIER_RE, has_project_context

    if re.search(r"projects?\s*&\s*costs?", normalize_pick_text(text)):
        return True
    if _PROJECT_INTENT_RE.search(text):
        return True
    if _SPEND_DISQUALIFIER_RE.search(text):
        return True
    if _PROJECT_COST_SUMMARY_RE.search(text):
        return True
    if re.search(r"\b(breakdown|overview)\b", text, re.I) and has_project_context(text):
        if derive_activity_type(text) not in {"attachments", "chatter_summary", "audit"}:
            return True
    return False


def is_active_documents_session(entities: dict[str, Any]) -> bool:
    """True when the user is mid-flow in the documents wizard."""
    if entities.get("intent") != "attachments":
        return False
    if entities.get("documents_step") in {"scope", "target", "pick_project"}:
        return True
    return bool(entities.get("documents_scope"))


def is_explicit_attachment_query(message: str) -> bool:
    """True only when the message is clearly about files/documents/attachments."""
    text = (message or "").strip()
    if not text:
        return False
    if is_documents_category_pick(text) or detect_scope_pick(text):
        return True
    return is_attachment_list_query(text) or derive_activity_type(text) == "attachments"


_DOCUMENTS_CATEGORY_LABELS = frozenset(
    {
        "documents & files",
        "documents and files",
        "documents",
        "files & documents",
        "files and documents",
    }
)
_SCOPE_OPTION_IDS = frozenset({"project", "agreement", "rfq", "record"})
_SCOPE_PICK_MAP: dict[str, str] = {
    "project documents": "project",
    "project document": "project",
    "agreement documents": "agreement",
    "agreement document": "agreement",
    "rfq attachments": "rfq",
    "rfq attachment": "rfq",
    "other record": "record",
    "record attachments": "record",
}
_RECORD_MODEL_TYPED_RE = re.compile(
    r"^([a-z][a-z0-9_.]+)\s*[,:\s]+\s*(\d+)\s*$",
    re.I,
)
_RFQ_ID_TYPED_RE = re.compile(r"^(\d+)\s*$")

DOCUMENT_SCOPE_OPTIONS: list[dict[str, str]] = [
    {"id": "project", "label": "Project documents", "icon": "🏗️"},
    {"id": "agreement", "label": "Agreement documents", "icon": "📜"},
    {"id": "rfq", "label": "RFQ attachments", "icon": "📋"},
    {"id": "record", "label": "Other record (model + ID)", "icon": "📎"},
]


@dataclass
class DocumentsFlowResult:
    text: str
    visualization: dict[str, Any] | None = None
    suggestions: list[str] = field(default_factory=list)
    tool_names: list[str] = field(default_factory=list)
    ui_blocks: list[dict[str, Any]] = field(default_factory=list)

    @property
    def is_picker(self) -> bool:
        return bool(self.ui_blocks)


def is_documents_category_pick(message: str) -> bool:
    norm = normalize_pick_text(message)
    if detect_scope_pick(message):
        return False
    return norm in _DOCUMENTS_CATEGORY_LABELS


def detect_scope_pick(message: str) -> str | None:
    norm = normalize_pick_text(message)
    if norm in _SCOPE_PICK_MAP:
        return _SCOPE_PICK_MAP[norm]
    for label, scope in _SCOPE_PICK_MAP.items():
        if label in norm:
            return scope
    return None


def detect_scope_pick_from_option_id(option_id: str | None) -> str | None:
    if not option_id:
        return None
    token = str(option_id).strip().lower()
    if token in _SCOPE_OPTION_IDS:
        return token
    return None


def infer_documents_scope(message: str) -> str | None:
    """Infer attachment scope only when the message is actually about files."""
    text = (message or "").strip()
    if is_project_cost_query(text):
        return None
    if not is_explicit_attachment_query(text):
        return None
    if _AGREEMENT_CONTEXT_RE.search(text):
        return "agreement"
    if re.search(r"\brfq\b|request\s+for\s+quotation", text, re.I):
        return "rfq"
    if re.search(r"\bres_model\b|model\s+[a-z]", text, re.I):
        return "record"
    if re.search(r"\bproject\b", text, re.I) or extract_project_name_hint(text):
        return "project"
    return None


_FILE_HINT_PREFIX_RE = re.compile(
    r"^(?:files?|documents?|attachments?|uploads?)\s+(?:of|for|on)?\s*",
    re.I,
)


def extract_documents_project_hint(message: str) -> str | None:
    """Project name fragment for documents flow — strips file/attachment lead-ins."""
    from gateway.core.project_activity_routing import extract_activity_project_hint

    hint = extract_activity_project_hint(message) or extract_project_name_hint(message)
    if not hint:
        return None
    cleaned = _FILE_HINT_PREFIX_RE.sub("", hint.strip(), count=1).strip(" .,?")
    return cleaned or None


def cached_project_matches_message(message: str, entities: dict[str, Any]) -> bool:
    """True when session project_id still applies to this message (not a new project)."""
    from gateway.agent.project_resolve import extract_project_id_from_message

    msg_id = extract_project_id_from_message(message)
    cached_id = entities.get("project_id")
    if msg_id is not None:
        return cached_id is not None and int(msg_id) == int(cached_id)

    hint = extract_documents_project_hint(message)
    if not hint:
        return cached_id is not None

    if not cached_id:
        return False

    cached_name = str(entities.get("project_name") or "").lower()
    hint_lower = hint.lower()
    if not cached_name:
        return False
    if hint_lower in cached_name or cached_name in hint_lower:
        return True

    hint_words = {word for word in re.split(r"\s+", hint_lower) if len(word) > 2}
    name_words = {word for word in re.split(r"\s+", cached_name) if len(word) > 2}
    if not hint_words:
        return True
    overlap = len(hint_words & name_words) / len(hint_words)
    return overlap >= 0.5


def resolve_documents_project_id(message: str, entities: dict[str, Any]) -> int | None:
    """Pick project_id from message first; ignore stale session id when name changed."""
    from gateway.agent.project_resolve import extract_project_id_from_message

    msg_id = extract_project_id_from_message(message)
    if msg_id is not None:
        return int(msg_id)
    cached_id = entities.get("project_id")
    if cached_id and cached_project_matches_message(message, entities):
        return int(cached_id)
    return None


def has_resolved_attachment_target(entities: dict[str, Any], message: str) -> bool:
    from gateway.agent.project_resolve import extract_project_id_from_message

    if is_project_cost_query(message):
        return False
    if not is_explicit_attachment_query(message) and entities.get("intent") != "attachments":
        return False

    if extract_project_id_from_message(message):
        return True
    if entities.get("project_id") and entities.get("documents_scope") in {None, "project"}:
        if infer_documents_scope(message) in {None, "project"} or entities.get("intent") == "attachments":
            if cached_project_matches_message(message, entities):
                return True
    if entities.get("agreement_id") and entities.get("documents_scope") == "agreement":
        return True
    if entities.get("rfq_id") and entities.get("documents_scope") == "rfq":
        return True
    if entities.get("attachment_res_model") and entities.get("attachment_res_id"):
        return True
    record_match = _RECORD_MODEL_TYPED_RE.search((message or "").strip())
    if record_match:
        return True
    return False


def _project_picker_options(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from gateway.agent.project_resolve import project_id_from_row, project_name_from_row

    options: list[dict[str, Any]] = []
    for row in rows:
        pid = project_id_from_row(row)
        if pid is None:
            continue
        name = project_name_from_row(row)
        wo = row.get("wo_ref_no")
        label = f"{name} (ID: {pid})" if name else f"Project {pid}"
        if wo:
            label = f"{label} — WO {wo}"
        options.append({"id": str(pid), "label": label, "icon": "🏗️"})
    return options


def _target_prompt(scope: str, *, language: str) -> str:
    if language == "ar":
        prompts = {
            "project": "أي مشروع؟ اكتب اسم المشروع أو رقم WO أو (ID: 1234)",
            "agreement": "أي عقد؟ اكتب اسم العقد أو رقم الاتفاقية",
            "rfq": "ما رقم RFQ؟",
            "record": "اكتب model و ID مثل: account.move 12345",
        }
        return prompts.get(scope, "ما السجل الذي تريد مرفقاته؟")
    prompts = {
        "project": "Which project? Type the project name, WO number, or (ID: 1234)",
        "agreement": "Which agreement? Type the agreement name or number",
        "rfq": "What is the RFQ / requisition ID?",
        "record": "Type model and record ID — e.g. purchase.order 98765",
    }
    return prompts.get(scope, "Which record should I fetch attachments for?")


async def _list_attachments_result(
    *,
    tool_input: dict[str, Any],
    adapter: Any,
    user: Any | None,
    session_id: str | None,
    message: str,
    language: str,
) -> DocumentsFlowResult | None:
    from gateway.agent.response_finalize import finalize_chat_response
    from gateway.agent.tools_registry import execute_tool
    from gateway.attachments.visualization import build_file_list_visualization

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
        logger.warning("[DocumentsFlow] list_attachments failed: %s", exc)
        return None

    if not isinstance(result, dict) or result.get("status") != "success":
        return None

    files = result.get("files") or []
    label = str(result.get("label") or "Documents")
    if not files:
        text = (
            f"No downloadable files found for **{label}**."
            if language != "ar"
            else f"لا توجد ملفات قابلة للتنزيل لـ **{label}**."
        )
        return DocumentsFlowResult(
            text=text,
            suggestions=["Show purchase orders", "Project expense breakdown"],
            tool_names=[tool_name],
        )

    from gateway.attachments.visualization import file_list_summary_text

    visualization = build_file_list_visualization(result, session_id=session_id)
    text = file_list_summary_text(label, len(files), language=language)
    suggestions = ["Show purchase orders", "Project expense breakdown", "Chatter summary"]
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
    return DocumentsFlowResult(
        text=clean_text,
        visualization=built_visual or visualization,
        suggestions=suggestion_labels,
        tool_names=[tool_name],
    )


async def _resolve_project_target(
    *,
    message: str,
    adapter: Any,
    session_id: str | None,
    language: str,
    entities: dict[str, Any],
) -> DocumentsFlowResult | None:
    from gateway.agent.project_resolve import (
        extract_project_id_from_message,
        project_id_from_row,
        project_name_from_row,
        search_projects_fast,
    )
    from gateway.agent.session_entities import update_entities

    project_id = resolve_documents_project_id(message, entities)
    if project_id:
        tool_input = {"project_id": int(project_id), "limit": 50}
        update_entities(
            session_id,
            project_id=int(project_id),
            documents_scope="project",
            documents_step="done",
            intent="attachments",
        )
        return await _list_attachments_result(
            tool_input=tool_input,
            adapter=adapter,
            user=None,
            session_id=session_id,
            message=message,
            language=language,
        )

    hint = (
        extract_documents_project_hint(message)
        or normalize_pick_text(message)
    )
    if not hint or hint in _SCOPE_PICK_MAP.values():
        prompt = _target_prompt("project", language=language)
        return DocumentsFlowResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, [], allow_typed_input=True)],
            suggestions=[],
        )

    rows = await search_projects_fast(adapter, hint)
    if not rows:
        text = (
            f"I could not find a project matching **{hint}** within 5 seconds. "
            "Try a WO number, exact name fragment, or **(ID: 1234)**."
            if language != "ar"
            else f"لم أجد مشروعًا يطابق **{hint}**. جرّب رقم WO أو (ID: 1234)."
        )
        prompt = _target_prompt("project", language=language)
        return DocumentsFlowResult(
            text=text,
            ui_blocks=[pill_block(prompt, [], allow_typed_input=True)],
            suggestions=[],
        )

    if len(rows) == 1:
        row = rows[0]
        pid = project_id_from_row(row)
        if pid is None:
            return None
        update_entities(
            session_id,
            project_id=pid,
            project_name=project_name_from_row(row),
            documents_scope="project",
            documents_step="done",
            intent="attachments",
        )
        return await _list_attachments_result(
            tool_input={"project_id": pid, "limit": 50},
            adapter=adapter,
            user=None,
            session_id=session_id,
            message=message,
            language=language,
        )

    prompt = (
        "Which project did you mean?"
        if language != "ar"
        else "أي مشروع تقصد؟"
    )
    options = _project_picker_options(rows)
    update_entities(session_id, documents_scope="project", documents_step="pick_project", intent="attachments")
    return DocumentsFlowResult(
        text=prompt,
        ui_blocks=[pill_block(prompt, options, allow_typed_input=True)],
        suggestions=[],
    )


async def _resolve_scope_target(
    *,
    scope: str,
    message: str,
    adapter: Any,
    user: Any | None,
    session_id: str | None,
    language: str,
    entities: dict[str, Any],
) -> DocumentsFlowResult | None:
    from gateway.agent.session_entities import update_entities

    update_entities(session_id, documents_scope=scope, intent="attachments")

    if scope == "project":
        return await _resolve_project_target(
            message=message,
            adapter=adapter,
            session_id=session_id,
            language=language,
            entities=entities,
        )

    text = (message or "").strip()
    if scope == "rfq":
        match = _RFQ_ID_TYPED_RE.match(text)
        if match:
            rfq_id = int(match.group(1))
            update_entities(session_id, rfq_id=rfq_id, documents_step="done")
            return await _list_attachments_result(
                tool_input={"rfq_id": rfq_id, "limit": 50},
                adapter=adapter,
                user=user,
                session_id=session_id,
                message=message,
                language=language,
            )
        prompt = _target_prompt("rfq", language=language)
        update_entities(session_id, documents_step="target")
        return DocumentsFlowResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, [], allow_typed_input=True)],
            suggestions=[],
        )

    if scope == "record":
        match = _RECORD_MODEL_TYPED_RE.match(text)
        if match:
            res_model = match.group(1)
            res_id = int(match.group(2))
            update_entities(
                session_id,
                attachment_res_model=res_model,
                attachment_res_id=res_id,
                documents_step="done",
            )
            return await _list_attachments_result(
                tool_input={"res_model": res_model, "res_id": res_id, "limit": 50},
                adapter=adapter,
                user=user,
                session_id=session_id,
                message=message,
                language=language,
            )
        prompt = _target_prompt("record", language=language)
        update_entities(session_id, documents_step="target")
        return DocumentsFlowResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, [], allow_typed_input=True)],
            suggestions=[],
        )

    if scope == "agreement":
        agreement_id = entities.get("agreement_id")
        if agreement_id:
            return await _list_attachments_result(
                tool_input={"agreement_id": int(agreement_id), "limit": 50},
                adapter=adapter,
                user=user,
                session_id=session_id,
                message=message,
                language=language,
            )
        prompt = _target_prompt("agreement", language=language)
        update_entities(session_id, documents_step="target")
        return DocumentsFlowResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, [], allow_typed_input=True)],
            suggestions=[],
        )

    return None


async def try_documents_flow(
    *,
    message: str,
    user: Any | None,
    adapter: Any,
    session_id: str | None,
    language: str = "en",
    skip_clarification: bool = False,
    confirmed_entities: list[Any] | None = None,
    documents_scope: str | None = None,
) -> DocumentsFlowResult | None:
    """Clarify document scope/target, then list files — avoids slow EntityResolver."""
    if not session_id:
        return None

    from gateway.agent.project_resolve import extract_project_id_from_message, project_id_from_row
    from gateway.agent.session_entities import get_entities, update_entities

    text = (message or "").strip()
    if not text:
        return None

    if is_project_cost_query(text):
        from gateway.agent.session_entities import clear_documents_entities

        clear_documents_entities(session_id)
        return None

    entities = get_entities(session_id)

    if entities.get("intent") == "project_expense" and not is_explicit_attachment_query(text):
        return None

    scope_pick = detect_scope_pick_from_option_id(documents_scope) or detect_scope_pick(text)

    if confirmed_entities and is_active_documents_session(entities):
        for entity in confirmed_entities:
            etype = getattr(entity, "type", None) or (entity.get("type") if isinstance(entity, dict) else None)
            eid = getattr(entity, "id", None) or (entity.get("id") if isinstance(entity, dict) else None)
            if etype == "project" and eid:
                update_entities(session_id, project_id=int(eid), documents_scope="project", intent="attachments")

    entities = get_entities(session_id)
    picker_project_id = entities.get("project_id") or extract_project_id_from_message(text)
    if (
        confirmed_entities
        and picker_project_id
        and entities.get("intent") == "attachments"
        and entities.get("documents_scope") == "project"
        and entities.get("documents_step") == "pick_project"
    ):
        update_entities(session_id, project_id=int(picker_project_id), documents_step="done")
        return await _list_attachments_result(
            tool_input={"project_id": int(picker_project_id), "limit": 50},
            adapter=adapter,
            user=user,
            session_id=session_id,
            message=message,
            language=language,
        )

    if scope_pick and (
        entities.get("documents_step") == "scope"
        or (
            entities.get("intent") == "attachments"
            and entities.get("documents_step") in {None, "scope", "target"}
        )
    ):
        update_entities(session_id, documents_step="target", documents_scope=scope_pick, intent="attachments")
        return await _resolve_scope_target(
            scope=scope_pick,
            message="",
            adapter=adapter,
            user=user,
            session_id=session_id,
            language=language,
            entities=get_entities(session_id),
        )

    if is_documents_category_pick(text):
        update_entities(session_id, intent="attachments", documents_step="scope")
        prompt = (
            "What type of documents do you need?"
            if language != "ar"
            else "ما نوع المستندات التي تريدها؟"
        )
        return DocumentsFlowResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, DOCUMENT_SCOPE_OPTIONS)],
            suggestions=[],
        )

    if entities.get("documents_step") == "pick_project" and re.fullmatch(r"\d+", text):
        update_entities(session_id, project_id=int(text), documents_step="done")
        return await _list_attachments_result(
            tool_input={"project_id": int(text), "limit": 50},
            adapter=adapter,
            user=user,
            session_id=session_id,
            message=message,
            language=language,
        )

    if (
        entities.get("documents_scope")
        and entities.get("documents_step") == "target"
        and entities.get("intent") == "attachments"
        and not is_project_cost_query(text)
    ):
        return await _resolve_scope_target(
            scope=str(entities["documents_scope"]),
            message=text,
            adapter=adapter,
            user=user,
            session_id=session_id,
            language=language,
            entities=entities,
        )

    is_attachment = is_explicit_attachment_query(text)
    if not is_attachment and entities.get("intent") != "attachments":
        return None

    if is_attachment and is_project_cost_query(text):
        return None

    if has_resolved_attachment_target(entities, text) and (
        not skip_clarification or confirmed_entities or extract_project_id_from_message(text)
    ):
        pid = resolve_documents_project_id(text, entities)
        if pid:
            return await _list_attachments_result(
                tool_input={"project_id": int(pid), "limit": 50},
                adapter=adapter,
                user=user,
                session_id=session_id,
                message=message,
                language=language,
            )

    inferred = infer_documents_scope(text) or entities.get("documents_scope")
    if inferred:
        if not cached_project_matches_message(text, entities):
            update_entities(session_id, project_id=None, project_name=None)
        update_entities(session_id, documents_scope=inferred, documents_step="target", intent="attachments")
        return await _resolve_scope_target(
            scope=str(inferred),
            message=text,
            adapter=adapter,
            user=user,
            session_id=session_id,
            language=language,
            entities=get_entities(session_id),
        )

    if not skip_clarification:
        update_entities(session_id, intent="attachments", documents_step="scope")
        prompt = (
            "What type of documents do you need?"
            if language != "ar"
            else "ما نوع المستندات التي تريدها؟"
        )
        return DocumentsFlowResult(
            text=prompt,
            ui_blocks=[pill_block(prompt, DOCUMENT_SCOPE_OPTIONS)],
            suggestions=[],
        )

    return None
