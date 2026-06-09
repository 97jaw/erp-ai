from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def odoo_identity_cache_fresh(user: Any, *, ttl_hours: int) -> bool:
    """True when cached Odoo identity is present and within TTL."""
    if ttl_hours <= 0:
        return False
    odoo_user_id = user.get("odoo_user_id") if isinstance(user, dict) else user["odoo_user_id"]
    verified_at = user.get("odoo_verified_at") if isinstance(user, dict) else user["odoo_verified_at"]
    if not odoo_user_id or not verified_at:
        return False
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=timezone.utc)
    age = datetime.now(timezone.utc) - verified_at
    return age < timedelta(hours=ttl_hours)


def has_cached_odoo_identity(user: Any) -> bool:
    odoo_user_id = user.get("odoo_user_id") if isinstance(user, dict) else user["odoo_user_id"]
    verified_at = user.get("odoo_verified_at") if isinstance(user, dict) else user["odoo_verified_at"]
    return bool(odoo_user_id and verified_at)
