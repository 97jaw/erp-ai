from __future__ import annotations

import json
import re
from typing import Any

from adapters.v14.connector import OdooV14Adapter
from core.entity_normalization import client_name_matches_scope, normalize_client_query
from gateway.session_scope import SessionScopeStore

PO_KEYWORDS = re.compile(
    r"\b(?:purchase orders?|purchase order|lpo)\b",
    re.IGNORECASE,
)
PO_LIMIT_RE = re.compile(r"\blast\s+(\d+)\b", re.IGNORECASE)
PO_CLIENT_PATTERNS = (
    re.compile(
        r"\b(?:purchase orders?|purchase order|lpo)\b\s+(?:for|of)\s+(?:client\s+)?(.+?)(?:[.?!]|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:for|of)\s+(?:client\s+)?(.+?)\s+\b(?:purchase orders?|purchase order|lpo)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:give|show|share|send|get|fetch)\s+(?:me\s+)?(?:the\s+)?(?:last\s+\d+\s+)?(?:for|of)\s+(.+)$",
        re.IGNORECASE,
    ),
)


def _clean_client_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip(" \"'.,;:-")
    cleaned = re.sub(
        r"^(?:client|customer)\s+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = cleaned.strip(" \"'.,;:-")
    variants = normalize_client_query(cleaned)
    return variants[0] if variants else cleaned


def parse_purchase_order_request(message: str) -> dict[str, Any] | None:
    text = message or ""
    if not PO_KEYWORDS.search(text):
        if not PO_LIMIT_RE.search(text):
            return None
        if not re.search(r"\bfor\b", text, re.IGNORECASE):
            return None

    limit = 20
    limit_match = PO_LIMIT_RE.search(text)
    if limit_match:
        limit = int(limit_match.group(1))

    client_name = None
    for pattern in PO_CLIENT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        candidate = _clean_client_name(match.group(1))
        if candidate and (
            client_name is None or len(candidate) > len(client_name)
        ):
            client_name = candidate

    if not client_name:
        return None

    return {
        "client_name": client_name,
        "limit"      : min(max(limit, 1), 50),
    }


def purchase_order_client_filter_fields() -> set[str]:
    import os

    return {
        name.strip()
        for name in os.environ.get(
            "ODOO_PO_CLIENT_FIELDS",
            "client,client_id,customer_id,x_client_id",
        ).split(",")
        if name.strip()
    }


def purchase_order_search_is_client_scoped(filters: list[Any]) -> bool:
    scoped_fields = purchase_order_client_filter_fields() | {
        "project_id",
        "id",
        "name",
    }
    for clause in filters:
        if not isinstance(clause, (list, tuple)) or len(clause) < 3:
            continue
        if clause[0] in scoped_fields:
            return True
    return False


def _filter_orders_to_scope(
    orders: list[dict[str, Any]],
    *,
    requested_client: str | None,
    matched_clients: list[dict[str, Any]],
    project_ids: list[int],
) -> list[dict[str, Any]]:
    if not orders:
        return []

    requested_names = normalize_client_query(requested_client or "")
    matched_names = [client.get("name", "") for client in matched_clients]
    allowed_project_ids = {int(project_id) for project_id in project_ids}

    filtered: list[dict[str, Any]] = []
    for order in orders:
        project_id = order.get("project_id")
        if isinstance(project_id, int) and project_id in allowed_project_ids:
            filtered.append(order)
            continue
        if client_name_matches_scope(
            order.get("client_name"),
            requested_names = requested_names,
            matched_names   = matched_names,
        ):
            filtered.append(order)
    return filtered


