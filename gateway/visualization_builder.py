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
    return False
