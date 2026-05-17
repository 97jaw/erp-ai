from __future__ import annotations

import os

import pytest

requires_db = pytest.mark.skipif(
    not os.environ.get("OOA_DB_URL"),
    reason="OOA_DB_URL not set — skip admin DB integration tests",
)


@pytest.mark.asyncio
@requires_db
async def test_health_and_seed_counts() -> None:
    from admin.db.connection import close_admin_db, init_admin_db
    from admin.db.repositories.users import UserRepository

    db = await init_admin_db()
    try:
        assert await db.health_check() is True
        repo = UserRepository(db)
        counts = await repo.count_seed_data()
        assert counts["roles"] >= 7
        assert counts["permissions"] >= 30
        assert counts["departments"] >= 8
    finally:
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_create_super_admin_idempotent() -> None:
    from admin.db.connection import close_admin_db, init_admin_db
    from admin.db.repositories.users import UserRepository

    file_id = "test-super-admin-99999"
    db = await init_admin_db()
    try:
        repo = UserRepository(db)
        first = await repo.create_super_admin(
            file_id=file_id,
            name="Test Super Admin",
            email="test-super@example.com",
        )
        second = await repo.create_super_admin(
            file_id=file_id,
            name="Test Super Admin",
            email="test-super@example.com",
        )
        assert first["user_id"] == second["user_id"]
        perms = await repo.super_admin_permission_count(file_id)
        assert perms >= 30
    finally:
        await close_admin_db()


def test_split_sql_statements() -> None:
    from admin.db.connection import _split_sql_statements

    sql = "SELECT 1;\n\n-- comment\nSELECT 2;"
    statements = _split_sql_statements(sql)
    assert len(statements) == 2
