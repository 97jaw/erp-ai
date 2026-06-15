"""List downloadable Odoo attachments — project, agreement, RFQ, or any record."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

ATTACHMENTS_SOURCE = "list_attachments"

LIST_ATTACHMENTS_TOOL_NAMES = frozenset({"list_attachments"})

RFQ_MODEL_CANDIDATES = (
    "purchase.requisition",
    "purchase.order",
)

LIST_ATTACHMENTS_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "list_attachments",
        "description": (
            "List downloadable FILES (not invoice/PO rows) linked to a project, "
            "agreement, RFQ, or any Odoo record.\n\n"
            "USE for: 'attachments/documents/files for project X', 'agreement documents', "
            "'RFQ attachments', 'files on purchase order 123', "
            "'ir.attachment for model account.move id 456'.\n\n"
            "Reads project.attachment folders, agreement.attachment, and ir.attachment. "
            "Returns metadata + download tokens — never embeds file bytes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "project_id": {"type": "integer", "description": "project.project ID"},
                "agreement_id": {"type": "integer", "description": "Agreement / sale.contracted.order ID"},
                "rfq_id": {"type": "integer", "description": "RFQ / purchase requisition ID"},
                "res_model": {
                    "type": "string",
                    "description": "Odoo model technical name for generic ir.attachment lookup",
                },
                "res_id": {"type": "integer", "description": "Record ID for generic ir.attachment lookup"},
                "include_agreement": {
                    "type": "boolean",
                    "description": "When project_id is set, also list agreement.attachment docs",
                    "default": True,
                },
                "limit": {"type": "integer", "default": 50},
            },
        },
    },
]


def _m2o_id(value: Any) -> int | None:
    if isinstance(value, (list, tuple)) and value:
        try:
            return int(value[0])
        except (TypeError, ValueError):
            return None
    try:
        return int(value) if value else None
    except (TypeError, ValueError):
        return None


def _m2o_name(value: Any) -> str | None:
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return str(value[1])
    return None


def _text(value: Any) -> str | None:
    if value is None or value is False:
        return None
    text = str(value).strip()
    return text or None


def _normalize_ir_row(row: dict[str, Any], *, source_label: str) -> dict[str, Any] | None:
    attachment_id = _m2o_id(row.get("id")) or row.get("id")
    if attachment_id is None:
        return None
    try:
        attachment_id = int(attachment_id)
    except (TypeError, ValueError):
        return None
    name = _text(row.get("name"))
    if not name:
        return None
    size = row.get("file_size")
    return {
        "odoo_attachment_id": attachment_id,
        "name": name,
        "mimetype": _text(row.get("mimetype")) or "application/octet-stream",
        "size_bytes": int(size) if isinstance(size, (int, float)) else None,
        "uploaded_at": _text(row.get("create_date")),
        "uploaded_by": _m2o_name(row.get("create_uid")),
        "source": source_label,
        "res_model": _text(row.get("res_model")),
        "res_id": _m2o_id(row.get("res_id")),
        "description": _text(row.get("description")),
    }


def _dedupe_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[int] = set()
    unique: list[dict[str, Any]] = []
    for row in files:
        attachment_id = row.get("odoo_attachment_id")
        if attachment_id is None:
            continue
        try:
            key = int(attachment_id)
        except (TypeError, ValueError):
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _collect_ir_rows(
    adapter: Any,
    *,
    res_model: str,
    res_id: int | None = None,
    res_ids: list[int] | None = None,
    source_label: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not hasattr(adapter, "read_ir_attachments"):
        return []
    try:
        if res_ids:
            payload = adapter.read_ir_attachments(
                res_model=res_model,
                res_ids=res_ids,
                limit=limit,
            )
        else:
            payload = adapter.read_ir_attachments(
                res_model=res_model,
                res_id=res_id,
                limit=limit,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[ListAttachments] ir read failed %s: %s", res_model, exc)
        return []
    files: list[dict[str, Any]] = []
    for row in payload.get("rows") or []:
        if not isinstance(row, dict):
            continue
        normalized = _normalize_ir_row(row, source_label=source_label)
        if normalized:
            files.append(normalized)
    return files


def execute_list_attachments(
    tool_input: dict[str, Any],
    adapter: Any,
) -> dict[str, Any]:
    limit = int(tool_input.get("limit") or 50)
    project_id = tool_input.get("project_id")
    agreement_id = tool_input.get("agreement_id")
    rfq_id = tool_input.get("rfq_id")
    res_model = _text(tool_input.get("res_model"))
    res_id = tool_input.get("res_id")
    include_agreement = tool_input.get("include_agreement", True)

    files: list[dict[str, Any]] = []
    context_label = "Attachments"

    if project_id:
        project_id = int(project_id)
        names = adapter.safe_search_read(
            "project.project",
            [["id", "=", project_id]],
            ["name", "agreement_id"],
            limit=1,
        )
        project_name = _text(names[0].get("name")) if names else f"Project {project_id}"
        context_label = f"{project_name} — documents"

        folder_ids: list[int] = []
        try:
            pa_result = adapter.read_project_attachments(project_id, limit=limit)
            for row in pa_result.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                if row.get("mimetype"):
                    normalized = _normalize_ir_row(row, source_label="project.project")
                    if normalized:
                        files.append(normalized)
                    continue
                folder_id = _m2o_id(row.get("id"))
                if folder_id:
                    folder_ids.append(folder_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ListAttachments] project.attachment read failed: %s", exc)

        if folder_ids:
            files.extend(
                _collect_ir_rows(
                    adapter,
                    res_model="project.attachment",
                    res_ids=folder_ids,
                    source_label="project.attachment",
                    limit=limit,
                )
            )

        files.extend(
            _collect_ir_rows(
                adapter,
                res_model="project.project",
                res_id=project_id,
                source_label="project.project",
                limit=limit,
            )
        )

        if include_agreement and not agreement_id and names:
            agreement_id = _m2o_id(names[0].get("agreement_id"))

    if agreement_id:
        agreement_id = int(agreement_id)
        folder_ids = []
        try:
            agr_result = adapter.read_agreement_attachments(agreement_id, limit=limit)
            for row in agr_result.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                folder_id = _m2o_id(row.get("id"))
                if folder_id:
                    folder_ids.append(folder_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ListAttachments] agreement.attachment read failed: %s", exc)

        if folder_ids:
            files.extend(
                _collect_ir_rows(
                    adapter,
                    res_model="agreement.attachment",
                    res_ids=folder_ids,
                    source_label="agreement.attachment",
                    limit=limit,
                )
            )

    if rfq_id:
        rfq_id = int(rfq_id)
        for model in RFQ_MODEL_CANDIDATES:
            files.extend(
                _collect_ir_rows(
                    adapter,
                    res_model=model,
                    res_id=rfq_id,
                    source_label=model,
                    limit=limit,
                )
            )

    if res_model and res_id:
        files.extend(
            _collect_ir_rows(
                adapter,
                res_model=res_model,
                res_id=int(res_id),
                source_label=res_model,
                limit=limit,
            )
        )

    unique = _dedupe_files(files)[:limit]
    return {
        "status": "success",
        "_source": ATTACHMENTS_SOURCE,
        "label": context_label,
        "total_count": len(unique),
        "returned_count": len(unique),
        "files": unique,
    }


def run_list_attachments_tool(
    tool_name: str,
    tool_input: dict[str, Any],
    adapter: Any,
) -> dict[str, Any]:
    if tool_name == "list_attachments":
        return execute_list_attachments(tool_input, adapter)
    raise ValueError(f"Unknown attachments tool: {tool_name}")
