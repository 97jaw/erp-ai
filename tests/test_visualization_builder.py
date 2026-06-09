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


def test_builds_project_expense_summary_visual_from_unified_source():
    payload = {
        "status": "success",
        "_source": "project_expense_summary",
        "project_id": 14549,
        "project_name": "Zayidia Boys School",
        "currency": "AED",
        "wo_amount": 0,
        "total_expenses": 103_370,
        "spend_percent_of_wo": 0,
        "variance_amount": -103_370,
        "is_over_budget": False,
        "top_expenses": [{"name": "Civil", "amount": 103_370, "percent": 100.0}],
        "expense_lines": [{"label": "Civil", "amount": 103_370}],
    }

    visual = build_visualization_from_tool_results(
        ["get_project_expense_summary"],
        [payload],
    )

    assert visual["visual_type"] == "PROJECT_EXPENSE_SUMMARY"
    assert visual["kpis"]["total_expenses"]["value"] == 103_370


def test_builds_project_expense_summary_visual_from_dashboard_source():
    payload = {
        "status": "success",
        "_source": "project_expense_dashboard",
        "project_id": 31034,
        "project_name": "Villa Maintenance No. 34",
        "currency": "AED",
        "wo_amount": 463_189,
        "total_expenses": 103_370,
        "spend_percent_of_wo": 22.3,
        "variance_amount": 359_819,
        "is_over_budget": False,
        "top_expenses": [{"name": "Civil", "amount": 103_370, "percent": 100.0}],
        "expense_lines": [{"label": "Civil", "amount": 103_370}],
    }

    visual = build_visualization_from_tool_results(
        ["get_project_expense_summary"],
        [payload],
    )

    assert visual["visual_type"] == "PROJECT_EXPENSE_SUMMARY"
    assert visual["expense_lines"][0]["label"] == "Civil"


def test_builds_project_expense_summary_visual():
    payload = {
        "status": "success",
        "_source": "project_expense_summary_mobile",
        "project_id": 14549,
        "project_name": "Zayidia Boys School",
        "currency": "AED",
        "wo_amount": 2_240_000,
        "total_expenses": 1_745_000,
        "spend_percent_of_wo": 77.9,
        "variance_amount": 495_000,
        "is_over_budget": False,
        "top_expenses": [{"name": "Civil", "amount": 580_000, "percent": 33.2}],
        "expense_lines": [{"label": "LPO", "amount": 400_000}],
    }

    visual = build_visualization_from_tool_results(
        ["get_project_expense_summary"],
        [payload],
    )

    assert visual["visual_type"] == "PROJECT_EXPENSE_SUMMARY"
    assert visual["kpis"]["wo_amount"]["value"] == 2_240_000
    assert visual["top_expenses"][0]["label"] == "Civil"
    assert visual["data"]["summary_chart"]["data"]["rows"][0]["value"] == 580_000


def test_builds_project_expense_breakdown_visual():
    payload = {
        "status": "success",
        "_source": "project_expense_breakdown_mobile",
        "project_id": 14549,
        "project_name": "Zayidia Boys School",
        "currency": "AED",
        "grand_total": 150_000,
        "group_count": 1,
        "groups": [
            {
                "code": "MG01",
                "name": "Direct Costs",
                "total": 150_000,
                "subgroups": [
                    {
                        "code": "SG01",
                        "name": "Materials",
                        "total": 150_000,
                        "accounts": [{"code": "5001", "name": "Steel", "total": 100_000}],
                    },
                ],
            },
        ],
    }

    visual = build_visualization_from_tool_results(
        ["get_project_expense_breakdown"],
        [payload],
    )

    assert visual["visual_type"] == "PROJECT_EXPENSE_BREAKDOWN"
    assert visual["groups"][0]["expanded"] is True
    assert visual["groups"][0]["subgroups"][0]["accounts"][0]["total"] == 100_000


def test_builds_project_expense_comparison_visual():
    payload = {
        "status": "success",
        "_source": "compare_project_expenses",
        "projects": [
            {
                "project_id": 14549,
                "project_name": "Zayidia Boys School",
                "currency": "AED",
                "wo_amount": 2_240_000,
                "total_expenses": 1_745_000,
                "spend_percent_of_wo": 78,
                "is_over_budget": False,
            },
            {
                "project_id": 14610,
                "project_name": "Zayidia Girls School",
                "currency": "AED",
                "wo_amount": 2_850_000,
                "total_expenses": 2_910_000,
                "spend_percent_of_wo": 102,
                "is_over_budget": True,
            },
        ],
        "totals": {
            "combined_wo": 5_090_000,
            "combined_expenses": 4_655_000,
            "over_budget_count": 1,
        },
        "ranked_by": "total_expenses",
    }

    visual = build_visualization_from_tool_results(
        ["compare_project_expenses"],
        [payload],
    )

    assert visual["visual_type"] == "PROJECT_EXPENSE_COMPARISON"
    assert len(visual["projects"]) == 2
    assert visual["projects"][1]["is_over_budget"] is True
    assert visual["insights"]
