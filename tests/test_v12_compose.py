from __future__ import annotations

from gateway.compose_tools import calculate, compose_report


def test_calculate_sum_and_average() -> None:
    result = calculate({
        "operations": [
            {"id": "total", "op": "sum", "values": [10, 20, 30]},
            {"id": "avg", "op": "average", "values": [10, 20, 30]},
        ],
    })

    assert result["result_count"] == 2
    assert result["results"][0]["result"] == 60.0
    assert result["results"][1]["result"] == 20.0


def test_compose_report_builds_table_payload() -> None:
    result = compose_report({
        "title": "Project Costs",
        "columns": ["Project", "Cost"],
        "rows": [
            {"Project": "Alpha", "Cost": 100},
            {"Project": "Beta", "Cost": 250},
        ],
    })

    assert result["row_count"] == 2
    assert result["data"]["headers"] == ["Project", "Cost"]
    assert result["totals"]["Cost"] == 350.0


def test_calculate_requires_operations() -> None:
    result = calculate({})
    assert result["error"] == "missing_operations"
