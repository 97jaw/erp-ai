from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from adapters.v14.connector import OdooV14Adapter, ProjectAmbiguousError, ProjectNotFoundError
from core.base_adapter import KPIRequest
from gateway.session_entities import enrich_tool_input

logger = logging.getLogger(__name__)

TOP_PROJECTS_SCAN_LIMIT = int(os.environ.get("OOA_TOP_PROJECTS_SCAN_LIMIT", "40"))
OVERRUN_SCAN_LIMIT = int(os.environ.get("OOA_OVERRUN_SCAN_LIMIT", "40"))


def _month_bounds() -> tuple[str, str]:
    today = date.today()
    return today.replace(day=1).isoformat(), today.isoformat()


def _project_error_payload(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, ProjectAmbiguousError):
        candidates = []
        for candidate in exc.candidates:
            candidates.append({
                "id": candidate.get("id"),
                "name": candidate.get("name"),
                "wo_ref_no": candidate.get("wo_ref_no"),
                "client": (
                    candidate.get("partner_id")[1]
                    if isinstance(candidate.get("partner_id"), list)
                    else candidate.get("partner_id")
                ),
            })
        return {
            "error": "multiple_projects_found",
            "message": f"Found {len(candidates)} projects matching your search.",
            "candidates": candidates,
        }
    if isinstance(exc, ProjectNotFoundError):
        return {
            "error": "project_not_found",
            "message": (
                f"No project found matching '{exc.search_term}'. "
                "Please provide the WO reference number or full project name."
            ),
        }
    raise exc


