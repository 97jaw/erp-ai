"""Tests for gateway.session_scope."""

from __future__ import annotations

from gateway.session_scope import SessionScopeStore


def test_clear_removes_session_scope() -> None:
    SessionScopeStore.update("sess-1", project_id=15157, project_name="Villa 34")
    assert SessionScopeStore.get("sess-1")["project_id"] == 15157

    SessionScopeStore.clear("sess-1")
    assert SessionScopeStore.get("sess-1") == {}

    SessionScopeStore.clear("sess-missing")
