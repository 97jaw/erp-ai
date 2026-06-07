from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from admin.auth.config import (
    LOCKOUT_MINUTES,
    MAX_FAILED_ATTEMPTS,
    VERIFY_ODOO_ON_LOGIN,
    auth_db_enabled,
)
from admin.auth.jwt_tokens import (
    create_access_token,
    create_mfa_challenge_token,
    create_refresh_token,
    decode_token,
    hash_token,
)
from admin.auth.odoo_verify import verify_file_id_with_odoo
from admin.auth.principal import CurrentUser
from admin.db.connection import AdminDatabase, init_admin_db
from admin.db.repositories.audit import AuditRepository
from admin.db.repositories.sessions import SessionRepository
from admin.db.repositories.roles import RoleRepository
from admin.db.repositories.users import UserRepository

logger = logging.getLogger(__name__)

# Dev fallback when DB auth is off or user not yet provisioned
LEGACY_ALLOWED_FILE_IDS: dict[str, dict[str, Any]] = {
    "2721": {
        "user_name": "Mohammad Jawad",
        "language": "en",
        "file_id": "2721",
        "welcome_title": "Welcome",
        "welcome_message": "Good to see you again. Your Odoo workspace is ready.",
    },
}


def normalize_file_id(file_id: str) -> str:
    return re.sub(r"\s+", "", file_id or "")


