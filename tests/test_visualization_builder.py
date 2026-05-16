from gateway.visualization_builder import (
    build_visualization_from_tool_results,
    choose_response_visualization,
    is_renderable_visualization,
)


def test_builds_purchase_order_table():
    payload = {
        "request": {"client_name": "COLORS", "limit": 20},
        "count": 1,
        "orders": [{
            "po_number": "CCT-PO-133",
            "supplier_name": "Vendor",
            "client_name": "COLORS",
            "project_name": "Villa",
            "date_order": "2025-10-30",
            "amount_total": 1000,
            "state": "locked",
        }],
    }

    visual = build_visualization_from_tool_results(
        ["get_purchase_orders"],
        [payload],
    )

    assert visual["visual_type"] == "DATA_TABLE"
    assert visual["value"] == 1
    assert visual["data"]["rows"][0][0] == "CCT-PO-133"


def test_empty_table_is_not_renderable():
    visual = {
        "visual_type": "DATA_TABLE",
        "label": "No rows",
        "value": 0,
        "unit": "orders",
        "data": {"headers": ["PO"], "rows": []},
    }

    assert not is_renderable_visualization(visual)


def test_zero_count_kpi_is_renderable():
    visual = {
        "visual_type": "KPI_CARD",
        "label": "Client purchase orders",
        "value": 0,
        "unit": "orders",
        "data": {},
    }

    assert is_renderable_visualization(visual)


def test_builds_financial_report_from_tool_payload():
    payload = {
        "report_name": "Profit and Loss",
        "date_from": "2026-05-01",
        "date_to": "2026-05-13",
        "kpis": {
            "total_income": 1000,
            "total_expense": 400,
            "net_profit": 600,
            "margin": 60.0,
        },
    }

    visual = build_visualization_from_tool_results(
        ["get_financial_report"],
        [payload],
    )

    assert visual["visual_type"] == "FINANCIAL_REPORT"
    assert visual["kpis"]["net_profit"] == 600


def test_prefers_tool_visual_over_invalid_model_block():
    payload = {
        "report_name": "Profit and Loss",
        "date_from": "2026-05-01",
        "date_to": "2026-05-13",
        "kpis": {
            "total_income": 1000,
            "total_expense": 400,
            "net_profit": 600,
            "margin": 60.0,
        },
    }
    model_visual = {
        "visual_type": "FINANCIAL_REPORT",
        "label": "Profit and Loss",
        "value": 0,
        "unit": "AED",
        "data": {},
        "suggestions": ["Compare with last month"],
    }

    visual = choose_response_visualization(
        model_visual,
        ["get_financial_report"],
        [payload],
    )

    assert visual["visual_type"] == "FINANCIAL_REPORT"
    assert visual["kpis"]["net_profit"] == 600


def test_normalizes_nested_financial_kpis():
    model_visual = {
        "visual_type": "FINANCIAL_REPORT",
        "label": "Profit and Loss",
        "value": 600,
        "unit": "AED",
        "data": {
            "date_from": "2026-05-01",
            "date_to": "2026-05-13",
            "kpis": {
                "total_income": 1000,
                "total_expense": 400,
                "net_profit": 600,
                "margin": 60.0,
            },
        },
    }

    visual = choose_response_visualization(model_visual, [], [])

    assert visual["visual_type"] == "FINANCIAL_REPORT"
    assert visual["kpis"]["net_profit"] == 600
    assert visual["date_from"] == "2026-05-01"


def test_builds_project_counts_by_client_table():
    payload = {
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
        "clients": [
            {"client": "Alpha", "project_count": 3},
            {"client": "Beta", "project_count": 1},
        ],
        "count": 2,
    }

    visual = build_visualization_from_tool_results(
        ["get_project_counts_by_client"],
        [payload],
    )

    assert visual["visual_type"] == "DATA_TABLE"
    assert visual["data"]["rows"][0] == ["Alpha", 3]