def wrap_purchase_order_result(
    result: dict[str, Any],
    *,
    client_name: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    requested_client = client_name or result.get("requested_client")
    requested_limit = limit or result.get("requested_limit") or result.get("limit") or 20
    matched_clients = result.get("matched_clients") or []
    project_ids = [int(project_id) for project_id in (result.get("project_ids") or [])]
    orders = _filter_orders_to_scope(
        result.get("orders") or [],
        requested_client = requested_client,
        matched_clients  = matched_clients,
        project_ids      = project_ids,
    )
    count = len(orders)

    return {
        "request": {
            "client_name": requested_client,
            "limit"      : requested_limit,
        },
        "matched_clients": matched_clients,
        "projects"       : result.get("projects") or [],
        "orders"         : orders,
        "count"          : count,
        "requested_limit": requested_limit,
        "client_fields"  : result.get("client_fields") or [],
        "strategies"     : result.get("strategies") or [],
        "note"           : result.get("note"),
        "guidance"       : (
            "Describe only orders in this payload. "
            "client_name is the customer on the purchase order; supplier_name is the vendor. "
            "If count is lower than requested_limit, report the exact count and do not invent rows. "
            "Do not mention purchase orders for other clients."
        ),
    }


def fetch_purchase_orders(
    adapter: OdooV14Adapter,
    *,
    client_name: str | None = None,
    partner_ids: list[int] | None = None,
    project_name: str | None = None,
    project_id: int | None = None,
    limit: int = 20,
    session_id: str | None = None,
) -> dict[str, Any]:
    scope = SessionScopeStore.get(session_id) if session_id else {}
    if not client_name:
        client_name = scope.get("client_name")
    if not partner_ids:
        partner_ids = scope.get("partner_ids")

    result = adapter.get_purchase_orders(
        client_name  = client_name,
        partner_ids  = partner_ids,
        project_name = project_name,
        project_id   = project_id,
        limit        = limit,
    )
    wrapped = wrap_purchase_order_result(
        result,
        client_name = client_name,
        limit       = limit,
    )
    if session_id:
        SessionScopeStore.update(
            session_id,
            client_name = client_name,
            partner_ids = (
                [int(client["id"]) for client in wrapped["matched_clients"]]
                if wrapped.get("matched_clients")
                else result.get("partner_ids")
            ),
            project_ids = result.get("project_ids"),
        )
    return wrapped


def purchase_order_search_via_get_tool(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    filters = tool_input.get("filters") or []
    client_name = None
    partner_ids: list[int] = []
    project_id = None
    project_name = None

    client_fields = purchase_order_client_filter_fields()
    for clause in filters:
        if not isinstance(clause, (list, tuple)) or len(clause) < 3:
            continue
        field, operator, value = clause[0], clause[1], clause[2]
        if field in client_fields and operator in {"ilike", "like", "=", "in"}:
            if operator == "in" and isinstance(value, list):
                partner_ids.extend(int(item) for item in value)
            elif isinstance(value, str):
                client_name = value
        elif field == "project_id" and operator in {"=", "in"}:
            if operator == "in" and isinstance(value, list) and value:
                project_id = int(value[0])
            elif isinstance(value, int):
                project_id = value
        elif field == "name" and operator in {"ilike", "like", "="} and isinstance(value, str):
            project_name = value

    limit = int(tool_input.get("limit") or 20)
    if not client_name and not partner_ids and not project_id and not project_name:
        return {
            "error"    : "unscoped_purchase_order_search",
            "message"  : (
                "Use get_purchase_orders for client or project purchase order lists. "
                "On purchase.order, partner_id is the supplier/vendor, not the client."
            ),
            "hint_tool": "get_purchase_orders",
        }

    return fetch_purchase_orders(
        adapter,
        client_name  = client_name,
        partner_ids  = partner_ids or None,
        project_name = project_name,
        project_id   = project_id,
        limit        = limit,
    )


def prefetch_purchase_orders(
    adapter: OdooV14Adapter,
    message: str,
    *,
    session_id: str | None = None,
) -> dict[str, Any] | None:
    request = parse_purchase_order_request(message)
    if not request:
        return None
    return fetch_purchase_orders(
        adapter,
        client_name = request["client_name"],
        limit       = request["limit"],
        session_id  = session_id,
    )


def prefetch_system_block(payload: dict[str, Any]) -> str:
    return (
        "\n\nAUTHORITATIVE PURCHASE ORDER LOOKUP (already fetched from Odoo):\n"
        f"{json.dumps(payload, default=str)}\n"
        "Use only this payload for the purchase-order answer. "
        "Do not describe unrelated purchase orders from other clients."
    )
