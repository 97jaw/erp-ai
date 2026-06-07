"""Tests for visualize.data_resolver — full row extraction from summary payloads."""

from visualize.data_resolver import enrich_pdf_sections, resolve_table_from_visualization


def test_financial_report_uses_all_rows_when_summary_rows_empty():
    viz = {
        "visual_type": "FINANCIAL_REPORT",
        "level": "summary",
        "data": {
            "headers": ["Account", "Debit", "Credit", "Balance"],
            "rows": [],
            "all_rows": [
                {"Account": "Sales", "Debit": 0, "Credit": 100, "Balance": 100},
                {"Account": "Rent", "Debit": 50, "Credit": 0, "Balance": -50},
            ],
            "detail_table": {
                "headers": ["Account", "Debit", "Credit", "Balance"],
                "rows": [
                    {"Account": "Sales", "Debit": 0, "Credit": 100, "Balance": 100},
                ],
            },
        },
    }
    table = resolve_table_from_visualization(viz)
    assert len(table["rows"]) == 2
    assert table["headers"][0] == "Account"


def test_enrich_pdf_sections_fills_empty_table():
    items = [{
        "question": "P&L",
        "visualization": {
            "visual_type": "DATA_TABLE",
            "data": {
                "headers": ["Name", "Amount"],
                "rows": [],
                "all_rows": [{"Name": "A", "Amount": 10}],
            },
        },
    }]
    sections = [{
        "type": "table",
        "title": "Data",
        "data": {"headers": ["Name", "Amount"], "rows": []},
    }]
    enriched = enrich_pdf_sections(sections, items)
    assert enriched[0]["data"]["rows"]
    assert enriched[0]["data"]["rows"][0]["Name"] == "A"
