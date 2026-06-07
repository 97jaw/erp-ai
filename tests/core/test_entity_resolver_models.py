"""Tests for gateway.core.entity_resolver data models."""

from __future__ import annotations

from gateway.core.entity_resolver import (
    AMBIGUITY_LEVELS,
    Decision,
    Match,
    ResolutionResult,
)


def test_match_instantiates_with_all_fields() -> None:
    match = Match(
        entity={"id": 42, "name": "National Guard HQ"},
        confidence=0.92,
        strategy="exact_phrase_match",
    )

    assert match.entity == {"id": 42, "name": "National Guard HQ"}
    assert match.confidence == 0.92
    assert match.strategy == "exact_phrase_match"


def test_resolution_result_instantiates_correctly() -> None:
    top = Match(
        entity={"id": 7, "name": "National Guard"},
        confidence=0.95,
        strategy="all_words_match",
    )
    result = ResolutionResult(
        query="national guard",
        total_matches=3,
        confident_matches=[top],
        top_match=top,
        confidence=0.95,
        ambiguity_level="unambiguous",
        strategies_used=["exact_phrase_match", "all_words_match"],
    )

    assert result.query == "national guard"
    assert result.total_matches == 3
    assert len(result.confident_matches) == 1
    assert result.top_match is top
    assert result.confidence == 0.95
    assert result.ambiguity_level == "unambiguous"
    assert result.strategies_used == ["exact_phrase_match", "all_words_match"]


def test_decision_with_use_match_action_works() -> None:
    match = Match(
        entity={"id": 1, "name": "Zayidia Boys School"},
        confidence=0.98,
        strategy="exact_phrase_match",
    )
    decision = Decision(
        action="use_match",
        match=match,
        note="Resolved unambiguously to Zayidia Boys School",
    )

    assert decision.action == "use_match"
    assert decision.match is match
    assert decision.alternatives == []
    assert decision.note == "Resolved unambiguously to Zayidia Boys School"


def test_ambiguity_levels_are_the_correct_strings() -> None:
    assert AMBIGUITY_LEVELS == (
        "no_match",
        "unambiguous",
        "clear_winner",
        "multiple_strong",
        "weak_matches",
    )


def test_match_with_confidence_one_point_zero_is_valid() -> None:
    match = Match(
        entity={"id": 99, "name": "National Guard"},
        confidence=1.0,
        strategy="exact_phrase_match",
    )

    assert match.confidence == 1.0


def test_match_with_confidence_zero_point_zero_is_valid() -> None:
    match = Match(
        entity={"id": 100, "name": "Unknown Project"},
        confidence=0.0,
        strategy="fuzzy_match",
    )

    assert match.confidence == 0.0


def test_resolution_result_with_empty_confident_matches_is_valid() -> None:
    result = ResolutionResult(
        query="missing project",
        total_matches=0,
        confident_matches=[],
        top_match=None,
        confidence=0.0,
        ambiguity_level="no_match",
        strategies_used=["exact_phrase_match", "fuzzy_match"],
    )

    assert result.confident_matches == []
    assert result.top_match is None
    assert result.confidence == 0.0
    assert result.ambiguity_level == "no_match"
