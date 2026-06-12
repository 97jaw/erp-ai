"""Audit session memory — cap and retrieval."""

from gateway.audit.memory import (
    MAX_AUDIT_TURNS,
    append_audit_turn,
    audit_sessions,
    clear_audit_session,
    get_audit_history,
)


def test_append_and_retrieve() -> None:
    clear_audit_session("s1")
    append_audit_turn("s1", "hello", "hi there")
    history = get_audit_history("s1")
    assert len(history) == 2
    assert history[0] == {"role": "user", "content": "hello"}
    assert history[1] == {"role": "assistant", "content": "hi there"}
    clear_audit_session("s1")


def test_caps_at_ten_turns() -> None:
    clear_audit_session("s2")
    for index in range(MAX_AUDIT_TURNS + 3):
        append_audit_turn("s2", f"user-{index}", f"assistant-{index}")
    history = get_audit_history("s2")
    assert len(history) == MAX_AUDIT_TURNS * 2
    assert history[0]["content"] == "user-3"
    assert history[-1]["content"] == f"assistant-{MAX_AUDIT_TURNS + 2}"
    clear_audit_session("s2")


def test_isolated_sessions() -> None:
    audit_sessions.clear()
    append_audit_turn("a", "one", "two")
    append_audit_turn("b", "three", "four")
    assert len(get_audit_history("a")) == 2
    assert len(get_audit_history("b")) == 2
    audit_sessions.clear()
