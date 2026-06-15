"""Session-scoped download tokens for Odoo attachments (not persisted in chat DB)."""

from __future__ import annotations

import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TTL_SECONDS = 8 * 60 * 60  # 8 hours
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


@dataclass(frozen=True)
class EphemeralFileRef:
    token: str
    session_id: str
    odoo_attachment_id: int
    name: str
    mimetype: str
    size_bytes: int | None
    expires_at: float


class EphemeralFileStore:
    """In-memory registry of short-lived download tokens."""

    _entries: dict[str, EphemeralFileRef] = {}

    @classmethod
    def register(
        cls,
        *,
        session_id: str,
        files: list[dict[str, Any]],
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> list[dict[str, Any]]:
        cls.cleanup_expired()
        now = time.time()
        expires_at = now + max(1, int(ttl_seconds))
        registered: list[dict[str, Any]] = []
        for row in files:
            attachment_id = row.get("odoo_attachment_id") or row.get("id")
            if attachment_id is None:
                continue
            try:
                attachment_id = int(attachment_id)
            except (TypeError, ValueError):
                continue
            token = secrets.token_urlsafe(24)
            ref = EphemeralFileRef(
                token=token,
                session_id=str(session_id or ""),
                odoo_attachment_id=attachment_id,
                name=str(row.get("name") or "file"),
                mimetype=str(row.get("mimetype") or "application/octet-stream"),
                size_bytes=int(row["size_bytes"]) if row.get("size_bytes") is not None else None,
                expires_at=expires_at,
            )
            cls._entries[token] = ref
            registered.append(
                {
                    **row,
                    "download_token": token,
                    "download_url": f"/attachments/download/{token}",
                }
            )
        return registered

    @classmethod
    def resolve(cls, token: str) -> EphemeralFileRef | None:
        cls.cleanup_expired()
        ref = cls._entries.get(str(token or ""))
        if not ref:
            return None
        if ref.expires_at <= time.time():
            cls._entries.pop(ref.token, None)
            return None
        return ref

    @classmethod
    def cleanup_expired(cls) -> int:
        now = time.time()
        expired = [key for key, ref in cls._entries.items() if ref.expires_at <= now]
        for key in expired:
            cls._entries.pop(key, None)
        return len(expired)

    @classmethod
    def cleanup_session(cls, session_id: str) -> int:
        if not session_id:
            return 0
        keys = [key for key, ref in cls._entries.items() if ref.session_id == session_id]
        for key in keys:
            cls._entries.pop(key, None)
        return len(keys)

    @classmethod
    def clear_for_tests(cls) -> None:
        cls._entries.clear()
