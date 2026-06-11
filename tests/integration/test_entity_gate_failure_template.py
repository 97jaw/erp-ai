"""Regression tests for entity gate failure template bug (Zayidia analysis)."""

from __future__ import annotations

import pytest

from gateway.core.entity_resolver import EntityResolver, Match, ResolutionResult
from gateway.core.failure_handler import FailureMode, HonestFailureResponder
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.result_synthesizer import ResultSynthesizer
from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
from gateway.intelligent_handler import IntelligentQueryHandler
from tests.core.test_entity_resolver import MockProjectSearch, PROJECT_CATALOG
from tests.integration.test_intelligent_handler import (
    FixedContextStackBuilder,
    FixedIntentAnalyzer,
    StubProactiveIntelligence,
    ZAYIDIA_CATALOG,
    _handler,
    _stack_for_user,
    _super_admin,
)


def _assert_never_data_ambiguous(response_text: str, failure_mode: str | None) -> None:
    lowered = response_text.lower()
    assert failure_mode != FailureMode.DATA_AMBIGUOUS.value
    assert "double-count" not in lowered
    assert "multiple records match" not in lowered


ZAYIDIA_PREFIXED_CATALOG = [
    {
        "id": 14549,
        "name": "1420250016 - Zayidia Boys School",
        "wo_ref_no": "RCC-AA-MOE-2025-016",
        "description": "School renovation",
    },
]


@pytest.mark.asyncio
async def test_zayidia_boys_school_single_match_shows_confirm_not_ambiguous_error() -> None:
    """Test 1: one Odoo match → confirm card, not DATA_AMBIGUOUS."""
    intent = Intent(
        primary_action="other",
        subject_area="general",
        specific_intent="show me Zayidia Boys School costs",
    )
    response = await _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=[PROJECT_CATALOG[3]],
    ).handle("show me Zayidia Boys School costs", _super_admin(), adapter=object(), deep_think=True)

    assert response.awaiting_clarification
    assert response.clarification is not None
    assert response.clarification.get("options")
    _assert_never_data_ambiguous(response.text, response.failure_mode)
    assert "couldn't find" not in response.text.lower()
    assert any(
        "zayidia" in str(option.get("label", "")).lower()
        for option in response.clarification["options"]
    )


@pytest.mark.asyncio
async def test_prefixed_zayidia_name_shows_confirm_card_not_not_found() -> None:
    """Test 2: prefixed Odoo display name → confirm card with WO, not couldn't find."""
    intent = Intent(
        primary_action="other",
        subject_area="general",
        specific_intent="show me Zayidia Boys School costs",
    )
    response = await _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=ZAYIDIA_PREFIXED_CATALOG,
    ).handle("show me Zayidia Boys School costs", _super_admin(), adapter=object(), deep_think=True)

    assert response.awaiting_clarification
    assert response.clarification is not None
    assert response.clarification.get("reason") == "entity_confirmation"
    _assert_never_data_ambiguous(response.text, response.failure_mode)
    assert "couldn't find" not in response.text.lower()
    combined = f"{response.text} {response.clarification}".lower()
    assert "rcc-aa-moe-2025-016" in combined or "zayidia" in combined
    assert response.clarification.get("options")
    assert any(
        option.get("action") == "confirm_entity"
        for option in response.clarification["options"]
    )


@pytest.mark.asyncio
async def test_nonexistent_project_shows_not_found_with_broaden_options() -> None:
    """Test 5: zero matches → couldn't find copy + broaden actions, no real WO numbers."""
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="show me XYZABC123 costs",
        entities=[EntityReference(type="project", value="XYZABC123", confidence=0.9)],
    )
    response = await _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=[],
    ).handle("show me XYZABC123 costs", _super_admin(), adapter=object(), deep_think=True)

    assert response.awaiting_clarification
    assert response.clarification is not None
    assert response.clarification.get("reason") == "entity_not_found"
    _assert_never_data_ambiguous(response.text, response.failure_mode)
    assert "couldn't find a project" in response.text.lower()
    combined = f"{response.text} {response.clarification}"
    assert "RCC-AA-MOE-2025-016" not in combined
    options = response.clarification.get("options") or []
    actions = {option.get("action") for option in options}
    assert "search_broader_entity" in actions
    assert "try_different_name" in actions


