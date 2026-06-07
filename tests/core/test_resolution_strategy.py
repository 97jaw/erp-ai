"""Tests for gateway.core.entity_resolver.ResolutionStrategy."""

from __future__ import annotations

from gateway.core.entity_resolver import Match, ResolutionResult, ResolutionStrategy
from tests.core.test_context_stack import _make_context_stack


def _match(entity_id: int, name: str, confidence: float) -> Match:
    return Match(
        entity={"id": entity_id, "name": name},
        confidence=confidence,
        strategy="exact_phrase_match",
    )


def _result(
    matches: list[Match],
    *,
    ambiguity_level: str = "unambiguous",
) -> ResolutionResult:
    return ResolutionResult(
        query="national guard",
        total_matches=len(matches),
        confident_matches=matches,
        top_match=matches[0] if matches else None,
        confidence=matches[0].confidence if matches else 0.0,
        ambiguity_level=ambiguity_level,
        strategies_used=["exact_phrase_match"],
    )


def test_no_matches_returns_search_broader() -> None:
    strategy = ResolutionStrategy()
    decision = strategy.decide(_result([]), _make_context_stack())

    assert decision.action == "search_broader"
    assert decision.match is None


def test_one_match_requires_confirmation() -> None:
    strategy = ResolutionStrategy()
    match = _match(1, "National Guard HQ", 0.95)
    decision = strategy.decide(_result([match]), _make_context_stack())

    assert decision.action == "show_candidates"
    assert decision.alternatives == [match]


def test_clear_winner_requires_confirmation_for_all_users() -> None:
    strategy = ResolutionStrategy()
    matches = [
        _match(1, "National Guard HQ", 0.92),
        _match(2, "National Guard Network", 0.45),
    ]
    regular = strategy.decide(
        _result(matches, ambiguity_level="clear_winner"),
        _make_context_stack(level=30),
    )
    admin = strategy.decide(
        _result(matches, ambiguity_level="clear_winner"),
        _make_context_stack(primary_role="super_admin", level=100),
    )

    assert regular.action == "show_candidates"
    assert admin.action == "show_candidates"
    assert len(regular.alternatives) == 2


def test_multiple_strong_always_returns_show_candidates() -> None:
    strategy = ResolutionStrategy()
    matches = [
        _match(1, "National Guard HQ", 0.88),
        _match(2, "National Guard Network", 0.82),
        _match(3, "National Guard Training", 0.79),
    ]
    context = _make_context_stack(primary_role="super_admin", level=100)
    decision = strategy.decide(
        _result(matches, ambiguity_level="multiple_strong"),
        context,
    )

    assert decision.action == "show_candidates"
    assert len(decision.alternatives) == 3


def test_weak_matches_returns_show_candidates() -> None:
    strategy = ResolutionStrategy()
    matches = [
        _match(1, "Guard Services", 0.55),
        _match(2, "National Services", 0.52),
    ]
    decision = strategy.decide(
        _result(matches, ambiguity_level="weak_matches"),
        _make_context_stack(),
    )

    assert decision.action == "show_candidates"
    assert len(decision.alternatives) == 2


def test_decision_always_has_a_note_string() -> None:
    strategy = ResolutionStrategy()
    scenarios = [
        _result([]),
        _result([_match(1, "National Guard HQ", 0.95)]),
        _result(
            [_match(1, "National Guard HQ", 0.92), _match(2, "National Guard Network", 0.45)],
            ambiguity_level="clear_winner",
        ),
    ]

    for result in scenarios:
        decision = strategy.decide(result, _make_context_stack(level=30))
        assert isinstance(decision.note, str)
        assert decision.note.strip()
