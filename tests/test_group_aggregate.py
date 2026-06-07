from __future__ import annotations

from unittest.mock import MagicMock

from gateway.group_aggregate_tools import _apply_date_range_to_domain, group_and_aggregate
from gateway.tool_input_normalization import normalize_group_aggregate_input
from gateway.visualization_builder import build_visualization_from_tool_results


def test_normalize_group_aggregate_input_parses_aliases() -> None:
    normalized = normalize_group_aggregate_input({
        "model": "project.project",
        "filters": "[['active','=',True]]",
        "group_by": "partner_id",
        "aggregates": "id:count",
        "order": "id:count desc",
    })

    assert normalized["domain"] == [["active", "=", True]]
    assert normalized["group_by"] == ["partner_id"]
    assert normalized["aggregates"] == ["id:count"]
    assert normalized["order_by"] == "id:count desc"


def test_apply_date_range_adds_upper_and_lower_bounds() -> None:
    domain = _apply_date_range_to_domain(
        "account.move",
        [],
        "2026-01-01",
        "2026-03-31",
    )
    assert domain == [
        ["invoice_date", ">=", "2026-01-01"],
        ["invoice_date", "<=", "2026-03-31"],
    ]


def test_group_and_aggregate_single_level() -> None:
    adapter = MagicMock()
    adapter.call_method.side_effect = Exception("remote unavailable")
    adapter.read_group.return_value = [
        {
            "partner_id": [1, "Alpha"],
            "partner_id_count": 3,
            "__count": 3,
        }
    ]

    result = group_and_aggregate(
        adapter,
        {
            "model": "project.project",
            "domain": [["active", "=", True]],
            "group_by": ["partner_id"],
            "aggregates": ["id:count"],
            "order_by": "id:count desc",
            "limit": 10,
        },
    )

    assert result["groups"][0]["partner_id"] == [1, "Alpha"]
    assert result["groups"][0]["id:count"] == 3.0
    assert result["source"] == "read_group"


def test_group_and_aggregate_multi_level() -> None:
    adapter = MagicMock()
    adapter.call_method.side_effect = Exception("remote unavailable")
    adapter.read_group.side_effect = [
        [
            {
                "partner_id": [1, "Alpha"],
                "partner_id_count": 2,
                "__count": 2,
                "__domain": [["partner_id", "=", 1]],
            }
        ],
        [
            {
                "stage_id": [10, "In Progress"],
                "stage_id_count": 2,
                "__count": 2,
            }
        ],
    ]

    result = group_and_aggregate(
        adapter,
        {
            "model": "project.project",
            "group_by": ["partner_id", "stage_id"],
            "aggregates": ["id:count"],
            "limit": 5,
        },
    )

    assert result["groups"][0]["children"][0]["stage_id"] == [10, "In Progress"]


def test_group_and_aggregate_applies_having() -> None:
    adapter = MagicMock()
    adapter.call_method.side_effect = Exception("remote unavailable")
    adapter.read_group.return_value = [
        {"partner_id": [1, "Alpha"], "id:count": 5, "__count": 5},
        {"partner_id": [2, "Beta"], "id:count": 1, "__count": 1},
    ]

    result = group_and_aggregate(
        adapter,
        {
            "model": "project.project",
            "group_by": ["partner_id"],
            "aggregates": ["id:count"],
            "having": {"id:count": [">", 2]},
        },
    )

    assert len(result["groups"]) == 1
    assert result["groups"][0]["partner_id"] == [1, "Alpha"]


def test_group_and_aggregate_requires_model_and_group_by() -> None:
    adapter = MagicMock()

    missing_model = group_and_aggregate(adapter, {"group_by": ["partner_id"]})
    missing_group = group_and_aggregate(adapter, {"model": "project.project"})

    assert missing_model["error"] == "missing_model"
    assert missing_group["error"] == "missing_group_by"


def test_group_and_aggregate_visualization_builds_grouped_table() -> None:
    visual = build_visualization_from_tool_results(
        ["group_and_aggregate"],
        [{
            "model": "project.project",
            "group_by": ["partner_id", "stage_id"],
            "aggregates": ["id:count"],
            "total_groups": 1,
            "groups": [{
                "group_label": "Alpha",
                "id:count": 2,
                "children": [{
                    "group_label": "In Progress",
                    "id:count": 2,
                }],
            }],
        }],
    )

    assert visual is not None
    assert visual["visual_type"] == "GROUPED_TABLE"
    assert visual["data"]["groups"][0]["name"] == "Alpha"
