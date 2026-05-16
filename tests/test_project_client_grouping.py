from __future__ import annotations

from unittest.mock import MagicMock

from gateway.aggregate_tools import _normalize_read_group_order, sql_aggregate
from gateway.project_client_grouping import parse_projects_by_client_request


def test_parse_projects_by_client_request_detects_year() -> None:
    request = parse_projects_by_client_request(
        "Show projects grouped by client in 2024"
    )
    assert request == {"year": 2024, "limit": 100}


def test_normalize_read_group_order_maps_count_syntax() -> None:
    assert _normalize_read_group_order(
        "partner_id:count desc",
        ["partner_id"],
        ["partner_id:count"],
    ) == "partner_id_count desc"


def test_sql_aggregate_uses_odoo_count_order() -> None:
    adapter = MagicMock()
    adapter.read_group.return_value = [
        {
            "partner_id": [1, "Alpha"],
            "partner_id_count": 3,
            "__count": 3,
        }
    ]

    result = sql_aggregate(
        adapter,
        {
            "model": "project.project",
            "filters": [
                ["date_start", ">=", "2024-01-01"],
                ["date_start", "<=", "2024-12-31"],
            ],
            "group_by": ["partner_id"],
            "aggregates": ["partner_id:count"],
            "order": "partner_id:count desc",
            "limit": 50,
        },
    )

    adapter.read_group.assert_called_once()
    kwargs = adapter.read_group.call_args.kwargs
    assert kwargs["order"] == "partner_id_count desc"
    assert kwargs["fields"] == ["partner_id"]
    assert result["rows"][0]["partner_id:count"] == 3.0
