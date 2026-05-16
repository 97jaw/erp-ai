from __future__ import annotations

from typing import Any

from gateway.quality_formatting import format_currency


def _f(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _partner_label(row: dict[str, Any], fallback_key: str) -> str:
    return str(row.get("partner_name") or fallback_key)


def normalize_partner_ageing(
    raw: dict[str, Any],
    *,
    source: str,
    applied_filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    period_list = list(raw.get("period_list") or [])
    partners_in: dict[str, Any] = dict(raw.get("partners") or {})
    partners: dict[str, Any] = {}

    for key, row in partners_in.items():
        if not isinstance(row, dict):
            continue
        partner_id = row.get("partner_id", key)
        bucket_total = round(sum(_f(row.get(period)) for period in period_list), 2)
        line_total = _f(row.get("total"))
        # Prefer Odoo line total; recompute from buckets when missing or divergent.
        if line_total == 0 and bucket_total != 0:
            line_total = bucket_total
        elif bucket_total != 0 and abs(line_total - bucket_total) > 0.05:
            line_total = bucket_total

        clean = {
            "partner_id": partner_id,
            "partner_name": _partner_label(row, str(key)),
            "total": line_total,
            "total_outstanding": round(abs(line_total), 2),
        }
        for period in period_list:
            clean[period] = _f(row.get(period))
        partners[str(partner_id)] = clean

    table_rows: list[list[Any]] = []
    for partner_id in sorted(
        partners.keys(),
        key=lambda pid: partners[pid].get("partner_name", pid),
    ):
        row = partners[partner_id]
        table_rows.append(
            [
                row.get("partner_name", partner_id),
                *[row.get(period, 0.0) for period in period_list],
                row.get("total", 0.0),
            ]
        )

    report_total_raw = raw.get("report_total") or {}
    sum_signed = round(sum(partner.get("total", 0.0) for partner in partners.values()), 2)

    if isinstance(report_total_raw, dict) and report_total_raw.get("total") is not None:
        grand_total = _f(report_total_raw.get("total"))
        total_buckets = {period: _f(report_total_raw.get(period)) for period in period_list}
    else:
        grand_total = sum_signed
        total_buckets = {
            period: round(sum(partner.get(period, 0.0) for partner in partners.values()), 2)
            for period in period_list
        }

    if table_rows:
        table_rows.append(
            ["Total"] + [total_buckets.get(period, 0.0) for period in period_list] + [grand_total]
        )

    as_of_date = str(raw.get("as_of_date") or raw.get("date_from") or "")
    headers = ["Partner"] + period_list + ["Total"]

    return {
        "report_type": "partner_ageing",
        "report_name": "Partner Ageing",
        "as_of_date": as_of_date,
        "date_from": as_of_date,
        "period_list": period_list,
        "partners": partners,
        "partner_count": len(partners),
        "totals": {
            "total": grand_total,
            "sum_partner_totals": sum_signed,
            "buckets": total_buckets,
        },
        "totals_formatted": {
            "total": format_currency(grand_total),
        },
        "data": {
            "headers": headers,
            "rows": table_rows,
        },
        "filters": raw.get("filters") or {},
        "applied_filters": applied_filters or {},
        "result_selection": raw.get("result_selection", "customer"),
        "source": source,
        "synthesized": False,
    }
