from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import asyncpg

from admin.db.connection import AdminDatabase


class UserRepository:
    def __init__(self, db: AdminDatabase) -> None:
        self._db = db

    async def get_by_file_id(self, file_id: str) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT *
            FROM users
            WHERE file_id = $1 AND deleted_at IS NULL
            """,
            file_id,
        )

    async def get_by_id(self, user_id: int) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT *
            FROM users
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
        )

    async def set_odoo_user_id(self, user_id: int, odoo_user_id: int | None) -> None:
        await self._db.execute(
            """
            UPDATE users
            SET odoo_user_id = $2, updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
            odoo_user_id,
        )

    async def set_odoo_identity(
        self,
        user_id: int,
        *,
        odoo_user_id: int | None = None,
        odoo_employee_id: int | None = None,
        odoo_verified_at: datetime | None = None,
        odoo_identity_json: dict[str, Any] | None = None,
        language: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            UPDATE users
            SET odoo_user_id = COALESCE($2, odoo_user_id),
                odoo_employee_id = COALESCE($3, odoo_employee_id),
                odoo_verified_at = COALESCE($4, odoo_verified_at),
                odoo_identity_json = COALESCE($5::jsonb, odoo_identity_json),
                language = COALESCE($6, language),
                updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
            odoo_user_id,
            odoo_employee_id,
            odoo_verified_at,
            json.dumps(odoo_identity_json) if odoo_identity_json is not None else None,
            language,
        )

    async def create_super_admin(
        self,
        *,
        file_id: str,
        name: str,
        email: str | None = None,
        department_code: str = "IT",
    ) -> dict[str, Any]:
        async with self._db.transaction() as conn:
            user_id = await conn.fetchval(
                """
                INSERT INTO users (file_id, email, name, language, is_active, is_super_admin)
                VALUES ($1, $2, $3, 'en', TRUE, TRUE)
                ON CONFLICT (file_id) DO UPDATE
                SET name = EXCLUDED.name,
                    email = COALESCE(EXCLUDED.email, users.email),
                    is_active = TRUE,
                    is_super_admin = TRUE,
                    updated_at = NOW(),
                    deleted_at = NULL
                RETURNING id
                """,
                file_id,
                email,
                name,
            )
            role_id = await conn.fetchval(
                "SELECT id FROM roles WHERE name = $1",
                "super_admin",
            )
            if role_id:
                await conn.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id, role_id) DO NOTHING
                    """,
                    user_id,
                    role_id,
                )
            dept_id = await conn.fetchval(
                "SELECT id FROM departments WHERE code = $1",
                department_code,
            )
            if dept_id:
                await conn.execute(
                    """
                    INSERT INTO user_departments (user_id, department_id, is_primary)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (user_id, department_id)
                    DO UPDATE SET is_primary = TRUE
                    """,
                    user_id,
                    dept_id,
                )
            return {"user_id": user_id, "file_id": file_id, "role": "super_admin"}

    async def count_seed_data(self) -> dict[str, int]:
        return {
            "users": int(await self._db.fetchval("SELECT COUNT(*) FROM users") or 0),
            "roles": int(await self._db.fetchval("SELECT COUNT(*) FROM roles") or 0),
            "permissions": int(
                await self._db.fetchval("SELECT COUNT(*) FROM permissions") or 0
            ),
            "role_permissions": int(
                await self._db.fetchval("SELECT COUNT(*) FROM role_permissions") or 0
            ),
            "departments": int(
                await self._db.fetchval("SELECT COUNT(*) FROM departments") or 0
            ),
        }

    async def get_permissions(self, user_id: int) -> list[str]:
        rows = await self._db.fetch(
            """
            SELECT DISTINCT p.code
            FROM permissions p
            JOIN role_permissions rp ON rp.permission_id = p.id
            JOIN user_roles ur ON ur.role_id = rp.role_id
            WHERE ur.user_id = $1
              AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
            ORDER BY p.code
            """,
            user_id,
        )
        return [row["code"] for row in rows]

    async def get_roles(self, user_id: int) -> list[str]:
        rows = await self._db.fetch(
            """
            SELECT r.name
            FROM roles r
            JOIN user_roles ur ON ur.role_id = r.id
            WHERE ur.user_id = $1
              AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
            ORDER BY r.level DESC
            """,
            user_id,
        )
        return [row["name"] for row in rows]

    async def get_department_ids(self, user_id: int) -> list[int]:
        rows = await self._db.fetch(
            """
            SELECT department_id
            FROM user_departments
            WHERE user_id = $1
            ORDER BY is_primary DESC, department_id
            """,
            user_id,
        )
        return [int(row["department_id"]) for row in rows]

    async def get_department_codes(self, user_id: int) -> list[str]:
        rows = await self._db.fetch(
            """
            SELECT d.code
            FROM departments d
            JOIN user_departments ud ON ud.department_id = d.id
            WHERE ud.user_id = $1
            ORDER BY ud.is_primary DESC, d.code
            """,
            user_id,
        )
        return [row["code"] for row in rows]

    async def provision_user(
        self,
        *,
        file_id: str,
        name: str,
        email: str | None = None,
        odoo_user_id: int | None = None,
        language: str = "en",
        role_name: str = "user",
    ) -> int:
        async with self._db.transaction() as conn:
            user_id = await conn.fetchval(
                """
                INSERT INTO users (file_id, email, name, language, odoo_user_id, is_active)
                VALUES ($1, $2, $3, $4, $5, TRUE)
                ON CONFLICT (file_id) DO UPDATE
                SET name = EXCLUDED.name,
                    email = COALESCE(EXCLUDED.email, users.email),
                    odoo_user_id = COALESCE(EXCLUDED.odoo_user_id, users.odoo_user_id),
                    language = EXCLUDED.language,
                    is_active = TRUE,
                    updated_at = NOW(),
                    deleted_at = NULL
                RETURNING id
                """,
                file_id,
                email,
                name,
                language,
                odoo_user_id,
            )
            role_id = await conn.fetchval(
                "SELECT id FROM roles WHERE name = $1",
                role_name,
            )
            if role_id:
                await conn.execute(
                    """
                    INSERT INTO user_roles (user_id, role_id)
                    VALUES ($1, $2)
                    ON CONFLICT (user_id, role_id) DO NOTHING
                    """,
                    user_id,
                    role_id,
                )
            return int(user_id)

    async def update_last_login(self, user_id: int, ip_address: str | None) -> None:
        await self._db.execute(
            """
            UPDATE users
            SET last_login_at = NOW(),
                last_login_ip = $2,
                failed_attempts = 0,
                locked_until = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            user_id,
            ip_address,
        )

    async def record_failed_login(
        self,
        file_id: str,
        *,
        max_attempts: int,
        lockout_minutes: int,
    ) -> None:
        await self._db.execute(
            """
            UPDATE users
            SET failed_attempts = failed_attempts + 1,
                locked_until = CASE
                    WHEN failed_attempts + 1 >= $2
                    THEN NOW() + make_interval(mins => $3)
                    ELSE locked_until
                END,
                updated_at = NOW()
            WHERE file_id = $1 AND deleted_at IS NULL
            """,
            file_id,
            max_attempts,
            lockout_minutes,
        )

    async def list_users(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> list[asyncpg.Record]:
        if search:
            pattern = f"%{search}%"
            return await self._db.fetch(
                """
                SELECT id, file_id, email, name, language, is_active, is_super_admin,
                       last_login_at, created_at
                FROM users
                WHERE deleted_at IS NULL
                  AND (name ILIKE $1 OR file_id ILIKE $1 OR email ILIKE $1)
                ORDER BY name
                LIMIT $2 OFFSET $3
                """,
                pattern,
                limit,
                offset,
            )
        return await self._db.fetch(
            """
            SELECT id, file_id, email, name, language, is_active, is_super_admin,
                   last_login_at, created_at
            FROM users
            WHERE deleted_at IS NULL
            ORDER BY name
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )

    async def assign_role(self, user_id: int, role_id: int, *, granted_by: int | None = None) -> None:
        await self._db.execute(
            """
            INSERT INTO user_roles (user_id, role_id, granted_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (user_id, role_id) DO NOTHING
            """,
            user_id,
            role_id,
            granted_by,
        )

    async def remove_role(self, user_id: int, role_id: int) -> bool:
        result = await self._db.execute(
            "DELETE FROM user_roles WHERE user_id = $1 AND role_id = $2",
            user_id,
            role_id,
        )
        return result.endswith("1")

    async def create_user(
        self,
        *,
        file_id: str,
        name: str,
        email: str | None = None,
        language: str = "en",
        role_name: str = "user",
        department_code: str | None = None,
        is_super_admin: bool = False,
    ) -> int:
        user_id = await self.provision_user(
            file_id=file_id,
            name=name,
            email=email,
            language=language,
            role_name=role_name,
        )
        if is_super_admin:
            await self._db.execute(
                "UPDATE users SET is_super_admin = TRUE WHERE id = $1",
                user_id,
            )
        if department_code:
            dept_id = await self._db.fetchval(
                "SELECT id FROM departments WHERE code = $1",
                department_code,
            )
            if dept_id:
                await self._db.execute(
                    """
                    INSERT INTO user_departments (user_id, department_id, is_primary)
                    VALUES ($1, $2, TRUE)
                    ON CONFLICT (user_id, department_id) DO UPDATE SET is_primary = TRUE
                    """,
                    user_id,
                    dept_id,
                )
        return user_id

    async def update_user(
        self,
        user_id: int,
        *,
        name: str | None = None,
        email: str | None = None,
        language: str | None = None,
        name_arabic: str | None = None,
        phone: str | None = None,
        is_active: bool | None = None,
        is_super_admin: bool | None = None,
    ) -> bool:
        if not await self.get_by_id(user_id):
            return False
        await self._db.execute(
            """
            UPDATE users
            SET name = COALESCE($2, name),
                email = COALESCE($3, email),
                language = COALESCE($4, language),
                name_arabic = COALESCE($5, name_arabic),
                phone = COALESCE($6, phone),
                is_active = COALESCE($7, is_active),
                is_super_admin = COALESCE($8, is_super_admin),
                updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
            name,
            email,
            language,
            name_arabic,
            phone,
            is_active,
            is_super_admin,
        )
        return True

    async def soft_delete(self, user_id: int) -> bool:
        result = await self._db.execute(
            """
            UPDATE users
            SET deleted_at = NOW(), is_active = FALSE, updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
        )
        return result.endswith("1")

    async def set_active(self, user_id: int, *, active: bool) -> bool:
        result = await self._db.execute(
            """
            UPDATE users
            SET is_active = $2, updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
            active,
        )
        return result.endswith("1")

    async def unlock(self, user_id: int) -> bool:
        result = await self._db.execute(
            """
            UPDATE users
            SET failed_attempts = 0, locked_until = NULL, updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
        )
        return result.endswith("1")

    async def reset_mfa(self, user_id: int) -> bool:
        result = await self._db.execute(
            """
            UPDATE users
            SET mfa_enabled = FALSE,
                mfa_secret = NULL,
                mfa_pending_secret = NULL,
                updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
        )
        return result.endswith("1")

    async def set_mfa_pending(self, user_id: int, encrypted_secret: str) -> bool:
        result = await self._db.execute(
            """
            UPDATE users
            SET mfa_pending_secret = $2, updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
            encrypted_secret,
        )
        return result.endswith("1")

    async def confirm_mfa(self, user_id: int) -> bool:
        result = await self._db.execute(
            """
            UPDATE users
            SET mfa_enabled = TRUE,
                mfa_secret = mfa_pending_secret,
                mfa_pending_secret = NULL,
                updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL AND mfa_pending_secret IS NOT NULL
            """,
            user_id,
        )
        return result.endswith("1")

    async def get_mfa_secrets(self, user_id: int) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT mfa_enabled, mfa_secret, mfa_pending_secret
            FROM users
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
        )

    async def set_password_hash(self, user_id: int, password_hash: str) -> bool:
        result = await self._db.execute(
            """
            UPDATE users SET password_hash = $2, updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
            password_hash,
        )
        return result.endswith("1")

    async def get_auth_credentials(self, user_id: int) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT id, file_id, email, password_hash, mfa_enabled
            FROM users
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
        )

    async def get_by_email(self, email: str) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT * FROM users
            WHERE email = $1 AND deleted_at IS NULL
            """,
            email.strip().lower(),
        )

    async def set_password_reset(self, user_id: int, token_hash: str, expires_at: Any) -> bool:
        result = await self._db.execute(
            """
            UPDATE users
            SET password_reset_token_hash = $2,
                password_reset_expires_at = $3,
                updated_at = NOW()
            WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
            token_hash,
            expires_at,
        )
        return result.endswith("1")

    async def clear_password_reset(self, user_id: int) -> None:
        await self._db.execute(
            """
            UPDATE users
            SET password_reset_token_hash = NULL,
                password_reset_expires_at = NULL,
                updated_at = NOW()
            WHERE id = $1
            """,
            user_id,
        )

    async def find_by_reset_token(self, token_hash: str) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT id, file_id, email, name
            FROM users
            WHERE password_reset_token_hash = $1
              AND password_reset_expires_at > NOW()
              AND deleted_at IS NULL
            """,
            token_hash,
        )

    async def count_locked_users(self) -> int:
        return int(
            await self._db.fetchval(
                """
                SELECT COUNT(*) FROM users
                WHERE deleted_at IS NULL AND locked_until > NOW()
                """
            )
            or 0
        )

    async def count_mfa_enabled(self) -> int:
        return int(
            await self._db.fetchval(
                """
                SELECT COUNT(*) FROM users
                WHERE deleted_at IS NULL AND mfa_enabled = TRUE
                """
            )
            or 0
        )

    async def super_admin_permission_count(self, file_id: str) -> int:
        return int(
            await self._db.fetchval(
                """
                SELECT COUNT(*)
                FROM users u
                JOIN user_roles ur ON ur.user_id = u.id
                JOIN role_permissions rp ON rp.role_id = ur.role_id
                WHERE u.file_id = $1 AND u.deleted_at IS NULL
                """,
                file_id,
            )
            or 0
        )
