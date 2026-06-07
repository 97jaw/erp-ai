"""Predict next user actions and schedule background pre-computation (Phase 7)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent, JsonCompletionClient
from gateway.core.precompute_cache import (
    GLOBAL_PRECOMPUTE_CACHE,
    PrecomputeCache,
    cache_fingerprint,
)
from gateway.core.result_synthesizer import SynthesizedResult

logger = logging.getLogger(__name__)

PROACTIVE_MODEL = "claude-sonnet-4-20250514"
LIKELIHOOD_THRESHOLD = 0.7
MAX_BACKGROUND_TASKS = 3


@dataclass
class PredictedAction:
    """One predicted follow-up the user may take."""

    action: str
    likelihood: float
    pre_computable: bool
    suggestion_text: str
    query_message: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PredictedAction:
        suggestion = str(data.get("suggestion_text") or data.get("action") or "").strip()
        query = str(data.get("query_message") or suggestion).strip()
        return cls(
            action=str(data.get("action") or suggestion),
            likelihood=float(data.get("likelihood") or 0.0),
            pre_computable=bool(data.get("pre_computable")),
            suggestion_text=suggestion,
            query_message=query,
        )


@dataclass
class ProactiveActions:
    """Output of proactive anticipation for one response turn."""

    predicted_actions: list[PredictedAction] = field(default_factory=list)
    pre_compute_recommendations: list[str] = field(default_factory=list)
    scheduled_cache_keys: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProactiveActions:
        actions = [
            PredictedAction.from_dict(item)
            for item in data.get("predicted_actions") or []
            if isinstance(item, dict)
        ]
        return cls(
            predicted_actions=actions,
            pre_compute_recommendations=[
                str(item) for item in data.get("pre_compute_recommendations") or []
            ],
        )


PrecomputeRunner = Callable[..., Coroutine[Any, Any, None]]


class ProactiveIntelligence:
    """Predict likely next queries and warm cache entries in the background."""

    def __init__(
        self,
        *,
        client: JsonCompletionClient | None = None,
        model: str = PROACTIVE_MODEL,
        cache: PrecomputeCache | None = None,
        likelihood_threshold: float = LIKELIHOOD_THRESHOLD,
    ) -> None:
        self._client = client
        self._model = model
        self._cache = cache or GLOBAL_PRECOMPUTE_CACHE
        self._likelihood_threshold = likelihood_threshold
        self._background_tasks: set[asyncio.Task[Any]] = set()

    async def anticipate(
        self,
        synthesized: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
    ) -> ProactiveActions:
        """Predict next likely actions for the current response."""
        if intent.out_of_scope:
            return ProactiveActions()

        raw = await self._predict(synthesized, intent, context)
        actions = ProactiveActions.from_dict(raw)
        actions.predicted_actions = [
            action for action in actions.predicted_actions if action.suggestion_text
        ][:5]
        logger.info(
            "[ProactiveIntelligence] intent=%r predictions=%d",
            intent.specific_intent[:80],
            len(actions.predicted_actions),
        )
        return actions

    def schedule_precompute(
        self,
        proactive: ProactiveActions,
        *,
        session_id: str,
        runner: PrecomputeRunner,
    ) -> ProactiveActions:
        """Launch background tasks for high-likelihood pre-computable actions."""
        if not session_id:
            return proactive

        scheduled = 0
        for action in proactive.predicted_actions:
            if scheduled >= MAX_BACKGROUND_TASKS:
                break
            if action.likelihood < self._likelihood_threshold:
                continue
            if not action.pre_computable:
                continue
            if not action.query_message.strip():
                continue

            key = self._cache.mark_pending(
                session_id,
                suggestion_text=action.suggestion_text,
                query_message=action.query_message,
            )
            proactive.scheduled_cache_keys.append(key)
            task = asyncio.create_task(
                runner(
                    session_id=session_id,
                    cache_key=key,
                    query_message=action.query_message,
                    suggestion_text=action.suggestion_text,
                ),
            )
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
            scheduled += 1
            logger.info(
                "[ProactiveIntelligence] scheduled precompute key=%s query=%r",
                key,
                action.query_message[:80],
            )
        return proactive

    async def _predict(
        self,
        synthesized: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
    ) -> dict[str, Any]:
        if self._client is not None:
            try:
                prompt = self._build_prompt(synthesized, intent, context)
                raw = await self._client.complete_json(
                    model=self._model,
                    prompt=prompt,
                    max_tokens=900,
                )
                return json.loads(self._extract_json(raw))
            except Exception as exc:
                logger.warning("[ProactiveIntelligence] Claude prediction failed: %s", exc)

        return self._rule_based_prediction(synthesized, intent, context)

    def _build_prompt(
        self,
        synthesized: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
    ) -> str:
        narrative = synthesized.text[:500]
        visual_type = (synthesized.visualization or {}).get("visual_type") or "NONE"
        return (
            "You predict the next likely user actions after an ERP assistant response.\n"
            f"User query: {intent.specific_intent}\n"
            f"Primary action: {intent.primary_action}\n"
            f"Subject area: {intent.subject_area}\n"
            f"Response narrative: {narrative}\n"
            f"Visualization type: {visual_type}\n"
            f"User role: {context.user.primary_role}\n"
            f"User patterns: {json.dumps(context.working_memory.user_patterns, default=str)}\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "predicted_actions": [\n'
            "    {\n"
            '      "action": "short label",\n'
            '      "likelihood": 0.0,\n'
            '      "pre_computable": true,\n'
            '      "suggestion_text": "Chip label (4-12 words)",\n'
            '      "query_message": "Full query to run if user clicks the chip"\n'
            "    }\n"
            "  ],\n"
            '  "pre_compute_recommendations": ["optional notes"]\n'
            "}\n"
            "Rules:\n"
            "- Return exactly 3 predicted_actions when possible.\n"
            "- Mark drill-down period comparisons and exports as pre_computable when they map to data tools.\n"
            "- suggestion_text must be specific to entities/periods just shown.\n"
            "- query_message must be a complete standalone user query.\n"
            "- Do not predict unavailable HR/payroll capabilities.\n"
        )

    @staticmethod
    def _extract_json(raw_response: str) -> str:
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def _rule_based_prediction(
        synthesized: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
    ) -> dict[str, Any]:
        """Deterministic fallback when Claude is unavailable."""
        del context
        actions: list[dict[str, Any]] = []
        top_client = _top_client_from_visualization(synthesized.visualization)
        visual_type = (synthesized.visualization or {}).get("visual_type") or ""

        if intent.primary_action == "compare" and top_client:
            actions.extend([
                {
                    "action": "compare_expenses",
                    "likelihood": 0.82,
                    "pre_computable": True,
                    "suggestion_text": f"Compare project expenses for {top_client}",
                    "query_message": f"Compare project expenses for {top_client} last quarter",
                },
                {
                    "action": "export_comparison",
                    "likelihood": 0.74,
                    "pre_computable": False,
                    "suggestion_text": "Export this comparison to Excel",
                    "query_message": "Export the revenue comparison to Excel",
                },
            ])
        elif top_client:
            actions.extend([
                {
                    "action": "compare_period",
                    "likelihood": 0.8,
                    "pre_computable": True,
                    "suggestion_text": f"Compare {top_client} revenue vs last year",
                    "query_message": f"Compare revenue for {top_client} this quarter vs same quarter last year",
                },
                {
                    "action": "drill_expenses",
                    "likelihood": 0.78,
                    "pre_computable": True,
                    "suggestion_text": f"Show project expenses for {top_client}",
                    "query_message": f"Show project expenses for {top_client} last quarter",
                },
            ])

        if visual_type in {"DATA_TABLE", "BAR_CHART"}:
            actions.append({
                "action": "export_table",
                "likelihood": 0.72,
                "pre_computable": False,
                "suggestion_text": "Export this table to Excel",
                "query_message": "Export this table to Excel",
            })

        if not actions:
            actions.append({
                "action": "revenue_by_client",
                "likelihood": 0.75,
                "pre_computable": True,
                "suggestion_text": "Show revenue by client for last quarter",
                "query_message": "Show revenue by client for the last quarter",
            })

        return {
            "predicted_actions": actions[:3],
            "pre_compute_recommendations": [],
        }


def _top_client_from_visualization(visualization: dict[str, Any] | None) -> str | None:
    if not visualization:
        return None
    data = visualization.get("data") or {}
    rows = data.get("rows") or []
    if not rows:
        return None
    first = rows[0]
    if isinstance(first, (list, tuple)) and first:
        label = str(first[0]).strip()
        return label or None
    if isinstance(first, dict):
        for key in ("Client", "client", "name", "label"):
            if first.get(key):
                return str(first[key]).strip()
    return None


def precompute_key_for(session_id: str, query_message: str) -> str:
    """Expose cache fingerprint helper for tests and handlers."""
    return cache_fingerprint(session_id, query_message)
