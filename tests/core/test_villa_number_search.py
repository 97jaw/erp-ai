"""Tests for villa number + maintenance typo entity resolution."""

from __future__ import annotations

import pytest

from gateway.core.entity_gate import EntityGate, _project_discovery_query
from gateway.core.entity_resolver import EntityResolver, _villa_number_ilike_domain
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.project_query_utils import (
    extract_project_number_hint,
    normalize_project_search_tokens,
    project_record_matches_number,
)
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_entity_resolver import MockProjectSearch

VILLA_CATALOG = [
    {
        "id": 17001,
        "name": "General maintenance for Villa 17 - Officers' Villas, Falaj Hazza, Villa 7",
        "wo_ref_no": "W.O 1420230065-90",
    },
    {
        "id": 15157,
        "name": "Villa Maintenance No. 34",
        "wo_ref_no": "1420240098-38",
    },
    {
        "id": 15158,
        "name": "Villa Maintenance No. 37",
        "wo_ref_no": "1420240098-37",
    },
    {
        "id": 15159,
        "name": "Villa Maintenance No . 48",
        "wo_ref_no": "1420240098-35",
    },
]

FULL_VILLA_CATALOG = [
    *VILLA_CATALOG[:1],
    {
        "id": 19019,
        "name": "Falej Hazza Villas – Al Ain, Villa No. – Housing Department – Al Ain Region",
        "wo_ref_no": "1420240098-19",
    },
    *VILLA_CATALOG[1:],
    {
        "id": 16202,
        "name": "Comprehensive building maintenance - Al Waqan Police Station",
        "wo_ref_no": "1420200102-162",
    },
]


def test_extract_project_number_hint_from_typo_query() -> None:
    assert extract_project_number_hint("expense for villa maintanence 37") == "37"


def test_normalize_maintenance_typo() -> None:
    tokens = normalize_project_search_tokens("villa maintanence 37")
    assert "maintenance" in tokens
    assert "37" in tokens


def test_project_record_matches_number() -> None:
    assert project_record_matches_number({"name": "Villa Maintenance No. 37"}, "37")
    assert project_record_matches_number({"name": "Villa Maintenance No . 37"}, "37")
    assert not project_record_matches_number({"name": "Villa Maintenance No. 34"}, "37")


def test_project_discovery_query_prefers_message_number() -> None:
    message = "expense for villa maintanence 37"
    assert _project_discovery_query(message, "villa maintanence") == "villa maintanence 37"


def test_infer_required_entities_preserves_number_from_message() -> None:
    message = "expense for villa maintanence 37"
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent=message,
        entities=[EntityReference(type="project", value="villa maintanence", confidence=0.9)],
    )
    required = EntityGate.infer_required_entities(message, intent)
    assert required == [("project", "villa maintanence 37")]


def test_villa_number_ilike_domain_includes_spaced_no_dot() -> None:
    domain = _villa_number_ilike_domain("37")
    flat = " ".join(str(part) for part in domain)
    assert "No . 37" in flat
    assert "Maintenance No . 37" in flat


@pytest.mark.asyncio
async def test_villa_37_typo_query_auto_confirms() -> None:
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(VILLA_CATALOG))
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="expense for villa maintanence 37",
        entities=[EntityReference(type="project", value="villa maintanence 37", confidence=0.9)],
    )
    result = await gate.evaluate(
        intent,
        _make_context_stack(),
        "expense for villa maintanence 37",
    )
    assert result.status == "confirmed"
    assert result.confirmed["project"]["id"] == 15158
    assert "37" in result.confirmed["project"]["name"]


@pytest.mark.asyncio
async def test_villa_37_intent_missing_number_auto_confirms() -> None:
    """LLM entity fragment without 37 must still resolve Villa 37 from the message."""
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(FULL_VILLA_CATALOG))
    message = "expense for villa maintanence 37"
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent=message,
        entities=[EntityReference(type="project", value="villa maintanence", confidence=0.9)],
    )
    result = await gate.evaluate(intent, _make_context_stack(), message)
    assert result.status == "confirmed"
    assert result.confirmed["project"]["id"] == 15158
    labels = " ".join(str(option.get("label", "")) for option in result.options)
    assert "34" not in labels


@pytest.mark.asyncio
async def test_villa_37_no_dot_spacing_resolves() -> None:
    catalog = [
        {
            "id": 15160,
            "name": "Villa Maintenance No . 37",
            "wo_ref_no": "1420240098-37",
        },
        {
            "id": 15157,
            "name": "Villa Maintenance No. 34",
            "wo_ref_no": "1420240098-38",
        },
    ]
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(catalog))
    message = "expense for villa maintenance 37"
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent=message,
        entities=[EntityReference(type="project", value="villa maintenance", confidence=0.9)],
    )
    result = await gate.evaluate(intent, _make_context_stack(), message)
    assert result.status == "confirmed"
    assert result.confirmed["project"]["id"] == 15160


@pytest.mark.asyncio
async def test_villa_maintenance_number_rejects_unrelated_villa_name() -> None:
    """A generic 'Villa 37' project must not match a 'villa maintenance 37' query."""
    catalog = [
        {
            "id": 99001,
            "name": "Request for AC replacement - Villa 37 - Al Ain City",
            "wo_ref_no": "1420240101-019",
        },
        {
            "id": 15157,
            "name": "Villa Maintenance No. 34",
            "wo_ref_no": "1420240098-38",
        },
    ]
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(catalog))
    message = "expense for villa maintanence 37"
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent=message,
        entities=[EntityReference(type="project", value="villa maintanence", confidence=0.9)],
    )
    result = await gate.evaluate(intent, _make_context_stack(), message)
    assert result.status == "not_found"


@pytest.mark.asyncio
async def test_villa_37_missing_returns_not_found_not_villa_34() -> None:
    catalog_without_37 = [p for p in VILLA_CATALOG if p["id"] != 15158]
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(catalog_without_37))
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="expense for villa maintanence 37",
        entities=[EntityReference(type="project", value="villa maintanence 37", confidence=0.9)],
    )
    result = await gate.evaluate(
        intent,
        _make_context_stack(),
        "expense for villa maintanence 37",
    )
    assert result.status == "not_found"
    labels = " ".join(str(option.get("label", "")) for option in result.options)
    assert "34" not in labels
