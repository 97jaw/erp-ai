from __future__ import annotations

from gateway.partner_ageing_normalize import normalize_partner_ageing


def test_normalize_partner_ageing_buckets_and_total() -> None:
    raw = {
        "as_of_date": "2026-05-16",
        "period_list": ["Not Due", "0 - 30"],
        "partners": {
            "42": {
                "partner_id": 42,
                "partner_name": "Acme Corp",
                "Not Due": 1000.0,
                "0 - 30": 250.0,
                "total": 1250.0,
            },
            "99": {
                "partner_id": 99,
                "partner_name": "Beta LLC",
                "Not Due": 500.0,
                "0 - 30": 0.0,
                "total": 500.0,
            },
        },
        "report_total": {
            "Not Due": 1500.0,
            "0 - 30": 250.0,
            "total": 1750.0,
        },
        "result_selection": "customer",
    }
    result = normalize_partner_ageing(raw, source="project.financial.service")

    assert result["partner_count"] == 2
    assert result["totals"]["total"] == 1750.0
    assert result["period_list"] == ["Not Due", "0 - 30"]
    assert result["partners"]["42"]["partner_name"] == "Acme Corp"
    assert result["partners"]["42"]["total"] == 1250.0
    assert result["totals"]["sum_partner_totals"] == 1750.0
    rows = result["data"]["rows"]
    assert rows[-1][0] == "Total"
    assert rows[-1][-1] == 1750.0
