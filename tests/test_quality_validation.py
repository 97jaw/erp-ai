from __future__ import annotations

from gateway.quality_validation import is_suspicious_group_result, validate_response_quality


def test_validate_response_quality_rejects_raw_syntax() -> None:
    passed, issues = validate_response_quality({
        "text": "amount_total:sum is high",
        "visualization": {"visual_type": "DATA_TABLE", "data": {"rows": [["A", 1]]}},
    })
    assert not passed
    assert any("Raw field syntax" in issue for issue in issues)


def test_validate_response_quality_requires_narrative_with_visual() -> None:
    passed, issues = validate_response_quality({
        "text": "",
        "visualization": {
            "visual_type": "BAR_CHART",
            "data": {"values": [10], "labels": ["Client A"]},
        },
    })
    assert not passed
    assert "Visualization without narrative" in issues


def test_is_suspicious_group_result_detects_all_zero() -> None:
    assert is_suspicious_group_result({
        "groups": [{"amount_total:sum": 0}, {"amount_total:sum": 0}],
        "aggregates": ["amount_total:sum"],
    })
