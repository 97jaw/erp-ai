"""
Translate list_records intent into a concrete Odoo query/aggregate plan.
"""
from __future__ import annotations
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Map subject_area → default Odoo model
SUBJECT_MODEL_MAP = {
    "project":   "project.project",
    "hr":        "hr.employee",
    "financial": "account.move",
    "sales":     "sale.order",
    "purchase":  "purchase.order",
    "inventory": "stock.quant",
    "fleet":     "fleet.vehicle",
    "agreement": "sale.contracted.order",  # Elrace custom
    "payroll":   "hr.payslip",
}

# Default fields per model (keep responses concise)
DEFAULT_FIELDS = {
    "project.project":       ["name", "partner_id", "date_start", "date", "state"],
    "project.task":          ["name", "project_id", "user_ids", "stage_id", "date_deadline"],
    "hr.employee":           ["name", "department_id", "job_title", "active"],
    "hr.contract":           ["name", "employee_id", "date_start", "date_end", "state"],
    "account.move":          ["name", "partner_id", "amount_total", "state", "invoice_date"],
    "sale.order":            ["name", "partner_id", "amount_total", "state"],
    "purchase.order":        ["name", "partner_id", "amount_total", "state", "date_order"],
    "fleet.vehicle":         ["name", "driver_id", "license_plate", "state_id"],
    "stock.quant":           ["product_id", "location_id", "quantity", "reserved_quantity"],
    "sale.contracted.order": ["name", "partner_id", "amount_total", "state"],
    "hr.payslip":            ["name", "employee_id", "date_from", "date_to", "state"],
}


def build_list_query(intent: Any, message: str) -> dict[str, Any]:
    """
    Convert a list_records intent into a query plan dict with keys:
      model, domain, fields, limit, order, use_aggregate, group_by, aggregates
    """
    subject = (getattr(intent, "subject_area", None) or "").lower()
    entities = getattr(intent, "entities", None) or []

    # Refine model from entities or message keywords
    model = _resolve_model(subject, message, entities)
    domain: list[Any] = []
    group_by: str | None = None
    use_aggregate = False
    limit = 50
    order = None

    for entity in entities:
        etype = getattr(entity, "type", "") or ""
        evalue = getattr(entity, "value", "") or ""
        erelation = getattr(entity, "relation", "") or ""

        if etype == "date_filter":
            domain += _date_filter_domain(evalue, model)

        elif etype == "status_filter":
            domain += _status_filter_domain(evalue)

        elif etype == "group_by":
            group_by = evalue
            use_aggregate = True

        elif etype == "related_entity":
            domain += _related_entity_domain(evalue, erelation, model)

        elif etype == "anti_join":
            # anti-join handled as best-effort domain; complex cases need two-step
            domain += _anti_join_domain(evalue, model)

    # Auto-detect group_by from message
    if not group_by and _message_wants_grouping(message):
        group_by, use_aggregate = _infer_group_by(message, model)

    # Auto-detect limit / ordering
    top_n = _extract_top_n(message)
    if top_n:
        limit = top_n
        order = _infer_order(message, model)

    fields = DEFAULT_FIELDS.get(model, [])

    plan: dict[str, Any] = {
        "model": model,
        "domain": domain,
        "fields": fields,
        "limit": limit,
        "order": order,
        "use_aggregate": use_aggregate,
        "group_by": [group_by] if group_by and isinstance(group_by, str) else (group_by or []),
        "aggregates": ["id:count"],
    }
    logger.info("[ListQueryRouter] plan=%s", plan)
    return plan


def _resolve_model(subject: str, message: str, entities: list[Any]) -> str:
    msg = message.lower()
    # Financial sub-types
    if subject == "financial":
        if any(k in msg for k in ("invoice", "bill", "receivable")):
            return "account.move"
        if any(k in msg for k in ("payslip", "salary", "payroll")):
            return "hr.payslip"
        return "account.move"
    # HR sub-types
    if subject == "hr":
        if "payslip" in msg or "salary" in msg:
            return "hr.payslip"
        if "contract" in msg and "employee" not in msg:
            return "hr.contract"
        return "hr.employee"
    # Purchase sub-types
    if subject == "purchase":
        return "purchase.order"
    # Project sub-types
    if subject == "project":
        if "task" in msg:
            return "project.task"
        return "project.project"
    return SUBJECT_MODEL_MAP.get(subject, "project.project")


def _date_filter_domain(value: str, model: str) -> list[Any]:
    v = str(value).strip()
    if len(v) == 4 and v.isdigit():  # Year only
        # Use model-appropriate date field
        date_field = "date_start"
        if model == "account.move":
            date_field = "invoice_date"
        elif model == "purchase.order":
            date_field = "date_order"
        elif model == "hr.payslip":
            date_field = "date_from"
        elif model == "sale.order":
            date_field = "date_order"
        return [
            [date_field, ">=", f"{v}-01-01"],
            [date_field, "<=", f"{v}-12-31"],
        ]
    return []


def _status_filter_domain(value: str) -> list[Any]:
    v = (value or "").lower()
    if v in ("active", "open"):
        return [["active", "=", True]]
    if v in ("inactive", "closed", "done"):
        return [["active", "=", False]]
    return []


def _related_entity_domain(value: str, relation: str, model: str) -> list[Any]:
    """Return best-effort text-search domain for cross-list queries."""
    if "partner" in relation:
        return [["partner_id.name", "ilike", value]]
    if "project" in relation or "analytic" in relation:
        return [["project_id.name", "ilike", value]]
    if "employee" in relation or "driver" in relation:
        return [["|", "employee_id.name", "ilike", value]]
    # Fallback: name search on the related entity
    return [["name", "ilike", value]]


def _anti_join_domain(value: str, model: str) -> list[Any]:
    """Return empty — anti-join requires a two-step query handled at call site."""
    return []


def _message_wants_grouping(message: str) -> bool:
    msg = message.lower()
    return any(k in msg for k in (
        "wise", "by client", "by partner", "grouped", "group by",
        "per client", "per partner",
    ))


def _infer_group_by(message: str, model: str) -> tuple[str, bool]:
    msg = message.lower()
    if "client" in msg or "partner" in msg:
        return "partner_id", True
    if "department" in msg:
        return "department_id", True
    if "status" in msg or "state" in msg:
        return "state", True
    return "partner_id", True


def _extract_top_n(message: str) -> int | None:
    import re
    m = re.search(r"\btop\s+(\d+)\b", message, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _infer_order(message: str, model: str) -> str | None:
    msg = message.lower()
    if "expense" in msg or "cost" in msg or "amount" in msg:
        return "amount_total desc"
    return None
