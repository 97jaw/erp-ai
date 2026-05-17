from __future__ import annotations

import asyncio
import logging
from typing import Any

from admin.auth.config import auth_db_enabled

logger = logging.getLogger(__name__)


def _enabled() -> bool:
    return auth_db_enabled()


def schedule_usage(coro) -> None:
    if not _enabled():
        return
    try:
        asyncio.get_running_loop().create_task(coro)
    except RuntimeError:
        pass


def schedule_audit(coro) -> None:
    schedule_usage(coro)


async def track_agent_turn(
    user_id: int | None,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    tools: list[str] | None = None,
) -> None:
    if not user_id or not _enabled():
        return
    from admin.db.connection import init_admin_db
    from admin.db.repositories.usage import UsageRepository
    from admin.db.repositories.audit import AuditRepository

    tokens = int(input_tokens or 0) + int(output_tokens or 0)
    db = await init_admin_db()
    usage = UsageRepository(db)
    audit = AuditRepository(db)
    await usage.record(user_id, queries=1, tokens=tokens)
    await audit.log(
        user_id=user_id,
        event_type="query",
        event_action="chat.completed",
        status="success",
        metadata={"tools": tools or [], "tokens": tokens},
    )


async def track_pdf_generated(user_id: int | None, *, report_type: str | None = None) -> None:
    if not user_id or not _enabled():
        return
    from admin.db.connection import init_admin_db
    from admin.db.repositories.usage import UsageRepository
    from admin.db.repositories.audit import AuditRepository

    db = await init_admin_db()
    await UsageRepository(db).record(user_id, pdfs=1)
    await AuditRepository(db).log(
        user_id=user_id,
        event_type="query",
        event_action="pdf.generated",
        status="success",
        resource_type="report",
        resource_id=report_type,
    )


async def track_voice_minutes(user_id: int | None, minutes: float) -> None:
    if not user_id or not _enabled() or minutes <= 0:
        return
    from admin.db.connection import init_admin_db
    from admin.db.repositories.usage import UsageRepository

    db = await init_admin_db()
    await UsageRepository(db).record(user_id, voice_minutes=minutes)


async def track_permission_denied(
    user_id: int | None,
    *,
    permission: str,
    tool_name: str | None = None,
) -> None:
    if not user_id or not _enabled():
        return
    await audit_event(
        user_id,
        event_type="security",
        event_action="permission.denied",
        status="failure",
        metadata={"permission": permission, "tool": tool_name},
    )


async def audit_event(
    user_id: int | None,
    *,
    event_type: str,
    event_action: str,
    status: str = "success",
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> None:
    if not _enabled():
        return
    try:
        from admin.db.connection import init_admin_db
        from admin.db.repositories.audit import AuditRepository

        db = await init_admin_db()
        await AuditRepository(db).log(
            user_id=user_id,
            event_type=event_type,
            event_action=event_action,
            status=status,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            ip_address=ip_address,
        )
    except Exception as exc:
        logger.warning("[Observability] audit failed: %s", exc)


def extract_token_usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if not usage:
        return 0, 0
    return int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0)
