"""PostgreSQL persistence for AI interaction telemetry (Phase 8)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from admin.db.connection import AdminDatabase
from gateway.core.interaction_telemetry import InteractionTelemetry, normalize_message, suggestion_match


class TelemetryRepository:
    """Parameterized access to ai_interactions and learning tables."""

    def __init__(self, db: AdminDatabase) -> None:
        self._db = db

    async def insert(self, telemetry: InteractionTelemetry) -> None:
        record = telemetry.to_db_record()
        await self._db.execute(
            """
            INSERT INTO ai_interactions (
                id, user_id, session_id, created_at, user_query, user_query_language,
                intent, strategy, tools_called, tool_durations_ms, orchestration_log,
                quality_review, retries_needed, quality_passed, quality_pass_rate, confidence,
                response_text, response_length, visualization_type, suggestions_offered,
                failure_mode, cache_hit, proactive_cache_keys,
                user_satisfaction_signal, suggestion_clicked, next_query_within_60s, chat_continued,
                tokens_input, tokens_output, cost_cents, total_duration_ms,
                orchestration_duration_ms, metadata
            ) VALUES (
                $1::uuid, $2, $3, $4, $5, $6,
                $7::jsonb, $8::jsonb, $9, $10::jsonb, $11::jsonb,
                $12::jsonb, $13, $14, $15, $16,
                $17, $18, $19, $20,
                $21, $22, $23,
                $24, $25, $26, $27,
                $28, $29, $30, $31,
                $32, $33::jsonb
            )
            """,
            record["id"],
            record["user_id"],
            record["session_id"],
            record["created_at"],
            record["user_query"],
            record["user_query_language"],
            _json_text(record["intent"]),
            _json_text(record["strategy"]),
            record["tools_called"],
            _json_text(record["tool_durations_ms"]),
            _json_text(record["orchestration_log"]),
            _json_text(record["quality_review"]),
            record["retries_needed"],
            record["quality_passed"],
            record["quality_pass_rate"],
            record["confidence"],
            record["response_text"],
            record["response_length"],
            record["visualization_type"],
            record["suggestions_offered"],
            record["failure_mode"],
            record["cache_hit"],
            record["proactive_cache_keys"],
            record["user_satisfaction_signal"],
            record["suggestion_clicked"],
            record["next_query_within_60s"],
            record["chat_continued"],
            record["tokens_input"],
            record["tokens_output"],
            record["cost_cents"],
            record["total_duration_ms"],
            record["orchestration_duration_ms"],
            _json_text(record["metadata"]),
        )

    async def get_by_id(self, interaction_id: str) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            "SELECT * FROM ai_interactions WHERE id = $1::uuid",
            interaction_id,
        )

    async def list_recent(
        self,
        *,
        hours: int = 24,
        user_id: int | None = None,
        limit: int = 500,
    ) -> list[asyncpg.Record]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        if user_id is not None:
            return await self._db.fetch(
                """
                SELECT * FROM ai_interactions
                WHERE created_at >= $1 AND user_id = $2
                ORDER BY created_at DESC
                LIMIT $3
                """,
                since,
                user_id,
                limit,
            )
        return await self._db.fetch(
            """
            SELECT * FROM ai_interactions
            WHERE created_at >= $1
            ORDER BY created_at DESC
            LIMIT $2
            """,
            since,
            limit,
        )

    async def list_for_admin(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        user_id: int | None = None,
    ) -> list[asyncpg.Record]:
        if user_id is not None:
            return await self._db.fetch(
                """
                SELECT
                    id, user_id, session_id, created_at, user_query, user_query_language,
                    tools_called, quality_passed, quality_pass_rate, failure_mode, cache_hit,
                    visualization_type, suggestions_offered, total_duration_ms, cost_cents,
                    user_satisfaction_signal, suggestion_clicked, chat_continued
                FROM ai_interactions
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
                """,
                user_id,
                limit,
                offset,
            )
        return await self._db.fetch(
            """
            SELECT
                id, user_id, session_id, created_at, user_query, user_query_language,
                tools_called, quality_passed, quality_pass_rate, failure_mode, cache_hit,
                visualization_type, suggestions_offered, total_duration_ms, cost_cents,
                user_satisfaction_signal, suggestion_clicked, chat_continued
            FROM ai_interactions
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            limit,
            offset,
        )

    async def summary(self, *, hours: int = 24) -> asyncpg.Record | None:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        return await self._db.fetchrow(
            """
            SELECT
                COUNT(*) AS interactions,
                COUNT(DISTINCT user_id) AS active_users,
                COUNT(*) FILTER (WHERE quality_passed) AS quality_passed_count,
                COUNT(*) FILTER (WHERE failure_mode IS NOT NULL) AS failure_count,
                COUNT(*) FILTER (WHERE cache_hit) AS cache_hits,
                COUNT(*) FILTER (WHERE suggestion_clicked IS NOT NULL) AS suggestion_clicks,
                COALESCE(AVG(total_duration_ms), 0) AS avg_duration_ms,
                COALESCE(SUM(cost_cents), 0) AS total_cost_cents
            FROM ai_interactions
            WHERE created_at >= $1
            """,
            since,
        )

    async def latest_for_session(
        self,
        *,
        user_id: int,
        session_id: str,
    ) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT * FROM ai_interactions
            WHERE user_id = $1 AND session_id = $2
            ORDER BY created_at DESC
            LIMIT 1
            """,
            user_id,
            session_id,
        )

    async def apply_follow_up_signals(
        self,
        *,
        user_id: int,
        session_id: str,
        next_query: str,
        within_seconds: int = 60,
    ) -> None:
        previous = await self.latest_for_session(user_id=user_id, session_id=session_id)
        if previous is None:
            return

        created_at = previous["created_at"]
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - created_at
        if delta.total_seconds() > within_seconds:
            await self._db.execute(
                """
                UPDATE ai_interactions
                SET chat_continued = TRUE
                WHERE id = $1::uuid
                """,
                str(previous["id"]),
            )
            return

        suggestions = list(previous["suggestions_offered"] or [])
        clicked = suggestion_match(next_query, suggestions)
        await self._db.execute(
            """
            UPDATE ai_interactions
            SET chat_continued = TRUE,
                next_query_within_60s = $2,
                suggestion_clicked = COALESCE($3, suggestion_clicked)
            WHERE id = $1::uuid
            """,
            str(previous["id"]),
            next_query[:2000],
            clicked,
        )

    async def set_satisfaction(self, interaction_id: str, signal: str) -> bool:
        result = await self._db.execute(
            """
            UPDATE ai_interactions
            SET user_satisfaction_signal = $2
            WHERE id = $1::uuid
            """,
            interaction_id,
            signal,
        )
        return result.endswith("1")

    async def get_user_patterns(self, user_id: int) -> dict[str, Any]:
        row = await self._db.fetchrow(
            "SELECT patterns FROM user_learning_patterns WHERE user_id = $1",
            user_id,
        )
        if not row:
            return {}
        patterns = row["patterns"]
        if isinstance(patterns, str):
            patterns = json.loads(patterns)
        if not isinstance(patterns, dict):
            return {}
        return {str(key): value for key, value in patterns.items()}

    async def upsert_user_patterns(self, user_id: int, patterns: dict[str, Any]) -> None:
        await self._db.execute(
            """
            INSERT INTO user_learning_patterns (user_id, patterns, updated_at)
            VALUES ($1, $2::jsonb, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                patterns = EXCLUDED.patterns,
                updated_at = NOW()
            """,
            user_id,
            _json_text(patterns),
        )

    async def start_learning_job(self, hours: int) -> int:
        return int(
            await self._db.fetchval(
                """
                INSERT INTO learning_job_runs (hours_analyzed, status)
                VALUES ($1, 'running')
                RETURNING id
                """,
                hours,
            )
        )

    async def finish_learning_job(
        self,
        job_id: int,
        *,
        status: str,
        interactions_analyzed: int,
        summary: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        await self._db.execute(
            """
            UPDATE learning_job_runs
            SET finished_at = NOW(),
                status = $2,
                interactions_analyzed = $3,
                summary = $4::jsonb,
                error_message = $5
            WHERE id = $1
            """,
            job_id,
            status,
            interactions_analyzed,
            _json_text(summary),
            error_message,
        )

    async def latest_learning_job(self) -> asyncpg.Record | None:
        return await self._db.fetchrow(
            """
            SELECT * FROM learning_job_runs
            ORDER BY started_at DESC
            LIMIT 1
            """
        )


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, default=str)
