from __future__ import annotations

from gateway.tool_input_normalization import (
    normalize_search_odoo_input,
    normalize_sql_aggregate_input,
)


def test_search_odoo_input_parses_stringified_lists() -> None:
    normalized = normalize_search_odoo_input(
        {
            "model": "project.project",
            "fields": "['name', 'partner_id', 'date_start']",
            "filters": "[['date_start', '>=', '2024-01-01'], ['date_start', '<=', '2024-12-31']]",
        }
    )

    assert normalized["fields"] == ["name", "partner_id", "date_start"]
    assert normalized["filters"] == [
        ["date_start", ">=", "2024-01-01"],
        ["date_start", "<=", "2024-12-31"],
    ]


def test_group_aggregate_input_aliases_groupby() -> None:
    from gateway.tool_input_normalization import normalize_group_aggregate_input

    normalized = normalize_group_aggregate_input(
        {
            "model": "account.move",
            "groupby": "partner_id",
            "aggregates": "amount_total:sum",
        }
    )
    assert normalized["group_by"] == ["partner_id"]
    assert "groupby" not in normalized


def test_sql_aggregate_input_parses_stringified_lists() -> None:
    normalized = normalize_sql_aggregate_input(
        {
            "model": "project.project",
            "filters": "[['date_start', '>=', '2024-01-01'], ['date_start', '<=', '2024-12-31']]",
            "group_by": "['partner_id']",
            "aggregates": "['partner_id:count']",
        }
    )

    assert normalized["group_by"] == ["partner_id"]
    assert normalized["aggregates"] == ["partner_id:count"]
    assert normalized["filters"][0] == ["date_start", ">=", "2024-01-01"]
