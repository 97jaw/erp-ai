from __future__ import annotations

import os
from datetime import date, timedelta
from typing import Any

import asyncpg

from admin.db.connection import AdminDatabase

TOKEN_CENTS_PER_1K = float(os.environ.get("OOA_TOKEN_CENTS_PER_1K", "0.35"))
PDF_CENTS = int(os.environ.get("OOA_PDF_CENTS", "25"))
VOICE_CENTS_PER_MIN = float(os.environ.get("OOA_VOICE_CENTS_PER_MIN", "8"))


def estimate_cost_cents(*, tokens: int = 0, pdfs: int = 0, voice_minutes: float = 0) -> int:
    total = (tokens / 1000.0) * TOKEN_CENTS_PER_1K
    total += pdfs * PDF_CENTS
    total += voice_minutes * VOICE_CENTS_PER_MIN
    return max(0, int(round(total)))


class UsageRepository:
    def __init__(self, db: AdminDatabase) -> None:
        self._db = db

    async def record(
        self,
        user_id: int,
        *,
        queries: int = 0,
        tokens: int = 0,
        pdfs: int = 0,
        voice_minutes: float = 0,
        on_date: date | None = None,
    ) -> None:
        day = on_date or date.today()
        cost = estimate_cost_cents(tokens=tokens, pdfs=pdfs, voice_minutes=voice_minutes)
        await self._db.execute(
            """
            INSERT INTO usage_stats (user_id, date, queries_count, tokens_used, cost_cents, pdfs_generated, voice_minutes)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (user_id, date) DO UPDATE SET
                queries_count = usage_stats.queries_count + EXCLUDED.queries_count,
                tokens_used = usage_stats.tokens_used + EXCLUDED.tokens_used,
                cost_cents = usage_stats.cost_cents + EXCLUDED.cost_cents,
                pdfs_generated = usage_stats.pdfs_generated + EXCLUDED.pdfs_generated,
                voice_minutes = usage_stats.voice_minutes + EXCLUDED.voice_minutes
            """,
            user_id,
            day,
            queries,
            tokens,
            cost,
            pdfs,
            voice_minutes,
        )

    async def system_summary(self, *, date_from: date, date_to: date) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT
                COALESCE(SUM(queries_count), 0) AS queries_count,
                COALESCE(SUM(tokens_used), 0) AS tokens_used,
                COALESCE(SUM(cost_cents), 0) AS cost_cents,
                COALESCE(SUM(pdfs_generated), 0) AS pdfs_generated,
                COALESCE(SUM(voice_minutes), 0) AS voice_minutes,
                COUNT(DISTINCT user_id) AS active_users
            FROM usage_stats
            WHERE date >= $1 AND date <= $2
            """,
            date_from,
            date_to,
        )

    async def by_user(
        self,
        *,
        date_from: date,
        date_to: date,
        limit: int = 50,
    ) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT
                u.id AS user_id,
                u.name,
                u.file_id,
                COALESCE(SUM(us.queries_count), 0) AS queries_count,
                COALESCE(SUM(us.tokens_used), 0) AS tokens_used,
                COALESCE(SUM(us.cost_cents), 0) AS cost_cents,
                COALESCE(SUM(us.pdfs_generated), 0) AS pdfs_generated
            FROM users u
            LEFT JOIN usage_stats us ON us.user_id = u.id AND us.date >= $1 AND us.date <= $2
            WHERE u.deleted_at IS NULL
            GROUP BY u.id, u.name, u.file_id
            ORDER BY cost_cents DESC, queries_count DESC
            LIMIT $3
            """,
            date_from,
            date_to,
            limit,
        )

    async def by_department(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT
                d.code,
                d.name,
                COALESCE(SUM(us.queries_count), 0) AS queries_count,
                COALESCE(SUM(us.tokens_used), 0) AS tokens_used,
                COALESCE(SUM(us.cost_cents), 0) AS cost_cents,
                COUNT(DISTINCT us.user_id) AS active_users
            FROM departments d
            JOIN user_departments ud ON ud.department_id = d.id
            JOIN usage_stats us ON us.user_id = ud.user_id AND us.date >= $1 AND us.date <= $2
            WHERE d.is_active = TRUE
            GROUP BY d.id, d.code, d.name
            ORDER BY cost_cents DESC
            """,
            date_from,
            date_to,
        )

    async def daily_totals(self, *, days: int = 30) -> list[asyncpg.Record]:
        start = date.today() - timedelta(days=max(days - 1, 0))
        return await self._db.fetch(
            """
            SELECT
                date,
                SUM(queries_count) AS queries_count,
                SUM(tokens_used) AS tokens_used,
                SUM(cost_cents) AS cost_cents,
                COUNT(DISTINCT user_id) AS active_users
            FROM usage_stats
            WHERE date >= $1
            GROUP BY date
            ORDER BY date ASC
            """,
            start,
        )

    async def monthly_totals(self, *, months: int = 12) -> list[asyncpg.Record]:
        return await self._db.fetch(
            """
            SELECT
                date_trunc('month', date)::date AS month,
                SUM(queries_count) AS queries_count,
                SUM(tokens_used) AS tokens_used,
                SUM(cost_cents) AS cost_cents,
                COUNT(DISTINCT user_id) AS active_users
            FROM usage_stats
            WHERE date >= (CURRENT_DATE - ($1::int * INTERVAL '1 month'))
            GROUP BY date_trunc('month', date)
            ORDER BY month ASC
            """,
            months,
        )

    async def cost_breakdown(self, *, date_from: date, date_to: date) -> dict[str, Any]:
        row = await self.system_summary(date_from=date_from, date_to=date_to)
        if not row:
            return {"token_cost_cents": 0, "pdf_cost_cents": 0, "voice_cost_cents": 0, "total_cents": 0}
        tokens = int(row["tokens_used"] or 0)
        pdfs = int(row["pdfs_generated"] or 0)
        voice = float(row["voice_minutes"] or 0)
        token_cost = int(round((tokens / 1000.0) * TOKEN_CENTS_PER_1K))
        pdf_cost = pdfs * PDF_CENTS
        voice_cost = int(round(voice * VOICE_CENTS_PER_MIN))
        return {
            "token_cost_cents": token_cost,
            "pdf_cost_cents": pdf_cost,
            "voice_cost_cents": voice_cost,
            "total_cents": int(row["cost_cents"] or 0),
            "queries_count": int(row["queries_count"] or 0),
            "tokens_used": tokens,
            "pdfs_generated": pdfs,
            "voice_minutes": voice,
        }
