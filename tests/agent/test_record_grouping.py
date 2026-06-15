"""Tests for list grouping and query correction."""

from gateway.agent.preflight import run_chat_preflight
from gateway.agent.query_correction import suggest_query_corrections
from gateway.agent.session_entities import (
    clear_entities,
    update_entities,
    update_entities_from_message,
)
from gateway.record_list_grouping import build_grouped_table_visual, enhance_list_visualization


def test_group_lpo_rows_by_vendor() -> None:
    table = {
        "visual_type": "DATA_TABLE",
        "label": "National Guard — LPO Invoices",
        "data": {
            "headers": ["Bill", "Date", "Vendor", "Total (AED)", "Due (AED)", "Payment"],
            "rows": [
                ["RCC/1", "2026-06-04", "Vendor A", 100, 100, "not_paid"],
                ["RCC/2", "2026-06-02", "Vendor B", 200, 200, "not_paid"],
                ["RCC/3", "2026-06-01", "Vendor A", 50, 50, "not_paid"],
            ],
        },
    }
    grouped = build_grouped_table_visual(table, group_field="vendor")
    assert grouped is not None
    assert grouped["visual_type"] == "GROUPED_TABLE"
    groups = grouped["data"]["groups"]
    assert len(groups) == 2
    vendor_a = next(group for group in groups if group["name"] == "Vendor A")
    assert vendor_a["aggregates"]["count"] == 2
    assert vendor_a["aggregates"]["total (AED)"] == 150


def test_enhance_list_on_group_by_vendor_instruction() -> None:
    table = {
        "visual_type": "DATA_TABLE",
        "label": "LPO list",
        "data": {
            "headers": ["Bill", "Date", "Vendor", "Total (AED)"],
            "rows": [["A", "2026-01-01", "X", 10]],
        },
    }
    result = enhance_list_visualization(table, "group by that lpos vendor wise")
    assert result["visual_type"] == "GROUPED_TABLE"


def test_fleet_table_not_auto_grouped() -> None:
    table = {
        "visual_type": "DATA_TABLE",
        "label": "Fleet vehicles — Adil Khan",
        "data": {
            "headers": ["Plate", "Model", "Driver/Employee", "Project", "Location", "Mobile"],
            "rows": [["A 123", "Navara", "Adil Khan", "Site A", "AUH", "050"]],
        },
    }
    result = enhance_list_visualization(table, "")
    assert result["visual_type"] == "DATA_TABLE"


def test_query_correction_suggests_typo_fix() -> None:
    suggestion = suggest_query_corrections("need lpos for natioanl gurad project")
    assert suggestion is not None
    labels = [option["label"] for option in suggestion["options"]]
    assert any("national" in label.lower() for label in labels)


def test_procurement_preflight_asks_for_date() -> None:
    clear_entities("lpo-date")
    update_entities(
        "lpo-date",
        intent="procurement",
        procurement_record_type="lpo_invoices",
        project_id=123,
        project_name="National Guard",
    )
    update_entities_from_message("lpo-date", "need lpos for national guard")
    preflight = run_chat_preflight(
        "need lpos for national guard — National Guard Center",
        session_id="lpo-date",
        confirmed_entities=[],
    )
    assert preflight is not None
    assert preflight.ui_blocks
    assert preflight.ui_blocks[0]["type"] == "date_quick"
    clear_entities("lpo-date")
