"""Tests for gateway.core.entity_resolver.EntityResolver."""

from __future__ import annotations

from typing import Any

import pytest

from gateway.core.entity_resolver import EntityResolver, Match
from tests.core.test_context_stack import _make_context_stack


PROJECT_CATALOG: list[dict[str, Any]] = [
    {
        "id": 101,
        "name": "National Guard HQ - Maintenance",
        "wo_ref_no": "WO-101",
        "description": "Facilities maintenance for National Guard HQ",
    },
    {
        "id": 102,
        "name": "National Guard Network Upgrade",
        "wo_ref_no": "WO-102",
        "description": "Network infrastructure",
    },
    {
        "id": 103,
        "name": "Airport NGC Buildings",
        "wo_ref_no": "WO-103",
        "description": "Airport buildings project",
    },
    {
        "id": 201,
        "name": "Zayidia Boys School Renovation",
        "wo_ref_no": "WO-201",
        "description": "School renovation",
    },
]


class MockProjectSearch:
    """In-memory project search for resolver unit tests."""

    def __init__(self, catalog: list[dict[str, Any]] | None = None) -> None:
        self.catalog = catalog or PROJECT_CATALOG

    async def search_projects(self, domain: list[Any], *, limit: int = 20) -> list[dict[str, Any]]:
        if self._is_active_only_domain(domain):
            return [
                dict(project)
                for project in self.catalog
                if project.get("active", True)
            ][:limit]

        id_filter = self._extract_id_in_filter(domain)
        if id_filter is not None:
            return [
                dict(project)
                for project in self.catalog
                if int(project.get("id") or 0) in id_filter
            ][:limit]

        terms = self._extract_ilike_terms(domain)
        if not terms and domain in ([], [[]]):
            return [dict(project) for project in self.catalog[:limit]]

        matches: list[dict[str, Any]] = []
        for project in self.catalog:
            haystacks = [
                str(project.get("name") or "").lower(),
                str(project.get("description") or "").lower(),
                str(project.get("project_name_arabic") or "").lower(),
            ]
            if self._domain_matches(terms, domain, haystacks):
                matches.append(dict(project))
        return matches[:limit]

    @staticmethod
    def _is_active_only_domain(domain: list[Any]) -> bool:
        return domain == [["active", "=", True]]

    @staticmethod
    def _extract_id_in_filter(domain: list[Any]) -> set[int] | None:
        for item in domain:
            if isinstance(item, list) and len(item) == 3 and item[0] == "id" and item[1] == "in":
                return {int(value) for value in item[2]}
        return None

    def _extract_ilike_terms(self, domain: list[Any]) -> list[str]:
        terms: list[str] = []
        for item in domain:
            if (
                isinstance(item, list)
                and len(item) == 3
                and item[1] == "ilike"
            ):
                terms.append(str(item[2]).lower())
        return terms

    def _domain_matches(
        self,
        terms: list[str],
        domain: list[Any],
        haystacks: list[str],
    ) -> bool:
        if not terms:
            return False
        if any(token in ("&", "|") for token in domain):
            operator = "&" if "&" in domain else "|"
            checks = [any(term in hay for hay in haystacks) for term in terms]
            return all(checks) if operator == "&" else any(checks)
        return any(any(term in hay for hay in haystacks) for term in terms)


def _resolver(catalog: list[dict[str, Any]] | None = None) -> EntityResolver:
    return EntityResolver(MockProjectSearch(catalog))


@pytest.mark.asyncio
async def test_resolve_project_returns_resolution_result() -> None:
    result = await _resolver().resolve_project("National Guard", _make_context_stack())
    assert result.query == "National Guard"
    assert isinstance(result.total_matches, int)
    assert isinstance(result.confident_matches, list)
    assert result.strategies_used


@pytest.mark.asyncio
async def test_exact_phrase_match_finds_national_guard_projects() -> None:
    result = await _resolver().resolve_project("National Guard HQ", _make_context_stack())
    names = [match.entity["name"] for match in result.confident_matches]
    assert any("National Guard HQ" in name for name in names)


@pytest.mark.asyncio
async def test_all_words_match_finds_multiple_national_guard_projects() -> None:
    result = await _resolver().resolve_project("national guard", _make_context_stack())
    assert len(result.confident_matches) >= 2
    assert all("National Guard" in match.entity["name"] for match in result.confident_matches[:2])


@pytest.mark.asyncio
async def test_acronym_ngc_resolves_to_national_guard_projects() -> None:
    result = await _resolver().resolve_project("NGC", _make_context_stack())
    names = [match.entity["name"] for match in result.confident_matches]
    assert names
    assert any("NGC" in name or "National Guard" in name for name in names)


@pytest.mark.asyncio
async def test_merged_results_deduplicate_by_id() -> None:
    resolver = _resolver()
    merged = resolver._merge_results(
        [
            [{"id": 101, "name": "National Guard HQ", "_strategy": "exact_phrase_match"}],
            [{"id": 101, "name": "National Guard HQ", "_strategy": "all_words_match"}],
        ],
    )
    assert len(merged) == 1
    assert "exact_phrase_match" in merged[0]["_strategy"]
    assert "all_words_match" in merged[0]["_strategy"]


