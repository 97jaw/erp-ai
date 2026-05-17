from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from admin.api.schemas import (
    CreateDepartmentBody,
    CreateFeatureFlagBody,
    CreateRoleBody,
    CreateUserBody,
    DepartmentUserBody,
    UpdateDepartmentBody,
    UpdateFeatureFlagBody,
    UpdateRoleBody,
    UpdateUserBody,
)
from admin.auth.dependencies import get_current_user
from admin.auth.principal import CurrentUser
from admin.auth.service import get_auth_service
from admin.db.repositories.audit import AuditRepository
from admin.db.repositories.departments import DepartmentRepository
from admin.db.repositories.feature_flags import FeatureFlagRepository
from admin.db.repositories.roles import RoleRepository
from admin.db.repositories.sessions import SessionRepository
from admin.db.repositories.users import UserRepository
from admin.rbac.checks import require_permission

management_router = APIRouter(tags=["admin-management"])


async def _audit(
    actor: CurrentUser,
    action: str,
    *,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    service = await get_auth_service()
    if service:
        await service._audit.log(
            user_id=actor.id,
            event_type="admin",
            event_action=action,
            status="success",
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
        )


# --- Users CRUD ---


@management_router.post(
    "/admin/users",
    dependencies=[Depends(require_permission("admin.users.create"))],
)
async def create_user(
    body: CreateUserBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    if await service._users.get_by_file_id(body.file_id.strip()):
        raise HTTPException(status_code=409, detail="File ID already exists")
    user_id = await service._users.create_user(
        file_id=body.file_id.strip(),
        name=body.name.strip(),
        email=body.email,
        language=body.language,
        role_name=body.role_name,
        department_code=body.department_code,
    )
    await _audit(actor, "user.created", resource_type="user", resource_id=str(user_id))
    return {"user_id": user_id, "file_id": body.file_id}


@management_router.patch(
    "/admin/users/{user_id}",
    dependencies=[Depends(require_permission("admin.users.edit"))],
)
async def update_user(
    user_id: int,
    body: UpdateUserBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.update_user(user_id, **body.model_dump(exclude_unset=True)):
        raise HTTPException(status_code=404, detail="User not found")
    await _audit(actor, "user.updated", resource_type="user", resource_id=str(user_id))
    return {"status": "updated"}


@management_router.delete(
    "/admin/users/{user_id}",
    dependencies=[Depends(require_permission("admin.users.delete"))],
)
async def delete_user(
    user_id: int,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if user_id == actor.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    if not await service._users.soft_delete(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    await service._sessions.revoke_all_for_user(user_id, reason="user_deleted")
    await _audit(actor, "user.deleted", resource_type="user", resource_id=str(user_id))
    return {"status": "deleted"}


@management_router.post(
    "/admin/users/{user_id}/activate",
    dependencies=[Depends(require_permission("admin.users.edit"))],
)
async def activate_user(user_id: int, actor: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.set_active(user_id, active=True):
        raise HTTPException(status_code=404, detail="User not found")
    await _audit(actor, "user.activated", resource_type="user", resource_id=str(user_id))
    return {"status": "activated"}


@management_router.post(
    "/admin/users/{user_id}/deactivate",
    dependencies=[Depends(require_permission("admin.users.edit"))],
)
async def deactivate_user(user_id: int, actor: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.set_active(user_id, active=False):
        raise HTTPException(status_code=404, detail="User not found")
    await service._sessions.revoke_all_for_user(user_id, reason="deactivated")
    await _audit(actor, "user.deactivated", resource_type="user", resource_id=str(user_id))
    return {"status": "deactivated"}


@management_router.post(
    "/admin/users/{user_id}/unlock",
    dependencies=[Depends(require_permission("admin.users.edit"))],
)
async def unlock_user(user_id: int, actor: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.unlock(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    await _audit(actor, "user.unlocked", resource_type="user", resource_id=str(user_id))
    return {"status": "unlocked"}


@management_router.post(
    "/admin/users/{user_id}/reset_mfa",
    dependencies=[Depends(require_permission("admin.users.edit"))],
)
async def reset_user_mfa(user_id: int, actor: CurrentUser = Depends(get_current_user)) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.reset_mfa(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    await _audit(actor, "user.mfa_reset", resource_type="user", resource_id=str(user_id))
    return {"status": "mfa_reset"}


@management_router.get(
    "/admin/users/{user_id}/sessions",
    dependencies=[Depends(require_permission("admin.users.view"))],
)
async def list_user_sessions(user_id: int) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.get_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    sessions = SessionRepository(service._db)
    rows = await sessions.list_for_user(user_id)
    return {
        "sessions": [
            {
                "id": str(r["id"]),
                "ip_address": r["ip_address"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                "expires_at": r["expires_at"].isoformat() if r["expires_at"] else None,
                "revoked_at": r["revoked_at"].isoformat() if r["revoked_at"] else None,
            }
            for r in rows
        ]
    }


@management_router.delete(
    "/admin/users/{user_id}/sessions",
    dependencies=[Depends(require_permission("admin.users.edit"))],
)
async def revoke_user_sessions(
    user_id: int,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.get_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    count = await service._sessions.revoke_all_for_user(user_id, reason="admin_revoke_all")
    await _audit(actor, "user.sessions_revoked", resource_type="user", resource_id=str(user_id))
    return {"status": "revoked", "count": count}


@management_router.get(
    "/admin/users/{user_id}/audit",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def user_audit_trail(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.get_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    audit = AuditRepository(service._db)
    rows = await audit.list_events(user_id=user_id, limit=min(limit, 100), offset=offset)
    return {"events": [_audit_row(r) for r in rows], "limit": limit, "offset": offset}


# --- Roles CRUD ---


@management_router.post(
    "/admin/roles",
    dependencies=[Depends(require_permission("admin.roles.manage"))],
)
async def create_role(
    body: CreateRoleBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    role_id = await service._roles.create_role(
        name=body.name.strip(),
        display_name=body.display_name,
        display_name_ar=body.display_name_ar,
        description=body.description,
        level=body.level,
    )
    await _audit(actor, "role.created", resource_type="role", resource_id=str(role_id))
    return {"role_id": role_id, "name": body.name}


@management_router.patch(
    "/admin/roles/{role_id}",
    dependencies=[Depends(require_permission("admin.roles.manage"))],
)
async def update_role(
    role_id: int,
    body: UpdateRoleBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._roles.update_role(role_id, **body.model_dump(exclude_unset=True)):
        raise HTTPException(status_code=404, detail="Role not found")
    await _audit(actor, "role.updated", resource_type="role", resource_id=str(role_id))
    return {"status": "updated"}


@management_router.delete(
    "/admin/roles/{role_id}",
    dependencies=[Depends(require_permission("admin.roles.manage"))],
)
async def delete_role(
    role_id: int,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._roles.delete_role(role_id):
        raise HTTPException(status_code=400, detail="Cannot delete system role or role not found")
    await _audit(actor, "role.deleted", resource_type="role", resource_id=str(role_id))
    return {"status": "deleted"}


# --- Departments CRUD ---


@management_router.post(
    "/admin/departments",
    dependencies=[Depends(require_permission("admin.settings.manage"))],
)
async def create_department(
    body: CreateDepartmentBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    repo = DepartmentRepository(service._db)
    if await repo.get_by_code(body.code.upper()):
        raise HTTPException(status_code=409, detail="Department code already exists")
    dept_id = await repo.create(
        code=body.code.upper(),
        name=body.name,
        name_arabic=body.name_arabic,
        parent_id=body.parent_id,
        description=body.description,
    )
    await _audit(actor, "department.created", resource_type="department", resource_id=str(dept_id))
    return {"department_id": dept_id, "code": body.code.upper()}


@management_router.patch(
    "/admin/departments/{department_id}",
    dependencies=[Depends(require_permission("admin.settings.manage"))],
)
async def update_department(
    department_id: int,
    body: UpdateDepartmentBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    repo = DepartmentRepository(service._db)
    if not await repo.update(department_id, **body.model_dump(exclude_unset=True)):
        raise HTTPException(status_code=404, detail="Department not found")
    await _audit(actor, "department.updated", resource_type="department", resource_id=str(department_id))
    return {"status": "updated"}


@management_router.delete(
    "/admin/departments/{department_id}",
    dependencies=[Depends(require_permission("admin.settings.manage"))],
)
async def delete_department(
    department_id: int,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    repo = DepartmentRepository(service._db)
    if not await repo.delete(department_id):
        raise HTTPException(status_code=404, detail="Department not found")
    await _audit(actor, "department.deleted", resource_type="department", resource_id=str(department_id))
    return {"status": "deactivated"}


@management_router.get(
    "/admin/departments/{department_id}/users",
    dependencies=[Depends(require_permission("admin.users.view"))],
)
async def department_users(department_id: int) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    repo = DepartmentRepository(service._db)
    if not await repo.get_by_id(department_id):
        raise HTTPException(status_code=404, detail="Department not found")
    rows = await repo.users_in_department(department_id)
    return {"users": [dict(r) for r in rows]}


@management_router.post(
    "/admin/departments/{department_id}/users",
    dependencies=[Depends(require_permission("admin.users.edit"))],
)
async def add_department_user(
    department_id: int,
    body: DepartmentUserBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    repo = DepartmentRepository(service._db)
    if not await repo.get_by_id(department_id):
        raise HTTPException(status_code=404, detail="Department not found")
    if not await service._users.get_by_id(body.user_id):
        raise HTTPException(status_code=404, detail="User not found")
    await repo.add_user(department_id, body.user_id, is_primary=body.is_primary)
    await _audit(
        actor,
        "department.user_added",
        resource_type="department",
        resource_id=str(department_id),
        metadata={"user_id": body.user_id},
    )
    return {"status": "added"}


# --- Feature flags ---


@management_router.get(
    "/admin/feature-flags",
    dependencies=[Depends(require_permission("admin.feature_flags.manage"))],
)
async def list_feature_flags() -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    repo = FeatureFlagRepository(service._db)
    rows = await repo.list_all()
    return {"feature_flags": [_flag_row(r) for r in rows]}


@management_router.post(
    "/admin/feature-flags",
    dependencies=[Depends(require_permission("admin.feature_flags.manage"))],
)
async def create_feature_flag(
    body: CreateFeatureFlagBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    repo = FeatureFlagRepository(service._db)
    if await repo.get_by_code(body.code):
        raise HTTPException(status_code=409, detail="Feature flag code already exists")
    flag_id = await repo.create(
        code=body.code,
        name=body.name,
        description=body.description,
        is_enabled=body.is_enabled,
        rollout_percent=body.rollout_percent,
    )
    await _audit(actor, "feature_flag.created", resource_type="feature_flag", resource_id=str(flag_id))
    return {"id": flag_id, "code": body.code}


@management_router.patch(
    "/admin/feature-flags/{flag_id}",
    dependencies=[Depends(require_permission("admin.feature_flags.manage"))],
)
async def update_feature_flag(
    flag_id: int,
    body: UpdateFeatureFlagBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    repo = FeatureFlagRepository(service._db)
    if not await repo.update(flag_id, **body.model_dump(exclude_unset=True)):
        raise HTTPException(status_code=404, detail="Feature flag not found")
    await _audit(actor, "feature_flag.updated", resource_type="feature_flag", resource_id=str(flag_id))
    return {"status": "updated"}


@management_router.delete(
    "/admin/feature-flags/{flag_id}",
    dependencies=[Depends(require_permission("admin.feature_flags.manage"))],
)
async def delete_feature_flag(
    flag_id: int,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    repo = FeatureFlagRepository(service._db)
    if not await repo.delete(flag_id):
        raise HTTPException(status_code=404, detail="Feature flag not found")
    await _audit(actor, "feature_flag.deleted", resource_type="feature_flag", resource_id=str(flag_id))
    return {"status": "deleted"}


@management_router.post(
    "/admin/feature-flags/{flag_id}/enable_for_role/{role_id}",
    dependencies=[Depends(require_permission("admin.feature_flags.manage"))],
)
async def enable_flag_for_role(flag_id: int, role_id: int) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    repo = FeatureFlagRepository(service._db)
    if not await repo.get_by_id(flag_id):
        raise HTTPException(status_code=404, detail="Feature flag not found")
    if not await service._roles.get_by_id(role_id):
        raise HTTPException(status_code=404, detail="Role not found")
    await repo.enable_for_role(flag_id, role_id)
    return {"status": "enabled"}


@management_router.post(
    "/admin/feature-flags/{flag_id}/enable_for_user/{target_user_id}",
    dependencies=[Depends(require_permission("admin.feature_flags.manage"))],
)
async def enable_flag_for_user(flag_id: int, target_user_id: int) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    repo = FeatureFlagRepository(service._db)
    if not await repo.get_by_id(flag_id):
        raise HTTPException(status_code=404, detail="Feature flag not found")
    if not await service._users.get_by_id(target_user_id):
        raise HTTPException(status_code=404, detail="User not found")
    await repo.enable_for_user(flag_id, target_user_id)
    return {"status": "enabled"}


# --- Audit logs ---


@management_router.get(
    "/admin/audit",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def list_audit_logs(
    user_id: int | None = None,
    event_type: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    from datetime import date as date_cls, datetime, timedelta

    df = datetime.combine(date_cls.fromisoformat(date_from), datetime.min.time()) if date_from else None
    dt = (
        datetime.combine(date_cls.fromisoformat(date_to) + timedelta(days=1), datetime.min.time())
        if date_to
        else None
    )
    service = await get_auth_service()
    assert service is not None
    audit = AuditRepository(service._db)
    rows = await audit.list_events(
        user_id=user_id,
        event_type=event_type,
        status=status,
        date_from=df,
        date_to=dt,
        limit=min(limit, 100),
        offset=offset,
    )
    return {"events": [_audit_row(r) for r in rows], "limit": limit, "offset": offset}


@management_router.get(
    "/admin/audit/{event_id}",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def get_audit_event(event_id: int) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    audit = AuditRepository(service._db)
    row = await audit.get_event(event_id)
    if not row:
        raise HTTPException(status_code=404, detail="Audit event not found")
    return {"event": dict(row)}


def _audit_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "event_type": row["event_type"],
        "event_action": row["event_action"],
        "resource_type": row.get("resource_type"),
        "resource_id": row.get("resource_id"),
        "status": row["status"],
        "ip_address": row.get("ip_address"),
        "created_at": row["created_at"].isoformat() if row.get("created_at") else None,
        "metadata": row.get("metadata"),
    }


def _flag_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "description": row["description"],
        "is_enabled": row["is_enabled"],
        "rollout_percent": row["rollout_percent"],
        "enabled_roles": row["enabled_roles"] or [],
        "enabled_users": row["enabled_users"] or [],
    }
