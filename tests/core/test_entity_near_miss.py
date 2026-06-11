"""Tests for related-project suggestion on entity near-miss."""

from __future__ import annotations

import pytest

from gateway.core.entity_gate import EntityGate
from gateway.core.entity_resolver import EntityResolver, Match
from gateway.core.project_query_utils import (
    extract_suggestion_tokens,
    rank_related_project,
)
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_entity_resolver import MockProjectSearch


def test_extract_suggestion_tokens_strips_numbers_and_short_words() -> None:
    tokens = extract_suggestion_tokens("expense for villa maintenance No. 37")
    assert tokens == ["villa", "maintenance"]
    assert "37" not in tokens
    assert "no" not in tokens


def test_extract_suggestion_tokens_min_length_three() -> None:
    tokens = extract_suggestion_tokens("ng expense for ab")
    assert tokens == []


def test_rank_related_project_prefers_more_token_overlap() -> None:
    maintenance_project = {"name": "Villa Maintenance No. 34"}
    villa_only = {"name": "Request for AC - Villa 37 - Al Ain"}
    tokens = ["villa", "maintenance"]
    assert rank_related_project(maintenance_project, tokens) > rank_related_project(
        villa_only,
        tokens,
    )


def test_rank_related_project_requires_name_token_overlap() -> None:
    unrelated = {"name": "Zayidia Boys School Renovation"}
    assert rank_related_project(unrelated, ["villa", "maintenance"]) < 0


def test_extract_suggestion_tokens_dedupes_typo() -> None:
    tokens = extract_suggestion_tokens("expense for villa maintanence 37")
    assert tokens == ["villa", "maintenance"]
    assert "maintanence" not in tokens


class _NoOdooSearch(MockProjectSearch):
    """Fails if near-miss tries Odoo when pool already has candidates."""

    async def search_projects(self, domain: list, *, limit: int = 20) -> list:
        raise AssertionError(
            f"search_projects should not run when pool has matches: {domain!r}",
        )


@pytest.mark.asyncio
async def test_rank_from_pool_beats_empty_search() -> None:
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(_NoOdooSearch())
    pool = [
        Match(
            entity={"id": 15157, "name": "Villa Maintenance No. 34"},
            confidence=0.5,
            strategy="test",
        ),
        Match(
            entity={"id": 15159, "name": "Villa Maintenance No . 48"},
            confidence=0.45,
            strategy="test",
        ),
    ]
    related = await gate._discover_related_projects(
        "villa maintenance 37",
        "expense for villa maintenance No. 37",
        _make_context_stack(),
        pool_matches=pool,
    )
    assert len(related) >= 2
    labels = " ".join(str(item.get("name", "")) for item in related)
    assert "34" in labels
    assert "48" in labels


class _CallCountingSearch(MockProjectSearch):
    def __init__(self, catalog: list | None = None) -> None:
        super().__init__(catalog)
        self.call_count = 0

    async def search_projects(self, domain: list, *, limit: int = 20) -> list:
        self.call_count += 1
        return await super().search_projects(domain, limit=limit)


@pytest.mark.asyncio
async def test_discover_related_uses_single_search_not_per_token() -> None:
    catalog = [
        {"id": 15157, "name": "Villa Maintenance No. 34"},
        {"id": 15159, "name": "Villa Maintenance No . 48"},
    ]
    search = _CallCountingSearch(catalog)
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(search)
    related = await gate._discover_related_projects(
        "villa maintanence 37",
        "expense for villa maintanence No. 37",
        _make_context_stack(),
    )
    assert len(related) >= 1
    assert search.call_count == 1
