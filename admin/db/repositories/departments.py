from __future__ import annotations

import asyncpg

from admin.db.connection import AdminDatabase


class DepartmentRepository:
    def __init__(self, db: AdminDatabase) -> None:
        self._db = db

    async def list_departments(self) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT id, code, name, name_arabic, parent_id, is_active
            FROM departments
            WHERE is_active = TRUE
            ORDER BY code
            """
        )

    async def get_by_id(self, department_id: int) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            "SELECT * FROM departments WHERE id = $1",
            department_id,
        )

    async def get_by_code(self, code: str) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            "SELECT * FROM departments WHERE code = $1",
            code,
        )

    async def create(
        self,
        *,
        code: str,
        name: str,
        name_arabic: str | None = None,
        parent_id: int | None = None,
        description: str | None = None,
    ) -> int:
        return int(
            await self._db.fetchval(
                """
                INSERT INTO departments (code, name, name_arabic, parent_id, description)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                code,
                name,
                name_arabic,
                parent_id,
                description,
            )
        )

    async def update(
        self,
        department_id: int,
        *,
        name: str | None = None,
        name_arabic: str | None = None,
        parent_id: int | None = None,
        description: str | None = None,
        is_active: bool | None = None,
    ) -> bool:
        if not await self.get_by_id(department_id):
            return False
        await self._db.execute(
            """
            UPDATE departments
            SET name = COALESCE($2, name),
                name_arabic = COALESCE($3, name_arabic),
                parent_id = COALESCE($4, parent_id),
                description = COALESCE($5, description),
                is_active = COALESCE($6, is_active)
            WHERE id = $1
            """,
            department_id,
            name,
            name_arabic,
            parent_id,
            description,
            is_active,
        )
        return True

    async def delete(self, department_id: int) -> bool:
        result = await self._db.execute(
            "UPDATE departments SET is_active = FALSE WHERE id = $1",
            department_id,
        )
        return result.endswith("1")

    async def add_user(
        self,
        department_id: int,
        user_id: int,
        *,
        is_primary: bool = False,
    ) -> None:
        await self._db.execute(
            """
            INSERT INTO user_departments (user_id, department_id, is_primary)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, department_id)
            DO UPDATE SET is_primary = EXCLUDED.is_primary
            """,
            user_id,
            department_id,
            is_primary,
        )

    async def users_in_department(self, department_id: int) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT u.id, u.file_id, u.name, u.email, ud.is_primary
            FROM users u
            JOIN user_departments ud ON ud.user_id = u.id
            WHERE ud.department_id = $1 AND u.deleted_at IS NULL
            ORDER BY u.name
            """,
            department_id,
        )
