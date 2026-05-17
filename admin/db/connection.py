from __future__ import annotations

import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

import asyncpg

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def get_database_url() -> str:
    url = os.environ.get("OOA_DB_URL") or os.environ.get("POSTGRES_DSN")
    if not url:
        raise RuntimeError(
            "OOA_DB_URL is not configured. Example: "
            "postgresql://postgres:devpassword@localhost:5433/ooa"
        )
    return url


class AdminDatabase:
    """Async PostgreSQL access layer — parameterized queries only."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    @classmethod
    async def create(cls, dsn: str | None = None, *, min_size: int = 2, max_size: int = 10) -> AdminDatabase:
        pool = await asyncpg.create_pool(dsn or get_database_url(), min_size=min_size, max_size=max_size)
        return cls(pool)

    async def close(self) -> None:
        await self._pool.close()

    async def health_check(self) -> bool:
        value = await self.fetchval("SELECT 1")
        return value == 1

    async def execute(self, query: str, *args: Any) -> str:
        async with self._pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetchval(self, query: str, *args: Any) -> Any:
        async with self._pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> asyncpg.Record | None:
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, *args)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[asyncpg.Connection]:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def run_migrations(self) -> list[str]:
        applied: list[str] = []
        await self.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.name
            exists = await self.fetchval(
                "SELECT 1 FROM schema_migrations WHERE version = $1",
                version,
            )
            if exists:
                continue
            sql = path.read_text(encoding="utf-8")
            await self._execute_script(sql)
            await self.execute(
                "INSERT INTO schema_migrations (version) VALUES ($1) ON CONFLICT DO NOTHING",
                version,
            )
            applied.append(version)
            logger.info("[AdminDB] Applied migration %s", version)
        return applied

    async def _execute_script(self, sql: str) -> None:
        statements = _split_sql_statements(sql)
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                for statement in statements:
                    await conn.execute(statement)


def _split_sql_statements(sql: str) -> list[str]:
    """Split SQL file into executable statements (simple parser)."""
    chunks = re.split(r";\s*\n", sql)
    statements: list[str] = []
    for chunk in chunks:
        lines = [
            line for line in chunk.splitlines()
            if line.strip() and not line.strip().startswith("--")
        ]
        if not lines:
            continue
        statement = "\n".join(lines).strip()
        if statement:
            statements.append(statement)
    return statements


async def init_admin_db(dsn: str | None = None) -> AdminDatabase:
    global _pool
    db = await AdminDatabase.create(dsn)
    _pool = db._pool
    return db


def get_admin_db() -> AdminDatabase:
    if _pool is None:
        raise RuntimeError("Admin database not initialized. Call init_admin_db() first.")
    return AdminDatabase(_pool)


async def close_admin_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
