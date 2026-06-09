from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def _odoo_configured() -> bool:
    required = ("ODOO_V14_URL", "ODOO_V14_DB", "ODOO_V14_USER", "ODOO_V14_PASSWORD")
    return all(os.environ.get(key) for key in required)


def _get_adapter():
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter

    return get_shared_odoo_adapter()


async def verify_file_id_with_odoo(file_id: str) -> dict[str, Any] | None:
    """
    Verify File ID against Odoo.
    Primary: hr.employee emp_id / employee_code = File ID (Elrace).
    Fallback: res.users.login = File ID.
    """
    if not _odoo_configured():
        return None

    from gateway.hr_identity import normalize_employee_file_id, resolve_employee_by_file_id

    normalized = normalize_employee_file_id(file_id)

    def _lookup() -> dict[str, Any] | None:
        adapter = _get_adapter()
        employee, _strategy = resolve_employee_by_file_id(adapter, normalized or file_id)
        if employee:
            lang = "en"
            odoo_user_id = None
            related = employee.get("user_id")
            if isinstance(related, (list, tuple)) and related:
                odoo_user_id = int(related[0])
                users = adapter.search_read(
                    "res.users",
                    [["id", "=", odoo_user_id]],
                    ["lang"],
                    limit=1,
                )
                if users and users[0].get("lang"):
                    lang = (users[0]["lang"] or "en_US").split("_")[0]
            return {
                "odoo_user_id": odoo_user_id,
                "employee_id": employee.get("id"),
                "name": employee.get("name") or normalized,
                "email": employee.get("work_email"),
                "file_id": normalized or file_id,
                "language": lang if lang in ("en", "ar") else "en",
            }

        users = adapter.search_read(
            "res.users",
            [["login", "=", normalized or file_id], ["active", "=", True]],
            ["id", "name", "email", "login", "lang"],
            limit=1,
        )
        if not users:
            return None
        row = users[0]
        lang = (row.get("lang") or "en_US").split("_")[0]
        return {
            "odoo_user_id": row.get("id"),
            "name": row.get("name") or file_id,
            "email": row.get("email"),
            "file_id": row.get("login") or file_id,
            "language": lang if lang in ("en", "ar") else "en",
        }

    try:
        return await asyncio.to_thread(_lookup)
    except Exception as exc:
        logger.warning("[Auth] Odoo verification failed for %s: %s", file_id, exc)
        return None
