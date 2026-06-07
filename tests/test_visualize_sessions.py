from __future__ import annotations

from visualize.sessions import build_initial_greeting, create_session, initial_response


def test_build_initial_greeting_single_item() -> None:
    text = build_initial_greeting([
        {"question": "P&L this month", "vizType": "KPI_CARD"},
    ])
    # Placeholder until the analysis brain pre-fills build instructions in the UI.
    assert text == ""


def test_initial_response_includes_actions() -> None:
    payload = initial_response([{"question": "Test"}])
    assert payload["item_count"] == 1
    assert len(payload["actions"]) >= 2
    assert any(action["value"] == "pdf" for action in payload["actions"])


def test_create_session_stores_items() -> None:
    session = create_session(user_id=1, items=[{"question": "A"}])
    assert session.session_id
    assert len(session.dropped_items) == 1
