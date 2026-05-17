from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from admin.auth.config import auth_db_enabled, rbac_enforce
from admin.auth.principal import CurrentUser
from admin.auth.service import get_auth_service

_bearer = HTTPBearer(auto_error=False)


def _is_jwt(value: str | None) -> bool:
    return bool(value and value.count(".") == 2)


def extract_bearer_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials is not None:
        return credentials.credentials
    header = request.headers.get("authorization") or request.headers.get("Authorization")
    if header and header.lower().startswith("bearer "):
        return header[7:].strip()
    session_id = request.query_params.get("session_id")
    if _is_jwt(session_id):
        return session_id
    return None


async def resolve_authenticated_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser | None:
    if not auth_db_enabled():
        return None
    token = extract_bearer_token(request, credentials)
    if not token:
        return None
    service = await get_auth_service()
    if service is None:
        return None
    return await service.resolve_current_user(token)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if not auth_db_enabled():
        raise HTTPException(
            status_code=503,
            detail="Database authentication not configured",
        )
    token = extract_bearer_token(request, credentials)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    service = await get_auth_service()
    assert service is not None
    return await service.resolve_current_user(token)


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser | None:
    return await resolve_authenticated_user(request, credentials)


async def require_chat_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session_id: str | None = None,
) -> CurrentUser | None:
    """Enforce JWT auth on chat when RBAC_ENFORCE is on (default with OOA_DB_URL)."""
    if not rbac_enforce():
        return None
    token = extract_bearer_token(request, credentials)
    if not token and _is_jwt(session_id):
        token = session_id
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    service = await get_auth_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Authentication service unavailable")
    return await service.resolve_current_user(token)


def chat_user_dependency(session_id: str | None):
    """Factory for FastAPI Depends with body session_id."""

    async def _dep(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    ) -> CurrentUser | None:
        return await require_chat_user(request, credentials, session_id=session_id)

    return _dep
