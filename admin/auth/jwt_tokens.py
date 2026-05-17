from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt

from admin.auth.config import (
    ACCESS_TOKEN_EXPIRE_HOURS,
    ALGORITHM,
    REFRESH_TOKEN_EXPIRE_DAYS,
    jwt_secret,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    *,
    user_id: int,
    file_id: str,
    roles: list[str] | None = None,
    is_super_admin: bool = False,
) -> tuple[str, datetime]:
    expires = _utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    from admin.security.rate_limit import primary_role_for_limits

    role_list = list(roles or [])
    payload = {
        "sub": str(user_id),
        "fid": file_id,
        "exp": expires,
        "iat": _utcnow(),
        "type": "access",
        "roles": role_list,
        "role": primary_role_for_limits(role_list, is_super_admin=is_super_admin),
        "sa": is_super_admin,
    }
    token = jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)
    return token, expires


def create_mfa_challenge_token(*, user_id: int) -> str:
    expires = _utcnow() + timedelta(minutes=5)
    payload = {
        "sub": str(user_id),
        "exp": expires,
        "iat": _utcnow(),
        "type": "mfa_challenge",
    }
    return jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)


def create_refresh_token(*, user_id: int, file_id: str) -> tuple[str, datetime]:
    expires = _utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(user_id),
        "fid": file_id,
        "exp": expires,
        "iat": _utcnow(),
        "type": "refresh",
    }
    token = jwt.encode(payload, jwt_secret(), algorithm=ALGORITHM)
    return token, expires


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
    if expected_type and payload.get("type") != expected_type:
        raise ValueError(f"Expected token type {expected_type}")
    return payload