class AuthService:
    def __init__(self, db: AdminDatabase) -> None:
        self._db = db
        self._users = UserRepository(db)
        self._roles = RoleRepository(db)
        self._sessions = SessionRepository(db)
        self._audit = AuditRepository(db)

    @classmethod
    async def create(cls) -> AuthService:
        return cls(await init_admin_db())

    async def login(
        self,
        file_id: str,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        normalized = normalize_file_id(file_id)
        if not normalized:
            raise HTTPException(status_code=400, detail="File ID is required.")

        user = await self._users.get_by_file_id(normalized)
        if user is None:
            user = await self._resolve_and_provision(normalized)
        if user is None:
            await self._users.record_failed_login(
                normalized,
                max_attempts=MAX_FAILED_ATTEMPTS,
                lockout_minutes=LOCKOUT_MINUTES,
            )
            await self._audit.log(
                user_id=None,
                event_type="auth",
                event_action="user.login",
                status="failure",
                ip_address=ip_address,
                user_agent=user_agent,
                metadata={"file_id": normalized, "reason": "not_found"},
            )
            raise HTTPException(status_code=401, detail="File ID not recognized.")

        if not user["is_active"]:
            raise HTTPException(status_code=403, detail="Account is disabled.")

        locked_until = user["locked_until"]
        if locked_until and locked_until > datetime.now(timezone.utc):
            raise HTTPException(
                status_code=403,
                detail=f"Account locked until {locked_until.isoformat()}",
            )

        if VERIFY_ODOO_ON_LOGIN:
            verified = await verify_file_id_with_odoo(normalized)
            if not verified:
                await self._users.record_failed_login(
                    normalized,
                    max_attempts=MAX_FAILED_ATTEMPTS,
                    lockout_minutes=LOCKOUT_MINUTES,
                )
                await self._audit.log(
                    user_id=user["id"],
                    event_type="auth",
                    event_action="user.login",
                    status="failure",
                    ip_address=ip_address,
                    user_agent=user_agent,
                    metadata={"reason": "odoo_verification_failed"},
                )
                raise HTTPException(status_code=401, detail="File ID not recognized.")

        await self._sync_odoo_user_link(user)

        if user["mfa_enabled"] and user["mfa_secret"]:
            language = user["language"] or "en"
            welcome = self._welcome_for_user(user)
            return {
                "status": "mfa_required",
                "mfa_required": True,
                "mfa_token": create_mfa_challenge_token(user_id=user["id"]),
                "user_name": user["name"],
                "language": language,
                "file_id": user["file_id"],
                "welcome_title": welcome.get("welcome_title", "Welcome"),
                "welcome_message": welcome.get("welcome_message"),
            }

        return await self._issue_login_tokens(
            user,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def complete_login_after_mfa(
        self,
        user_id: int,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        user = await self._users.get_by_id(user_id)
        if not user or not user["is_active"]:
            raise HTTPException(status_code=401, detail="User not found")
        if not user["mfa_enabled"]:
            raise HTTPException(status_code=400, detail="MFA is not enabled")
        payload = await self._issue_login_tokens(
            user,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._audit.log(
            user_id=user_id,
            event_type="auth",
            event_action="mfa.verify",
            status="success",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return payload

    async def _sync_odoo_user_link(self, user: Any) -> None:
        """Keep users.odoo_user_id aligned with Odoo res.users login = file_id."""
        from admin.auth.odoo_verify import _odoo_configured, verify_file_id_with_odoo

        if not _odoo_configured():
            return
        verified = await verify_file_id_with_odoo(user["file_id"])
        if verified and verified.get("odoo_user_id"):
            odoo_uid = int(verified["odoo_user_id"])
            if user.get("odoo_user_id") != odoo_uid:
                await self._users.set_odoo_user_id(int(user["id"]), odoo_uid)
                user["odoo_user_id"] = odoo_uid

    async def _issue_login_tokens(
        self,
        user: Any,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict[str, Any]:
        roles = await self._users.get_roles(user["id"])
        access_token, access_expires = create_access_token(
            user_id=user["id"],
            file_id=user["file_id"],
            roles=roles,
            is_super_admin=bool(user["is_super_admin"]),
        )
        refresh_token, _refresh_expires = create_refresh_token(
            user_id=user["id"],
            file_id=user["file_id"],
        )
        session_id = await self._sessions.create(
            user_id=user["id"],
            token_hash=hash_token(access_token),
            refresh_token_hash=hash_token(refresh_token),
            expires_at=access_expires,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._users.update_last_login(user["id"], ip_address)
        await self._audit.log(
            user_id=user["id"],
            event_type="auth",
            event_action="user.login",
            status="success",
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        language = user["language"] or "en"
        welcome = self._welcome_for_user(user)
        return {
            "status": "success",
            "mfa_required": False,
            "session_id": access_token,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int((access_expires - datetime.now(timezone.utc)).total_seconds()),
            "user_name": user["name"],
            "language": language,
            "file_id": user["file_id"],
            "welcome_title": welcome.get("welcome_title", "Welcome"),
            "welcome_message": welcome.get("welcome_message"),
            "audio_response": f"/sounds/login-success-{language}.mp3",
            "roles": roles,
            "permissions": await self._users.get_permissions(user["id"]),
            "departments": await self._users.get_department_codes(user["id"]),
        }

    async def _resolve_and_provision(self, file_id: str) -> Any:
        odoo_user = await verify_file_id_with_odoo(file_id)
        if odoo_user:
            user_id = await self._users.provision_user(
                file_id=odoo_user["file_id"],
                name=odoo_user["name"],
                email=odoo_user.get("email"),
                odoo_user_id=odoo_user.get("odoo_user_id"),
                language=odoo_user.get("language", "en"),
                role_name="user",
            )
            return await self._users.get_by_id(user_id)

        legacy = LEGACY_ALLOWED_FILE_IDS.get(file_id)
        if legacy:
            user_id = await self._users.provision_user(
                file_id=file_id,
                name=legacy.get("user_name", file_id),
                language=legacy.get("language", "en"),
                role_name="user",
            )
            return await self._users.get_by_id(user_id)

        return None

    async def get_profile_from_token(self, token: str | None) -> dict[str, Any]:
        if not token:
            raise HTTPException(status_code=401, detail="Session expired or invalid")
        normalized = token.strip()
        if normalized.lower().startswith("bearer "):
            normalized = normalized[7:].strip()

        session = await self._sessions.get_active_by_token_hash(hash_token(normalized))
        if not session:
            raise HTTPException(status_code=401, detail="Session expired or invalid")

        await self._sessions.touch(session["id"])
        welcome = self._welcome_for_user(session)
        return {
            "user_name": session["name"],
            "language": session["language"] or "en",
            "file_id": session["file_id"],
            "welcome_title": welcome.get("welcome_title", "Welcome"),
            "welcome_message": welcome.get("welcome_message"),
            "user_id": session["user_id"],
            "roles": await self._users.get_roles(session["user_id"]),
            "permissions": await self._users.get_permissions(session["user_id"]),
        }

    async def logout(self, token: str | None) -> dict[str, str]:
        if token:
            normalized = token.strip()
            if normalized.lower().startswith("bearer "):
                normalized = normalized[7:].strip()
            await self._sessions.revoke(hash_token(normalized))
        return {"status": "logged_out"}

    async def refresh(self, refresh_token: str) -> dict[str, Any]:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

        refresh_hash = hash_token(refresh_token)
        row = await self._db.fetchrow(
            """
            SELECT s.*, u.file_id, u.name, u.is_active
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.refresh_token = $1
              AND s.revoked_at IS NULL
              AND u.deleted_at IS NULL
            """,
            refresh_hash,
        )
        if not row or not row["is_active"]:
            raise HTTPException(status_code=401, detail="Session expired or revoked")

        await self._sessions.revoke_by_refresh_hash(refresh_hash, reason="rotated")
        user = await self._users.get_by_id(int(payload["sub"]))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        roles = await self._users.get_roles(user["id"])
        access_token, access_expires = create_access_token(
            user_id=user["id"],
            file_id=user["file_id"],
            roles=roles,
            is_super_admin=bool(user["is_super_admin"]),
        )
        new_refresh, _ = create_refresh_token(user_id=user["id"], file_id=user["file_id"])
        await self._sessions.create(
            user_id=user["id"],
            token_hash=hash_token(access_token),
            refresh_token_hash=hash_token(new_refresh),
            expires_at=access_expires,
        )
        return {
            "access_token": access_token,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "expires_in": int((access_expires - datetime.now(timezone.utc)).total_seconds()),
        }

    async def build_current_user(self, user_id: int) -> CurrentUser:
        user = await self._users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return CurrentUser.from_record(
            dict(user),
            roles=await self._users.get_roles(user_id),
            permissions=await self._users.get_permissions(user_id),
            department_ids=await self._users.get_department_ids(user_id),
            department_codes=await self._users.get_department_codes(user_id),
        )

    async def resolve_current_user(self, token: str) -> CurrentUser:
        row = await self.resolve_user_from_token(token)
        user_id = int(row.get("user_id") or row["id"])
        return await self.build_current_user(user_id)

    async def log_permission_denied(self, user_id: int, permission_code: str) -> None:
        await self._audit.log(
            user_id=user_id,
            event_type="security",
            event_action="permission.denied",
            status="failure",
            metadata={"permission": permission_code},
        )

    async def resolve_user_from_token(self, token: str) -> dict[str, Any]:
        normalized = token.strip()
        if normalized.lower().startswith("bearer "):
            normalized = normalized[7:].strip()
        session = await self._sessions.get_active_by_token_hash(hash_token(normalized))
        if session:
            await self._sessions.touch(session["id"])
            return dict(session)
        try:
            payload = decode_token(normalized, expected_type="access")
        except ValueError as exc:
            raise HTTPException(status_code=401, detail="Invalid token") from exc
        user = await self._users.get_by_id(int(payload["sub"]))
        if not user or not user["is_active"]:
            raise HTTPException(status_code=403, detail="User not active")
        return dict(user)

    @staticmethod
    def _welcome_for_user(user: Any) -> dict[str, str]:
        legacy = LEGACY_ALLOWED_FILE_IDS.get(user["file_id"], {})
        return {
            "welcome_title": legacy.get("welcome_title", "Welcome"),
            "welcome_message": legacy.get(
                "welcome_message",
                "Your Odoo workspace is ready.",
            ),
        }


_db_auth_service: AuthService | None = None


async def get_auth_service() -> AuthService | None:
    global _db_auth_service
    if not auth_db_enabled():
        return None
    if _db_auth_service is None:
        _db_auth_service = await AuthService.create()
    return _db_auth_service
