"""search_entities must resolve numeric IDs by id, not fuzzy name search."""

from __future__ import annotations

from typing import Any

import pytest

from gateway.core.entity_resolver import EntityResolver
from gateway.tools.search_entities import execute_search_entities, minimal_search_context
from tests.core.test_entity_resolver import MockProjectSearch, PROJECT_CATALOG


class MockAdapter:
    def __init__(self, records: list[dict[str, Any]] | None = None) -> None:
        self.records = records or []
        self.safe_search_read_calls: list[tuple[Any, ...]] = []

    def safe_search_read(
        self,
        model: str,
        domain: list[Any],
        fields: list[str],
        limit: int = 100,
        offset: int = 0,
        order: str | None = None,
    ) -> list[dict[str, Any]]:
        del offset, order
        self.safe_search_read_calls.append((model, domain, fields, limit))
        return list(self.records)


class FailingResolver(EntityResolver):
    async def resolve_project(self, query: str, context: Any, *, min_confidence: float = 0.3) -> Any:
        del query, context, min_confidence
        raise AssertionError("resolve_project must not run for numeric ID queries")


@pytest.mark.asyncio
async def test_numeric_query_fetches_project_by_id() -> None:
    adapter = MockAdapter(
        records=[
            {
                "id": 15157,
                "name": "Villa Maintenance No. 34",
                "wo_ref_no": "WO-15157",
                "description": "Villa maintenance",
                "partner_id": False,
            },
        ],
    )
    context = minimal_search_context(user_message="15157")

    result = await execute_search_entities(
        adapter,
        {"entity_type": "project", "query": "15157"},
        context,
        project_resolver=FailingResolver(MockProjectSearch([])),
    )

    assert adapter.safe_search_read_calls == [
        (
            "project.project",
            [["id", "=", 15157]],
            ["id", "name", "wo_ref_no", "description", "partner_id"],
            1,
        ),
    ]
    assert result["total_matches"] == 1
    assert result["candidates"][0]["id"] == 15157
    assert result["candidates"][0]["name"] == "Villa Maintenance No. 34"


@pytest.mark.asyncio
async def test_name_query_still_uses_fuzzy_resolver() -> None:
    adapter = MockAdapter()
    catalog = [project for project in PROJECT_CATALOG if "Villa" in str(project.get("name", ""))]
    if not catalog:
        catalog = [
            {
                "id": 31034,
                "name": "Villa Maintenance No. 34",
                "wo_ref_no": "WO-31034",
                "description": "Villa maintenance contract",
            },
        ]
    context = minimal_search_context(user_message="Villa")

    result = await execute_search_entities(
        adapter,
        {"entity_type": "project", "query": "Villa"},
        context,
        project_resolver=EntityResolver(MockProjectSearch(catalog)),
    )

    assert adapter.safe_search_read_calls == []
    assert result["total_matches"] >= 1
    assert any("Villa" in str(candidate.get("name", "")) for candidate in result["candidates"])
