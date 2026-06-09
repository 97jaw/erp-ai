"""Tests for gateway.core.clarification_validation (Phase F5)."""

from __future__ import annotations

from gateway.core.clarification_validation import validate_clarification
from gateway.core.intent_analyzer import Intent


def _intent(**overrides) -> Intent:
    defaults = {
        "primary_action": "fetch_data",
        "subject_area": "project",
        "specific_intent": "expense report",
    }
    defaults.update(overrides)
    return Intent(**defaults)


def test_pure_format_clarification_stripped() -> None:
    intent = _intent(
        requires_clarification=True,
        clarification_question="Would you prefer PDF or Excel format?",
    )

    cleaned = validate_clarification(intent)

    assert cleaned.requires_clarification is False
    assert cleaned.clarification_question is None


def test_entity_clarification_kept() -> None:
    intent = _intent(
        requires_clarification=True,
        clarification_question="Which Al Mushrif project did you mean?",
    )

    cleaned = validate_clarification(intent)

    assert cleaned.requires_clarification is True
    assert cleaned.clarification_question is not None
    assert "Al Mushrif" in cleaned.clarification_question


def test_mixed_clarification_keeps_entity_strips_format() -> None:
    intent = _intent(
        requires_clarification=True,
        clarification_question=(
            "Could you confirm which Al Mushrif project. "
            "Also, would you prefer PDF or Excel format?"
        ),
    )

    cleaned = validate_clarification(intent)

    assert cleaned.requires_clarification is True
    assert cleaned.clarification_question is not None
    assert "Al Mushrif" in cleaned.clarification_question
    assert "PDF" not in cleaned.clarification_question
    assert "Excel" not in cleaned.clarification_question


def test_requires_clarification_without_question_is_cleared() -> None:
    intent = _intent(requires_clarification=True, clarification_question=None)

    cleaned = validate_clarification(intent)

    assert cleaned.requires_clarification is False