@pytest.mark.asyncio
async def test_zayidia_two_matches_shows_candidate_list() -> None:
    """Test 3: two Zayidia matches → pick-from-list clarification."""
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="Zayidia project costs",
        entities=[EntityReference(type="project", value="Zayidia", confidence=0.85)],
    )
    zayidia_only = [p for p in ZAYIDIA_CATALOG if "zayidia" in p["name"].lower()][:2]
    response = await _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=zayidia_only,
    ).handle("Show me the Zayidia project costs", _super_admin(), adapter=object(), deep_think=True)

    assert response.awaiting_clarification
    assert response.clarification is not None
    options = response.clarification.get("options") or []
    assert len(options) >= 2
    _assert_never_data_ambiguous(response.text, response.failure_mode)


@pytest.mark.asyncio
async def test_match_with_wo_ref_never_classified_not_found() -> None:
    """Test 4: discovery rows with WO ref → confirm candidate, never not_found."""
    from gateway.core.entity_gate import EntityGate

    gate = EntityGate(object())
    gate._project_resolver = __import__(
        "gateway.core.entity_resolver",
        fromlist=["EntityResolver"],
    ).EntityResolver(
        __import__(
            "tests.core.test_entity_resolver",
            fromlist=["MockProjectSearch"],
        ).MockProjectSearch(ZAYIDIA_PREFIXED_CATALOG),
    )
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="show me Zayidia Boys School costs",
        entities=[EntityReference(type="project", value="Zayidia Boys School", confidence=0.9)],
    )
    from tests.core.test_context_stack import _make_context_stack

    result = await gate.evaluate(
        intent,
        _make_context_stack(primary_role="super_admin", level=100),
        "show me Zayidia Boys School costs",
    )
    assert result.status != "not_found"
    assert result.options
    assert result.matches[0].get("wo_ref_no") == "RCC-AA-MOE-2025-016"


def test_entity_resolution_stage_never_maps_to_data_ambiguous() -> None:
    """grep-level guarantee — entity_resolution never yields DATA_AMBIGUOUS."""
    outcomes = ("not_found", "needs_confirm", "ambiguous", "exception")
    for outcome in outcomes:
        failure = HonestFailureResponder.failure_from_entity_resolution(
            outcome,
            "show me Zayidia Boys School costs",
            exc=ValueError("adapter timeout"),
            query_label="Zayidia Boys School",
            matches=[{"name": "A"}, {"name": "B"}],
        )
        if outcome == "needs_confirm":
            assert failure is None
        else:
            assert failure is not None
            assert failure.mode != FailureMode.DATA_AMBIGUOUS

    stage_failure = HonestFailureResponder.failure_from_stage(
        "entity_resolution",
        ValueError("No matching records found for project"),
        "show me Zayidia Boys School costs",
    )
    assert stage_failure is not None
    assert stage_failure.mode == FailureMode.NO_DATA_FOUND
    assert stage_failure.mode != FailureMode.DATA_AMBIGUOUS

    ambiguous_failure = HonestFailureResponder.failure_from_stage(
        "entity_resolution",
        ValueError("Multiple matches found for Zayidia"),
        "show me Zayidia costs",
    )
    assert ambiguous_failure is not None
    assert ambiguous_failure.mode == FailureMode.AMBIGUOUS_REFERENCE


