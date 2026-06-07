"""Progressive report disclosure (QUERY_RESPONSE_INTELLIGENCE Phase 3)."""
from __future__ import annotations

import json
import re
from typing import Any

from gateway.query_pagination import QueryPageStore

SUMMARY_CHART_LIMIT = 5
STANDARD_PAGE_SIZE = 20
FULL_ROW_CAP = 500

_DETAIL_PATTERN = re.compile(
    r"\b("
    r"detail(?:ed|s)?|breakdown|line\s*items?|all\s+accounts?|"
    r"full\s+report|show\s+everything|expand|drill\s*down|"
    r"account\s+level|see\s+accounts?|table|rows"
    r")\b",
    re.IGNORECASE,
)
_FULL_PATTERN = re.compile(
    r"\b(all\s+records?|full\s+list|load\s+all|everything|complete\s+report|export\s+all)\b",
    re.IGNORECASE,
)

_DISCLOSURE_TYPES = frozenset({
    "FINANCIAL_REPORT",
    "DATA_TABLE",
    "GROUPED_TABLE",
})


def detect_disclosure_level(user_message: str = "") -> str:
    text = (user_message or "").strip()
    if not text:
        return "summary"
    if _FULL_PATTERN.search(text):
        return "full"
    if _DETAIL_PATTERN.search(text):
        return "standard"
    return "summary"


