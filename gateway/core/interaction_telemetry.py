"""Interaction telemetry models for Phase 8 learning and admin analytics."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from gateway.core.intent_analyzer import Intent
from gateway.core.quality_gate import QualityReview
from gateway.core.strategy_planner import Strategy


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    return str(value)


def visualization_type_from(visualization: dict[str, Any] | None) -> str:
    if not visualization:
        return "NONE"
    return str(visualization.get("visual_type") or "NONE")


@dataclass
class InteractionTelemetry:
    """Full record of one AI interaction turn."""

    interaction_id: str
    user_id: int
    session_id: str
    timestamp: datetime
    user_query: str
    user_query_language: str = "en"
    intent_extracted: Intent | None = None
    strategy_used: Strategy | None = None
    tools_called: list[str] = field(default_factory=list)
    tool_durations_ms: dict[str, int] = field(default_factory=dict)
    orchestration_log: list[dict[str, Any]] = field(default_factory=list)
    quality_review: QualityReview | None = None
    retries_needed: int = 0
    quality_passed: bool = True
    quality_pass_rate: float = 1.0
    confidence: float | None = None
    response_text: str = ""
    response_length: int = 0
    visualization_type: str = "NONE"
    suggestions_offered: list[str] = field(default_factory=list)
    failure_mode: str | None = None
    cache_hit: bool = False
    proactive_cache_keys: list[str] = field(default_factory=list)
    user_satisfaction_signal: str | None = None
    suggestion_clicked: str | None = None
    next_query_within_60s: str | None = None
    chat_continued: bool = False
    tokens_input: int = 0
    tokens_output: int = 0
    cost_cents: int = 0
    total_duration_ms: int = 0
    orchestration_duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    entity_discovery_count: int = 0
    entity_top_confidence: float = 0.0
    entity_gate_status: str = "skipped"
    entity_confirmed_by_user: bool = False
    entity_auto_confirmed: bool = False
    entity_strategies_used: list[str] = field(default_factory=list)
    entity_strategy_that_matched: str | None = None

    @classmethod
    def start(
        cls,
        *,
        user_id: int,
        session_id: str,
        user_query: str,
        user_query_language: str = "en",
        interaction_id: str | None = None,
    ) -> InteractionTelemetry:
        return cls(
            interaction_id=interaction_id or str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            timestamp=_utc_now(),
            user_query=user_query,
            user_query_language=user_query_language,
        )

    def finalize_response(
        self,
        *,
        response_text: str,
        visualization: dict[str, Any] | None,
        suggestions: list[str],
        total_duration_ms: int,
        orchestration_duration_ms: int = 0,
        failure_mode: str | None = None,
        cache_hit: bool = False,
        proactive_cache_keys: list[str] | None = None,
        quality_review: QualityReview | None = None,
        quality_checks_passed: int = 0,
        quality_checks_total: int = 0,
        retries_needed: int = 0,
        tools_called: list[str] | None = None,
        orchestration_log: list[dict[str, Any]] | None = None,
        intent: Intent | None = None,
        strategy: Strategy | None = None,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_cents: int = 0,
        confidence: float | None = None,
    ) -> None:
        self.response_text = response_text
        self.response_length = len(response_text)
        self.visualization_type = visualization_type_from(visualization)
        self.suggestions_offered = list(suggestions[:10])
        self.total_duration_ms = total_duration_ms
        self.orchestration_duration_ms = orchestration_duration_ms
        self.failure_mode = failure_mode
        self.cache_hit = cache_hit
        self.proactive_cache_keys = list(proactive_cache_keys or [])
        self.intent_extracted = intent or self.intent_extracted
        self.strategy_used = strategy or self.strategy_used
        self.tools_called = list(tools_called or [])
        self.orchestration_log = list(orchestration_log or [])
        self.quality_review = quality_review
        self.retries_needed = retries_needed
        if quality_review is not None:
            self.quality_passed = quality_review.passed
            self.quality_pass_rate = quality_review.pass_rate
        self.tokens_input = tokens_input
        self.tokens_output = tokens_output
        self.cost_cents = cost_cents
        self.confidence = confidence
        if quality_checks_total:
            self.metadata.setdefault("quality_checks_passed", quality_checks_passed)
            self.metadata.setdefault("quality_checks_total", quality_checks_total)
        self.metadata.setdefault("entity_discovery_count", self.entity_discovery_count)
        self.metadata.setdefault("entity_top_confidence", self.entity_top_confidence)
        self.metadata.setdefault("entity_gate_status", self.entity_gate_status)
        self.metadata.setdefault("entity_confirmed_by_user", self.entity_confirmed_by_user)
        self.metadata.setdefault("entity_auto_confirmed", self.entity_auto_confirmed)
        self.metadata.setdefault("entity_strategies_used", self.entity_strategies_used)
        self.metadata.setdefault("entity_strategy_that_matched", self.entity_strategy_that_matched)
        self.tool_durations_ms = _tool_durations_from_log(self.orchestration_log)

    def to_db_record(self) -> dict[str, Any]:
        """Serialize for PostgreSQL insert — excludes raw tool payloads."""
        return {
            "id": self.interaction_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "created_at": self.timestamp,
            "user_query": self.user_query,
            "user_query_language": self.user_query_language,
            "intent": _json_safe(self.intent_extracted.to_dict()) if self.intent_extracted else None,
            "strategy": _json_safe(self.strategy_used.to_dict()) if self.strategy_used else None,
            "tools_called": self.tools_called,
            "tool_durations_ms": _json_safe(self.tool_durations_ms),
            "orchestration_log": _json_safe(self.orchestration_log),
            "quality_review": _quality_review_dict(self.quality_review),
            "retries_needed": self.retries_needed,
            "quality_passed": self.quality_passed,
            "quality_pass_rate": self.quality_pass_rate,
            "confidence": self.confidence,
            "response_text": self.response_text,
            "response_length": self.response_length,
            "visualization_type": self.visualization_type,
            "suggestions_offered": self.suggestions_offered,
            "failure_mode": self.failure_mode,
            "cache_hit": self.cache_hit,
            "proactive_cache_keys": self.proactive_cache_keys,
            "user_satisfaction_signal": self.user_satisfaction_signal,
            "suggestion_clicked": self.suggestion_clicked,
            "next_query_within_60s": self.next_query_within_60s,
            "chat_continued": self.chat_continued,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "cost_cents": self.cost_cents,
            "total_duration_ms": self.total_duration_ms,
            "orchestration_duration_ms": self.orchestration_duration_ms,
            "metadata": _json_safe(self.metadata),
        }

    @classmethod
    def from_db_row(cls, row: Any) -> InteractionTelemetry:
        """Hydrate from an asyncpg record."""
        metadata = _coerce_json_dict(row.get("metadata"))
        intent_data = row.get("intent")
        if isinstance(intent_data, str):
            intent_data = json.loads(intent_data)
        if isinstance(intent_data, dict):
            metadata.setdefault("subject_area", intent_data.get("subject_area"))
            metadata.setdefault("primary_action", intent_data.get("primary_action"))
        strategy_data = row.get("strategy")
        if isinstance(strategy_data, str):
            strategy_data = json.loads(strategy_data)
        if isinstance(strategy_data, dict):
            metadata.setdefault("strategy_label", strategy_data.get("synthesis_approach"))

        return cls(
            interaction_id=str(row["id"]),
            user_id=int(row["user_id"]),
            session_id=str(row["session_id"] or ""),
            timestamp=row["created_at"],
            user_query=str(row["user_query"]),
            user_query_language=str(row["user_query_language"] or "en"),
            tools_called=list(row["tools_called"] or []),
            tool_durations_ms=_coerce_json_dict(row.get("tool_durations_ms")),
            orchestration_log=_coerce_json_list(row.get("orchestration_log")),
            retries_needed=int(row["retries_needed"] or 0),
            quality_passed=bool(row["quality_passed"]),
            quality_pass_rate=float(row["quality_pass_rate"] or 1.0),
            confidence=float(row["confidence"]) if row["confidence"] is not None else None,
            response_text=str(row["response_text"] or ""),
            response_length=int(row["response_length"] or 0),
            visualization_type=str(row["visualization_type"] or "NONE"),
            suggestions_offered=list(row["suggestions_offered"] or []),
            failure_mode=row["failure_mode"],
            cache_hit=bool(row["cache_hit"]),
            proactive_cache_keys=list(row["proactive_cache_keys"] or []),
            user_satisfaction_signal=row["user_satisfaction_signal"],
            suggestion_clicked=row["suggestion_clicked"],
            next_query_within_60s=row["next_query_within_60s"],
            chat_continued=bool(row["chat_continued"]),
            tokens_input=int(row["tokens_input"] or 0),
            tokens_output=int(row["tokens_output"] or 0),
            cost_cents=int(row["cost_cents"] or 0),
            total_duration_ms=int(row["total_duration_ms"] or 0),
            orchestration_duration_ms=int(row["orchestration_duration_ms"] or 0),
            metadata=metadata,
        )


def _quality_review_dict(review: QualityReview | None) -> dict[str, Any] | None:
    if review is None:
        return None
    return {
        "pass_rate": review.pass_rate,
        "passed": review.passed,
        "issues": list(review.issues),
        "checks": [
            {"name": check.name, "passed": check.passed, "issue": check.issue}
            for check in review.checks
        ],
    }


def _tool_durations_from_log(orchestration_log: list[dict[str, Any]]) -> dict[str, int]:
    durations: dict[str, int] = {}
    for entry in orchestration_log:
        tool = str(entry.get("tool") or "")
        duration = entry.get("duration_ms")
        if tool and isinstance(duration, int):
            durations[tool] = durations.get(tool, 0) + duration
    return durations


def _coerce_json_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, str):
        parsed = json.loads(value)
        return dict(parsed) if isinstance(parsed, dict) else {}
    if isinstance(value, dict):
        return dict(value)
    return {}


def _coerce_json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, str):
        parsed = json.loads(value)
        return list(parsed) if isinstance(parsed, list) else []
    if isinstance(value, list):
        return list(value)
    return []


def normalize_message(message: str) -> str:
    return " ".join(message.strip().lower().split())


def suggestion_match(message: str, suggestions: list[str]) -> str | None:
    normalized = normalize_message(message)
    for suggestion in suggestions:
        if normalize_message(suggestion) == normalized:
            return suggestion
    return None
