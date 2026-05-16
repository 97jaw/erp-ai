from __future__ import annotations

from unittest.mock import MagicMock

from gateway.aggregate_tools import _normalize_read_group_order
from gateway.group_aggregate_domain import (
    apply_model_domain_defaults,
    build_group_aggregate_error,
    normalize_account_move_domain,
)
from gateway.tool_validation import validate_tool_result


def test_normalize_read_group_order_maps_sum_syntax() -> None:
    assert _normalize_read_group_order(
        "amount_total:sum desc",
        ["partner_id"],
        ["amount_total:sum"],
    ) == "amount_total_sum desc"


def test_normalize_account_move_domain_uses_move_type() -> None:
    adapter = MagicMock()
    adapter._get_model_fields.return_value = {
        "move_type": {"type": "selection"},
        "state": {"type": "selection"},
    }
    domain = normalize_account_move_domain(
        adapter,
        "account.move",
        [["type", "=", "out_invoice"], ["state", "=", "posted"]],
    )
    assert domain == [["move_type", "=", "out_invoice"], ["state", "=", "posted"]]


def test_apply_model_domain_defaults_adds_posted_and_invoice_field() -> None:
    adapter = MagicMock()
    adapter._get_model_fields.return_value = {
        "move_type": {"type": "selection"},
        "state": {"type": "selection"},
        "company_id": {"type": "many2one"},
    }
    domain = apply_model_domain_defaults(adapter, "account.move", [])
    assert ["move_type", "=", "out_invoice"] in domain
    assert ["state", "=", "posted"] in domain
    assert ["company_id", "=", 1] in domain


def test_group_aggregate_error_includes_recovery() -> None:
    payload = build_group_aggregate_error(
        error="group_and_aggregate_failed",
        message="Invalid field order amount_total:sum desc",
        model="account.move",
        domain=[["type", "=", "out_invoice"]],
        group_by=["partner_id"],
        aggregates=["amount_total:sum"],
        adapter=MagicMock(_get_model_fields=MagicMock(return_value={"move_type": {}})),
    )
    assert payload["recovery"]["fallback_tool"] == "sql_aggregate"
    assert payload["recovery"]["suggested_order_by"] == "amount_total_sum desc"


def test_validate_tool_result_enriches_group_aggregate_error() -> None:
    result = validate_tool_result(
        "group_and_aggregate",
        {"error": "group_and_aggregate_failed", "message": "Invalid field type"},
    )
    assert result["recovery"]["switch_strategy"] is True
    assert result["recovery"]["fallback_tool"] == "sql_aggregate"
