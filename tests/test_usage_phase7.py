from __future__ import annotations

import os
from datetime import date

import pytest

requires_db = pytest.mark.skipif(
    not os.environ.get("OOA_DB_URL") or not os.environ.get("JWT_SECRET"),
    reason="OOA_DB_URL and JWT_SECRET required",
)


def test_estimate_cost_cents() -> None:
    from admin.db.repositories.usage import estimate_cost_cents

    assert estimate_cost_cents(tokens=2000, pdfs=1, voice_minutes=2) > 0


@pytest.mark.asyncio
@requires_db
async def test_usage_record_and_summary() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.usage import UsageRepository
    from admin.db.repositories.users import UserRepository

    service = await AuthService.create()
    users = UserRepository(service._db)
    usage = UsageRepository(service._db)
    user_id = None
    try:
        user_id = await users.create_user(
            file_id="phase7-usage-user",
            name="Phase 7 Usage",
            email="phase7@test.com",
        )
        await usage.record(user_id, queries=2, tokens=1500, pdfs=1)
        summary = await usage.system_summary(
            date_from=date.today(),
            date_to=date.today(),
        )
        assert summary is not None
        assert int(summary["queries_count"]) >= 2
        assert int(summary["tokens_used"]) >= 1500
        breakdown = await usage.cost_breakdown(
            date_from=date.today(),
            date_to=date.today(),
        )
        assert breakdown["total_cents"] >= 0
        await users.soft_delete(user_id)
        user_id = None
    finally:
        if user_id:
            await users.soft_delete(user_id)
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_audit_export_list() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.audit import AuditRepository

    service = await AuthService.create()
    audit = AuditRepository(service._db)
    try:
        await audit.log(
            user_id=None,
            event_type="query",
            event_action="test.export",
            status="success",
            metadata={"phase": 7},
        )
        rows = await audit.export_events(limit=5)
        assert len(rows) >= 1
    finally:
        await close_admin_db()