@pytest.mark.asyncio
async def test_national_guard_scenario_has_confident_matches() -> None:
    result = await _resolver().resolve_project(
        "national guard",
        _make_context_stack(primary_role="super_admin", level=100),
    )
    assert result.confident_matches
    assert result.top_match is not None
    assert "national guard" in result.top_match.entity["name"].lower()


@pytest.mark.asyncio
async def test_clear_winner_ambiguity_when_top_beats_second() -> None:
    resolver = _resolver()
    matches = [
        Match(entity={"id": 1, "name": "National Guard HQ"}, confidence=0.95, strategy="test"),
        Match(entity={"id": 2, "name": "Other Project"}, confidence=0.45, strategy="test"),
    ]
    assert resolver._calculate_ambiguity(matches) == "clear_winner"


@pytest.mark.asyncio
async def test_no_match_returns_empty_confident_matches() -> None:
    result = await _resolver([]).resolve_project("unknown project xyz", _make_context_stack())
    assert result.confident_matches == []
    assert result.top_match is None
    assert result.ambiguity_level == "no_match"


@pytest.mark.asyncio
async def test_score_matches_exact_name_gets_confidence_one() -> None:
    resolver = _resolver()
    scored = resolver._score_matches(
        [{"id": 1, "name": "National Guard", "_strategy": "exact_phrase_match"}],
        "National Guard",
    )
    assert scored[0].confidence == 1.0


def test_clean_name_for_scoring_strips_numeric_prefix() -> None:
    resolver = _resolver()
    assert (
        resolver._clean_name_for_scoring("1420250016 - Zayidia Boys School")
        == "Zayidia Boys School"
    )
    assert (
        resolver._clean_name_for_scoring("RCC-AA-MOE-2025-016 - Zayidia Boys School")
        == "Zayidia Boys School"
    )


def test_score_prefixed_project_name_scores_high_after_strip() -> None:
    resolver = _resolver()
    project = {
        "id": 14549,
        "name": "1420250016 - Zayidia Boys School",
        "wo_ref_no": "RCC-AA-MOE-2025-016",
        "_strategy": "all_words_match",
    }
    score = resolver._score_entity(project, "Zayidia Boys School")
    assert score >= 0.8


def test_score_uses_highest_across_name_fields() -> None:
    resolver = _resolver()
    project = {
        "id": 14549,
        "name": "1420250016 - Zayidia Boys School",
        "x_project_name": "Zayidia Boys School",
        "wo_ref_no": "RCC-AA-MOE-2025-016",
        "_strategy": "all_words_match",
    }
    score = resolver._score_entity(project, "Zayidia Boys School")
    assert score >= 0.8


@pytest.mark.asyncio
async def test_prefixed_zayidia_project_is_confident_match() -> None:
    catalog = [
        {
            "id": 14549,
            "name": "1420250016 - Zayidia Boys School",
            "wo_ref_no": "RCC-AA-MOE-2025-016",
            "description": "School renovation",
        },
    ]
    result = await _resolver(catalog).resolve_project(
        "Zayidia Boys School",
        _make_context_stack(primary_role="super_admin", level=100),
    )
    assert result.confident_matches
    assert result.confident_matches[0].confidence >= 0.8
    assert result.weak_matches == []


@pytest.mark.asyncio
async def test_full_cost_query_scores_prefixed_project_confidently() -> None:
    catalog = [
        {
            "id": 14549,
            "name": "1420250016 - Zayidia Boys School",
            "wo_ref_no": "RCC-AA-MOE-2025-016",
            "description": "School renovation",
        },
    ]
    result = await _resolver(catalog).resolve_project(
        "show me Zayidia Boys School costs",
        _make_context_stack(primary_role="super_admin", level=100),
    )
    assert result.confident_matches
    assert result.confident_matches[0].confidence >= 0.8


@pytest.mark.asyncio
async def test_acronym_in_phrase_expands_for_project_search() -> None:
    result = await _resolver().resolve_project(
        "show me NGC project costs",
        _make_context_stack(primary_role="super_admin", level=100),
    )
    assert result.confident_matches
    names = " ".join(match.entity["name"] for match in result.confident_matches).lower()
    assert "ngc" in names or "national guard" in names


@pytest.mark.asyncio
async def test_resolver_prefers_active_villa_over_wo_pending_duplicate() -> None:
    catalog = [
        {
            "id": 15157,
            "name": "Villa Maintenance No. 34 (WO: Pending)",
            "wo_ref_no": "",
            "wo_amount": 0,
            "description": "Pending duplicate",
        },
        {
            "id": 31034,
            "name": "Villa Maintenance No. 34",
            "wo_ref_no": "463189",
            "wo_amount": 463189,
            "description": "Active villa maintenance",
        },
    ]
    resolver = EntityResolver(MockProjectSearch(catalog))
    result = await resolver.resolve_project(
        "Villa Maintenance No. 34",
        _make_context_stack(primary_role="super_admin", level=100),
    )
    assert result.top_match is not None
    assert result.top_match.entity["id"] == 31034
