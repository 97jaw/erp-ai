"""Tests for related-project suggestion on entity near-miss."""

from __future__ import annotations

from gateway.core.project_query_utils import (
    extract_suggestion_tokens,
    rank_related_project,
)


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
