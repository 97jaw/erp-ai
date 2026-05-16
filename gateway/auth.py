from __future__ import annotations

import logging
import re
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

logger = logging.getLogger(__name__)

ALLOWED_FILE_IDS: dict[str, dict[str, Any]] = {
    "2721": {
        "user_name"      : "Mohammad Jawad",
        "language"       : "en",
        "file_id"        : "2721",
        "welcome_title"  : "Welcome",
        "welcome_message": "Good to see you again. Your Odoo workspace is ready.",
    },
}


class AuthSessionStore:
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


def login_with_file_id(file_id: str) -> dict[str, Any]:
    normalized = _normalize_file_id(file_id)
    if not normalized:
        raise HTTPException(status_code=400, detail="File ID is required.")

    profile = ALLOWED_FILE_IDS.get(normalized)
    if profile is None:
        raise HTTPException(status_code=401, detail="File ID not recognized.")

    session_id = AuthSessionStore.create(dict(profile))
    language = profile.get("language") or "en"
    return {
        "status"         : "success",
        "session_id"     : session_id,
        "user_name"      : profile.get("user_name"),
        "language"       : language,
        "file_id"        : normalized,
        "welcome_title"  : profile.get("welcome_title", "Welcome"),
        "welcome_message": profile.get("welcome_message"),
        "audio_response" : f"/sounds/login-success-{language}.mp3",
    }


def get_profile(session_id: str | None) -> dict[str, Any]:
    user = AuthSessionStore.get(session_id)
    if not user:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return {
        "user_name"      : user.get("user_name"),
        "language"       : user.get("language", "en"),
        "file_id"        : user.get("file_id"),
        "welcome_title"  : user.get("welcome_title"),
        "welcome_message": user.get("welcome_message"),
    }


def logout(session_id: str | None) -> dict[str, str]:
    AuthSessionStore.clear(session_id)
    return {"status": "logged_out"}
