from __future__ import annotations

import json
from typing import Any

from gateway.quality_formatting import humanize_aggregate_spec, humanize_group_label


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


def _purchase_orders_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    orders = payload.get("orders") or []
    request = payload.get("request") or {}
    client_name = request.get("client_name") or "Client"
    count = int(payload.get("count") or len(orders))

    if not orders:
        return {
            "visual_type": "KPI_CARD",
            "label"      : f"{client_name} purchase orders",
            "value"      : 0,
            "unit"       : "orders",
            "data"       : {
                "matched_clients": len(payload.get("matched_clients") or []),
                "projects"       : len(payload.get("projects") or []),
            },
        }

    rows = []
    for order in orders:
        rows.append([
            order.get("po_number"),
            order.get("supplier_name"),
            order.get("client_name"),
            order.get("project_name"),
            order.get("date_order"),
            order.get("amount_total"),
            order.get("state"),
        ])

    return {
        "visual_type": "DATA_TABLE",
        "label"      : f"{client_name} purchase orders ({count})",
        "value"      : count,
        "unit"       : "orders",
        "data"       : {
            "headers": [
                "PO Number",
                "Supplier",
                "Client",
                "Project",
                "Date",
                "Amount (AED)",
                "Status",
            ],
            "rows": rows,
        },
    }


def _projects_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    projects = payload.get("projects") or []
    if not projects:
        return None

    rows = []
    for project in projects:
        partner = project.get("partner_id")
        client_name = partner[1] if isinstance(partner, (list, tuple)) and len(partner) > 1 else partner
        rows.append([
            project.get("name"),
            project.get("wo_ref_no"),
            client_name,
            project.get("active"),
        ])

    return {
        "visual_type": "DATA_TABLE",
        "label"      : f"Active projects ({len(projects)})",
        "value"      : len(projects),
        "unit"       : "projects",
        "data"       : {
            "headers": ["Project", "Work Order", "Client", "Active"],
            "rows"   : rows,
        },
    }


def _entity_candidates_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    from gateway.core.entity_gate import build_entity_options, format_entity_confirm_label

    candidates = payload.get("candidates") or []
    if not candidates:
        return None

    rows = []
    for candidate in candidates:
        rows.append([
            candidate.get("name") or format_entity_confirm_label(candidate),
            candidate.get("wo_ref_no") or candidate.get("detail"),
            candidate.get("id"),
        ])

    return {
        "visual_type": "ENTITY_CANDIDATES",
        "label": payload.get("query") or "Matching records",
        "value": len(candidates),
        "unit": "matches",
        "query": payload.get("query"),
        "candidates": candidates,
        "options": build_entity_options(candidates),
        "data": {
            "headers": ["Name", "Detail", "ID"],
            "rows": rows,
        },
    }


def _financial_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    kpis = payload.get("kpis")
    if not isinstance(kpis, dict):
        return None

    if {"total_income", "total_expense", "net_profit", "margin"} <= set(kpis):
        return {
            "visual_type": "FINANCIAL_REPORT",
            "label"      : payload.get("report_name") or payload.get("label") or "Financial report",
            "value"      : kpis.get("net_profit", 0),
            "unit"       : "AED",
            "date_from"  : payload.get("date_from"),
            "date_to"    : payload.get("date_to"),
            "kpis"       : kpis,
        }

    if "total_cost" in kpis or "net_profit" in kpis:
        return {
            "visual_type": "KPI_CARD",
            "label"      : payload.get("project_name") or payload.get("label") or "Project summary",
            "value"      : kpis.get("total_cost", kpis.get("net_profit", 0)),
            "unit"       : "AED",
            "data"       : kpis,
        }

    return None


