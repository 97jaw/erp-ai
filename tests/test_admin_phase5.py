from __future__ import annotations

import os

import pytest

requires_db = pytest.mark.skipif(
    not os.environ.get("OOA_DB_URL") or not os.environ.get("JWT_SECRET"),
    reason="OOA_DB_URL and JWT_SECRET required",
)


@pytest.mark.asyncio
@requires_db
async def test_create_user_and_department() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.departments import DepartmentRepository
    from admin.db.repositories.users import UserRepository

    service = await AuthService.create()
    users = UserRepository(service._db)
    depts = DepartmentRepository(service._db)

    user_id = None
    dept_id = None
    try:
        user_id = await users.create_user(
            file_id="phase5-test-user",
            name="Phase 5 Test",
            email="phase5@test.com",
            department_code="IT",
        )
        dept_id = await depts.create(
            code="TST",
            name="Test Dept",
        )
        await depts.add_user(dept_id, user_id, is_primary=False)
        row = await users.get_by_id(user_id)
        assert row is not None
        assert row["file_id"] == "phase5-test-user"
        await users.soft_delete(user_id)
        assert await users.get_by_id(user_id) is None
        user_id = None
    finally:
        if user_id:
            await users.soft_delete(user_id)
        if dept_id:
            await depts.delete(dept_id)
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_custom_role_crud() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.roles import RoleRepository

    service = await AuthService.create()
    roles = RoleRepository(service._db)
    role_id = await roles.create_role(
        name="phase5_custom",
        display_name="Phase 5 Custom",
        level=25,
    )
    try:
        assert await roles.get_by_id(role_id) is not None
        await roles.update_role(role_id, display_name="Updated Custom")
        assert await roles.delete_role(role_id)
        assert await roles.get_by_id(role_id) is None
        role_id = None
    finally:
        if role_id and await roles.get_by_id(role_id):
            await roles.delete_role(role_id)
        await close_admin_db()


@pytest.mark.asyncio
@requires_db
async def test_feature_flag_create() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.feature_flags import FeatureFlagRepository

    service = await AuthService.create()
    flags = FeatureFlagRepository(service._db)
    flag_id = await flags.create(code="phase5_flag_test", name="Phase 5 Flag")
    try:
        row = await flags.get_by_id(flag_id)
        assert row is not None
        await flags.update(flag_id, is_enabled=False)
        assert await flags.delete(flag_id)
        flag_id = None
    finally:
        if flag_id:
            await flags.delete(flag_id)
        await close_admin_db()
