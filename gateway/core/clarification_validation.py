"""Strip premature format clarifications from analyzed intents (Phase F5)."""

from __future__ import annotations

import re
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.core.intent_analyzer import Intent

FORMAT_KEYWORDS = (
    "pdf",
    "excel",
    "format",
    "csv",
    "xlsx",
    "download",
    "spreadsheet",
)

ENTITY_KEYWORDS = (
    "which",
    "what project",
    "what client",
    "specify",
    "confirm",
    "project name",
    "project id",
    "exact project",
    "did you mean",
    "provide the project",
)

CLARIFICATION_PROMPT_RULES = """
CLARIFICATION RULES:
1. ENTITY ambiguity → requires_clarification=true only when entity resolution truly needs user input.
2. PERIOD ambiguity → do NOT clarify. Use a sensible default (last 3 months) and mention it inline.
3. OUTPUT FORMAT ambiguity → NEVER clarify upfront. Offer PDF/Excel as suggestions after data is shown.
4. SCOPE ambiguity (summary vs detailed) → default to summary; offer drill-down as a suggestion.
5. Multiple ambiguities → clarify the highest-severity one only. Never ask 2+ questions at once.
When in doubt: resolve and show data, state assumptions inline, offer changes as suggestions.
Never put PDF, Excel, CSV, or download format questions in clarification_question.
"""


def _is_entity_clarification(question_lower: str) -> bool:
    return any(keyword in question_lower for keyword in ENTITY_KEYWORDS)


def _strip_format_sentences(question: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", question.strip())
    kept = [
        part.strip()
        for part in parts
        if part.strip() and not any(keyword in part.lower() for keyword in FORMAT_KEYWORDS)
    ]
    return " ".join(kept).strip()


def validate_clarification(intent: Intent) -> Intent:
    """Remove blocking format questions; keep entity clarifications."""
    question = intent.clarification_question
    if not question:
        if intent.requires_clarification:
            return replace(intent, requires_clarification=False)
        return intent

    question_lower = question.lower()
    if not any(keyword in question_lower for keyword in FORMAT_KEYWORDS):
        return intent

    if not _is_entity_clarification(question_lower):
        return replace(
            intent,
            requires_clarification=False,
            clarification_question=None,
        )

    cleaned_question = _strip_format_sentences(question)
    if not cleaned_question:
        return replace(
            intent,
            requires_clarification=False,
            clarification_question=None,
        )
    return replace(
        intent,
        clarification_question=cleaned_question,
        requires_clarification=True,
    )
