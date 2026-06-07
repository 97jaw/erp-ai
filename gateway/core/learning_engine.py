"""Analyze telemetry and update working memory patterns (Phase 8)."""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Protocol

from admin.db.repositories.telemetry import TelemetryRepository
from gateway.core.interaction_telemetry import InteractionTelemetry
from gateway.core.working_memory import WorkingMemory

logger = logging.getLogger(__name__)

FOLLOW_UP_WINDOW_SECONDS = 60


@dataclass
class LearningPatterns:
    """Aggregated learnings from recent interactions."""

    common_failures: list[dict[str, Any]] = field(default_factory=list)
    successful_strategies: list[dict[str, Any]] = field(default_factory=list)
    user_specific_patterns: dict[str, dict[str, Any]] = field(default_factory=dict)
    tool_performance: list[dict[str, Any]] = field(default_factory=list)
    quality_drift: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "common_failures": self.common_failures,
            "successful_strategies": self.successful_strategies,
            "user_specific_patterns": self.user_specific_patterns,
            "tool_performance": self.tool_performance,
            "quality_drift": self.quality_drift,
        }


class LearningStore(Protocol):
    async def list_recent(self, *, hours: int = 24, user_id: int | None = None, limit: int = 500) -> list[Any]: ...

    async def upsert_user_patterns(self, user_id: int, patterns: dict[str, Any]) -> None: ...

    async def start_learning_job(self, hours: int) -> int: ...

    async def finish_learning_job(
        self,
        job_id: int,
        *,
        status: str,
        interactions_analyzed: int,
        summary: dict[str, Any],
        error_message: str | None = None,
    ) -> None: ...


