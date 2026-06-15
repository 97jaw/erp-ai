"""FILE_LIST visualization for ephemeral attachment downloads."""

from __future__ import annotations

from typing import Any

from gateway.ephemeral_files import EphemeralFileStore


def file_list_summary_text(label: str, file_count: int, *, language: str = "en") -> str:
    """Short chat line when FILE_LIST visual carries the download UI."""
    safe_label = str(label or "Documents").strip()
    count = max(int(file_count or 0), 0)
    if language == "ar":
        return f"**{count}** ملفًا متاحًا للتنزيل لـ **{safe_label}**."
    unit = "file" if count == 1 else "files"
    return f"**{count}** {unit} ready to download for **{safe_label}**."


def build_file_list_visualization(
    payload: dict[str, Any],
    *,
    session_id: str | None,
) -> dict[str, Any] | None:
    if payload.get("status") != "success":
        return None
    raw_files = payload.get("files") or []
    if not raw_files:
        return None

    session_key = str(session_id or "anonymous")
    files = EphemeralFileStore.register(session_id=session_key, files=raw_files)
    if not files:
        return None

    label = str(payload.get("label") or "Documents")
    total = int(payload.get("total_count") or len(files))
    return {
        "visual_type": "FILE_LIST",
        "label": label,
        "value": total,
        "unit": "files",
        "ephemeral": True,
        "disclosure_exempt": True,
        "data": {
            "files": files,
            "total_count": total,
            "expired_notice": "Downloads expire after this session. Ask again to refresh.",
        },
    }


def sanitize_visualization_for_persist(
    visualization: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Strip ephemeral download tokens before writing chat history to DB."""
    if not visualization or not visualization.get("ephemeral"):
        return visualization

    stripped = dict(visualization)
    data = dict(stripped.get("data") or {})
    files = data.get("files") or []
    count = len(files)
    data.pop("files", None)
    data["file_count"] = count
    data["expired_notice"] = (
        f"{count} file{'s' if count != 1 else ''} were listed — "
        "downloads are not kept in chat history. Ask again to refresh."
    )
    stripped["data"] = data
    stripped.pop("download_url", None)
    return stripped
