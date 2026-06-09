"""Tests for gateway.core.entity_gate."""

from __future__ import annotations

import pytest

from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.entity_gate import (
    ConfirmedEntityRef,
    EntityGate,
    build_entity_not_found_clarification,
    build_entity_options,
)
from tests.core.test_context_stack import _make_context_stack


def test_tool_requires_entity_for_project_expenses() -> None:
    assert EntityGate.tool_requires_entity("get_project_expenses") == ["project"]


def test_build_entity_options_includes_confirm_action() -> None:
    options = build_entity_options(
        [{"id": 201, "name": "Zayidia Boys School Renovation", "entity_type": "project", "wo_ref_no": "WO-201"}],
    )
    assert len(options) == 1
    assert options[0]["action"] == "confirm_entity"
    assert options[0]["entity_id"] == 201


def test_infer_required_entities_from_cost_query() -> None:
    intent = Intent(
        primary_action="other",
        subject_area="general",
        specific_intent="show me Zayidia Boys School costs",
    )
    required = EntityGate.infer_required_entities("show me Zayidia Boys School costs", intent)
    assert ("project", "Zayidia Boys School") in required


def test_follow_up_breakdown_skips_entity_confirmation_with_scope() -> None:
    context = _make_context_stack()
    context.working_memory.session_facts["last_expense_summary_project_id"] = 31034
    context.working_memory.session_facts["resolved_project_id"] = 31034
    intent = Intent(
        primary_action="other",
        subject_area="general",
        specific_intent="show me cost break down as well",
        requires_clarification=True,
        clarification_question="Which project would you like to see the cost breakdown for?",
    )
    message = "show me cost break down as well"

    assert EntityGate.infer_required_entities(message, intent, context) == []
    assert not EntityGate.intent_requires_entity_confirmation(message, intent, context)


def test_infer_required_entities_partner_mislabelled_as_project() -> None:
    """Claude often types schools as partner on short follow-up queries."""
    intent = Intent(
        primary_action="search_entity",
        subject_area="general",
        specific_intent="Search for information about Zayidia Boys School entity",
        entities=[EntityReference(type="partner", value="Zayidia Boys School", confidence=0.9)],
    )
    required = EntityGate.infer_required_entities("Zayidia Boys School", intent)
    assert required == [("project", "Zayidia Boys School")]


def test_confirmed_entity_ref_from_dict() -> None:
    parsed = ConfirmedEntityRef.from_dict({"type": "project", "id": 201, "name": "Zayidia Boys"})
    assert parsed is not None
    assert parsed.id == 201
    assert parsed.type == "project"


@pytest.mark.asyncio
async def test_evaluate_single_match_needs_confirmation() -> None:
    from tests.core.test_entity_resolver import MockProjectSearch, PROJECT_CATALOG

    class _Adapter:
        def search_read(self, **kwargs):
            return []

    gate = EntityGate(_Adapter())
    gate._project_resolver = __import__(
        "gateway.core.entity_resolver",
        fromlist=["EntityResolver"],
    ).EntityResolver(MockProjectSearch(PROJECT_CATALOG))

    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="show me Zayidia Boys School costs",
        entities=[EntityReference(type="project", value="Zayidia Boys School", confidence=0.9)],
    )
    context = _make_context_stack()
    result = await gate.evaluate(
        intent,
        context,
        "show me Zayidia Boys School costs",
    )
    assert result.status == "needs_confirmation"
    assert result.options
    assert any("zayidia" in str(option.get("label", "")).lower() for option in result.options)


@pytest.mark.asyncio
async def test_weak_matches_used_when_no_confident_matches() -> None:
    from gateway.core.entity_resolver import EntityResolver, Match
    from tests.core.test_entity_resolver import MockProjectSearch, PROJECT_CATALOG

    class _LowConfidenceResolver(EntityResolver):
        async def resolve_project(self, query, context, min_confidence=0.6):
            del query, context, min_confidence
            weak = Match(
                entity=PROJECT_CATALOG[3],
                confidence=0.45,
                strategy="all_words_match",
            )
            return __import__(
                "gateway.core.entity_resolver",
                fromlist=["ResolutionResult"],
            ).ResolutionResult(
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

    gate = EntityGate(object())
    gate._project_resolver = _LowConfidenceResolver(MockProjectSearch(PROJECT_CATALOG))
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="show me Zayidia Boys School costs",
        entities=[EntityReference(type="project", value="Zayidia Boys School", confidence=0.9)],
    )
    context = _make_context_stack()
    result = await gate.evaluate(
        intent,
        context,
        "show me Zayidia Boys School costs",
    )
    assert result.status == "weak_confirmation"
    assert result.options
    assert result.options[0].get("weak_match") is True


def test_build_entity_not_found_clarification_has_actions() -> None:
    payload = build_entity_not_found_clarification("Zayidia Boys School")
    assert "couldn't find a project" in payload["question"].lower()
    assert len(payload["options"]) == 2
    assert payload["options"][0]["action"] == "search_broader_entity"


@pytest.mark.asyncio
async def test_evaluate_with_confirmed_entities_skips_discovery() -> None:
    gate = EntityGate(object())
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="show me Zayidia Boys School costs",
        entities=[EntityReference(type="project", value="Zayidia Boys School", confidence=0.9)],
    )
    context = _make_context_stack()
    result = await gate.evaluate(
        intent,
        context,
        "show me Zayidia Boys School costs",
        confirmed_entities=[ConfirmedEntityRef(type="project", id=201, name="Zayidia Boys School Renovation")],
    )
    assert result.status == "confirmed"
    assert result.confirmed["project"]["id"] == 201
