from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from admin.auth.config import PASSWORD_RESET_HOURS, auth_db_enabled
from admin.auth.dependencies import get_current_user
from admin.auth.jwt_tokens import create_mfa_challenge_token, decode_token
from admin.auth.principal import CurrentUser
from admin.auth.service import get_auth_service
from admin.rbac.checks import require_permission
from admin.security.mfa import (
    build_provisioning_uri,
    decrypt_mfa_secret,
    encrypt_mfa_secret,
    generate_totp_secret,
    verify_totp_code,
)
from admin.security.passwords import (
    generate_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from admin.security.rate_limit import (
    ADMIN_LIMIT_PER_MIN,
    LOGIN_LIMIT,
    check_login_ip,
)
from admin.security.session_policy import SESSION_IDLE_MINUTES

auth_security_router = APIRouter(tags=["auth-security"])


class MfaVerifyBody(BaseModel):
    mfa_token: str
    code: str = Field(min_length=6, max_length=8)


class MfaCodeBody(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class PasswordSetBody(BaseModel):
    current_password: str | None = None
    new_password: str = Field(min_length=8, max_length=128)


class PasswordResetRequestBody(BaseModel):
    file_id: str | None = None
    email: str | None = None


class PasswordResetBody(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


@auth_security_router.post("/auth/mfa/verify")
async def verify_mfa_login(body: MfaVerifyBody, request: Request) -> dict[str, Any]:
    if not auth_db_enabled():
        raise HTTPException(status_code=503, detail="Database authentication not configured")
    try:
        payload = decode_token(body.mfa_token, expected_type="mfa_challenge")
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired MFA challenge") from exc

    service = await get_auth_service()
    assert service is not None
    user_id = int(payload["sub"])
    user = await service._users.get_by_id(user_id)
    if not user or not user["mfa_enabled"] or not user["mfa_secret"]:
        raise HTTPException(status_code=401, detail="MFA not enabled for user")

    secret = decrypt_mfa_secret(user["mfa_secret"])
    if not verify_totp_code(secret=secret, code=body.code):
        await service._audit.log(
            user_id=user_id,
            event_type="auth",
            event_action="mfa.verify",
            status="failure",
            ip_address=request.client.host if request.client else None,
        )
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return await service.complete_login_after_mfa(
        user_id,
        ip_address=client_ip,
        user_agent=user_agent,
    )


@auth_security_router.post("/auth/mfa/setup")
async def setup_mfa(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    secret = generate_totp_secret()
    encrypted = encrypt_mfa_secret(secret)
    if not await service._users.set_mfa_pending(user.id, encrypted):
        raise HTTPException(status_code=404, detail="User not found")
    uri = build_provisioning_uri(secret=secret, account_name=user.file_id or user.name)
    return {
        "secret": secret,
        "provisioning_uri": uri,
        "message": "Scan the URI in your authenticator app, then confirm with a code.",
    }


@auth_security_router.post("/auth/mfa/confirm")
async def confirm_mfa(
    body: MfaCodeBody,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    row = await service._users.get_mfa_secrets(user.id)
    if not row or not row["mfa_pending_secret"]:
        raise HTTPException(status_code=400, detail="Call /auth/mfa/setup first")
    secret = decrypt_mfa_secret(row["mfa_pending_secret"])
    if not verify_totp_code(secret=secret, code=body.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    if not await service._users.confirm_mfa(user.id):
        raise HTTPException(status_code=400, detail="Could not enable MFA")
    await service._audit.log(
        user_id=user.id,
        event_type="security",
        event_action="mfa.enabled",
        status="success",
    )
    return {"status": "mfa_enabled"}


@auth_security_router.delete("/auth/mfa")
async def disable_mfa(
    body: MfaCodeBody,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    row = await service._users.get_mfa_secrets(user.id)
    if not row or not row["mfa_enabled"] or not row["mfa_secret"]:
        raise HTTPException(status_code=400, detail="MFA is not enabled")
    secret = decrypt_mfa_secret(row["mfa_secret"])
    if not verify_totp_code(secret=secret, code=body.code):
        raise HTTPException(status_code=401, detail="Invalid MFA code")
    await service._users.reset_mfa(user.id)
    await service._audit.log(
        user_id=user.id,
        event_type="security",
        event_action="mfa.disabled",
        status="success",
    )
    return {"status": "mfa_disabled"}


@auth_security_router.post("/auth/password/set")
async def set_password(
    body: PasswordSetBody,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    creds = await service._users.get_auth_credentials(user.id)
    if creds is None:
        raise HTTPException(status_code=404, detail="User not found")
    if creds["password_hash"]:
        if not body.current_password or not verify_password(
            body.current_password, creds["password_hash"]
        ):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
    await service._users.set_password_hash(user.id, hash_password(body.new_password))
    await service._audit.log(
        user_id=user.id,
        event_type="security",
        event_action="password.changed",
        status="success",
    )
    return {"status": "password_set"}


@auth_security_router.post("/auth/password/reset/request")
async def request_password_reset(
    body: PasswordResetRequestBody,
    request: Request,
) -> dict[str, Any]:
    if not auth_db_enabled():
        raise HTTPException(status_code=503, detail="Database authentication not configured")
    check_login_ip(request.client.host if request.client else None)

    service = await get_auth_service()
    assert service is not None
    user = None
    if body.email:
        user = await service._users.get_by_email(body.email)
    elif body.file_id:
        from admin.auth.service import normalize_file_id

        user = await service._users.get_by_file_id(normalize_file_id(body.file_id))

    generic: dict[str, Any] = {
        "status": "ok",
        "message": "If the account exists, a reset token was issued.",
    }
    if not user:
        return generic

    plain, token_hash = generate_reset_token()
    expires = datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_HOURS)
    await service._users.set_password_reset(user["id"], token_hash, expires)
    await service._audit.log(
        user_id=user["id"],
        event_type="security",
        event_action="password.reset_requested",
        status="success",
        ip_address=request.client.host if request.client else None,
    )
    return {
        **generic,
        "reset_token": plain,
        "expires_in_hours": PASSWORD_RESET_HOURS,
    }


@auth_security_router.post("/auth/password/reset")
async def reset_password(body: PasswordResetBody, request: Request) -> dict[str, str]:
    if not auth_db_enabled():
        raise HTTPException(status_code=503, detail="Database authentication not configured")
    service = await get_auth_service()
    assert service is not None
    user = await service._users.find_by_reset_token(hash_reset_token(body.token))
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    await service._users.set_password_hash(user["id"], hash_password(body.new_password))
    await service._users.clear_password_reset(user["id"])
    await service._sessions.revoke_all_for_user(user["id"], reason="password_reset")
    await service._audit.log(
        user_id=user["id"],
        event_type="security",
        event_action="password.reset",
        status="success",
        ip_address=request.client.host if request.client else None,
    )
    return {"status": "password_reset"}


@auth_security_router.get("/profile/security")
async def profile_security(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    row = await service._users.get_mfa_secrets(user.id)
    creds = await service._users.get_auth_credentials(user.id)
    return {
        "mfa_enabled": bool(row and row["mfa_enabled"]),
        "has_password": bool(creds and creds["password_hash"]),
        "session_idle_minutes": SESSION_IDLE_MINUTES,
    }


@auth_security_router.get(
    "/admin/security/summary",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def security_summary() -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    locked = await service._users.count_locked_users()
    mfa_count = await service._users.count_mfa_enabled()
    active_sessions = int(
        await service._db.fetchval(
            "SELECT COUNT(*) FROM sessions WHERE revoked_at IS NULL AND expires_at > NOW()"
        )
        or 0
    )
    recent_failures = await service._db.fetch(
        """
        SELECT id, user_id, event_action, ip_address, created_at
        FROM audit_logs
        WHERE event_type = 'auth' AND status = 'failure'
        ORDER BY created_at DESC
        LIMIT 10
        """
    )
    return {
        "locked_accounts": locked,
        "mfa_enabled_users": mfa_count,
        "active_sessions": active_sessions,
        "rate_limits": {
            "login_per_ip": f"{LOGIN_LIMIT} / 15min",
            "admin_per_min": ADMIN_LIMIT_PER_MIN,
        },
        "recent_auth_failures": [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "event_action": r["event_action"],
                "ip_address": r["ip_address"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in recent_failures
        ],
    }
