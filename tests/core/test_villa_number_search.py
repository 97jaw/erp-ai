"""Tests for villa number + maintenance typo entity resolution."""

from __future__ import annotations

import pytest

from gateway.core.entity_gate import EntityGate, _project_discovery_query
from gateway.core.entity_resolver import EntityResolver, _villa_number_ilike_domain
from gateway.core.intent_analyzer import EntityReference, Intent
from gateway.core.project_query_utils import (
    extract_project_number_hint,
    extract_suggestion_tokens,
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


def test_token_search_uses_villa_and_maintenance() -> None:
    tokens = extract_suggestion_tokens("expense for villa maintanence No. 37")
    assert "villa" in tokens
    assert "maintenance" in tokens


@pytest.mark.asyncio
async def test_villa_maintenance_number_suggests_maintenance_sibling() -> None:
    """When Villa 37 is missing, suggest Villa Maintenance 34 over unrelated Villa 37."""
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
    assert result.status == "weak_confirmation"
    assert result.entity_near_miss is True
    labels = " ".join(str(option.get("label", "")) for option in result.options)
    assert "34" in labels
    assert result.options[0].get("entity_id") == 15157


class _NearMissCallCounter(MockProjectSearch):
    """Tracks Odoo search_projects calls during entity gate evaluation."""

    def __init__(self, catalog: list) -> None:
        super().__init__(catalog)
        self.call_count = 0

    async def search_projects(self, domain: list, *, limit: int = 20) -> list:
        self.call_count += 1
        return await super().search_projects(domain, limit=limit)


@pytest.mark.asyncio
async def test_villa_37_missing_suggests_from_resolver_pool() -> None:
    """Near-miss reuses Phase A pool without additional Odoo search_projects calls."""
    catalog_without_37 = [p for p in VILLA_CATALOG if p["id"] != 15158]
    maintenance_pool = [
        type("M", (), {"entity": project})()
        for project in catalog_without_37
        if "Maintenance" in project["name"]
    ]
    search = _NearMissCallCounter(catalog_without_37)
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(search)
    message = "expense for villa maintanence No. 37"
    baseline = search.call_count
    related = await gate._discover_related_projects(
        "villa maintanence 37",
        message,
        _make_context_stack(),
        pool_matches=maintenance_pool,
    )
    assert search.call_count == baseline
    assert len(related) >= 2
    labels = " ".join(str(item.get("name", "")) for item in related)
    assert "34" in labels
    assert "48" in labels


@pytest.mark.asyncio
async def test_villa_37_missing_suggests_maintenance_siblings() -> None:
    catalog_without_37 = [p for p in VILLA_CATALOG if p["id"] != 15158]
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(catalog_without_37))
    message = "expense for villa maintanence No. 37"
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent=message,
        entities=[EntityReference(type="project", value="villa maintanence", confidence=0.9)],
    )
    result = await gate.evaluate(intent, _make_context_stack(), message)
    assert result.status == "weak_confirmation"
    assert result.entity_near_miss is True
    labels = " ".join(str(option.get("label", "")) for option in result.options)
    assert "34" in labels
    assert "48" in labels


@pytest.mark.asyncio
async def test_true_not_found_when_no_token_overlap() -> None:
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(
        MockProjectSearch(
            [
                {
                    "id": 1,
                    "name": "Zayidia Boys School Renovation",
                    "wo_ref_no": "WO-001",
                },
            ],
        ),
    )
    message = "expense for xyzzy qwerty"
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent=message,
        entities=[EntityReference(type="project", value="xyzzy qwerty", confidence=0.9)],
    )
    result = await gate.evaluate(intent, _make_context_stack(), message)
    assert result.status == "not_found"
    assert not result.options
