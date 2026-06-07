"""Tests for gateway.core.project_query_utils."""

from __future__ import annotations

from gateway.core.project_query_utils import (
    extract_project_name_hint,
    looks_like_project_cost_query,
    meaningful_project_words,
)


def test_extract_project_name_hint_strips_cost_suffix() -> None:
    assert extract_project_name_hint("show me Zayidia Boys School costs") == "Zayidia Boys School"


def test_meanful_project_words_drop_stop_words() -> None:
    assert meaningful_project_words("Zayidia Boys School costs") == [
        "Zayidia",
        "Boys",
        "School",
    ]


def test_looks_like_project_cost_query() -> None:
    assert looks_like_project_cost_query("show me Zayidia Boys School costs")
    assert not looks_like_project_cost_query("hello there")
