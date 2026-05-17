from __future__ import annotations

import asyncpg

from admin.db.connection import AdminDatabase


class RoleRepository:
    def __init__(self, db: AdminDatabase) -> None:
        self._db = db

    async def list_roles(self) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT id, name, display_name, level, is_system
            FROM roles
            ORDER BY level DESC
            """
        )

    async def get_by_id(self, role_id: int) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            "SELECT * FROM roles WHERE id = $1",
            role_id,
        )

    async def list_permissions(self) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT id, code, category, display_name, description
            FROM permissions
            ORDER BY category, code
            """
        )

    async def role_permissions(self, role_id: int) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT p.id, p.code, p.category, p.display_name
            FROM permissions p
            JOIN role_permissions rp ON rp.permission_id = p.id
            WHERE rp.role_id = $1
            ORDER BY p.code
            """,
            role_id,
        )

    async def grant_permission(
        self,
        role_id: int,
        permission_id: int,
        *,
        granted_by: int | None = None,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO role_permissions (role_id, permission_id, granted_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """,
            role_id,
            permission_id,
            granted_by,
        )

    async def revoke_permission(self, role_id: int, permission_id: int) -> bool:
        result = await self._db.execute(
            """
            DELETE FROM role_permissions
            WHERE role_id = $1 AND permission_id = $2
            """,
            role_id,
            permission_id,
        )
        return result.endswith("1")

    async def create_role(
        self,
        *,
        name: str,
        display_name: str,
        level: int,
        description: str | None = None,
        display_name_ar: str | None = None,
    ) -> int:
        return int(
            await self._db.fetchval(
                """
                INSERT INTO roles (name, display_name, display_name_ar, description, level, is_system)
                VALUES ($1, $2, $3, $4, $5, FALSE)
                RETURNING id
                """,
                name,
                display_name,
                display_name_ar,
                description,
                level,
            )
        )

    async def update_role(
        self,
        role_id: int,
        *,
        display_name: str | None = None,
        display_name_ar: str | None = None,
        description: str | None = None,
        level: int | None = None,
    ) -> bool:
        if not await self.get_by_id(role_id):
            return False
        await self._db.execute(
            """
            UPDATE roles
            SET display_name = COALESCE($2, display_name),
                display_name_ar = COALESCE($3, display_name_ar),
                description = COALESCE($4, description),
                level = COALESCE($5, level)
            WHERE id = $1
            """,
            role_id,
            display_name,
            display_name_ar,
            description,
            level,
        )
        return True

    async def delete_role(self, role_id: int) -> bool:
        role = await self.get_by_id(role_id)
        if not role or role["is_system"]:
            return False
        result = await self._db.execute(
            "DELETE FROM roles WHERE id = $1 AND is_system = FALSE",
            role_id,
        )
        return result.endswith("1")
