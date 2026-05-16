from __future__ import annotations

from datetime import datetime
from typing import Any

FIELD_LABELS: dict[str, str] = {
    "amount_total": "Revenue",
    "amount_residual": "Outstanding Balance",
    "amount_untaxed": "Subtotal",
    "amount_tax": "Tax",
    "debit": "Debit",
    "credit": "Credit",
    "balance": "Balance",
    "wo_amount": "Contract Amount",
    "wo_ref_no": "WO Reference",
    "x_studio_total_cost": "Total Cost",
    "partner_id": "Client",
    "user_id": "Salesperson",
    "company_id": "Company",
    "currency_id": "Currency",
    "journal_id": "Journal",
    "account_id": "Account",
    "analytic_account_id": "Project",
    "stage_id": "Stage",
    "state": "Status",
    "type": "Type",
    "category_id": "Category",
    "date": "Date",
    "date_order": "Order Date",
    "invoice_date": "Invoice Date",
    "invoice_date_due": "Due Date",
    "date_start": "Start Date",
    "date_end": "End Date",
    "__count": "Count",
    "id:count": "Total Records",
    "date:day": "Day",
    "date:week": "Week",
    "date:month": "Month",
    "date:quarter": "Quarter",
    "date:year": "Year",
}

VALUE_LABELS: dict[str, str] = {
    "out_invoice": "Customer Invoice",
    "in_invoice": "Vendor Bill",
    "out_refund": "Customer Refund",
    "in_refund": "Vendor Refund",
    "draft": "Draft",
    "posted": "Posted",
    "cancel": "Cancelled",
    "paid": "Paid",
    "not_paid": "Unpaid",
    "partial": "Partially Paid",
    "open": "Open",
    "in_payment": "In Payment",
    "reversed": "Reversed",
}

AGGREGATE_FUNCTION_LABELS: dict[str, str] = {
    "sum": "Total",
    "avg": "Average",
    "min": "Minimum",
    "max": "Maximum",
    "count": "Count",
    "count_distinct": "Distinct Count",
}


def humanize_field(field: str) -> str:
    clean = (field or "").split(":")[0]
    return FIELD_LABELS.get(clean, clean.replace("_", " ").title())


def humanize_value(field: str, value: Any) -> Any:
    if field in {"state", "type", "payment_state"} and isinstance(value, str):
        return VALUE_LABELS.get(value, value)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[1]
    return value


def humanize_aggregate_spec(spec: Any) -> str:
    text = str(spec or "").strip()
    if not text:
        return "Value"
    if ":" not in text:
        return humanize_field(text)
    field, func = text.split(":", 1)
    base = humanize_field(field)
    if func == "sum" and field in {"amount_total", "debit", "credit", "balance", "wo_amount"}:
        return base
    return f"{base} ({AGGREGATE_FUNCTION_LABELS.get(func, func.title())})"


def humanize_group_label(label: Any) -> str:
    if label is None:
        return "Unassigned"
    if isinstance(label, (list, tuple)) and len(label) > 1:
        return str(label[1])
    text = str(label).strip()
    if not text or text.lower() in {"undefined", "false", "none"}:
        return "Unassigned"
    return text


def format_currency(amount: float | int | None, currency: str = "AED") -> str:
    if amount is None:
        return f"{currency} 0"
    value = float(amount)
    if value == 0:
        return f"{currency} 0"
    if abs(value) >= 1_000_000:
        return f"{currency} {value / 1_000_000:,.1f}M"
    if abs(value) >= 1_000:
        return f"{currency} {value:,.0f}"
    return f"{currency} {value:,.2f}"


def format_percentage(value: float | int | None, decimals: int = 1) -> str:
    if value is None:
        return "0%"
    return f"{float(value):,.{decimals}f}%"


def format_number(value: float | int | None, decimals: int = 0) -> str:
    if value is None:
        return "0"
    return f"{float(value):,.{decimals}f}"


def format_date(date_str: str, style: str = "long") -> str:
    try:
        dt = datetime.fromisoformat(str(date_str).split("T")[0])
    except ValueError:
        return str(date_str)
    if style == "short":
        return dt.strftime("%d %b %Y")
    if style == "month":
        return dt.strftime("%B %Y")
    if style == "long":
        return dt.strftime("%B %d, %Y")
    return dt.strftime("%Y-%m-%d")
