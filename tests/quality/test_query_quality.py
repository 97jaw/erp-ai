from __future__ import annotations

from gateway.quality_intent import detect_query_intent
from gateway.quality_response import polish_agent_response
from gateway.quality_validation import validate_response_quality

QUALITY_TESTS = [
    {
        "query": "Revenue comparison by client",
        "expectations": {
            "visualization_type": "BAR_CHART",
            "has_narrative": True,
            "currency_formatted": True,
            "no_raw_syntax": True,
        },
    },
    {
        "query": "Top 5 most expensive projects",
        "expectations": {
            "visualization_type": "BAR_CHART",
        },
    },
    {
        "query": "Monthly revenue trend 2026",
        "expectations": {
            "visualization_type": "LINE_CHART",
        },
    },
]


def assert_quality(response: dict, expected: dict) -> None:
    if expected.get("visualization_type"):
        assert response["visualization"]["visual_type"] == expected["visualization_type"]
    if expected.get("has_narrative"):
        assert response["text"].strip()
    if expected.get("currency_formatted"):
        assert "AED" in response["text"]
    if expected.get("no_raw_syntax"):
        forbidden = [":sum:", ":count:", "amount_total:", "partner_id["]
        for token in forbidden:
            assert token not in response["text"]
            assert token not in str(response["visualization"])


def test_revenue_comparison_by_client_polish() -> None:
    visual = {
        "visual_type": "GROUPED_TABLE",
        "label": "Grouped account move",
        "value": 4,
        "unit": "AED",
        "data": {
            "groups": [
                {
                    "name": "Abu Dhabi Police",
                    "aggregates": {"amount_total:sum": 10500000},
                },
                {
                    "name": "National Guard",
                    "aggregates": {"amount_total:sum": 4300000},
                },
            ],
        },
    }
    text, polished = polish_agent_response(
        "Revenue comparison by client",
        "",
        visual,
        ["group_and_aggregate"],
        [{"groups": visual["data"]["groups"], "aggregates": ["amount_total:sum"]}],
        "en",
    )
    response = {"text": text, "visualization": polished}
    assert_quality(response, QUALITY_TESTS[0]["expectations"])


def test_intent_detection_for_quality_cases() -> None:
    for case in QUALITY_TESTS:
        intent = detect_query_intent(case["query"])
        expected = case["expectations"].get("visualization_type")
        if expected:
            assert intent["visual_type"] == expected


def test_validate_polished_response_passes() -> None:
    response = {
        "text": "Abu Dhabi Police leads with AED 10.5M (67.3% of the total).",
        "visualization": {
            "visual_type": "BAR_CHART",
            "data": {
                "labels": ["Abu Dhabi Police"],
                "values": [10500000],
                "formatted_values": ["AED 10.5M"],
            },
        },
    }
    passed, issues = validate_response_quality(response)
    assert passed
    assert not issues
