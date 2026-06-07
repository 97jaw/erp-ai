"""Tests for gateway.core.precompute_cache."""

from __future__ import annotations

import time

from gateway.core.precompute_cache import PrecomputeCache, normalize_lookup_message


def test_lookup_matches_query_message_and_suggestion_text() -> None:
    cache = PrecomputeCache(ttl_seconds=60)
    key = cache.mark_pending(
        "session-1",
        suggestion_text="Compare Client A revenue vs last year",
        query_message="Compare revenue for Client A this quarter vs same quarter last year",
    )
    cache.put_ready(
        "session-1",
        key,
        text="Client A revenue comparison ready.",
        visualization={"visual_type": "DATA_TABLE", "data": {"rows": []}},
        suggestions=["Export to Excel"],
    )

    by_query = cache.lookup(
        "session-1",
        "Compare revenue for Client A this quarter vs same quarter last year",
    )
    by_chip = cache.lookup("session-1", "Compare Client A revenue vs last year")

    assert by_query is not None
    assert by_chip is not None
    assert by_query.text.startswith("Client A revenue")


def test_pending_entries_are_not_returned() -> None:
    cache = PrecomputeCache(ttl_seconds=60)
    cache.mark_pending(
        "session-2",
        suggestion_text="Show revenue by client",
        query_message="Show revenue by client for last quarter",
    )
    assert cache.lookup("session-2", "Show revenue by client for last quarter") is None


def test_entries_expire() -> None:
    cache = PrecomputeCache(ttl_seconds=0)
    key = cache.mark_pending(
        "session-3",
        suggestion_text="Export table",
        query_message="Export this table to Excel",
    )
    cache._by_session["session-3"][key].expires_at = time.monotonic() - 1
    cache.put_ready(
        "session-3",
        key,
        text="Ready",
        visualization=None,
    )
    assert cache.lookup("session-3", "Export this table to Excel") is None


def test_normalize_lookup_message_collapses_whitespace() -> None:
    assert normalize_lookup_message("  Compare   Revenue  ") == "compare revenue"
