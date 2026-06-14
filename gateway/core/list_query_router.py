"""
Translate list_records intent into a concrete Odoo query/aggregate plan.
Also exposes is_list_pattern() for keyword-based pre-detection.
"""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword-based pre-detection (used by intelligent_handler.py)
# ---------------------------------------------------------------------------

_LIST_KEYWORDS = re.compile(
    r"""
    \b(
        list\s+(down\s+|all\s+|of\s+)?               # "list", "list down", "list all"
      | show\s+(all|me\s+all)\s+                      # "show all", "show me all"
      | \w+\s+wise\s+                                 # "client wise", "partner wise"
      | grouped?\s+by\s+                              # "grouped by", "group by"
      | per\s+(client|partner|department|project)\s+  # "per client"
      | by\s+(client|partner|department)\s+           # "by client"
      | top\s+\d+\s+                                  # "top 10"
      | all\s+(active|open|closed|pending)\s+         # "all active"
      | (active|open)\s+(projects?|employees?|invoices?|orders?|vehicles?)
      | (employees?|staff|workers?)\s+(in|on|at|of|for|without|with\s+no)
      | (vehicles?|cars?)\s+(assigned|belonging|for)
      | (invoices?|bills?|pos?|orders?)\s+for\s+      # "invoices for X"
      | (projects?|tasks?)\s+for\s+                   # "projects for X"
      | (projects?|tasks?)\s+(of|in|for)\s+\d{4}     # "projects of 2024"
      | (agreements?|contracts?)\s+for\s+             # "agreements for X"
      | (without|with\s+no)\s+\w+                     # "without contracts"
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Patterns that look like list but are actually single-entity deep analysis
_NON_LIST_OVERRIDES = re.compile(
    r"""
    \b(
        expense|cost|p&l|profit|loss|balance\s+sheet
        |compare|vs\s+|breakdown|ledger|payroll\s+report
    )\b
    """,
    re.IGNORECASE | re.VERBOSE,
)


def is_list_pattern(message: str) -> bool:
    """Return True if the message strongly looks like a list/browse query."""
    if _NON_LIST_OVERRIDES.search(message):
        return False
    return bool(_LIST_KEYWORDS.search(message))


# ---------------------------------------------------------------------------
# Model and field maps
# ---------------------------------------------------------------------------

SUBJECT_MODEL_MAP = {
    "project":   "project.project",
    "hr":        "hr.employee",
    "financial": "account.move",
    "sales":     "sale.order",
    "purchase":  "purchase.order",
    "inventory": "stock.quant",
    "fleet":     "fleet.vehicle",
    "agreement": "sale.contracted.order",
    "payroll":   "hr.payslip",
}

DEFAULT_FIELDS = {
    "project.project":       ["name", "partner_id", "date_start", "date", "stage_id"],
    "project.task":          ["name", "project_id", "user_ids", "stage_id", "date_deadline"],
    "hr.employee":           ["name", "department_id", "job_title", "active"],
    "hr.contract":           ["name", "employee_id", "date_start", "date_end", "state"],
    "account.move":          ["name", "partner_id", "amount_total", "state", "invoice_date", "move_type"],
    "sale.order":            ["name", "partner_id", "amount_total", "state", "date_order"],
    "purchase.order":        ["name", "partner_id", "amount_total", "state", "date_order"],
    "fleet.vehicle":         ["name", "driver_id", "license_plate", "state_id"],
    "stock.quant":           ["product_id", "location_id", "quantity"],
    "sale.contracted.order": ["name", "partner_id", "amount_total", "state"],
    "hr.payslip":            ["name", "employee_id", "date_from", "date_to", "state"],
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def build_list_query(intent: Any, message: str) -> dict[str, Any]:
    """
    Convert a list_records intent into a query plan dict with keys:
      model, domain, fields, limit, order, use_aggregate, group_by, aggregates
    """
    subject = (getattr(intent, "subject_area", None) or "").lower()
    entities = getattr(intent, "entities", None) or []
    msg_lower = message.lower()

    model = _resolve_model(subject, message, entities)
    domain: list[Any] = _base_domain(model, msg_lower)
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
            domain += _anti_join_domain(evalue, model)

    # Keyword-based date extraction when intent entities missed it
    if not any(getattr(e, "type", "") == "date_filter" for e in entities):
        year_match = re.search(r"\b(20\d{2})\b", message)
        if year_match:
            domain += _date_filter_domain(year_match.group(1), model)

    # Keyword-based group_by when intent missed it
    if not group_by and _message_wants_grouping(msg_lower):
        group_by, use_aggregate = _infer_group_by(msg_lower, model)

    # Keyword-based related entity when intent missed it
    if not any(getattr(e, "type", "") in ("related_entity", "anti_join") for e in entities):
        extra = _keyword_related_domain(msg_lower, model)
        if extra:
            domain += extra

    # Top-N
    top_n = _extract_top_n(message)
    if top_n:
        limit = top_n
        order = _infer_order(msg_lower, model)

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
    logger.info("[ListQueryRouter] model=%s domain=%s use_aggregate=%s group_by=%s",
                model, domain, use_aggregate, group_by)
    return plan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_model(subject: str, message: str, entities: list[Any]) -> str:
    msg = message.lower()
    if subject == "financial":
        if any(k in msg for k in ("invoice", "bill", "receivable", "payable")):
            return "account.move"
        if any(k in msg for k in ("payslip", "salary", "payroll")):
            return "hr.payslip"
        return "account.move"
    if subject == "hr":
        if "payslip" in msg or "salary" in msg:
            return "hr.payslip"
        if "contract" in msg and "employee" not in msg:
            return "hr.contract"
        return "hr.employee"
    if subject == "purchase":
        return "purchase.order"
    if subject == "project":
        if "task" in msg:
            return "project.task"
        return "project.project"
    # Keyword override regardless of subject
    if any(k in msg for k in ("invoice", "bill")):
        return "account.move"
    if any(k in msg for k in ("purchase order", " po ", " lpo ")):
        return "purchase.order"
    if any(k in msg for k in ("employee", "staff", "worker")):
        return "hr.employee"
    if any(k in msg for k in ("vehicle", "car", "fleet")):
        return "fleet.vehicle"
    if any(k in msg for k in ("agreement", "contract")):
        return "sale.contracted.order"
    if any(k in msg for k in ("project",)):
        return "project.project"
    return SUBJECT_MODEL_MAP.get(subject, "project.project")


def _base_domain(model: str, msg: str) -> list[Any]:
    """Add default restricting filters (e.g. invoice type for account.move)."""
    if model == "account.move":
        # Narrow to customer/vendor invoices only (exclude journal entries, payments)
        if any(k in msg for k in ("invoice", "receivable", "customer")):
            return [["move_type", "in", ["out_invoice", "out_refund"]]]
        if any(k in msg for k in ("bill", "payable", "vendor", "supplier")):
            return [["move_type", "in", ["in_invoice", "in_refund"]]]
        # Generic — all posted invoices
        return [["move_type", "in", ["out_invoice", "out_refund", "in_invoice", "in_refund"]]]
    return []


def _date_filter_domain(value: str, model: str) -> list[Any]:
    v = str(value).strip()
    if len(v) == 4 and v.isdigit():
        # Map model to the right date field
        if model == "project.project":
            # For projects: match year in name OR date_start falls in that year.
            # write_date is unreliable (projects get updated every year).
            return [
                "|",
                ["name", "ilike", v],
                "&",
                ["date_start", ">=", f"{v}-01-01"],
                ["date_start", "<=", f"{v}-12-31"],
            ]
        field_map = {
            "account.move":          "invoice_date",
            "purchase.order":        "date_order",
            "sale.order":            "date_order",
            "hr.payslip":            "date_from",
            "hr.contract":           "date_start",
            "sale.contracted.order": "date_order",
        }
        date_field = field_map.get(model, "create_date")
        return [
            [date_field, ">=", f"{v}-01-01"],
            [date_field, "<=", f"{v}-12-31"],
        ]
    # Month-year like "June 2026"
    month_map = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    m = re.search(r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})", v, re.I)
    if m:
        month = month_map[m.group(1).lower()]
        year = m.group(2)
        field_map2 = {"account.move": "invoice_date", "purchase.order": "date_order"}
        date_field = field_map2.get(model, "create_date")
        return [
            [date_field, ">=", f"{year}-{month}-01"],
            [date_field, "<=", f"{year}-{month}-31"],
        ]
    return []


def _status_filter_domain(value: str) -> list[Any]:
    v = (value or "").lower()
    if v in ("active", "open"):
        return [["active", "=", True]]
    if v in ("inactive", "closed", "done", "cancelled"):
        return [["active", "=", False]]
    return []


def _related_entity_domain(value: str, relation: str, model: str) -> list[Any]:
    """Return best-effort text-search domain for cross-list queries."""
    rel = relation.lower()
    if "partner" in rel:
        return [["partner_id.name", "ilike", value]]
    if "project" in rel or "analytic" in rel:
        return [["project_id.name", "ilike", value]]
    if "employee" in rel or "driver" in rel:
        # fleet.vehicle has driver_id (partner); hr models have employee_id
        if model == "fleet.vehicle":
            return [["driver_id.name", "ilike", value]]
        return [["employee_id.name", "ilike", value]]
    # Fallback: search partner then name
    return [["partner_id.name", "ilike", value]]


def _anti_join_domain(_value: str, _model: str) -> list[Any]:
    return []  # Two-step query; caller handles this


def _keyword_related_domain(msg: str, model: str) -> list[Any]:
    """Detect 'X for Y' cross-entity patterns from the raw message."""
    # "invoices for Abu Dhabi Police" / "projects for LPO X"
    m = re.search(r"\bfor\s+(.{3,60}?)(?:\s*$|\s+(?:in|of|from|during|this|last)\b)", msg, re.I)
    if m:
        entity_val = m.group(1).strip()
        # Don't apply if entity_val looks like a date
        if not re.match(r"^\d{4}$|^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", entity_val, re.I):
            if model in ("account.move", "purchase.order", "sale.order", "sale.contracted.order"):
                return [["partner_id.name", "ilike", entity_val]]
            if model == "project.project":
                return [["partner_id.name", "ilike", entity_val]]
    # "employees on/at/in Villa 34"
    m2 = re.search(r"\b(on|at|in|assigned\s+to)\s+(.{3,50}?)(?:\s*$|\s+(?:in|of|from|this|last)\b)", msg, re.I)
    if m2:
        entity_val = m2.group(2).strip()
        if model == "hr.employee":
            return [["project_id.name", "ilike", entity_val]]
    return []


def _message_wants_grouping(msg: str) -> bool:
    return any(k in msg for k in (
        "wise", "by client", "by partner", "by department",
        "grouped", "group by", "per client", "per partner",
        "client-wise", "partner-wise",
    ))


def _infer_group_by(msg: str, _model: str) -> tuple[str, bool]:
    if "client" in msg or "partner" in msg:
        return "partner_id", True
    if "department" in msg:
        return "department_id", True
    if "status" in msg or "state" in msg:
        return "state", True
    if "project" in msg:
        return "project_id", True
    return "partner_id", True


def _extract_top_n(message: str) -> int | None:
    m = re.search(r"\btop\s+(\d+)\b", message, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _infer_order(msg: str, model: str) -> str | None:
    if any(k in msg for k in ("expense", "cost", "amount", "revenue")):
        return "amount_total desc"
    return None
