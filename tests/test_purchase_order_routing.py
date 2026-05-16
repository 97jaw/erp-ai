from core.entity_normalization import normalize_client_query
from gateway.purchase_order_routing import parse_purchase_order_request


def test_normalize_client_query_strips_operating_unit_suffix():
    variants = normalize_client_query(
        "COLORS FOR CONTRACTING TRADE AND TRANSPORTATION ESTABLISHMENT CCT"
    )
    assert "COLORS FOR CONTRACTING TRADE AND TRANSPORTATION ESTABLISHMENT" in variants
    assert "COLORS FOR CONTRACTING TRADE AND TRANSPORTATION ESTABLISHMENT CCT" in variants


def test_parse_colors_client_request():
    request = parse_purchase_order_request(
        "share last 20 purchase orders of client "
        "COLORS FOR CONTRACTING TRADE AND TRANSPORTATION ESTABLISHMENT"
    )
    assert request is not None
    assert request["limit"] == 20
    assert "COLORS FOR CONTRACTING" in request["client_name"]


def test_parse_follow_up_client_request_without_po_keyword():
    request = parse_purchase_order_request(
        "okay then give me last 20 for abu dhabi police"
    )
    assert request is not None
    assert request["limit"] == 20
    assert request["client_name"].lower() == "abu dhabi police"
