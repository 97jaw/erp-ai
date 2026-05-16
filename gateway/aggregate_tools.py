from __future__ import annotations

import re
from datetime import date
from typing import Any

from adapters.v14.connector import OdooV14Adapter
from gateway.tool_input_normalization import normalize_sql_aggregate_input


def _month_bounds() -> tuple[str, str]:
    today = date.today()
    return today.replace(day=1).isoformat(), today.isoformat()


def _normalize_model_name(model: str) -> str:
    return (model or "").strip().replace(".", "_").replace("-", "_")


def _field_sum_name(field: str) -> str:
    return f"{field}_sum" if not field.endswith("_sum") else field


def _row_value(row: dict[str, Any], field: str) -> float:
    if field in row:
        return float(row.get(field) or 0)
    sum_key = _field_sum_name(field)
    if sum_key in row:
        return float(row.get(sum_key) or 0)
    return 0.0


def _label_for_group(row: dict[str, Any], group_field: str) -> str:
    value = row.get(group_field)
    if isinstance(value, (list, tuple)) and len(value) > 1:
        return str(value[1])
    if value in (None, False):
        return "Undefined"
    return str(value)


def _read_group_fields(group_by: list[str], aggregates: list[Any]) -> list[str]:
    fields: list[str] = []
    for spec in aggregates:
        field_name = str(spec).strip()
        if not field_name:
            continue
        if field_name.endswith(":count"):
            continue
        if ":" in field_name:
            fields.append(field_name)
        else:
            fields.append(f"{field_name}:sum")
    if not fields and group_by:
        fields = [group_by[0]]
    return fields


def _normalize_read_group_order(
    order: str | None,
    group_by: list[str],
    aggregates: list[Any],
) -> str | None:
    if not order:
        if group_by and any(str(spec).endswith(":count") for spec in aggregates):
            return f"{group_by[0]}_count desc"
        if group_by:
            return group_by[0]
        return None

    normalized = str(order).strip()
    normalized = re.sub(
        r"(\w+):count\b",
        r"\1_count",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"(\w+):sum\b",
        r"\1_sum",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"(\w+):avg\b",
        r"\1_avg",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


def _aggregate_value(row: dict[str, Any], spec: Any) -> float:
    field_name = str(spec).strip()
    if field_name.endswith(":count"):
        base = field_name.split(":", 1)[0]
        for key in (f"{base}_count", "__count", f"{base}:count"):
            if key in row:
                return float(row.get(key) or 0)
        return 0.0
    return _row_value(row, field_name)


def _apply_having(rows: list[dict[str, Any]], having: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not having:
        return rows

    filtered: list[dict[str, Any]] = []
    for row in rows:
        keep = True
        for expression, expected in having.items():
            match = re.match(r"^([a-zA-Z0-9_]+)\s*(!=|=|>|<|>=|<=)\s*(.+)$", str(expression).strip())
            if not match:
                continue
            field, operator, raw_value = match.groups()
            left = _row_value(row, field)
            try:
                right = float(raw_value)
            except ValueError:
                right = raw_value
            if operator == "!=" and left == right:
                keep = False
            elif operator == "=" and left != right:
                keep = False
            elif operator == ">" and not left > right:
                keep = False
            elif operator == "<" and not left < right:
                keep = False
            elif operator == ">=" and not left >= right:
                keep = False
            elif operator == "<=" and not left <= right:
                keep = False
        if keep:
            filtered.append(row)
    return filtered


def sql_aggregate(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    tool_input = normalize_sql_aggregate_input(tool_input)
    model = tool_input.get("model")
    if not model:
        return {"error": "missing_model", "message": "model is required for sql_aggregate"}

    aggregates = tool_input.get("aggregates") or []
    if not aggregates:
        return {"error": "missing_aggregates", "message": "aggregates is required for sql_aggregate"}

    group_by = tool_input.get("group_by") or []
    fields = _read_group_fields(group_by, aggregates)
    order = _normalize_read_group_order(tool_input.get("order"), group_by, aggregates)

    try:
        rows = adapter.read_group(
            model=model,
            domain=tool_input.get("filters") or [],
            fields=fields,
            groupby=group_by,
            limit=int(tool_input.get("limit") or 100),
            order=order,
        )
    except Exception as exc:
        if order:
            rows = adapter.read_group(
                model=model,
                domain=tool_input.get("filters") or [],
                fields=fields,
                groupby=group_by,
                limit=int(tool_input.get("limit") or 100),
                order=None,
            )
        else:
            raise exc

    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized = dict(row)
        for field in aggregates:
            normalized[str(field)] = _aggregate_value(row, field)
        if group_by:
            normalized["group_label"] = _label_for_group(row, group_by[0])
        normalized_rows.append(normalized)

    normalized_rows = _apply_having(normalized_rows, tool_input.get("having"))

    return {
        "model": model,
        "rows": normalized_rows,
        "row_count": len(normalized_rows),
        "group_by": group_by,
        "aggregates": aggregates,
        "synthesized": True,
    }


def synthesize_trial_balance(
    adapter: OdooV14Adapter,
    date_from: str | None,
    date_to: str | None,
) -> dict[str, Any]:
    if not date_from or not date_to:
        date_from, date_to = _month_bounds()

    aggregate = sql_aggregate(
        adapter,
        {
            "model": "account.move.line",
            "filters": [
                ["parent_state", "=", "posted"],
                ["date", ">=", date_from],
                ["date", "<=", date_to],
            ],
            "group_by": ["account_id"],
            "aggregates": ["debit", "credit"],
            "limit": 5000,
            "order": "account_id",
        },
    )

    rows: list[list[Any]] = []
    total_debit = 0.0
    total_credit = 0.0
    for row in aggregate.get("rows") or []:
        debit = float(row.get("debit", 0) or 0)
        credit = float(row.get("credit", 0) or 0)
        balance = debit - credit
        if debit == 0 and credit == 0:
            continue
        rows.append([
            row.get("group_label") or row.get("account_id"),
            round(debit, 2),
            round(credit, 2),
            round(balance, 2),
        ])
        total_debit += debit
        total_credit += credit

    rows.append(["Total", round(total_debit, 2), round(total_credit, 2), round(total_debit - total_credit, 2)])
    balanced = abs(total_debit - total_credit) < 0.05

    return {
        "report_type": "trial_balance",
        "report_name": "Trial Balance",
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
        "row_count": max(len(rows) - 1, 0),
        "totals": {
            "debit": round(total_debit, 2),
            "credit": round(total_credit, 2),
            "difference": round(total_debit - total_credit, 2),
            "balanced": balanced,
        },
        "synthesized": True,
        "source": "sql_aggregate",
        "data": {
            "headers": ["Account", "Debit", "Credit", "Balance"],
            "rows": rows,
        },
        "quality_note": (
            "Simplified period-only trial balance (no initial/ending columns). "
            "Use ins.trial.balance wizard path for full Odoo parity."
        ),
    }
