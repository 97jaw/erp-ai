from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from admin.api.admin_management import management_router
from admin.api.usage_routes import usage_router
from admin.api.auth_security import auth_security_router
from admin.api.metrics_routes import metrics_router
from admin.api.telemetry_routes import telemetry_router
from admin.api.schemas import AssignRoleBody, GrantPermissionBody
from admin.auth.dependencies import get_current_user
from admin.auth.principal import CurrentUser
from admin.auth.service import get_auth_service
from admin.db.repositories.conversations import ConversationRepository
from admin.db.repositories.departments import DepartmentRepository
from admin.db.repositories.roles import RoleRepository
from admin.db.repositories.users import UserRepository
from admin.rbac.checks import require_any_permission, require_permission

admin_router = APIRouter(tags=["admin"])
admin_router.include_router(auth_security_router)
admin_router.include_router(management_router)
admin_router.include_router(usage_router)
admin_router.include_router(metrics_router)
admin_router.include_router(telemetry_router)


@admin_router.get("/auth/me")
async def auth_me(user: CurrentUser = Depends(get_current_user)) -> dict[str, Any]:
    return user.to_dict()


@admin_router.post(
    "/admin/permissions/sync",
    dependencies=[Depends(require_permission("admin.settings.manage"))],
)
async def sync_role_permission_matrix() -> dict[str, Any]:
    """Re-apply super_admin / admin Odoo grants after new permissions are added."""
    service = await get_auth_service()
    assert service is not None
    db = service._db
    await db.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r CROSS JOIN permissions p
        WHERE r.name = 'super_admin'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    await db.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id FROM roles r
        JOIN permissions p ON p.category = 'odoo' OR p.code = 'admin.roles.manage'
        WHERE r.name = 'admin'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    total = await db.fetchval("SELECT COUNT(*) FROM permissions")
    super_count = await db.fetchval(
        """
        SELECT COUNT(*) FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id WHERE r.name = 'super_admin'
        """
    )
    admin_count = await db.fetchval(
        """
        SELECT COUNT(*) FROM role_permissions rp
        JOIN roles r ON r.id = rp.role_id WHERE r.name = 'admin'
        """
    )
    return {
        "status": "synced",
        "permissions_total": int(total or 0),
        "super_admin_grants": int(super_count or 0),
        "admin_grants": int(admin_count or 0),
    }


@admin_router.get(
    "/admin/permissions",
    dependencies=[Depends(require_permission("admin.users.view"))],
)
async def list_permissions() -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    rows = await service._roles.list_permissions()
    return {
        "permissions": [
            {
                "id": r["id"],
                "code": r["code"],
                "category": r["category"],
                "display_name": r["display_name"],
            }
            for r in rows
        ]
    }


@admin_router.get(
    "/admin/roles",
    dependencies=[
        Depends(require_any_permission("admin.roles.manage", "admin.users.view")),
    ],
)
async def list_roles() -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    rows = await service._roles.list_roles()
    return {
        "roles": [
            {
                "id": r["id"],
                "name": r["name"],
                "display_name": r["display_name"],
                "level": r["level"],
                "is_system": r["is_system"],
            }
            for r in rows
        ]
    }