def normalize_visualization_shape(visual: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(visual, dict):
        return None

    normalized = dict(visual)
    data = normalized.get("data")
    if isinstance(data, dict):
        if not isinstance(normalized.get("kpis"), dict) and isinstance(data.get("kpis"), dict):
            normalized["kpis"] = data["kpis"]
        elif not isinstance(normalized.get("kpis"), dict):
            metric_keys = {
                "total_income",
                "total_expense",
                "net_profit",
                "margin",
                "total_cost",
            }
            if metric_keys & set(data):
                normalized["kpis"] = {
                    key: data[key]
                    for key in metric_keys
                    if key in data
                }

        for key in ("date_from", "date_to", "report_name", "label"):
            if normalized.get(key) is None and data.get(key) is not None:
                normalized[key] = data[key]

    return normalized


def choose_response_visualization(
    model_visualization: dict[str, Any] | None,
    tool_names          : list[str],
    tool_results        : list[Any],
) -> dict[str, Any] | None:
    model_visualization = normalize_visualization_shape(model_visualization)
    if not is_renderable_visualization(model_visualization):
        model_visualization = None

    tool_visualization = build_visualization_from_tool_results(tool_names, tool_results)
    if tool_visualization and is_renderable_visualization(tool_visualization):
        return tool_visualization

    return model_visualization


def _top_projects_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    projects = payload.get("projects") or []
    if not projects:
        return None

    rows = []
    for project in projects:
        rows.append([
            project.get("project_name") or project.get("name"),
            project.get("wo_ref_no"),
            project.get("client"),
            project.get("net_profit"),
            project.get("revenue"),
            project.get("total_cost"),
            project.get("budget"),
            project.get("margin_percent"),
        ])

    return {
        "visual_type": "DATA_TABLE",
        "label"      : f"Top projects by {payload.get('metric', 'metric')}",
        "value"      : len(projects),
        "unit"       : "projects",
        "data"       : {
            "headers": [
                "Project",
                "WO Ref",
                "Client",
                "Net Profit",
                "Revenue",
                "Total Cost",
                "Budget",
                "Margin %",
            ],
            "rows": rows,
        },
    }


def _cost_categories_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    categories = payload.get("categories") or []
    if not categories:
        return None

    return {
        "visual_type": "BAR_CHART",
        "label"      : payload.get("project_name") or "Project cost categories",
        "value"      : payload.get("total_cost", 0),
        "unit"       : "AED",
        "data"       : {
            "rows": [
                {
                    "label": category.get("category"),
                    "value": category.get("total", 0),
                }
                for category in categories
            ],
        },
    }


def _period_comparison_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    period_1 = payload.get("period_1") or {}
    period_2 = payload.get("period_2") or {}
    if not period_1 or not period_2:
        return None

    return {
        "visual_type": "DATA_TABLE",
        "label"      : "Period comparison",
        "value"      : period_1.get("net_profit", 0),
        "unit"       : "AED",
        "data"       : {
            "headers": ["Metric", period_1.get("label"), period_2.get("label")],
            "rows": [
                ["Income", period_1.get("income"), period_2.get("income")],
                ["Expense", period_1.get("expense"), period_2.get("expense")],
                ["Net profit", period_1.get("net_profit"), period_2.get("net_profit")],
                ["Margin %", period_1.get("margin"), period_2.get("margin")],
            ],
        },
    }


def _project_counts_by_client_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    clients = payload.get("clients") or []
    date_from = payload.get("date_from")
    date_to = payload.get("date_to")
    period = f"{date_from} to {date_to}" if date_from and date_to else "selected period"

    if not clients:
        return {
            "visual_type": "KPI_CARD",
            "label"      : f"Projects by client ({period})",
            "value"      : 0,
            "unit"       : "projects",
            "data"       : {
                "date_from": date_from,
                "date_to"  : date_to,
            },
        }

    rows = [
        [client.get("client"), client.get("project_count", 0)]
        for client in clients
    ]
    return {
        "visual_type": "DATA_TABLE",
        "label"      : f"Projects by client ({period})",
        "value"      : sum(int(client.get("project_count") or 0) for client in clients),
        "unit"       : "projects",
        "data"       : {
            "headers": ["Client", "Projects"],
            "rows"   : rows,
        },
    }


def _overrun_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    projects = payload.get("projects") or []
    if not projects:
        return None

    rows = []
    for project in projects:
        rows.append([
            project.get("project_name"),
            project.get("client"),
            project.get("budget"),
            project.get("total_cost"),
            project.get("usage_percent"),
            project.get("status"),
        ])

    return {
        "visual_type": "DATA_TABLE",
        "label"      : "Projects over budget",
        "value"      : len(projects),
        "unit"       : "projects",
        "data"       : {
            "headers": ["Project", "Client", "Budget", "Total Cost", "Usage %", "Status"],
            "rows"   : rows,
        },
    }


def _group_aggregate_value(row: dict[str, Any], spec: Any) -> Any:
    key = str(spec)
    if key in row:
        return row[key]
    base = key.split(":")[0]
    if base in row:
        return row[base]
    if key.endswith(":count") and "count" in row:
        return row["count"]
    return row.get("__count")


def _group_aggregate_node(
    row: dict[str, Any],
    group_by: list[str],
    aggregates: list[Any],
) -> dict[str, Any]:
    field = group_by[0].split(":")[0] if group_by else ""
    label = row.get("group_label")
    if not label:
        value = row.get(field)
        if isinstance(value, (list, tuple)) and len(value) > 1:
            label = value[1]
        else:
            label = value
    node: dict[str, Any] = {
        "name": str(label or "Group"),
        "aggregates": {},
    }
    for spec in aggregates:
        key = str(spec)
        node["aggregates"][key] = _group_aggregate_value(row, spec)
    if row.get("count") is not None:
        node["aggregates"].setdefault("count", row.get("count"))
    children = row.get("children") or []
    if children:
        node["children"] = [
            _group_aggregate_node(child, group_by[1:], aggregates)
            for child in children
        ]
    return node


def _group_aggregate_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    groups = payload.get("groups") or []
    if not groups:
        return None

    group_by = payload.get("group_by") or []
    aggregates = payload.get("aggregates") or []
    model = payload.get("model") or "records"
    label = f"Grouped {model.replace('.', ' ')}"
    unit = "AED" if model == "account.move" else "groups"

    if len(group_by) > 1 or any(group.get("children") for group in groups):
        return {
            "visual_type": "GROUPED_TABLE",
            "label": label,
            "value": payload.get("total_groups", len(groups)),
            "unit": "groups",
            "data": {
                "groups": [
                    _group_aggregate_node(group, group_by, aggregates)
                    for group in groups
                ],
            },
        }

    headers = ["Group"] + [humanize_aggregate_spec(spec) for spec in aggregates]
    if not aggregates:
        headers.append("count")
    rows: list[list[Any]] = []
    labels: list[str] = []
    values: list[float] = []
    primary = aggregates[0] if aggregates else "count"
    for group in groups:
        row_label = group.get("group_label")
        if not row_label and group_by:
            field = group_by[0].split(":")[0]
            value = group.get(field)
            if isinstance(value, (list, tuple)) and len(value) > 1:
                row_label = value[1]
            else:
                row_label = value
        row_label = humanize_group_label(row_label)
        if row_label == "Unassigned":
            continue
        row_values = [_group_aggregate_value(group, spec) for spec in aggregates]
        if not aggregates:
            row_values = [group.get("count", group.get("__count", 0))]
        rows.append([row_label, *row_values])
        labels.append(str(row_label or "Group"))
        try:
            values.append(float(_group_aggregate_value(group, primary) or 0))
        except (TypeError, ValueError):
            values.append(0.0)

    if aggregates and all(isinstance(value, (int, float)) for value in values):
        return {
            "visual_type": "BAR_CHART",
            "label": label,
            "value": payload.get("total_groups", len(groups)),
            "unit": unit,
            "data": {
                "labels": labels,
                "values": values,
                "rows": rows,
            },
        }

    return {
        "visual_type": "DATA_TABLE",
        "label": label,
        "value": payload.get("total_groups", len(groups)),
        "unit": unit,
        "data": {
            "headers": headers,
            "rows": rows,
        },
    }


def _aggregate_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data") or {}
    rows = data.get("rows") or payload.get("rows") or []
    if not rows:
        return None
    headers = data.get("headers")
    if not headers and rows and isinstance(rows[0], dict):
        headers = list(rows[0].keys())
    if not headers and rows and isinstance(rows[0], (list, tuple)):
        headers = [f"Column {index + 1}" for index in range(len(rows[0]))]
    return {
        "visual_type": "DATA_TABLE",
        "label": payload.get("report_name") or payload.get("label") or "Synthesized report",
        "value": payload.get("row_count", len(rows)),
        "unit": "rows",
        "data": {
            "headers": headers or [],
            "rows": rows,
        },
    }


def _pdf_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    if not payload.get("pdf_url"):
        return None
    return {
        "visual_type": "PDF_REPORT",
        "label": payload.get("title") or "Generated report",
        "value": payload.get("page_count", 1),
        "unit": "pages",
        "data": {
            "pdf_url": payload.get("pdf_url"),
            "preview_image": payload.get("preview_image"),
            "size_bytes": payload.get("size_bytes"),
            "generated_at": payload.get("generated_at"),
            "page_count": payload.get("page_count"),
        },
    }



def _normalize_top_expense_rows(top_expenses: list[Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in top_expenses or []:
        if not isinstance(item, dict):
            continue
        label = item.get("label") or item.get("name") or "Category"
        amount = float(item.get("amount") or item.get("value") or 0)
        pct = item.get("pct")
        if pct is None:
            pct = item.get("percent") or item.get("percentage")
        rows.append(
            {
                "label": str(label),
                "value": amount,
                "pct": float(pct or 0),
            },
        )
    return rows


def _build_expense_insights(payload: dict[str, Any]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    spend_status = payload.get("spend_status")
    spend_pct_raw = payload.get("spend_percent_of_wo")
    spend_pct = float(spend_pct_raw) if spend_pct_raw is not None else None
    currency = payload.get("currency") or "AED"
    wo_amount = float(payload.get("wo_amount") or 0)
    total_expenses = float(payload.get("total_expenses") or 0)

    if spend_status == "no_budget_assigned":
        insights.append(
            {
                "severity": "info",
                "title": "No W.O Budget",
                "message": (
                    f"{currency} {total_expenses:,.0f} recorded with no W.O budget assigned"
                ),
            },
        )
        return insights

    if spend_status == "no_data":
        return insights

    if payload.get("is_over_budget") or spend_status == "over_budget":
        over_amount = total_expenses - wo_amount
        pct_fragment = f" ({spend_pct:.1f}%)" if spend_pct is not None else ""
        insights.append(
            {
                "severity": "critical",
                "title": "Over Budget",
                "message": f"Over W.O by {currency} {over_amount:,.0f}{pct_fragment}",
            },
        )
    elif spend_pct is not None and spend_pct > 95:
        insights.append(
            {
                "severity": "warning",
                "title": "Near Budget Limit",
                "message": f"Spent {spend_pct:.1f}% of W.O",
            },
        )

    top_expenses = _normalize_top_expense_rows(payload.get("top_expenses") or [])
    if top_expenses and top_expenses[0].get("pct", 0) > 40:
        top = top_expenses[0]
        insights.append(
            {
                "severity": "info",
                "title": "Concentrated Spending",
                "message": (
                    f"{top['label']} alone is {top['pct']:.1f}% of total expenses"
                ),
            },
        )
    return insights


PROJECT_EXPENSE_SUMMARY_SOURCES = frozenset(
    {
        "project_expense_summary",
        "project_expense_summary_mobile",
        "project_expense_dashboard",
    },
)


def _project_expense_summary_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("status") != "success":
        return None
    if payload.get("_source") not in PROJECT_EXPENSE_SUMMARY_SOURCES:
        return None

    currency = payload.get("currency") or "AED"
    project_name = payload.get("project_name") or "Project"
    wo_amount = float(payload.get("wo_amount") or 0)
    total_expenses = float(payload.get("total_expenses") or 0)
    spend_status = payload.get("spend_status")
    status_label = payload.get("status_label")
    spend_pct_raw = payload.get("spend_percent_of_wo")
    spend_pct = float(spend_pct_raw) if spend_pct_raw is not None else None
    variance = float(payload.get("variance_amount") or (wo_amount - total_expenses))
    top_expenses = _normalize_top_expense_rows(payload.get("top_expenses") or [])

    spend_trend = "neutral"
    if spend_status == "no_budget_assigned":
        spend_context = status_label or "No W.O budget assigned"
    elif spend_status == "no_data":
        spend_context = status_label or "No expense data recorded"
    elif payload.get("is_over_budget") or spend_status == "over_budget":
        spend_trend = "down"
        spend_context = status_label or "Over budget"
    elif spend_pct is not None and spend_pct > 95:
        spend_trend = "down"
        spend_context = "Near limit"
    else:
        spend_context = status_label or "On track"

    variance_trend = "up" if variance >= 0 else "down"
    variance_context = (
        f"{currency} {variance:,.0f} available"
        if variance >= 0
        else f"{currency} {abs(variance):,.0f} over W.O"
    )

    return {
        "visual_type": "PROJECT_EXPENSE_SUMMARY",
        "label": f"{project_name} Expenses",
        "level": "summary",
        "project_id": payload.get("project_id"),
        "project_name": project_name,
        "currency": currency,
        "is_over_budget": bool(payload.get("is_over_budget")),
        "spend_percent_of_wo": spend_pct,
        "kpis": {
            "wo_amount": {
                "value": wo_amount,
                "label": "W.O Amount",
                "unit": currency,
            },
            "total_expenses": {
                "value": total_expenses,
                "label": "Total Spent",
                "unit": currency,
            },
            "spend_pct": {
                "value": spend_pct,
                "label": "Spend %",
                "unit": "%",
                "trend": {"direction": spend_trend, "context": spend_context},
            },
            "variance": {
                "value": variance,
                "label": "Remaining" if variance >= 0 else "Over W.O",
                "unit": currency,
                "trend": {"direction": variance_trend, "context": variance_context},
            },
        },
        "top_expenses": top_expenses,
        "expense_lines": payload.get("expense_lines") or [],
        "insights": _build_expense_insights(payload),
        "data": {
            "summary_chart": {
                "visual_type": "BAR_CHART",
                "label": "Top expense categories",
                "data": {
                    "rows": top_expenses,
                },
            },
        },
    }


def _breakdown_groups_for_viz(
    groups: list[dict[str, Any]],
    grand_total: float,
) -> list[dict[str, Any]]:
    viz_groups: list[dict[str, Any]] = []
    for index, group in enumerate(groups or []):
        group_total = float(group.get("total") or 0)
        subgroups: list[dict[str, Any]] = []
        for subgroup in group.get("subgroups") or []:
            sg_total = float(subgroup.get("total") or 0)
            accounts = [
                {
                    "code": account.get("code"),
                    "name": account.get("name"),
                    "total": float(account.get("total") or 0),
                }
                for account in (subgroup.get("accounts") or [])
            ]
            subgroups.append(
                {
                    "code": subgroup.get("code"),
                    "name": subgroup.get("name"),
                    "total": sg_total,
                    "pct": round((sg_total / grand_total) * 100, 1) if grand_total else 0,
                    "expanded": False,
                    "accounts": accounts,
                },
            )
        viz_groups.append(
            {
                "code": group.get("code"),
                "name": group.get("name"),
                "total": group_total,
                "pct": round((group_total / grand_total) * 100, 1) if grand_total else 0,
                "expanded": index == 0,
                "subgroups": subgroups,
            },
        )
    return viz_groups


def _project_expense_breakdown_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("status") != "success":
        return None
    if payload.get("_source") != "project_expense_breakdown_mobile":
        return None

    groups = payload.get("groups") or []
    if not groups:
        return None

    grand_total = float(payload.get("grand_total") or 0)
    project_name = payload.get("project_name") or "Project"
    currency = payload.get("currency") or "AED"

    return {
        "visual_type": "PROJECT_EXPENSE_BREAKDOWN",
        "label": f"GL Breakdown: {project_name}",
        "project_id": payload.get("project_id"),
        "project_name": project_name,
        "currency": currency,
        "grand_total": grand_total,
        "group_count": payload.get("group_count") or len(groups),
        "groups": _breakdown_groups_for_viz(groups, grand_total),
        "truncated": bool(payload.get("_truncated")),
    }


def _build_comparison_insights(projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []
    if len(projects) < 2:
        return insights

    over_budget = [project for project in projects if project.get("is_over_budget")]
    if over_budget:
        names = [str(project.get("project_name") or project.get("project_id")) for project in over_budget]
        insights.append(
            {
                "severity": "warning",
                "title": "Projects Over Budget",
                "message": (
                    f"{len(over_budget)} of {len(projects)} are over W.O: "
                    f"{', '.join(names)}"
                ),
            },
        )

    spend_pcts = [float(project.get("spend_percent_of_wo") or 0) for project in projects]
    if max(spend_pcts) - min(spend_pcts) > 30:
        insights.append(
            {
                "severity": "info",
                "title": "Wide Spend Variation",
                "message": (
                    f"Spend % ranges from {min(spend_pcts):.0f}% to "
                    f"{max(spend_pcts):.0f}% across projects"
                ),
            },
        )
    return insights


def _project_expense_comparison_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("status") != "success":
        return None
    if payload.get("_source") != "compare_project_expenses":
        return None

    projects = payload.get("projects") or []
    if len(projects) < 2:
        return None

    currency = projects[0].get("currency") or "AED"
    comparison_projects: list[dict[str, Any]] = []
    for index, project in enumerate(projects):
        comparison_projects.append(
            {
                "id": project.get("project_id"),
                "name": project.get("project_name"),
                "wo_amount": float(project.get("wo_amount") or 0),
                "total_expenses": float(project.get("total_expenses") or 0),
                "spend_pct": float(project.get("spend_percent_of_wo") or 0),
                "is_over_budget": bool(project.get("is_over_budget")),
                "rank": index + 1,
            },
        )

    totals = payload.get("totals") or {}
    return {
        "visual_type": "PROJECT_EXPENSE_COMPARISON",
        "label": "Project Expense Comparison",
        "currency": currency,
        "projects": comparison_projects,
        "totals": totals,
        "ranked_by": payload.get("ranked_by") or "total_expenses",
        "insights": _build_comparison_insights(projects),
        "chart_type": "side_by_side_bar",
        "data": {
            "summary_chart": {
                "visual_type": "BAR_CHART",
                "label": "Spend by project",
                "data": {
                    "rows": [
                        {
                            "label": project["name"],
                            "value": project["total_expenses"],
                        }
                        for project in comparison_projects
                    ],
                },
            },
        },
    }

_ENGINEER_DISCIPLINE_LABELS = (
    ("civil", "Civil Amount"),
    ("electrical", "Electrical Amount"),
    ("mechanical", "Mechanical Amount"),
    ("ict", "ICT Amount"),
)


def _profile_rows_engineers(
    payload: dict[str, Any],
    disciplines: tuple[str, ...] | None = None,
) -> list[list[Any]]:
    """Rows for engineer discipline allocations only."""
    distribution = (payload.get("amounts") or {}).get("distribution") or {}
    rows: list[list[Any]] = []
    for key, label in _ENGINEER_DISCIPLINE_LABELS:
        if disciplines is not None and key not in disciplines:
            continue
        value = distribution.get(key)
        rows.append([label, round(float(value), 2) if value is not None else "Not set"])
    return rows


def _profile_rows_amounts(payload: dict[str, Any]) -> list[list[Any]]:
    amounts = payload.get("amounts") or {}
    distribution = amounts.get("distribution") or {}
    labels = {
        "civil": "Civil Amount", "electrical": "Electrical Amount",
        "mechanical": "Mechanical Amount", "ict": "ICT Amount",
        "plumbing": "Plumbing Amount",
    }
    rows: list[list[Any]] = []
    if amounts.get("wo_amount") is not None:
        rows.append(["W.O Amount", round(float(amounts["wo_amount"]), 2)])
    if amounts.get("estimation_amount") is not None:
        rows.append(["Estimation Amount", round(float(amounts["estimation_amount"]), 2)])
    for key, label in labels.items():
        value = distribution.get(key)
        rows.append([label, round(float(value), 2) if value is not None else "Not set"])
    for key, label in (
        ("branch_manager", "Branch Manager Amount"),
        ("project_manager", "Project Manager Amount"),
    ):
        value = (amounts.get("role_allocations") or {}).get(key)
        if value is not None:
            rows.append([label, round(float(value), 2)])
    return rows


def _profile_rows_section(section: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for key, value in section.items():
        if isinstance(value, dict):
            value = value.get("name")
        if value is None or value == "":
            continue
        rows.append([key.replace("_", " ").title(), value])
    return rows


def _project_profile_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("status") != "success":
        return None
    focus = str(payload.get("focus") or "all")
    engineer_disciplines = {key for key, _ in _ENGINEER_DISCIPLINE_LABELS}
    amounts = payload.get("amounts") or {}
    if focus == "wo_amount":
        value = amounts.get("wo_amount")
        rows = [["W.O Amount", round(float(value), 2) if value is not None else "Not set"]]
        title = f"{payload.get('project_name')} — W.O Amount (AED)"
    elif focus == "estimation":
        value = amounts.get("estimation_amount")
        rows = [["Estimation Amount", round(float(value), 2) if value is not None else "Not set"]]
        title = f"{payload.get('project_name')} — Estimation Amount (AED)"
    elif focus == "engineers":
        rows = _profile_rows_engineers(payload)
        title = f"{payload.get('project_name')} — Engineer Amounts (AED)"
    elif focus in engineer_disciplines:
        rows = _profile_rows_engineers(payload, disciplines=(focus,))
        trade_label = dict(_ENGINEER_DISCIPLINE_LABELS)[focus]
        title = f"{payload.get('project_name')} — {trade_label} (AED)"
    elif focus == "amounts":
        rows = _profile_rows_amounts(payload)
        title = f"{payload.get('project_name')} — W.O Amount Distribution (AED)"
    elif focus in {"team", "schedule", "identity"}:
        section_key = {"team": "team", "schedule": "schedule", "identity": "identity"}[focus]
        rows = _profile_rows_section(payload.get(section_key) or {})
        title = f"{payload.get('project_name')} — {focus.title()}"
    elif focus == "status":
        rows = _profile_rows_section(payload.get("project_status") or {})
        rows += _profile_rows_section(payload.get("progress") or {})
        title = f"{payload.get('project_name')} — Status & Progress"
    else:
        rows = _profile_rows_amounts(payload)
        rows += _profile_rows_section(payload.get("team") or {})
        rows += _profile_rows_section(payload.get("schedule") or {})
        title = f"{payload.get('project_name')} — Project Profile"
    if not rows:
        return None
    return {
        "visual_type": "DATA_TABLE",
        "label": title,
        "disclosure_exempt": True,
        "data": {
            "headers": ["Field", "Value"],
            "rows": rows,
        },
        "suggestions": [],
    }


_RECORDS_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "invoices": [
        ("number", "Invoice"), ("kind", "Kind"), ("date", "Date"),
        ("partner", "Partner"), ("total", "Total (AED)"),
        ("due", "Due (AED)"), ("payment_state", "Payment"),
    ],
    "client_invoices": [
        ("number", "Invoice"), ("date", "Date"), ("partner", "Client"),
        ("total", "Total (AED)"), ("due", "Due (AED)"), ("payment_state", "Payment"),
    ],
    "lpo_invoices": [
        ("number", "Bill"), ("date", "Date"), ("partner", "Vendor"),
        ("total", "Total (AED)"), ("due", "Due (AED)"), ("payment_state", "Payment"),
    ],
    "purchase_orders": [
        ("number", "PO"), ("date", "Date"), ("vendor", "Vendor"),
        ("total", "Total (AED)"), ("state", "Status"), ("billing", "Billing"),
    ],
    "timesheets": [
        ("date", "Date"), ("employee", "Employee"), ("description", "Description"),
        ("hours", "Hours"), ("task", "Task"),
    ],
    "petty_cash": [
        ("number", "Ref"), ("date", "Date"), ("employee", "Employee"),
        ("description", "Description"), ("total", "Total (AED)"), ("state", "Status"),
    ],
    "petty_cash_sheets": [
        ("number", "Ref"), ("date", "Date"), ("employee", "Employee"),
        ("description", "Description"), ("total", "Total (AED)"), ("state", "Status"),
    ],
    "staff": [
        ("code", "Code"), ("name", "Name"), ("job", "Job"),
        ("status", "Status"), ("access", "Access"),
    ],
    "supervisors": [
        ("code", "Code"), ("name", "Name"), ("job", "Job"), ("status", "Status"),
    ],
}


def _project_activity_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("status") != "success":
        return None
    activity_type = str(payload.get("activity_type") or "")
    project_name = str(payload.get("project_name") or "Project")

    if activity_type == "attachments":
        rows: list[list[Any]] = []
        for row in payload.get("rows") or []:
            size = row.get("size_bytes")
            size_label = f"{int(size):,} B" if isinstance(size, (int, float)) else "—"
            rows.append([
                row.get("name") or "—",
                row.get("mimetype") or "—",
                size_label,
                row.get("uploaded_at") or "—",
                row.get("uploaded_by") or "—",
            ])
        if not rows:
            return None
        total = int(payload.get("total_count") or 0)
        shown = int(payload.get("returned_count") or 0)
        title = f"{project_name} — Attachments"
        if total > shown:
            title += f" (latest {shown} of {total})"
        return {
            "visual_type": "DATA_TABLE",
            "label": title,
            "disclosure_exempt": True,
            "data": {
                "headers": ["Name", "Type", "Size", "Uploaded", "By"],
                "rows": rows,
            },
            "suggestions": [],
        }

    if activity_type == "chatter_summary":
        return {
            "visual_type": "DATA_TABLE",
            "label": f"{project_name} — Chatter summary",
            "disclosure_exempt": True,
            "data": {
                "headers": ["Summary"],
                "rows": [[payload.get("summary") or "—"]],
            },
            "suggestions": [],
        }

    data = payload.get("progress_audit") or {}
    if activity_type == "progress":
        return {
            "visual_type": "DATA_TABLE",
            "label": f"{project_name} — Progress",
            "disclosure_exempt": True,
            "data": {
                "headers": ["Field", "Value"],
                "rows": [
                    ["Progress %", data.get("progress_percent")],
                    ["Status", data.get("project_status") or data.get("state")],
                    ["Last progress update", data.get("progress_last_update")],
                    ["Delayed weeks", data.get("delayed_weeks")],
                    ["On-time weeks", data.get("on_time_weeks")],
                ],
            },
            "suggestions": [],
        }

    if activity_type == "audit":
        return {
            "visual_type": "DATA_TABLE",
            "label": f"{project_name} — Audit trail",
            "disclosure_exempt": True,
            "data": {
                "headers": ["Field", "Value"],
                "rows": [
                    ["Created by", data.get("created_by")],
                    ["Created on", data.get("created_on")],
                    ["Last updated by", data.get("last_updated_by")],
                    ["Last updated on", data.get("last_updated_on")],
                ],
            },
            "suggestions": [],
        }
    return None


def _project_records_visual(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("status") != "success":
        return None
    record_type = str(payload.get("record_type") or "")
    columns = _RECORDS_COLUMNS.get(record_type)
    if not columns:
        return None
    rows: list[list[Any]] = []
    for row in payload.get("rows") or []:
        rows.append([
            row.get(key) if row.get(key) is not None else "—"
            for key, _label in columns
        ])
    if not rows:
        return None
    label = str(payload.get("record_label") or record_type).title()
    title = f"{payload.get('project_name')} — {label}"
    total = int(payload.get("total_count") or 0)
    shown = int(payload.get("returned_count") or 0)
    if total > shown:
        title += f" (latest {shown} of {total})"
    return {
        "visual_type": "DATA_TABLE",
        "label": title,
        # Complete answer card: the tool already pages (latest N) and the
        # narration carries the true total — disclosure must not replace the
        # table with a summary chart or offer a misleading "See all".
        "disclosure_exempt": True,
        "data": {
            "headers": [label_ for _key, label_ in columns],
            "rows": rows,
        },
        "suggestions": [],
    }


def _visual_from_payload(
    tool_name: str,
    payload  : dict[str, Any],
) -> dict[str, Any] | None:
    if tool_name == "get_purchase_orders":
        return _purchase_orders_visual(payload)
    if tool_name == "get_projects_summary":
        return _projects_visual(payload)
    if tool_name == "get_top_projects_by_metric":
        return _top_projects_visual(payload)
    if tool_name == "get_project_cost_categories":
        return _cost_categories_visual(payload)
    if tool_name == "get_period_comparison":
        return _period_comparison_visual(payload)
    if tool_name == "get_projects_with_overrun":
        return _overrun_visual(payload)
    if tool_name == "get_project_counts_by_client":
        return _project_counts_by_client_visual(payload)
    if tool_name in {
        "get_trial_balance",
        "get_general_ledger",
        "sql_aggregate",
        "compose_report",
        "query_accounting",
    }:
        return _aggregate_visual(payload)
    if tool_name == "group_and_aggregate":
        return _group_aggregate_visual(payload)
    if tool_name in {"generate_pdf_report", "synthesize_pdf"}:
        return _pdf_visual(payload)
    if tool_name == "get_project_profile" or payload.get("_source") == "project_profile":
        return _project_profile_visual(payload)
    if tool_name == "get_project_records" or payload.get("_source") == "project_records":
        return _project_records_visual(payload)
    if tool_name == "get_project_activity" or payload.get("_source") == "project_activity":
        return _project_activity_visual(payload)
    if tool_name == "get_project_expense_summary":
        return _project_expense_summary_visual(payload)
    if tool_name == "get_project_expense_breakdown":
        return _project_expense_breakdown_visual(payload)
    if tool_name == "compare_project_expenses":
        return _project_expense_comparison_visual(payload)
    if tool_name == "search_entities" or payload.get("_source") == "search_entities":
        return _entity_candidates_visual(payload)
    if tool_name in {
        "get_financial_report",
        "get_project_expenses",
        "get_project_financial_data",
    }:
        return _financial_visual(payload)
    if payload.get("orders"):
        return _purchase_orders_visual(payload)
    if payload.get("projects"):
        return _projects_visual(payload)
    if payload.get("kpis"):
        return _financial_visual(payload)
    if payload.get("clients"):
        return _project_counts_by_client_visual(payload)
    if payload.get("_source") in PROJECT_EXPENSE_SUMMARY_SOURCES:
        return _project_expense_summary_visual(payload)
    if payload.get("_source") == "project_expense_breakdown_mobile":
        return _project_expense_breakdown_visual(payload)
    if payload.get("_source") == "compare_project_expenses":
        return _project_expense_comparison_visual(payload)
    if payload.get("groups"):
        return _group_aggregate_visual(payload)
    return None


def build_visualization_from_tool_results(
    tool_names  : list[str],
    tool_results: list[Any],
) -> dict[str, Any] | None:
    for tool_name, result in zip(reversed(tool_names), reversed(tool_results)):
        payload = _coerce_payload(result)
        if not payload or payload.get("error"):
            continue
        visual = _visual_from_payload(tool_name, payload)
        if visual and is_renderable_visualization(visual):
            return visual
    return None


def is_renderable_visualization(visual: dict[str, Any] | None) -> bool:
    if not isinstance(visual, dict):
        return False

    visual_type = visual.get("visual_type")
    if visual_type == "KPI_CARD":
        return visual.get("label") is not None and visual.get("value") is not None
    if visual_type == "DATA_TABLE":
        rows = (visual.get("data") or {}).get("rows") or []
        return bool(rows)
    if visual_type == "FINANCIAL_REPORT":
        kpis = visual.get("kpis")
        if not isinstance(kpis, dict):
            return False
        return bool(
            {"total_income", "total_expense", "net_profit", "margin", "total_cost"} & set(kpis)
        )
    if visual_type == "BAR_CHART":
        data = visual.get("data") or {}
        if isinstance(data.get("rows"), list) and data["rows"]:
            return True
        return bool(data.get("labels") or data.get("values"))
    if visual_type == "GROUPED_TABLE":
        groups = (visual.get("data") or {}).get("groups") or visual.get("groups") or []
        return bool(groups)
    if visual_type == "PDF_REPORT":
        return bool((visual.get("data") or {}).get("pdf_url"))
    if visual_type == "PROJECT_EXPENSE_SUMMARY":
        kpis = visual.get("kpis")
        if not isinstance(kpis, dict):
            return False
        total_entry = kpis.get("total_expenses") or {}
        wo_entry = kpis.get("wo_amount") or {}
        total_value = float((total_entry.get("value") if isinstance(total_entry, dict) else total_entry) or 0)
        wo_value = float((wo_entry.get("value") if isinstance(wo_entry, dict) else wo_entry) or 0)
        if total_value > 0 or wo_value > 0:
            return True
        return bool(visual.get("expense_lines") or visual.get("top_expenses"))
    if visual_type == "PROJECT_EXPENSE_BREAKDOWN":
        groups = visual.get("groups") or []
        return bool(groups)
    if visual_type == "PROJECT_EXPENSE_COMPARISON":
        projects = visual.get("projects") or []
        return len(projects) >= 2
    if visual_type == "ENTITY_CANDIDATES":
        candidates = visual.get("candidates") or visual.get("options") or []
        return bool(candidates)
    return False