def _coerce_payload(result: Any) -> dict[str, Any] | None:
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _account_detail_rows(lines: list[dict[str, Any]]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for line in lines:
        level = int(line.get("level", 0) or 0)
        if level < 2:
            continue
        balance = float(line.get("balance", 0) or 0)
        debit = float(line.get("debit", 0) or 0)
        credit = float(line.get("credit", 0) or 0)
        if balance == 0 and debit == 0 and credit == 0:
            continue
        rows.append([
            line.get("name") or line.get("account_name") or "Account",
            debit,
            credit,
            balance,
        ])
    return rows


def _extract_detail_table(tool_results: list[Any]) -> dict[str, Any] | None:
    for result in reversed(tool_results):
        payload = _coerce_payload(result)
        if not payload:
            continue

        lines = payload.get("report_lines")
        if isinstance(lines, list) and lines:
            rows = _account_detail_rows(lines)
            if rows:
                return {
                    "headers": ["Account", "Debit", "Credit", "Balance"],
                    "rows": rows,
                }

        data = payload.get("data")
        if isinstance(data, dict):
            headers = data.get("headers")
            rows = data.get("rows") or []
            if rows:
                return {
                    "headers": headers or [],
                    "rows": rows,
                }

        rows = payload.get("rows")
        if isinstance(rows, list) and rows:
            headers = payload.get("headers") or []
            if not headers and rows and isinstance(rows[0], dict):
                headers = list(rows[0].keys())
            return {"headers": headers, "rows": rows}
    return None


def _build_summary_chart(rows: list[list[Any]], *, label: str = "Top accounts") -> dict[str, Any] | None:
    if not rows:
        return None

    ranked: list[tuple[str, float]] = []
    for row in rows:
        if not isinstance(row, (list, tuple)) or not row:
            continue
        name = str(row[0] or "Item")
        try:
            amount = abs(float(row[-1] or 0))
        except (TypeError, ValueError):
            amount = 0.0
        if amount <= 0:
            continue
        ranked.append((name, amount))

    ranked.sort(key=lambda item: item[1], reverse=True)
    top = ranked[:SUMMARY_CHART_LIMIT]
    if not top:
        return None

    return {
        "visual_type": "BAR_CHART",
        "label": label,
        "data": {
            "labels": [name for name, _ in top],
            "values": [value for _, value in top],
            "rows": [[name, value] for name, value in top],
        },
    }


def _slice_rows(rows: list[Any], level: str) -> tuple[list[Any], int, int]:
    total = len(rows)
    if level == "full":
        return rows[:FULL_ROW_CAP], min(total, FULL_ROW_CAP), total
    if level == "standard":
        return rows[:STANDARD_PAGE_SIZE], min(total, STANDARD_PAGE_SIZE), total
    return [], 0, total


def _register_query_page(
    visual: dict[str, Any],
    *,
    headers: list[Any],
    rows: list[Any],
) -> dict[str, Any]:
    if not rows:
        return visual
    enriched = dict(visual)
    query_id = QueryPageStore.register(
        headers=headers,
        rows=rows,
        label=str(enriched.get("label") or ""),
        visual_type=str(enriched.get("visual_type") or "DATA_TABLE"),
        meta={
            "date_from": enriched.get("date_from"),
            "date_to": enriched.get("date_to"),
            "date_was_defaulted": enriched.get("date_was_defaulted"),
        },
    )
    enriched["query_id"] = query_id
    enriched.setdefault("page_size", STANDARD_PAGE_SIZE)
    return enriched


def _apply_metadata(
    visual: dict[str, Any],
    *,
    level: str,
    total_records: int,
    shown_records: int,
    can_expand: bool,
    expand_label: str,
) -> dict[str, Any]:
    enriched = dict(visual)
    enriched["level"] = level
    enriched["total_records"] = total_records
    enriched["shown_records"] = shown_records
    enriched["can_expand"] = can_expand
    enriched["expand_label"] = expand_label
    enriched["page_size"] = STANDARD_PAGE_SIZE
    data = enriched.get("data") or {}
    if isinstance(data, dict):
        all_rows = data.get("all_rows") or data.get("detail_table", {}).get("rows") or []
        headers = (
            data.get("headers")
            or data.get("detail_table", {}).get("headers")
            or ["Account", "Debit", "Credit", "Balance"]
        )
        if all_rows and not enriched.get("query_id"):
            enriched = _register_query_page(enriched, headers=list(headers), rows=list(all_rows))
    return enriched


def apply_progressive_disclosure(
    visualization: dict[str, Any] | None,
    user_message: str,
    tool_results: list[Any] | None = None,
) -> dict[str, Any] | None:
    if not visualization:
        return None

    visual_type = visualization.get("visual_type")
    if visual_type not in _DISCLOSURE_TYPES:
        return visualization

    level = detect_disclosure_level(user_message)
    enriched = dict(visualization)
    data = dict(enriched.get("data") or {})
    tool_results = tool_results or []

    if visual_type == "FINANCIAL_REPORT":
        detail_table = data.get("detail_table") or _extract_detail_table(tool_results)
        if not detail_table:
            enriched["level"] = level if level != "summary" else "summary"
            enriched.setdefault("can_expand", False)
            return enriched

        all_rows = list(detail_table.get("rows") or [])
        data["detail_table"] = {
            "headers": detail_table.get("headers") or ["Account", "Debit", "Credit", "Balance"],
            "rows": all_rows,
        }
        data["all_rows"] = all_rows
        if level == "summary" and not data.get("summary_chart"):
            data["summary_chart"] = _build_summary_chart(
                all_rows,
                label=enriched.get("label") or "Top accounts",
            )

        visible_rows, shown, total = _slice_rows(all_rows, level)
        expand_label = f"See all {total} accounts" if total else "See account details"
        can_expand = total > shown and level != "full"

        if level in {"standard", "full"}:
            data["rows"] = visible_rows
            data["headers"] = data["detail_table"]["headers"]

        enriched["data"] = data
        return _apply_metadata(
            enriched,
            level=level,
            total_records=total,
            shown_records=shown if level != "summary" else 0,
            can_expand=can_expand or (level == "summary" and total > 0),
            expand_label=expand_label,
        )

    if visual_type == "DATA_TABLE":
        all_rows = list(data.get("all_rows") or data.get("rows") or [])
        if len(all_rows) <= SUMMARY_CHART_LIMIT:
            enriched.setdefault("level", "standard")
            enriched.setdefault("can_expand", False)
            enriched.setdefault("total_records", len(all_rows))
            enriched.setdefault("shown_records", len(all_rows))
            return enriched

        data["all_rows"] = all_rows
        if level == "summary" and not data.get("summary_chart"):
            data["summary_chart"] = _build_summary_chart(all_rows, label=enriched.get("label") or "Top items")

        visible_rows, shown, total = _slice_rows(all_rows, level)
        expand_label = f"See all {total} records"

        if level == "summary":
            data["rows"] = []
        else:
            data["rows"] = visible_rows

        enriched["data"] = data
        return _apply_metadata(
            enriched,
            level=level,
            total_records=total,
            shown_records=shown if level != "summary" else 0,
            can_expand=total > SUMMARY_CHART_LIMIT,
            expand_label=expand_label,
        )

    if visual_type == "GROUPED_TABLE":
        groups = (data.get("groups") or enriched.get("groups") or [])
        total = len(groups)
        if total <= SUMMARY_CHART_LIMIT:
            enriched.setdefault("level", "standard")
            enriched.setdefault("can_expand", False)
            return enriched

        data["all_groups"] = groups
        if level == "summary":
            data["groups"] = groups[:SUMMARY_CHART_LIMIT]
        elif level == "standard":
            data["groups"] = groups[:STANDARD_PAGE_SIZE]
        else:
            data["groups"] = groups[:FULL_ROW_CAP]

        enriched["data"] = data
        shown = len(data.get("groups") or [])
        return _apply_metadata(
            enriched,
            level=level,
            total_records=total,
            shown_records=shown if level != "summary" else min(total, SUMMARY_CHART_LIMIT),
            can_expand=total > shown,
            expand_label=f"See all {total} groups",
        )

    return visualization
