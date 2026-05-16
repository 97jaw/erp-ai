from __future__ import annotations

from gateway.quality_formatting import (
    format_currency,
    format_percentage,
    humanize_aggregate_spec,
    humanize_field,
    humanize_group_label,
)


def test_humanize_aggregate_spec_hides_raw_syntax() -> None:
    assert humanize_aggregate_spec("amount_total:sum") == "Revenue"
    assert humanize_aggregate_spec("partner_id:count") == "Client (Count)"


def test_format_currency_uses_aed() -> None:
    assert format_currency(17364135.58) == "AED 17.4M"
    assert format_currency(0) == "AED 0"


def test_humanize_group_label_maps_undefined() -> None:
    assert humanize_group_label("Undefined") == "Unassigned"
    assert humanize_group_label([12, "Abu Dhabi Police"]) == "Abu Dhabi Police"


def test_humanize_field_maps_common_fields() -> None:
    assert humanize_field("partner_id") == "Client"
    assert humanize_field("amount_total") == "Revenue"
