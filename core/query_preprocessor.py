"""
OOA Core — Query Preprocessor (Production Rewrite)
====================================================
File    : core/query_preprocessor.py
Author  : Lead Backend Developer
Version : 2.0.0

Handles ONLY two concerns:
    1. Format switch detection  → "show as table", "show as chart"
    2. Re-render detection      → same data, different format

Everything else (intent, routing, parameters) is handled by Claude
in IntentClassifierNode. No phrase mapping. No fragile string matching
for business logic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from core.state import AgentState, VisualType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Format Switch Patterns — ONLY visual format keywords
# ---------------------------------------------------------------------------

FORMAT_PATTERNS = {
    # English
    "table view"  : VisualType.DATA_TABLE,
    "as table"    : VisualType.DATA_TABLE,
    "in table"    : VisualType.DATA_TABLE,
    "list view"   : VisualType.DATA_TABLE,
    "as list"     : VisualType.DATA_TABLE,
    "bar chart"   : VisualType.BAR_CHART,
    "as chart"    : VisualType.BAR_CHART,
    "as bar chart": VisualType.BAR_CHART,
    "line chart"  : VisualType.LINE_CHART,
    "as line"     : VisualType.LINE_CHART,
    "kpi card"    : VisualType.KPI_CARD,
    "as card"     : VisualType.KPI_CARD,
    "as summary"  : VisualType.KPI_CARD,
    "pivot table" : VisualType.PIVOT_TABLE,
    "as pivot"    : VisualType.PIVOT_TABLE,
    # Arabic — ONLY visual format words, not business terms
    "كجدول"       : VisualType.DATA_TABLE,
    "جدول بيانات" : VisualType.DATA_TABLE,
    "كمخطط"       : VisualType.BAR_CHART,
    "رسم بياني"   : VisualType.BAR_CHART,
    "كبطاقة"      : VisualType.KPI_CARD,
}

# Re-render trigger phrases
RERENDER_TRIGGERS_EN = [
    "show as", "display as", "view as",
    "convert to", "change to", "switch to",
]
RERENDER_TRIGGERS_AR = [
    "اعرض كـ", "أظهر كـ", "حوّل إلى",
]


# ---------------------------------------------------------------------------
# Preprocessor Result
# ---------------------------------------------------------------------------

@dataclass
class PreprocessorResult:
    should_short_circuit : bool = False
    is_rerender          : bool = False
    is_format_switch     : bool = False
    visual_override      : VisualType | None = None
    enriched_input       : str | None = None


# ---------------------------------------------------------------------------
# Query Preprocessor
# ---------------------------------------------------------------------------

class QueryPreprocessor:
    """
    Lightweight preprocessor — format switches and re-render only.
    All business logic and intent classification handled by Claude.
    """

    def process(self, state: AgentState) -> PreprocessorResult:
        raw  = state.turn.raw_input.strip()
        lang = state.turn.input_language or "en"
        result = PreprocessorResult()

        # Detect format switch
        visual = self._detect_format_switch(raw, lang)
        if visual:
            result.is_format_switch = True
            result.visual_override  = visual

            # If existing data → re-render without re-fetching
            if state.session.last_response_data:
                result.should_short_circuit = True
                result.is_rerender          = True
                logger.info(
                    "[Preprocessor] Format switch → %s (re-render)", visual
                )
            else:
                logger.info(
                    "[Preprocessor] Format switch → %s (no data yet)", visual
                )

        # Inject project_id if context exists and input references financial data
        if not result.should_short_circuit:
            enriched = self._try_inject_project_context(raw, state)
            if enriched:
                result.enriched_input = enriched

        return result

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _detect_format_switch(
        self, text: str, lang: str
    ) -> VisualType | None:
        text_lower = text.lower()

        # Check exact phrase patterns
        for phrase, visual in FORMAT_PATTERNS.items():
            if phrase in text_lower:
                return visual

        # Check re-render triggers
        triggers = (
            RERENDER_TRIGGERS_AR if lang == "ar"
            else RERENDER_TRIGGERS_EN
        )
        for trigger in triggers:
            if trigger in text_lower:
                # Extract what comes after the trigger
                idx     = text_lower.find(trigger)
                rest    = text_lower[idx + len(trigger):].strip()
                for phrase, visual in FORMAT_PATTERNS.items():
                    if phrase in rest:
                        return visual

        return None

    def _try_inject_project_context(
        self, text: str, state: AgentState
    ) -> str | None:
        """
        If a project was resolved in the last turn and the current input
        does not already reference a project_id, inject it.
        This helps with follow-up questions like 'show me the expenses'.
        """
        if not state.session.last_resolved_entity:
            return None

        entity = state.session.last_resolved_entity
        pid    = entity.get("id")
        if not pid:
            return None

        # Do not inject if already present
        if f"[project_id={pid}]" in text:
            return None

        # Only inject for financial/project related queries
        financial_keywords = [
            "cost", "expense", "budget", "profit", "margin",
            "breakdown", "report", "trend", "financial", "spending",
            "تكلفة", "مصروف", "ميزانية", "ربح", "تقرير", "إنفاق",
        ]
        text_lower = text.lower()
        if any(kw in text_lower for kw in financial_keywords):
            logger.info(
                "[Preprocessor] Injecting project_id=%d from context", pid
            )
            return f"{text} [project_id={pid}]"

        return None