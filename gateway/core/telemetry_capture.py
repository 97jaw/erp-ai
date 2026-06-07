"""Capture and persist interaction telemetry (Phase 8)."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from admin.db.repositories.telemetry import TelemetryRepository
from admin.db.repositories.usage import UsageRepository
from gateway.core.interaction_telemetry import InteractionTelemetry

logger = logging.getLogger(__name__)


class TelemetryStore(Protocol):
    """Minimal persistence interface for tests and production."""

    async def insert(self, telemetry: InteractionTelemetry) -> None: ...

    async def apply_follow_up_signals(
        self,
        *,
        user_id: int,
        session_id: str,
        next_query: str,
        within_seconds: int = 60,
    ) -> None: ...


class InMemoryTelemetryStore:
    """Test double that keeps telemetry rows in memory."""

    def __init__(self) -> None:
        self.records: list[InteractionTelemetry] = []
        self.follow_up_updates: list[dict[str, Any]] = []

    async def insert(self, telemetry: InteractionTelemetry) -> None:
        self.records.append(telemetry)

    async def apply_follow_up_signals(
        self,
        *,
        user_id: int,
        session_id: str,
        next_query: str,
        within_seconds: int = 60,
    ) -> None:
        del within_seconds
        self.follow_up_updates.append(
            {
                "user_id": user_id,
                "session_id": session_id,
                "next_query": next_query,
            },
        )
        if not self.records:
            return
        previous = None
        for record in reversed(self.records):
            if record.user_id == user_id and record.session_id == session_id:
                previous = record
                break
        if previous is None:
            return
        previous.chat_continued = True
        previous.next_query_within_60s = next_query
        for suggestion in previous.suggestions_offered:
            if suggestion.strip().lower() == next_query.strip().lower():
                previous.suggestion_clicked = suggestion
                break


class TelemetryCapture:
    """Record every intelligent handler interaction."""

    def __init__(
        self,
        repository: TelemetryRepository | TelemetryStore | None = None,
        *,
        usage_repository: UsageRepository | None = None,
        enabled: bool = True,
    ) -> None:
        self._repository = repository
        self._usage = usage_repository
        self._enabled = enabled

    @classmethod
    def from_admin_db(cls, db: Any) -> TelemetryCapture:
        return cls(
            repository=TelemetryRepository(db),
            usage_repository=UsageRepository(db),
        )

    async def apply_follow_up_signals(
        self,
        *,
        user_id: int,
        session_id: str,
        next_query: str,
    ) -> None:
        if not self._enabled or self._repository is None or not session_id:
            return
        try:
            await self._repository.apply_follow_up_signals(
                user_id=user_id,
                session_id=session_id,
                next_query=next_query,
            )
        except Exception as exc:
            logger.warning("[TelemetryCapture] follow-up signal failed: %s", exc)

    async def record(self, telemetry: InteractionTelemetry) -> None:
        if not self._enabled or self._repository is None:
            return
        try:
            await self._repository.insert(telemetry)
            if self._usage is not None:
                tokens = telemetry.tokens_input + telemetry.tokens_output
                await self._usage.record(
                    telemetry.user_id,
                    queries=1,
                    tokens=tokens,
                )
            logger.info(
                "[TelemetryCapture] recorded interaction=%s user=%s duration_ms=%d",
                telemetry.interaction_id[:8],
                telemetry.user_id,
                telemetry.total_duration_ms,
            )
        except Exception as exc:
            logger.error("[TelemetryCapture] record failed: %s", exc)
