"""PostgreSQL integration tests for telemetry repository (Phase 8)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest

from gateway.core.interaction_telemetry import InteractionTelemetry

requires_db = pytest.mark.skipif(
    not os.environ.get("OOA_DB_URL"),
    reason="OOA_DB_URL not set",
)


def _telemetry(**kwargs) -> InteractionTelemetry:
    base = InteractionTelemetry.start(
        user_id=kwargs.pop("user_id", 1),
        session_id=kwargs.pop("session_id", "telemetry-test-session"),
        user_query=kwargs.pop("user_query", "Show revenue by client"),
    )
    base.response_text = kwargs.pop("response_text", "Revenue summary ready.")
    base.suggestions_offered = kwargs.pop("suggestions_offered", ["Compare with last year"])
    base.total_duration_ms = kwargs.pop("total_duration_ms", 900)
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


@pytest.mark.asyncio
@requires_db
async def test_migration_creates_ai_interactions_table() -> None:
    from admin.db.connection import close_admin_db, init_admin_db

    db = await init_admin_db()
    try:
        exists = await db.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'ai_interactions'
            )
            """
        )
        assert exists is True
    finally:
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_insert_and_get_by_id() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.telemetry import TelemetryRepository
    from admin.db.repositories.users import UserRepository

    service = await AuthService.create()
    repo = TelemetryRepository(service._db)
    users = UserRepository(service._db)
    user_id = None
    try:
        user_id = await users.create_user(
            file_id="telemetry-insert-user",
            name="Telemetry Insert",
            email="telemetry-insert@test.com",
        )
        telemetry = _telemetry(user_id=user_id, session_id="insert-session")
        await repo.insert(telemetry)
        row = await repo.get_by_id(telemetry.interaction_id)
        assert row is not None
        assert row["user_query"] == "Show revenue by client"
        assert row["response_text"] == "Revenue summary ready."
    finally:
        if user_id:
            await users.soft_delete(user_id)
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_list_recent_returns_inserted_rows() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.telemetry import TelemetryRepository
    from admin.db.repositories.users import UserRepository

    service = await AuthService.create()
    repo = TelemetryRepository(service._db)
    users = UserRepository(service._db)
    user_id = None
    try:
        user_id = await users.create_user(
            file_id="telemetry-list-user",
            name="Telemetry List",
            email="telemetry-list@test.com",
        )
        await repo.insert(_telemetry(user_id=user_id, user_query="List test query"))
        rows = await repo.list_recent(hours=1, user_id=user_id, limit=10)
        assert any(row["user_query"] == "List test query" for row in rows)
    finally:
        if user_id:
            await users.soft_delete(user_id)
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_summary_counts_interactions() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.telemetry import TelemetryRepository
    from admin.db.repositories.users import UserRepository

    service = await AuthService.create()
    repo = TelemetryRepository(service._db)
    users = UserRepository(service._db)
    user_id = None
    try:
        user_id = await users.create_user(
            file_id="telemetry-summary-user",
            name="Telemetry Summary",
            email="telemetry-summary@test.com",
        )
        before = await repo.summary(hours=1)
        before_count = int(before["interactions"] or 0) if before else 0
        await repo.insert(_telemetry(user_id=user_id))
        after = await repo.summary(hours=1)
        assert int(after["interactions"]) >= before_count + 1
    finally:
        if user_id:
            await users.soft_delete(user_id)
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_apply_follow_up_signals_updates_previous_row() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.telemetry import TelemetryRepository
    from admin.db.repositories.users import UserRepository

    service = await AuthService.create()
    repo = TelemetryRepository(service._db)
    users = UserRepository(service._db)
    user_id = None
    try:
        user_id = await users.create_user(
            file_id="telemetry-followup-user",
            name="Telemetry Followup",
            email="telemetry-followup@test.com",
        )
        session_id = "followup-session"
        first = _telemetry(
            user_id=user_id,
            session_id=session_id,
            suggestions_offered=["Compare with last year"],
        )
        await repo.insert(first)
        await repo.apply_follow_up_signals(
            user_id=user_id,
            session_id=session_id,
            next_query="Compare with last year",
        )
        row = await repo.get_by_id(first.interaction_id)
        assert row is not None
        assert row["chat_continued"] is True
        assert row["suggestion_clicked"] == "Compare with last year"
    finally:
        if user_id:
            await users.soft_delete(user_id)
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_upsert_user_patterns_round_trip() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.telemetry import TelemetryRepository
    from admin.db.repositories.users import UserRepository

    service = await AuthService.create()
    repo = TelemetryRepository(service._db)
    users = UserRepository(service._db)
    user_id = None
    try:
        user_id = await users.create_user(
            file_id="telemetry-patterns-user",
            name="Telemetry Patterns",
            email="telemetry-patterns@test.com",
        )
        payload = {"top_subject_areas": ["financial"], "preferred_tools": ["group_and_aggregate"]}
        await repo.upsert_user_patterns(user_id, payload)
        loaded = await repo.get_user_patterns(user_id)
        assert loaded["top_subject_areas"] == ["financial"]
    finally:
        if user_id:
            await users.soft_delete(user_id)
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_learning_job_run_lifecycle() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.telemetry import TelemetryRepository

    service = await AuthService.create()
    repo = TelemetryRepository(service._db)
    try:
        job_id = await repo.start_learning_job(24)
        await repo.finish_learning_job(
            job_id,
            status="success",
            interactions_analyzed=5,
            summary={"quality_drift": {"sample_size": 5}},
        )
        latest = await repo.latest_learning_job()
        assert latest is not None
        assert latest["status"] == "success"
        assert int(latest["interactions_analyzed"]) == 5
    finally:
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_list_for_admin_returns_redacted_columns() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.telemetry import TelemetryRepository
    from admin.db.repositories.users import UserRepository

    service = await AuthService.create()
    repo = TelemetryRepository(service._db)
    users = UserRepository(service._db)
    user_id = None
    try:
        user_id = await users.create_user(
            file_id="telemetry-admin-user",
            name="Telemetry Admin",
            email="telemetry-admin@test.com",
        )
        await repo.insert(_telemetry(user_id=user_id, user_query="Admin list query"))
        rows = await repo.list_for_admin(limit=5, user_id=user_id)
        assert rows
        assert "user_query" in rows[0].keys()
        assert "orchestration_log" not in rows[0].keys()
    finally:
        if user_id:
            await users.soft_delete(user_id)
        await close_admin_db()
