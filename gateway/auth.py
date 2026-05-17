from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, Request

from admin.auth.config import auth_db_enabled

logger = logging.getLogger(__name__)

ALLOWED_FILE_IDS: dict[str, dict[str, Any]] = {
    "2721": {
        "user_name": "Mohammad Jawad",
        "language": "en",
        "file_id": "2721",
        "welcome_title": "Welcome",
        "welcome_message": "Good to see you again. Your Odoo workspace is ready.",
    },
}


class AuthSessionStore:
    """Legacy in-memory sessions when OOA_DB_URL is not set."""

    _sessions: dict[str, dict[str, Any]] = {}

    @classmethod
    def create(cls, user: dict[str, Any]) -> str:
        session_id = str(uuid4())
        cls._sessions[session_id] = user
        return session_id

    @classmethod
    def get(cls, session_id: str | None) -> dict[str, Any] | None:
        if not session_id:
            return None
        return cls._sessions.get(session_id)

    @classmethod
    def clear(cls, session_id: str | None) -> None:
        if session_id:
            cls._sessions.pop(session_id, None)


def _normalize_file_id(file_id: str) -> str:
    return re.sub(r"\s+", "", file_id or "")


def _legacy_login(file_id: str) -> dict[str, Any]:
    normalized = _normalize_file_id(file_id)
    if not normalized:
        raise HTTPException(status_code=400, detail="File ID is required.")

    profile = ALLOWED_FILE_IDS.get(normalized)
    if profile is None:
        raise HTTPException(status_code=401, detail="File ID not recognized.")

    session_id = AuthSessionStore.create(dict(profile))
    language = profile.get("language") or "en"
    return {
        "status": "success",
        "session_id": session_id,
        "user_name": profile.get("user_name"),
        "language": language,
        "file_id": normalized,
        "welcome_title": profile.get("welcome_title", "Welcome"),
        "welcome_message": profile.get("welcome_message"),
        "audio_response": f"/sounds/login-success-{language}.mp3",
    }


async def login_with_file_id(
    file_id: str,
    *,
    request: Request | None = None,
) -> dict[str, Any]:
    if auth_db_enabled():
        from admin.security.rate_limit import check_login_ip
        from gateway.metrics import record_login_attempt

        client_ip = request.client.host if request and request.client else None
        try:
            check_login_ip(client_ip)
        except Exception as exc:
            record_login_attempt(status="failure", reason="rate_limit")
            raise

        from admin.auth.service import get_auth_service

        service = await get_auth_service()
        assert service is not None
        user_agent = request.headers.get("user-agent") if request else None
        try:
            result = await service.login(file_id, ip_address=client_ip, user_agent=user_agent)
            record_login_attempt(
                status="success" if result.get("status") != "mfa_required" else "mfa_required",
                reason="none",
            )
            return result
        except HTTPException as exc:
            reason = "not_found" if exc.status_code == 401 else "locked" if exc.status_code == 403 else "error"
            record_login_attempt(status="failure", reason=reason)
            raise
    try:
        return _legacy_login(file_id)
    except HTTPException:
        from gateway.metrics import record_login_attempt

        record_login_attempt(status="failure", reason="not_found")
        raise


async def get_profile(session_id: str | None) -> dict[str, Any]:
    if auth_db_enabled() and session_id and "." in session_id:
        from admin.auth.service import get_auth_service

        service = await get_auth_service()
        assert service is not None
        return await service.get_profile_from_token(session_id)
    user = AuthSessionStore.get(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return {
        "user_name": user.get("user_name"),
        "language": user.get("language", "en"),
        "file_id": user.get("file_id"),
        "welcome_title": user.get("welcome_title"),
        "welcome_message": user.get("welcome_message"),
    }


async def logout(session_id: str | None) -> dict[str, str]:
    if auth_db_enabled() and session_id and "." in session_id:
        from admin.auth.service import get_auth_service

        service = await get_auth_service()
        assert service is not None
        return await service.logout(session_id)
    AuthSessionStore.clear(session_id)
    return {"status": "logged_out"}


async def refresh_tokens(refresh_token: str) -> dict[str, Any]:
    from admin.auth.service import get_auth_service

    service = await get_auth_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Database authentication not configured")
    return await service.refresh(refresh_token)
