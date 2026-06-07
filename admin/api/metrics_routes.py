from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from admin.auth.dependencies import get_current_user
from admin.auth.principal import CurrentUser
from pydantic import BaseModel, Field

from admin.metrics.service import (
    get_ai_metrics,
    get_alerts,
    get_cost_metrics,
    get_infrastructure_metrics,
    get_odoo_metrics,
    get_overview,
    get_user_activity_metrics,
    search_logs,
    silence_alert,
)
from admin.rbac.checks import require_permission
from gateway.api_credits import get_last_credit_checks, run_all_credit_checks

metrics_router = APIRouter(tags=["admin-metrics"])

_METRICS_DEPS = [Depends(require_permission("admin.settings.manage"))]


@metrics_router.get("/admin/metrics/overview", dependencies=_METRICS_DEPS)
async def metrics_overview(
    _user: CurrentUser = Depends(get_current_user),
    days: int = Query(1, ge=1, le=90),
) -> dict[str, Any]:
    return await get_overview(days=days)


@metrics_router.get("/admin/metrics/ai", dependencies=_METRICS_DEPS)
async def metrics_ai(
    _user: CurrentUser = Depends(get_current_user),
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    return await get_ai_metrics(days=days)


@metrics_router.get("/admin/metrics/api-health", dependencies=_METRICS_DEPS)
async def api_health_metrics(
    _user: CurrentUser = Depends(get_current_user),
    refresh: bool = Query(False),
) -> dict[str, Any]:
    if refresh:
        results = await run_all_credit_checks()
        providers = {r.provider: r.to_dict() for r in results}
    else:
        providers = get_last_credit_checks()
    return {"providers": providers, "refreshed": refresh}


@metrics_router.get("/admin/metrics/infrastructure", dependencies=_METRICS_DEPS)
async def metrics_infrastructure(
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return await get_infrastructure_metrics()


@metrics_router.get("/admin/metrics/odoo", dependencies=_METRICS_DEPS)
async def metrics_odoo(
    _user: CurrentUser = Depends(get_current_user),
    days: int = Query(7, ge=1, le=90),
) -> dict[str, Any]:
    return await get_odoo_metrics(days=days)


@metrics_router.get("/admin/metrics/users", dependencies=_METRICS_DEPS)
async def metrics_users(
    _user: CurrentUser = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    return await get_user_activity_metrics(days=days)


@metrics_router.get("/admin/metrics/costs", dependencies=_METRICS_DEPS)
async def metrics_costs(
    _user: CurrentUser = Depends(get_current_user),
    days: int = Query(30, ge=1, le=365),
) -> dict[str, Any]:
    return await get_cost_metrics(days=days)


@metrics_router.get("/admin/logs", dependencies=_METRICS_DEPS)
async def admin_logs(
    _user: CurrentUser = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=500),
    level: str | None = Query(None),
    query: str | None = Query(None),
    service: str | None = Query(None),
) -> dict[str, Any]:
    return await search_logs(
        limit=limit, level=level, query=query, service=service
    )


@metrics_router.get("/admin/alerts", dependencies=_METRICS_DEPS)
async def admin_alerts(
    _user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    return await get_alerts()


class AlertSilenceBody(BaseModel):
    alertname: str = Field(..., min_length=1)
    duration_hours: float = Field(2, ge=0.25, le=168)
    comment: str = ""


@metrics_router.post("/admin/alerts/silence", dependencies=_METRICS_DEPS)
async def admin_alert_silence(
    body: AlertSilenceBody,
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    created_by = user.name or user.file_id or f"user-{user.id}"
    return await silence_alert(
        alertname=body.alertname,
        duration_hours=body.duration_hours,
        comment=body.comment,
        created_by=created_by,
    )