@admin_router.get(
    "/admin/roles/{role_id}/permissions",
    dependencies=[
        Depends(require_any_permission("admin.roles.manage", "admin.users.view")),
    ],
)
async def get_role_permissions(role_id: int) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    role = await service._roles.get_by_id(role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    perms = await service._roles.role_permissions(role_id)
    return {
        "role_id": role_id,
        "role_name": role["name"],
        "permissions": [{"id": p["id"], "code": p["code"]} for p in perms],
    }


@admin_router.post(
    "/admin/roles/{role_id}/permissions",
    dependencies=[Depends(require_permission("admin.roles.manage"))],
)
async def grant_role_permission(
    role_id: int,
    body: GrantPermissionBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._roles.get_by_id(role_id):
        raise HTTPException(status_code=404, detail="Role not found")
    await service._roles.grant_permission(
        role_id,
        body.permission_id,
        granted_by=actor.id,
    )
    await service._audit.log(
        user_id=actor.id,
        event_type="admin",
        event_action="role.permission.granted",
        status="success",
        resource_type="role",
        resource_id=str(role_id),
        metadata={"permission_id": body.permission_id},
    )
    return {"status": "granted"}


@admin_router.delete(
    "/admin/roles/{role_id}/permissions/{permission_id}",
    dependencies=[Depends(require_permission("admin.roles.manage"))],
)
async def revoke_role_permission(
    role_id: int,
    permission_id: int,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    removed = await service._roles.revoke_permission(role_id, permission_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Permission not assigned to role")
    await service._audit.log(
        user_id=actor.id,
        event_type="admin",
        event_action="role.permission.revoked",
        status="success",
        resource_type="role",
        resource_id=str(role_id),
        metadata={"permission_id": permission_id},
    )
    return {"status": "revoked"}


@admin_router.get(
    "/admin/users",
    dependencies=[Depends(require_permission("admin.users.view"))],
)
async def list_users(
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    rows = await service._users.list_users(limit=limit, offset=offset, search=search)
    return {
        "users": [dict(r) for r in rows],
        "limit": limit,
        "offset": offset,
    }


@admin_router.get(
    "/admin/users/{user_id}",
    dependencies=[Depends(require_permission("admin.users.view"))],
)
async def get_user(user_id: int) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    user = await service.build_current_user(user_id)
    return user.to_dict()


@admin_router.post(
    "/admin/users/{user_id}/roles",
    dependencies=[Depends(require_permission("admin.users.edit"))],
)
async def assign_user_role(
    user_id: int,
    body: AssignRoleBody,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.get_by_id(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    if not await service._roles.get_by_id(body.role_id):
        raise HTTPException(status_code=404, detail="Role not found")
    await service._users.assign_role(user_id, body.role_id, granted_by=actor.id)
    await service._audit.log(
        user_id=actor.id,
        event_type="admin",
        event_action="role.assigned",
        status="success",
        resource_type="user",
        resource_id=str(user_id),
        metadata={"role_id": body.role_id},
    )
    return {"status": "assigned"}


@admin_router.delete(
    "/admin/users/{user_id}/roles/{role_id}",
    dependencies=[Depends(require_permission("admin.users.edit"))],
)
async def remove_user_role(
    user_id: int,
    role_id: int,
    actor: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    if not await service._users.remove_role(user_id, role_id):
        raise HTTPException(status_code=404, detail="Role not assigned to user")
    await service._audit.log(
        user_id=actor.id,
        event_type="admin",
        event_action="role.removed",
        status="success",
        resource_type="user",
        resource_id=str(user_id),
        metadata={"role_id": role_id},
    )
    return {"status": "removed"}


@admin_router.get(
    "/admin/departments",
    dependencies=[Depends(require_permission("admin.users.view"))],
)
async def list_departments() -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    db = service._db
    repo = DepartmentRepository(db)
    rows = await repo.list_departments()
    return {"departments": [dict(r) for r in rows]}


@admin_router.get("/conversations")
async def list_my_conversations(
    user: CurrentUser = Depends(get_current_user),
    search: str | None = None,
    include_archived: bool = False,
    limit: int = 30,
    offset: int = 0,
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    repo = ConversationRepository(service._db)
    rows = await repo.list_for_user(
        user.id,
        search=search,
        include_archived=include_archived,
        limit=min(limit, 100),
        offset=offset,
    )
    return {
        "conversations": [
            {
                "id": str(r["id"]),
                "title": r["title"],
                "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                "last_message_at": r["last_message_at"].isoformat() if r["last_message_at"] else None,
                "message_count": r["message_count"],
                "is_pinned": r["is_pinned"],
                "is_archived": r["is_archived"],
                "external_session_key": r.get("external_session_key"),
            }
            for r in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@admin_router.get("/conversations/{conversation_id}")
async def get_conversation_detail(
    conversation_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    message_limit: int = 50,
    message_offset: int = 0,
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    repo = ConversationRepository(service._db)
    conv = await repo.get_conversation(user.id, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    messages = await repo.get_recent_messages(
        conversation_id,
        limit=min(message_limit, 100),
        offset=message_offset,
    )
    return {
        "conversation": {
            "id": str(conv["id"]),
            "title": conv["title"],
            "message_count": conv["message_count"],
            "started_at": conv["started_at"].isoformat() if conv["started_at"] else None,
            "last_message_at": conv["last_message_at"].isoformat() if conv["last_message_at"] else None,
            "external_session_key": conv.get("external_session_key"),
        },
        "messages": [
            {
                "id": str(m["id"]),
                "role": m["role"],
                "content": m["content"],
                "language": m["language"],
                "visualization": m["visualization"],
                "suggestions": m["suggestions"],
                "created_at": m["created_at"].isoformat() if m["created_at"] else None,
            }
            for m in reversed(messages)
        ],
    }


@admin_router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: UUID,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    repo = ConversationRepository(service._db)
    if not await repo.delete_conversation(user.id, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted"}


@admin_router.post("/conversations/{conversation_id}/archive")
async def archive_conversation(
    conversation_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    archived: bool = True,
) -> dict[str, str]:
    service = await get_auth_service()
    assert service is not None
    repo = ConversationRepository(service._db)
    if not await repo.set_archived(user.id, conversation_id, archived=archived):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "archived" if archived else "restored"}
