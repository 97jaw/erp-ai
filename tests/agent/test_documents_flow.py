from __future__ import annotations

import pytest

from gateway.agent.documents_flow import (
    cached_project_matches_message,
    detect_scope_pick,
    extract_documents_project_hint,
    infer_documents_scope,
    is_documents_category_pick,
    is_project_cost_query,
    try_documents_flow,
)
from gateway.agent.session_entities import get_entities, update_entities


class _SlowAdapter:
    def safe_search_read(self, model, domain, fields, limit=20, order=None, offset=0):
        return [
            {
                "id": 1374,
                "name": "National Guard Health Affairs Central Hospital Riyadh",
                "agreement_id": [88, "AG-88"],
            }
        ]


@pytest.mark.asyncio
async def test_documents_category_pick_shows_scope_picker() -> None:
    result = await try_documents_flow(
        message="Documents & Files",
        user=None,
        adapter=_SlowAdapter(),
        session_id="sess-docs-1",
        skip_clarification=True,
    )
    assert result is not None
    assert result.ui_blocks
    option_ids = {opt["id"] for opt in result.ui_blocks[0]["options"]}
    assert option_ids == {"project", "agreement", "rfq", "record"}


def test_infer_scope_from_project_files_query() -> None:
    assert infer_documents_scope("show me files for project national guard") == "project"


def test_infer_scope_skips_project_expense_queries() -> None:
    assert infer_documents_scope("show project expenses for national guard") is None
    assert infer_documents_scope("project cost summary for zayidia boys school") is None


def test_is_project_cost_query() -> None:
    assert is_project_cost_query("Projects & Costs")
    assert is_project_cost_query("show expense breakdown for national guard")
    assert is_project_cost_query("project summary for al hili")
    assert not is_project_cost_query("show me files for project national guard")


@pytest.mark.asyncio
async def test_expense_query_clears_stale_documents_session() -> None:
    session_id = "sess-docs-expense-switch"
    update_entities(
        session_id,
        intent="attachments",
        documents_scope="project",
        documents_step="target",
        project_id=1374,
        project_name="National Guard Health Affairs",
    )
    result = await try_documents_flow(
        message="show project expenses for national guard",
        user=None,
        adapter=_SlowAdapter(),
        session_id=session_id,
    )
    assert result is None
    entities = get_entities(session_id)
    assert entities.get("intent") != "attachments"
    assert "documents_scope" not in entities


@pytest.mark.asyncio
async def test_project_picker_for_expense_does_not_list_attachments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_id = "sess-expense-pick"
    update_entities(session_id, intent="project_expense")

    async def _should_not_run(*args, **kwargs):
        raise AssertionError("list_attachments should not run for expense project pick")

    monkeypatch.setattr("gateway.agent.tools_registry.execute_tool", _should_not_run)

    result = await try_documents_flow(
        message="National Guard Health Affairs (ID: 1374)",
        user=None,
        adapter=_SlowAdapter(),
        session_id=session_id,
        skip_clarification=True,
        confirmed_entities=[{"type": "project", "id": 1374, "name": "National Guard Health Affairs"}],
    )
    assert result is None


def test_detect_scope_pick_normalizes_label() -> None:
    assert detect_scope_pick("Project documents") == "project"


@pytest.mark.asyncio
async def test_project_files_query_uses_fast_search_not_entity_resolver() -> None:
    result = await try_documents_flow(
        message="show me files for project national guard",
        user=None,
        adapter=_SlowAdapter(),
        session_id="sess-docs-2",
    )
    assert result is not None
    entities = get_entities("sess-docs-2")
    assert entities.get("project_id") == 1374


def test_is_documents_category_pick() -> None:
    assert is_documents_category_pick("📎 Documents & Files")
    assert not is_documents_category_pick("Project documents")


@pytest.mark.asyncio
async def test_project_picker_selection_lists_attachments(monkeypatch: pytest.MonkeyPatch) -> None:
    session_id = "sess-docs-pick"
    update_entities(
        session_id,
        intent="attachments",
        documents_scope="project",
        documents_step="pick_project",
    )

    async def _fake_execute_tool(tool_name, tool_input, **kwargs):
        assert tool_name == "list_attachments"
        assert tool_input["project_id"] == 1374
        return {
            "status": "success",
            "label": "National Guard Health Affairs",
            "files": [
                {
                    "id": 1,
                    "name": "drawing.pdf",
                    "mimetype": "application/pdf",
                    "size": 1024,
                    "download_token": "tok-1",
                }
            ],
        }

    monkeypatch.setattr("gateway.agent.tools_registry.execute_tool", _fake_execute_tool)

    result = await try_documents_flow(
        message="Which project did you mean? — National Guard Health Affairs (ID: 1374)",
        user=None,
        adapter=_SlowAdapter(),
        session_id=session_id,
        skip_clarification=True,
        confirmed_entities=[{"type": "project", "id": 1374, "name": "National Guard Health Affairs"}],
    )
    assert result is not None
    assert "ready to download" in result.text
    assert result.tool_names == ["list_attachments"]


@pytest.mark.asyncio
async def test_scope_pick_after_category_advances_to_project_prompt() -> None:
    session_id = "sess-docs-scope"
    await try_documents_flow(
        message="Documents & Files",
        user=None,
        adapter=_SlowAdapter(),
        session_id=session_id,
        skip_clarification=True,
    )
    result = await try_documents_flow(
        message="Project documents",
        user=None,
        adapter=_SlowAdapter(),
        session_id=session_id,
        skip_clarification=True,
        documents_scope="project",
    )
    assert result is not None
    assert "Which project" in result.text
    assert result.ui_blocks


def test_cached_project_matches_message_detects_new_project_name() -> None:
    entities = {
        "project_id": 14436,
        "project_name": "Maintenance of Guard Room at Haggana",
        "intent": "attachments",
        "documents_scope": "project",
    }
    assert not cached_project_matches_message(
        "give me files of project Al Hili Healthcare Center",
        entities,
    )
    assert extract_documents_project_hint(
        "give me files of project Al Hili Healthcare Center",
    ) == "Al Hili Healthcare Center"


class _AlHiliAdapter:
    def safe_search_read(self, model, domain, fields, limit=20, order=None, offset=0):
        return [
            {
                "id": 12001,
                "name": "Al Hili Healthcare Center",
                "agreement_id": [10, "AG-10"],
                "wo_ref_no": "WO-12001",
            }
        ]


@pytest.mark.asyncio
async def test_new_project_name_clears_stale_session_project() -> None:
    session_id = "sess-docs-new-project"
    update_entities(
        session_id,
        intent="attachments",
        documents_scope="project",
        documents_step="done",
        project_id=14436,
        project_name="Maintenance of Guard Room at Haggana",
    )
    result = await try_documents_flow(
        message="give me files of project Al Hili Healthcare Center",
        user=None,
        adapter=_AlHiliAdapter(),
        session_id=session_id,
    )
    assert result is not None
    entities = get_entities(session_id)
    assert entities.get("project_id") == 12001