@pytest.mark.asyncio
async def test_entity_gate_candidates_override_intent_clarification() -> None:
    """Entity gate matches win over Claude's generic requires_clarification text."""
    from gateway.core.entity_resolver import EntityResolver
    from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
    from gateway.intelligent_handler import IntelligentQueryHandler
    from tests.core.test_entity_resolver import MockProjectSearch, PROJECT_CATALOG
    from tests.integration.test_intelligent_handler import (
        FixedContextStackBuilder,
        FixedIntentAnalyzer,
        StubProactiveIntelligence,
        _stack_for_user,
        _super_admin,
    )

    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="national guard expenses",
        entities=[EntityReference(type="project", value="national guard", confidence=0.9)],
        requires_clarification=True,
        clarification_question="Which project did you mean?",
    )
    handler = IntelligentQueryHandler(
        context_builder=FixedContextStackBuilder(_stack_for_user(_super_admin())),
        intent_analyzer=FixedIntentAnalyzer(intent),
        entity_resolver=EntityResolver(MockProjectSearch(PROJECT_CATALOG)),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )
    response = await handler.handle(
        "national guard expenses",
        _super_admin(),
        adapter=object(),
        deep_think=True,
    )

    assert response.awaiting_clarification
    assert response.clarification is not None
    assert response.clarification.get("reason") == "entity_confirmation"
    assert response.clarification.get("options")
    assert "which project did you mean" not in response.text.lower()
    assert "couldn't find" not in response.text.lower()


@pytest.mark.asyncio
async def test_entity_gate_transient_error_shows_honest_message() -> None:
    from gateway.core.entity_resolver import EntityResolver
    from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
    from gateway.intelligent_handler import IntelligentQueryHandler
    from tests.core.test_entity_resolver import MockProjectSearch
    from tests.integration.test_intelligent_handler import (
        FixedContextStackBuilder,
        FixedIntentAnalyzer,
        StubProactiveIntelligence,
        _stack_for_user,
        _super_admin,
    )

    class _FlakyResolver(EntityResolver):
        async def resolve_project(self, query, context, min_confidence=0.6):
            del query, context, min_confidence
            raise ConnectionError("502 Bad Gateway")

    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="national guard expenses",
        entities=[EntityReference(type="project", value="national guard", confidence=0.9)],
    )
    handler = IntelligentQueryHandler(
        context_builder=FixedContextStackBuilder(_stack_for_user(_super_admin())),
        intent_analyzer=FixedIntentAnalyzer(intent),
        entity_resolver=_FlakyResolver(MockProjectSearch([])),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )
    response = await handler.handle(
        "national guard expenses",
        _super_admin(),
        adapter=object(),
        deep_think=True,
    )

    assert response.awaiting_clarification
    assert "trouble reaching the database" in response.text.lower()
    assert "couldn't find" not in response.text.lower()
    assert response.clarification is not None
    assert response.clarification.get("reason") == "transient_error"


@pytest.mark.asyncio
async def test_weak_match_shown_with_caveat_not_discarded() -> None:
    """Weak confidence tier → possible-match caveat, not not_found."""
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="show me Zayidia Boys School costs",
        entities=[EntityReference(type="project", value="Zayidia Boys School", confidence=0.9)],
    )

    class _LowConfidenceResolver(EntityResolver):
        async def resolve_project(self, query, context, min_confidence=0.6):
            del query, context, min_confidence
            weak = Match(
                entity=PROJECT_CATALOG[3],
                confidence=0.45,
                strategy="all_words_match",
            )
            return ResolutionResult(
                query="Zayidia Boys School",
                total_matches=1,
                confident_matches=[],
                weak_matches=[weak],
                raw_discovery_count=1,
                top_match=weak,
                confidence=0.45,
                winning_strategy="all_words_match",
                ambiguity_level="weak_matches",
                strategies_used=["all_words_match"],
            )

    handler = IntelligentQueryHandler(
        context_builder=FixedContextStackBuilder(_stack_for_user(_super_admin())),
        intent_analyzer=FixedIntentAnalyzer(intent),
        entity_resolver=_LowConfidenceResolver(MockProjectSearch(PROJECT_CATALOG)),
        proactive_layer=StubProactiveIntelligence(),
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
        synthesizer=ResultSynthesizer(),
    )

    response = await handler.handle(
        "show me Zayidia Boys School costs",
        _super_admin(),
        adapter=object(),
        deep_think=True,
    )

    assert response.awaiting_clarification
    assert "possible match" in response.text.lower()
    _assert_never_data_ambiguous(response.text, response.failure_mode)
    assert response.clarification is not None
    assert response.clarification.get("options")
    assert response.clarification["options"][0].get("weak_match") is True
