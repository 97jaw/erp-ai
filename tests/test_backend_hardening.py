from __future__ import annotations

from unittest.mock import MagicMock

from gateway.analytics_tools import get_project_cost_categories, get_top_projects_by_metric
from gateway.session_entities import enrich_tool_input, update_scope_from_tool_result
from gateway.session_scope import SessionScopeStore
from gateway.tool_cache import ToolResultCache
from gateway.tool_validation import should_bust_cache, validate_tool_result


def setup_function() -> None:
    SessionScopeStore._memory.clear()
    ToolResultCache.clear()


def test_should_bust_cache_on_refresh_keywords() -> None:
    assert should_bust_cache("Please refresh the project costs")
    assert not should_bust_cache("Show project costs")


def test_tool_cache_round_trip() -> None:
    ToolResultCache.set("get_project_expenses", {"project_id": 5}, {"project_id": 5, "ok": True})
    cached = ToolResultCache.get("get_project_expenses", {"project_id": 5})
    assert cached == {"project_id": 5, "ok": True}


def test_validate_top_projects_filters_zero_rows() -> None:
    result = validate_tool_result(
        "get_top_projects_by_metric",
        {
            "projects": [
                {"project_name": "A", "revenue": 0, "total_cost": 0, "net_profit": 0},
            ],
        },
    )
    assert result["projects"] == []
    assert "warning" in result


def test_enrich_tool_input_uses_last_project_scope() -> None:
    SessionScopeStore.update("s1", project_id=42, project_name="National Guard Command")
    enriched = enrich_tool_input(
        "get_project_cost_categories",
        {},
        "s1",
    )
    assert enriched["project_id"] == 42
    assert enriched["project_name"] == "National Guard Command"


def test_update_scope_from_project_tool_result() -> None:
    update_scope_from_tool_result(
        "s1",
        "get_project_expenses",
        {"project_name": "National Guard Command"},
        {"project_id": 99, "project_name": "National Guard Command"},
    )
    scope = SessionScopeStore.get("s1")
    assert scope["project_id"] == 99
    assert scope["project_name"] == "National Guard Command"


def test_session_scope_merges_dict_lists_without_type_error() -> None:
    SessionScopeStore.update(
        "s1",
        projects=[{"id": 1, "name": "Alpha"}],
    )
    SessionScopeStore.update(
        "s1",
        projects=[{"id": 1, "name": "Alpha"}, {"id": 2, "name": "Beta"}],
    )
    scope = SessionScopeStore.get("s1")
    assert scope["projects"] == [
        {"id": 1, "name": "Alpha"},
        {"id": 2, "name": "Beta"},
    ]


def test_get_project_cost_categories_from_dashboard_distribution() -> None:
    adapter = MagicMock()
    adapter.call_method.side_effect = RuntimeError("missing remote method")
    adapter.get_kpi_data.return_value = MagicMock(
        raw_data={
            "project_id": 7,
            "project_name": "National Guard Command",
            "kpis": {"total_cost": 1500, "budget": 1000},
            "cost_distribution": [
                {
                    "name": "LPO",
                    "items": [{"name": "Paint", "amount": 1000}],
                },
                {
                    "name": "Petty Cash",
                    "items": [{"name": "Fuel", "amount": 500}],
                },
            ],
        }
    )

    result = get_project_cost_categories(adapter, {"project_id": 7}, session_id="s1")

    assert result["project_id"] == 7
    assert len(result["categories"]) == 2
    assert result["categories"][0]["category"] == "LPO"
    assert result["categories"][0]["total"] == 1000


def test_get_top_projects_by_metric_sorts_gateway_scan() -> None:
    adapter = MagicMock()
    adapter.call_method.side_effect = RuntimeError("missing remote method")
    adapter.search_read.return_value = [
        {"id": 1, "name": "Alpha", "partner_id": [10, "Client A"], "wo_ref_no": "A-1", "wo_amount": 1000},
        {"id": 2, "name": "Beta", "partner_id": [11, "Client B"], "wo_ref_no": "B-1", "wo_amount": 1000},
    ]
    adapter.get_kpi_data.side_effect = [
        MagicMock(raw_data={"kpis": {"total_income": 100, "total_expense": 40, "net_profit": 60, "margin": 60}}),
        MagicMock(raw_data={"kpis": {"total_income": 200, "total_expense": 50, "net_profit": 150, "margin": 75}}),
    ]

    result = get_top_projects_by_metric(
        adapter,
        {
            "metric": "net_profit",
            "limit": 2,
            "date_from": "2026-05-01",
            "date_to": "2026-05-13",
        },
    )

    assert result["projects"][0]["project_name"] == "Beta"
    assert result["projects"][0]["net_profit"] == 150
