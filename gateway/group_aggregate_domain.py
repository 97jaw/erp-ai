from __future__ import annotations

from typing import Any

from adapters.v14.connector import OdooV14Adapter


def _domain_has_field(domain: list[Any], field: str) -> bool:
    for item in domain:
        if isinstance(item, (list, tuple)) and item and item[0] == field:
            return True
    return False


def invoice_type_field(adapter: OdooV14Adapter, model: str) -> str | None:
    if model != "account.move":
        return None
    fields = adapter._get_model_fields(model)
    if "move_type" in fields:
        return "move_type"
    if "type" in fields:
        return "type"
    return None


def normalize_account_move_domain(
    adapter: OdooV14Adapter,
    model: str,
    domain: list[Any],
) -> list[Any]:
    if model != "account.move":
        return list(domain)

    invoice_field = invoice_type_field(adapter, model)
    normalized: list[Any] = []
    for item in domain:
        if not isinstance(item, (list, tuple)) or len(item) < 3:
            normalized.append(item)
            continue
        field, operator, value = item[0], item[1], item[2]
        if field in {"type", "move_type"} and invoice_field:
            normalized.append([invoice_field, operator, value])
        else:
            normalized.append([field, operator, value])
    return normalized


def apply_model_domain_defaults(
    adapter: OdooV14Adapter,
    model: str,
    domain: list[Any],
) -> list[Any]:
    normalized = normalize_account_move_domain(adapter, model, domain)
    if model == "account.move":
        invoice_field = invoice_type_field(adapter, model)
        if not _domain_has_field(normalized, "company_id"):
            normalized.append(["company_id", "=", 1])
        if not _domain_has_field(normalized, "state"):
            normalized.append(["state", "=", "posted"])
        if invoice_field and not _domain_has_field(normalized, invoice_field):
            normalized.append([invoice_field, "=", "out_invoice"])
    elif model == "account.move.line":
        if not _domain_has_field(normalized, "company_id"):
            normalized.append(["company_id", "=", 1])
        if not _domain_has_field(normalized, "parent_state"):
            normalized.append(["parent_state", "=", "posted"])
    return normalized


def build_group_aggregate_error(
    *,
    error: str,
    message: str,
    model: str,
    domain: list[Any],
    group_by: list[str],
    aggregates: list[Any],
    adapter: OdooV14Adapter | None = None,
) -> dict[str, Any]:
    lowered = message.lower()
    hints: list[str] = []
    suggested_order_by = None
    suggested_domain = list(domain)

    if model == "account.move":
        invoice_field = invoice_type_field(adapter, model) if adapter else "move_type"
        if invoice_field:
            hints.append(
                f"On account.move use {invoice_field}=out_invoice with state=posted for revenue grouping."
            )
            suggested_domain = apply_model_domain_defaults(adapter, model, suggested_domain) if adapter else suggested_domain
        if "type" in lowered and "invalid field" in lowered:
            hints.append("This database may use move_type instead of type on account.move.")

    if "order" in lowered or "orderby" in lowered:
        suggested_order_by = "amount_total_sum desc"
        hints.append("Use order_by like amount_total_sum desc instead of amount_total:sum desc.")

    if "field" in lowered and "does not exist" in lowered:
        hints.append("Verify group_by and aggregate fields exist on the selected model.")

    user_message = hints[0] if hints else message
    return {
        "error": error,
        "error_type": error,
        "message": message,
        "user_message": user_message,
        "recovery": {
            "switch_strategy": True,
            "do_not_repeat_same_call": True,
            "fallback_tool": "sql_aggregate",
            "suggested_domain": suggested_domain,
            "suggested_order_by": suggested_order_by,
            "suggested_group_by": group_by,
            "suggested_aggregates": aggregates,
        },
        "query": {
            "model": model,
            "domain": domain,
            "group_by": group_by,
            "aggregates": aggregates,
        },
    }
