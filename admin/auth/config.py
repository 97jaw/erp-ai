from __future__ import annotations

import os

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("JWT_ACCESS_HOURS", "8"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("JWT_REFRESH_DAYS", "30"))
MAX_FAILED_ATTEMPTS = int(os.environ.get("AUTH_MAX_FAILED_ATTEMPTS", "5"))
LOCKOUT_MINUTES = int(os.environ.get("AUTH_LOCKOUT_MINUTES", "15"))
VERIFY_ODOO_ON_LOGIN = os.environ.get("AUTH_VERIFY_ODOO_ON_LOGIN", "").strip().lower() in (
    "1",
    "true",
    "yes",
)
PASSWORD_RESET_HOURS = int(os.environ.get("AUTH_PASSWORD_RESET_HOURS", "1"))


def jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET", "").strip()
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured")
    return secret


def auth_db_enabled() -> bool:
    return bool(os.environ.get("OOA_DB_URL", "").strip())


def rbac_enforce() -> bool:
    explicit = os.environ.get("RBAC_ENFORCE")
    if explicit is None:
        return auth_db_enabled()
    return explicit.strip().lower() in ("1", "true", "yes")