def _load_project_dashboard(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    request = KPIRequest(
        kpi_type="expense_dashboard",
        model="project.financial.service",
        method="get_project_expense_dashboard",
        filters={
            "project_id": tool_input.get("project_id"),
            "project_name": tool_input.get("project_name"),
        },
    )
    try:
        return adapter.get_kpi_data(request).raw_data
    except (ProjectAmbiguousError, ProjectNotFoundError) as exc:
        return _project_error_payload(exc)


def _load_project_financial_data(
    adapter: OdooV14Adapter,
    project_id: int,
    date_from: str | None,
    date_to: str | None,
) -> dict[str, Any]:
    request = KPIRequest(
        kpi_type="financial_data",
        model="project.financial.service",
        method="get_project_financial_data",
        filters={
            "project_id": project_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    )
    return adapter.get_kpi_data(request).raw_data


def _categorize_distribution(distribution: list[dict[str, Any]]) -> list[dict[str, Any]]:
    categorized: list[dict[str, Any]] = []
    total = 0.0
    for category in distribution:
        items = category.get("items") or []
        category_total = sum(float(item.get("amount", 0) or 0) for item in items)
        total += category_total

    for category in distribution:
        items = category.get("items") or []
        category_total = sum(float(item.get("amount", 0) or 0) for item in items)
        percentage = round((category_total / total) * 100, 2) if total > 0 else 0.0
        sorted_items = sorted(
            items,
            key=lambda item: float(item.get("amount", 0) or 0),
            reverse=True,
        )
        categorized.append({
            "category": category.get("name"),
            "total": category_total,
            "percentage": percentage,
            "items_count": len(sorted_items),
            "top_items": sorted_items[:5],
        })

    categorized.sort(key=lambda item: item["total"], reverse=True)
    return categorized


def get_project_cost_categories(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    tool_input = enrich_tool_input("get_project_cost_categories", tool_input, session_id)

    try:
        remote = adapter.call_method(
            "project.financial.service",
            "get_ai_project_cost_categories",
            [
                tool_input.get("project_id"),
                tool_input.get("project_name"),
                tool_input.get("date_from"),
                tool_input.get("date_to"),
            ],
        )
        if isinstance(remote, dict) and remote.get("categories"):
            return remote
    except Exception as exc:
        logger.info("[Analytics] Odoo cost categories unavailable: %s", exc)

    dashboard = _load_project_dashboard(adapter, tool_input)
    if dashboard.get("error"):
        return dashboard

    distribution = dashboard.get("cost_distribution") or []
    categories = _categorize_distribution(distribution)
    kpis = dashboard.get("kpis") or {}
    total_cost = sum(category["total"] for category in categories)
    return {
        "project_id": dashboard.get("project_id") or tool_input.get("project_id"),
        "project_name": dashboard.get("project_name") or tool_input.get("project_name"),
        "wo_ref_no": dashboard.get("wo_ref_no"),
        "total_cost": total_cost or float(kpis.get("total_cost", 0) or 0),
        "budget": float(kpis.get("budget", 0) or 0),
        "categories": categories,
        "category_count": len(categories),
        "source": "expense_dashboard",
    }


def _project_ranking_row(
    project: dict[str, Any],
    financial: dict[str, Any],
    date_from: str | None,
    date_to: str | None,
) -> dict[str, Any]:
    kpis = financial.get("kpis") or {}
    budget = float(project.get("wo_amount") or kpis.get("budget", 0) or 0)
    revenue = float(kpis.get("total_income", 0) or 0)
    total_cost = float(kpis.get("total_expense", kpis.get("total_cost", 0)) or 0)
    net_profit = float(kpis.get("net_profit", revenue - total_cost) or 0)
    margin_percent = float(kpis.get("margin", 0) or 0)
    budget_overrun = ((total_cost - budget) / budget) * 100 if budget > 0 else 0.0
    partner = project.get("partner_id")
    client = partner[1] if isinstance(partner, (list, tuple)) and len(partner) > 1 else partner
    return {
        "project_id": project.get("id"),
        "project_name": project.get("name"),
        "wo_ref_no": project.get("wo_ref_no"),
        "client": client,
        "net_profit": net_profit,
        "revenue": revenue,
        "total_cost": total_cost,
        "budget": budget,
        "margin_percent": margin_percent,
        "budget_overrun": budget_overrun,
        "date_from": date_from,
        "date_to": date_to,
    }


def get_top_projects_by_metric(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    metric = tool_input.get("metric", "net_profit")
    limit = int(tool_input.get("limit", 5) or 5)
    order = tool_input.get("order", "desc")
    date_from = tool_input.get("date_from")
    date_to = tool_input.get("date_to")
    if not date_from or not date_to:
        date_from, date_to = _month_bounds()

    try:
        remote = adapter.call_method(
            "project.financial.service",
            "get_ai_top_projects",
            [metric, limit, order, date_from, date_to],
        )
        if isinstance(remote, dict) and remote.get("projects"):
            return remote
    except Exception as exc:
        logger.info("[Analytics] Odoo top projects unavailable: %s", exc)

    projects = adapter.search_read(
        model="project.project",
        domain=[["active", "=", True]],
        fields=["id", "name", "partner_id", "wo_ref_no", "wo_amount"],
        limit=TOP_PROJECTS_SCAN_LIMIT,
        order="name asc",
    )

    ranked: list[dict[str, Any]] = []
    for project in projects:
        try:
            financial = _load_project_financial_data(
                adapter,
                int(project["id"]),
                date_from,
                date_to,
            )
        except Exception as exc:
            logger.debug("[Analytics] Skip project %s: %s", project.get("id"), exc)
            continue
        ranked.append(_project_ranking_row(project, financial, date_from, date_to))

    reverse = order != "asc"
    ranked.sort(key=lambda row: float(row.get(metric, 0) or 0), reverse=reverse)
    return {
        "metric": metric,
        "limit": limit,
        "order": order,
        "date_from": date_from,
        "date_to": date_to,
        "projects": ranked[:limit],
        "scanned_projects": len(projects),
        "source": "gateway_scan",
    }


def get_period_comparison(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    report_type = tool_input.get("report_type", "pandl")
    period_1_from = tool_input["period_1_from"]
    period_1_to = tool_input["period_1_to"]
    period_2_from = tool_input["period_2_from"]
    period_2_to = tool_input["period_2_to"]

    try:
        remote = adapter.call_method(
            "project.financial.service",
            "get_ai_period_comparison",
            [
                report_type,
                period_1_from,
                period_1_to,
                period_2_from,
                period_2_to,
                tool_input.get("period_1_label"),
                tool_input.get("period_2_label"),
            ],
        )
        if isinstance(remote, dict) and remote.get("period_1"):
            return remote
    except Exception as exc:
        logger.info("[Analytics] Odoo period comparison unavailable: %s", exc)

    period_1 = adapter.accounting.get_financial_report(
        report_type=report_type,
        date_from=period_1_from,
        date_to=period_1_to,
    )
    period_2 = adapter.accounting.get_financial_report(
        report_type=report_type,
        date_from=period_2_from,
        date_to=period_2_to,
    )
    p1_kpis = period_1.get("kpis") or {}
    p2_kpis = period_2.get("kpis") or {}

    def variance(new: float, old: float) -> float | None:
        if old == 0:
            return None
        return round(((new - old) / old) * 100, 2)

    return {
        "report_type": report_type,
        "period_1": {
            "label": tool_input.get("period_1_label") or f"{period_1_from} to {period_1_to}",
            "income": p1_kpis.get("total_income", 0),
            "expense": p1_kpis.get("total_expense", 0),
            "net_profit": p1_kpis.get("net_profit", 0),
            "margin": p1_kpis.get("margin", 0),
        },
        "period_2": {
            "label": tool_input.get("period_2_label") or f"{period_2_from} to {period_2_to}",
            "income": p2_kpis.get("total_income", 0),
            "expense": p2_kpis.get("total_expense", 0),
            "net_profit": p2_kpis.get("net_profit", 0),
            "margin": p2_kpis.get("margin", 0),
        },
        "variance": {
            "income_pct": variance(
                float(p1_kpis.get("total_income", 0) or 0),
                float(p2_kpis.get("total_income", 0) or 0),
            ),
            "expense_pct": variance(
                float(p1_kpis.get("total_expense", 0) or 0),
                float(p2_kpis.get("total_expense", 0) or 0),
            ),
            "profit_pct": variance(
                float(p1_kpis.get("net_profit", 0) or 0),
                float(p2_kpis.get("net_profit", 0) or 0),
            ),
        },
        "source": "financial_report",
    }


def get_projects_with_overrun(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    threshold = float(tool_input.get("threshold_percent", 100) or 100)
    limit = int(tool_input.get("limit", 10) or 10)

    try:
        remote = adapter.call_method(
            "project.financial.service",
            "get_ai_projects_with_overrun",
            [threshold, limit],
        )
        if isinstance(remote, dict) and remote.get("projects") is not None:
            return remote
    except Exception as exc:
        logger.info("[Analytics] Odoo overrun list unavailable: %s", exc)

    projects = adapter.search_read(
        model="project.project",
        domain=[["active", "=", True]],
        fields=["id", "name", "partner_id", "wo_ref_no", "wo_amount"],
        limit=OVERRUN_SCAN_LIMIT,
        order="name asc",
    )

    overruns: list[dict[str, Any]] = []
    for project in projects:
        dashboard = _load_project_dashboard(adapter, {"project_id": project["id"]})
        if dashboard.get("error"):
            continue
        kpis = dashboard.get("kpis") or {}
        budget = float(kpis.get("budget", project.get("wo_amount", 0)) or 0)
        total_cost = float(kpis.get("total_cost", 0) or 0)
        exceed_percent = float(kpis.get("exceed_percent", 0) or 0)
        usage_percent = (total_cost / budget) * 100 if budget > 0 else exceed_percent
        if usage_percent < threshold and exceed_percent < threshold:
            continue
        partner = project.get("partner_id")
        client = partner[1] if isinstance(partner, (list, tuple)) and len(partner) > 1 else partner
        overruns.append({
            "project_id": project.get("id"),
            "project_name": project.get("name"),
            "wo_ref_no": project.get("wo_ref_no"),
            "client": client,
            "budget": budget,
            "total_cost": total_cost,
            "usage_percent": round(usage_percent, 2),
            "exceed_percent": exceed_percent,
            "status": kpis.get("status"),
        })

    overruns.sort(key=lambda row: row["usage_percent"], reverse=True)
    return {
        "threshold_percent": threshold,
        "limit": limit,
        "projects": overruns[:limit],
        "source": "expense_dashboard",
    }


def get_projects_by_client(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    client_name = tool_input.get("client_name")
    client_id = tool_input.get("client_id")
    include_financials = bool(tool_input.get("include_financials", True))

    try:
        remote = adapter.call_method(
            "project.financial.service",
            "get_ai_projects_by_client",
            [client_name, client_id, include_financials],
        )
        if isinstance(remote, dict) and remote.get("projects") is not None:
            return remote
    except Exception as exc:
        logger.info("[Analytics] Odoo projects-by-client unavailable: %s", exc)

    partner_ids: list[int] = []
    partners: list[dict[str, Any]] = []
    if client_id:
        partner_ids = [int(client_id)]
    elif client_name:
        partners = adapter.search_read(
            model="res.partner",
            domain=[["name", "ilike", client_name]],
            fields=["id", "name"],
            limit=5,
        )
        partner_ids = [int(partner["id"]) for partner in partners]

    if not partner_ids:
        return {
            "error": "client_not_found",
            "message": f"No client found matching '{client_name or client_id}'.",
            "projects": [],
        }

    projects = adapter.search_read(
        model="project.project",
        domain=[["active", "=", True], ["partner_id", "in", partner_ids]],
        fields=["id", "name", "partner_id", "wo_ref_no", "wo_amount", "date_start"],
        limit=int(tool_input.get("limit", 20) or 20),
        order="name asc",
    )

    enriched: list[dict[str, Any]] = []
    for project in projects:
        row = dict(project)
        if include_financials:
            dashboard = _load_project_dashboard(adapter, {"project_id": project["id"]})
            if not dashboard.get("error"):
                row["kpis"] = dashboard.get("kpis") or {}
        enriched.append(row)

    return {
        "client_name": client_name,
        "client_id": client_id,
        "partners": partners,
        "projects": enriched,
        "count": len(enriched),
    }


def _resolve_period_bounds(tool_input: dict[str, Any]) -> tuple[str | None, str | None]:
    date_from = tool_input.get("date_from")
    date_to = tool_input.get("date_to")
    year = tool_input.get("year")
    if year and not date_from:
        year_int = int(year)
        return f"{year_int}-01-01", f"{year_int}-12-31"
    return date_from, date_to


def get_project_counts_by_client(
    adapter: OdooV14Adapter,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    date_from, date_to = _resolve_period_bounds(tool_input)
    if not date_from or not date_to:
        return {
            "error": "missing_period",
            "message": "Provide year or both date_from and date_to.",
        }

    domain = [
        ["date_start", ">=", date_from],
        ["date_start", "<=", date_to],
    ]
    limit = int(tool_input.get("limit") or 100)
    order = "partner_id_count desc"

    try:
        rows = adapter.read_group(
            model="project.project",
            domain=domain,
            fields=["partner_id"],
            groupby=["partner_id"],
            limit=limit,
            order=order,
        )
    except Exception:
        rows = adapter.read_group(
            model="project.project",
            domain=domain,
            fields=["partner_id"],
            groupby=["partner_id"],
            limit=limit,
            order=None,
        )

    clients: list[dict[str, Any]] = []
    for row in rows:
        partner = row.get("partner_id")
        client_id = partner[0] if isinstance(partner, (list, tuple)) and partner else partner
        client_name = partner[1] if isinstance(partner, (list, tuple)) and len(partner) > 1 else str(partner or "Undefined")
        project_count = int(row.get("partner_id_count") or row.get("__count") or 0)
        clients.append({
            "client_id": client_id,
            "client": client_name,
            "project_count": project_count,
        })

    clients.sort(key=lambda item: item["project_count"], reverse=True)

    return {
        "date_from": date_from,
        "date_to": date_to,
        "clients": clients,
        "count": len(clients),
        "source": "read_group",
        "guidance": (
            "Use only this payload for project counts grouped by client in the period. "
            "Do not re-query with sql_aggregate or search_odoo for the same summary."
        ),
    }
