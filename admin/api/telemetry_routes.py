"""Admin routes for AI interaction telemetry (Phase 8)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from admin.auth.service import get_auth_service
from admin.db.repositories.telemetry import TelemetryRepository
from admin.rbac.checks import require_permission
from gateway.core.learning_engine import run_daily_learning_job

telemetry_router = APIRouter(tags=["admin-telemetry"])


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    out: dict[str, Any] = {}
    for key in row.keys():
        value = row[key]
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


@telemetry_router.get(
    "/admin/telemetry",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def list_telemetry(
    limit: int = Query(50, le=200),
    offset: int = 0,
    user_id: int | None = None,
    hours: int | None = Query(None, le=168),
) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    repo = TelemetryRepository(service._db)
    if hours is not None:
        rows = await repo.list_recent(hours=hours, user_id=user_id, limit=limit)
    else:
        rows = await repo.list_for_admin(limit=limit, offset=offset, user_id=user_id)
    summary = await repo.summary(hours=hours or 24)
    return {
        "interactions": [_row_dict(row) for row in rows],
        "summary": _row_dict(summary),
        "limit": limit,
        "offset": offset,
    }


@telemetry_router.get(
    "/admin/telemetry/summary",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def telemetry_summary(hours: int = Query(24, le=168)) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    summary = await TelemetryRepository(service._db).summary(hours=hours)
    return {"hours": hours, "summary": _row_dict(summary)}


@telemetry_router.get(
    "/admin/telemetry/{interaction_id}",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def get_telemetry(interaction_id: str) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    row = await TelemetryRepository(service._db).get_by_id(interaction_id)
    if not row:
        raise HTTPException(status_code=404, detail="Interaction not found")
    return {"interaction": _row_dict(row)}


@telemetry_router.post(
    "/admin/telemetry/learning/run",
    dependencies=[Depends(require_permission("admin.settings.manage"))],
)
async def run_learning(hours: int = Query(24, le=168)) -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    patterns = await run_daily_learning_job(TelemetryRepository(service._db), hours=hours)
    return {"status": "success", "hours": hours, "patterns": patterns.to_dict()}


@telemetry_router.get(
    "/admin/telemetry/learning/latest",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def latest_learning_job() -> dict[str, Any]:
    service = await get_auth_service()
    assert service is not None
    row = await TelemetryRepository(service._db).latest_learning_job()
    if not row:
        return {"job": None}
    return {"job": _row_dict(row)}