class LearningEngine:
    """Detect patterns from telemetry and persist learnings."""

    def __init__(self, repository: LearningStore) -> None:
        self._repository = repository

    async def learn_from_recent(self, hours: int = 24) -> LearningPatterns:
        job_id = await self._repository.start_learning_job(hours)
        try:
            rows = await self._repository.list_recent(hours=hours, limit=2000)
            interactions = [
                InteractionTelemetry.from_db_row(row)
                if hasattr(row, "keys")
                else row
                for row in rows
            ]
            patterns = self.analyze(interactions)
            await self._apply_learnings(patterns)
            await self._repository.finish_learning_job(
                job_id,
                status="success",
                interactions_analyzed=len(interactions),
                summary=patterns.to_dict(),
            )
            logger.info(
                "[LearningEngine] analyzed %d interactions over %dh",
                len(interactions),
                hours,
            )
            return patterns
        except Exception as exc:
            await self._repository.finish_learning_job(
                job_id,
                status="failed",
                interactions_analyzed=0,
                summary={},
                error_message=str(exc)[:500],
            )
            raise

    def analyze(self, interactions: list[InteractionTelemetry]) -> LearningPatterns:
        return LearningPatterns(
            common_failures=self._find_common_failures(interactions),
            successful_strategies=self._find_successful_strategies(interactions),
            user_specific_patterns=self._find_user_patterns(interactions),
            tool_performance=self._analyze_tool_performance(interactions),
            quality_drift=self._detect_quality_drift(interactions),
        )

    async def _apply_learnings(self, patterns: LearningPatterns) -> None:
        for user_id_str, payload in patterns.user_specific_patterns.items():
            try:
                user_id = int(user_id_str)
            except (TypeError, ValueError):
                continue
            await self._repository.upsert_user_patterns(user_id, payload)

    @staticmethod
    def apply_to_working_memory(working_memory: WorkingMemory, patterns: dict[str, Any]) -> None:
        """Merge persisted learnings into an in-memory WorkingMemory."""
        if not patterns:
            return
        merged = dict(working_memory.user_patterns)
        merged.update(patterns)
        working_memory.user_patterns = merged

    @staticmethod
    def _find_common_failures(interactions: list[InteractionTelemetry]) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        for item in interactions:
            if item.failure_mode:
                counter[item.failure_mode] += 1
            elif not item.quality_passed:
                counter["quality_failed"] += 1
        return [
            {"failure_mode": mode, "count": count}
            for mode, count in counter.most_common(5)
        ]

    @staticmethod
    def _find_successful_strategies(interactions: list[InteractionTelemetry]) -> list[dict[str, Any]]:
        counter: Counter[str] = Counter()
        for item in interactions:
            if not item.quality_passed or item.failure_mode:
                continue
            label = None
            if item.strategy_used is not None:
                label = item.strategy_used.synthesis_approach
            if not label:
                label = item.metadata.get("strategy_label")
            if not label:
                continue
            if len(label) > 120:
                label = label[:117] + "..."
            counter[str(label)] += 1
        return [
            {"strategy": label, "success_count": count}
            for label, count in counter.most_common(5)
        ]

    @staticmethod
    def _find_user_patterns(interactions: list[InteractionTelemetry]) -> dict[str, dict[str, Any]]:
        by_user: dict[int, list[InteractionTelemetry]] = defaultdict(list)
        for item in interactions:
            by_user[item.user_id].append(item)

        patterns: dict[str, dict[str, Any]] = {}
        for user_id, rows in by_user.items():
            subject_counter: Counter[str] = Counter()
            tool_counter: Counter[str] = Counter()
            suggestion_clicks = 0
            fast_followups = 0
            for row in rows:
                subject = None
                if row.intent_extracted and row.intent_extracted.subject_area:
                    subject = row.intent_extracted.subject_area
                else:
                    subject = row.metadata.get("subject_area")
                if subject:
                    subject_counter[str(subject)] += 1
                for tool in row.tools_called:
                    tool_counter[tool] += 1
                if row.suggestion_clicked:
                    suggestion_clicks += 1
                if row.next_query_within_60s:
                    fast_followups += 1

            top_subjects = [name for name, _ in subject_counter.most_common(3)]
            top_tools = [name for name, _ in tool_counter.most_common(3)]
            patterns[str(user_id)] = {
                "top_subject_areas": top_subjects,
                "preferred_tools": top_tools,
                "suggestion_click_rate": round(suggestion_clicks / max(len(rows), 1), 3),
                "fast_followup_rate": round(fast_followups / max(len(rows), 1), 3),
                "recent_query_count": len(rows),
            }
        return patterns

    @staticmethod
    def _analyze_tool_performance(interactions: list[InteractionTelemetry]) -> list[dict[str, Any]]:
        durations: dict[str, list[int]] = defaultdict(list)
        usage: Counter[str] = Counter()
        for item in interactions:
            for tool, duration in item.tool_durations_ms.items():
                usage[tool] += 1
                durations[tool].append(duration)

        stats: list[dict[str, Any]] = []
        for tool, count in usage.most_common(10):
            samples = durations[tool]
            stats.append(
                {
                    "tool": tool,
                    "calls": count,
                    "avg_duration_ms": int(sum(samples) / max(len(samples), 1)),
                    "max_duration_ms": max(samples) if samples else 0,
                },
            )
        return stats

    @staticmethod
    def _detect_quality_drift(interactions: list[InteractionTelemetry]) -> dict[str, Any]:
        if not interactions:
            return {"sample_size": 0, "avg_pass_rate": 1.0, "retry_rate": 0.0}
        pass_rates = [item.quality_pass_rate for item in interactions]
        retries = sum(1 for item in interactions if item.retries_needed > 0)
        return {
            "sample_size": len(interactions),
            "avg_pass_rate": round(sum(pass_rates) / len(pass_rates), 4),
            "retry_rate": round(retries / len(interactions), 4),
            "cache_hit_rate": round(
                sum(1 for item in interactions if item.cache_hit) / len(interactions),
                4,
            ),
        }


async def run_daily_learning_job(
    repository: TelemetryRepository | None = None,
    *,
    hours: int = 24,
) -> LearningPatterns:
    """Entry point for scheduled learning — analyzes the last N hours."""
    if repository is None:
        from admin.db.connection import get_admin_db

        repository = TelemetryRepository(get_admin_db())
    engine = LearningEngine(repository)
    return await engine.learn_from_recent(hours=hours)
