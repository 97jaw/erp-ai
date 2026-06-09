"""Typo-tolerant entity resolution — Phase B fuzzy + transliteration variants."""

from __future__ import annotations

import time
from typing import Any

import pytest

from gateway.core.entity_resolver import EntityResolver, FUZZY_LOCAL_SCORE_CUTOFF
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_entity_resolver import MockProjectSearch, _resolver


ZAYIDIA_TYPO_CATALOG: list[dict[str, Any]] = [
    {
        "id": 14549,
        "name": "Zayidia Boys School",
        "wo_ref_no": "RCC-AA-MOE-2025-016",
        "description": "School renovation",
        "active": True,
    },
    {
        "id": 14610,
        "name": "Zayidia Girls School Al Ain",
        "wo_ref_no": "RCC-AA-MOE-2025-018",
        "description": "School renovation",
        "active": True,
    },
    {
        "id": 9001,
        "name": "AL Borooj School",
        "wo_ref_no": "RCC-AA-MOE-2024-006",
        "active": True,
    },
    {
        "id": 9002,
        "name": "ALBEDAA SCHOOL",
        "wo_ref_no": "WOCM 49:156",
        "active": True,
    },
    {
        "id": 11667,
        "name": "HATTA HOSPITAL",
        "wo_ref_no": "WO-HATTA",
        "active": True,
    },
]


def _zayidia_resolver() -> EntityResolver:
    return _resolver(ZAYIDIA_TYPO_CATALOG)


def _top_name(result) -> str:
    match = result.top_match or (result.confident_matches[0] if result.confident_matches else None)
    assert match is not None
    return str(match.entity.get("name") or "")


@pytest.mark.asyncio
async def test_zaidia_typo_finds_zayidia_boys_school() -> None:
    result = await _zayidia_resolver().resolve_project(
        "zaidia boys school",
        _make_context_stack(),
    )
    assert result.confident_matches
    assert result.top_match is not None
    assert result.top_match.confidence > 0.8
    assert "Zayidia Boys School" in _top_name(result)


@pytest.mark.asyncio
async def test_zayedia_typo_finds_zayidia_boys_school() -> None:
    result = await _zayidia_resolver().resolve_project(
        "zayedia boys school",
        _make_context_stack(),
    )
    assert result.top_match is not None
    assert result.top_match.confidence > 0.75
    assert "Zayidia Boys School" in _top_name(result)


@pytest.mark.asyncio
async def test_zaidiya_partial_finds_zayidia() -> None:
    result = await _zayidia_resolver().resolve_project(
        "zaidiya",
        _make_context_stack(),
    )
    assert result.top_match is not None
    assert result.top_match.confidence > 0.7
    assert "Zayidia" in _top_name(result)


@pytest.mark.asyncio
async def test_exact_zayidia_uses_phase_a_fast_path() -> None:
    result = await _zayidia_resolver().resolve_project(
        "Zayidia Boys School",
        _make_context_stack(),
    )
    assert result.confident_matches
    assert result.top_match is not None
    assert result.top_match.strategy != "fuzzy_local"
    assert "Zayidia Boys School" in _top_name(result)


@pytest.mark.asyncio
async def test_nonexistent_query_stays_not_found() -> None:
    result = await _zayidia_resolver().resolve_project(
        "XYZNONEXISTENT",
        _make_context_stack(),
    )
    assert result.confident_matches == []
    assert result.top_match is None
    assert result.ambiguity_level == "no_match"


@pytest.mark.asyncio
async def test_hatta_hospital_exact_skips_fuzzy_local() -> None:
    result = await _zayidia_resolver().resolve_project(
        "hatta hospital",
        _make_context_stack(),
    )
    assert result.confident_matches
    assert result.top_match is not None
    assert result.top_match.strategy != "fuzzy_local"
    assert "HATTA HOSPITAL" in _top_name(result)


def test_broad_fetch_words_uses_school_for_zaidia_query() -> None:
    resolver = _zayidia_resolver()
    words = resolver._broad_fetch_words("zaidia boys school")
    assert "school" in words
    assert "boys" not in words


@pytest.mark.asyncio
async def test_broad_fetch_includes_zayidia_via_school_word() -> None:
    resolver = _zayidia_resolver()
    candidates = await resolver._fetch_broad_candidates("zaidia boys school", _make_context_stack())
    names = {str(item.get("name") or "") for item in candidates}
    assert any("Zayidia Boys School" in name for name in names)


def test_local_fuzzy_wratio_score_above_80() -> None:
    resolver = _zayidia_resolver()
    candidates = [{"id": 14549, "name": "Zayidia Boys School"}]
    matches = resolver._local_fuzzy_match("zaidia boys school", candidates)
    assert matches
    assert matches[0].confidence > 0.8


@pytest.mark.asyncio
async def test_phase_b_completes_under_two_seconds() -> None:
    resolver = _zayidia_resolver()
    started = time.perf_counter()
    result = await resolver.resolve_project("zaidia boys school", _make_context_stack())
    elapsed = time.perf_counter() - started
    assert result.top_match is not None
    assert elapsed < 2.0


def test_local_fuzzy_sequence_fallback_without_rapidfuzz() -> None:
    resolver = _zayidia_resolver()
    candidates = {14549: {"id": 14549, "name": "Zayidia Boys School"}}
    matches = resolver._local_fuzzy_match_sequence("zaidia boys school", candidates)
    assert matches
    assert matches[0].confidence * 100 >= FUZZY_LOCAL_SCORE_CUTOFF
