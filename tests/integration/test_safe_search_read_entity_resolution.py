"""Integration tests for safe_search_read in entity resolution."""

from __future__ import annotations

import pytest

from gateway.core.intent_analyzer import Intent
from tests.core.test_entity_resolver import PROJECT_CATALOG
from tests.integration.test_intelligent_handler import (
    _handler,
    _stack_for_user,
    _super_admin,
)


@pytest.mark.asyncio
async def test_zayidia_costs_shows_confirm_not_hatta_hospital() -> None:
    intent = Intent(
        primary_action="other",
        subject_area="general",
        specific_intent="show me Zayidia Boys School costs",
    )
    response = await _handler(
        intent=intent,
        stack=_stack_for_user(_super_admin()),
        entity_catalog=[PROJECT_CATALOG[3]],
    ).handle("show me Zayidia Boys School costs", _super_admin(), adapter=object())

    assert response.awaiting_clarification
    assert response.clarification is not None
    combined = f"{response.text} {response.clarification}".lower()
    assert "hatta hospital" not in combined
    assert "couldn't find" not in response.text.lower()
    assert any(
        "zayidia" in str(option.get("label", "")).lower()
        for option in response.clarification.get("options") or []
    )


@pytest.mark.live
def test_live_safe_search_read_finds_zayidia_projects() -> None:
    import os

    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if not os.environ.get("ODOO_V14_URL"):
        pytest.skip("Odoo credentials not configured")

    from gateway.main import get_adapter

    try:
        adapter = get_adapter()
    except ConnectionError:
        pytest.skip("Odoo not reachable from this environment")

    records = adapter.safe_search_read(
        "project.project",
        [["name", "ilike", "Zayidia"]],
        ["id", "name", "partner_id"],
        limit=20,
    )
    ids = [record["id"] for record in records]
    assert 14549 in ids
    assert 14610 in ids
    names = " ".join(str(record.get("name") or "") for record in records).lower()
    assert "hatta hospital" not in names
