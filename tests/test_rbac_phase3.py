from __future__ import annotations

import os

import pytest

requires_rbac = pytest.mark.skipif(
    not os.environ.get("OOA_DB_URL") or not os.environ.get("JWT_SECRET"),
    reason="OOA_DB_URL and JWT_SECRET required",
)


def test_permission_for_tool_mapping() -> None:
    from admin.rbac.tool_permissions import permission_for_tool

    assert permission_for_tool("query_accounting", {"report_type": "pandl"}) == "reports.pandl.view"
    assert permission_for_tool("generate_pdf_report") == "features.pdf_generation"


def test_apply_data_scope_department() -> None:
    from admin.auth.principal import CurrentUser
    from admin.rbac.data_scope import apply_data_scope

    user = CurrentUser(
        id=2,
        file_id="u2",
        name="Dept User",
        language="en",
        is_super_admin=False,
        is_active=True,
        permissions=frozenset({"data.own_department_only", "reports.pandl.view"}),
        department_ids=(3,),
        department_codes=("FIN",),
    )
    scoped = apply_data_scope({"report_type": "pandl"}, user)
    assert scoped["department_ids"] == [3]
    assert scoped.get("_rbac_department_scoped") is True


def test_check_tool_allowed_denied() -> None:
    from admin.auth.principal import CurrentUser
    from admin.rbac.tool_permissions import check_tool_allowed

    guest = CurrentUser(
        id=3,
        file_id="guest1",
        name="Guest",
        language="en",
        is_super_admin=False,
        is_active=True,
        permissions=frozenset(),
    )
    err = check_tool_allowed(guest, "query_accounting", {"report_type": "pandl"})
    assert err and "reports.pandl.view" in err


@pytest.mark.asyncio
@requires_rbac
async def test_super_admin_auth_me() -> None:
    from admin.auth.jwt_tokens import create_access_token, hash_token
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db

    service = await AuthService.create()
    try:
        login = await service.login("2721")
        user = await service.resolve_current_user(login["access_token"])
        assert user.has_permission("admin.users.view")
        assert user.has_role("super_admin")
    finally:
        await close_admin_db()


@pytest.mark.asyncio
@requires_rbac
async def test_guest_user_lacks_admin_permission() -> None:
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.users import UserRepository

    service = await AuthService.create()
    try:
        uid = await service._users.provision_user(
            file_id="rbac-guest-test-001",
            name="RBAC Guest Test",
            role_name="guest",
        )
        user = await service.build_current_user(uid)
        assert not user.has_permission("admin.users.view")
        assert user.has_role("guest")
    finally:
        await close_admin_db()
