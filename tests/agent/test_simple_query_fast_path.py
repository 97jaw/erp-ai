from __future__ import annotations

from gateway.agent.simple_query_fast_path import (
    _EMP_COUNT_BY_DEPT_RE,
    _aggregate_group_rows,
    _build_headcount_chart_visual,
    _is_org_directory_query,
    _is_simple_factual_query,
    _merge_org_directory_rows,
)
from gateway.progressive_disclosure import apply_progressive_disclosure


def test_employee_count_by_department_matches_suggestion_chip() -> None:
    assert _EMP_COUNT_BY_DEPT_RE.search("Show employee count by department")
    assert _is_simple_factual_query("Show employee count by department")


def test_org_directory_query_matches_departments_and_sections() -> None:
    assert _is_org_directory_query("name all departments and sections")
    assert _is_org_directory_query("list all departments")
    assert _is_org_directory_query("list all sections")
    assert _is_simple_factual_query("name all departments and sections")


def test_merge_org_directory_rows_tags_type_column() -> None:
    merged = _merge_org_directory_rows(
        [["Civil", "Manager A", 12]],
        [["Site A", "", 4]],
    )
    assert merged == [
        ["Department", "Civil", "Manager A", 12],
        ["Section", "Site A", "", 4],
    ]


def test_aggregate_group_rows_skips_unassigned() -> None:
    rows = _aggregate_group_rows(
        {
            "rows": [
                {"group_label": "Civil", "id:count": 10},
                {"group_label": "Unassigned", "id:count": 2},
            ]
        },
        "department_id",
    )
    assert rows == [["Civil", "", 10]]


def test_headcount_chart_includes_all_departments() -> None:
    chart_rows = [[f"Dept {index}", "", index + 1] for index in range(22)]
    visual = _build_headcount_chart_visual(chart_rows)
    assert visual["visual_type"] == "BAR_CHART"
    assert visual["disclosure_exempt"] is True
    assert visual["scrollable"] is True
    assert len(visual["data"]["labels"]) == 22


def test_progressive_disclosure_skips_paginated_tables() -> None:
    visual = {
        "visual_type": "DATA_TABLE",
        "label": "Company departments",
        "query_id": "abc123",
        "level": "standard",
        "data": {"headers": ["Department"], "rows": [["Civil"]]},
    }
    enriched = apply_progressive_disclosure(visual, "list all departments", [])
    assert enriched is not None
    assert enriched.get("query_id") == "abc123"
    assert enriched.get("data", {}).get("summary_chart") is None
    assert enriched["level"] == "standard"
