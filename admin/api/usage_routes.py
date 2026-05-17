from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from admin.api.admin_management import _audit_row
from admin.auth.service import get_auth_service
from admin.db.repositories.audit import AuditRepository
from admin.db.repositories.usage import UsageRepository
from admin.rbac.checks import require_permission

usage_router = APIRouter(tags=["admin-usage"])


def _parse_date(value: str | None, default: date) -> date:
    if not value:
        return default
    return date.fromisoformat(value)


def _date_range(
    date_from: str | None,
    date_to: str | None,
    *,
    default_days: int = 30,
) -> tuple[date, date]:
    end = _parse_date(date_to, date.today())
    start = _parse_date(date_from, end - timedelta(days=default_days - 1))
    if start > end:
        start, end = end, start
    return start, end


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    out: dict[str, Any] = {}
    for key in row.keys():
        val = row[key]
        if hasattr(val, "isoformat"):
            out[key] = val.isoformat()
        else:
            out[key] = val
    return out


@usage_router.get(
    "/admin/usage",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def system_usage(
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    start, end = _date_range(date_from, date_to)
    service = await get_auth_service()
    assert service is not None
    repo = UsageRepository(service._db)
    summary = await repo.system_summary(date_from=start, date_to=end)
    daily = await repo.daily_totals(days=(end - start).days + 1)
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "summary": _row_dict(summary),
        "daily": [_row_dict(r) for r in daily],
    }


@usage_router.get(
    "/admin/usage/by-user",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def usage_by_user(
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = Query(50, le=200),
) -> dict[str, Any]:
    start, end = _date_range(date_from, date_to)
    service = await get_auth_service()
    assert service is not None
    rows = await UsageRepository(service._db).by_user(
        date_from=start,
        date_to=end,
        limit=limit,
    )
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "users": [_row_dict(r) for r in rows],
    }


@usage_router.get(
    "/admin/usage/by-department",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def usage_by_department(
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    start, end = _date_range(date_from, date_to)
    service = await get_auth_service()
    assert service is not None
    rows = await UsageRepository(service._db).by_department(
        date_from=start,
        date_to=end,
    )
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "departments": [_row_dict(r) for r in rows],
    }


@usage_router.get(
    "/admin/usage/costs",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def usage_costs(
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    start, end = _date_range(date_from, date_to)
    service = await get_auth_service()
    assert service is not None
    breakdown = await UsageRepository(service._db).cost_breakdown(
        date_from=start,
        date_to=end,
    )
    monthly = await UsageRepository(service._db).monthly_totals(months=12)
    return {
        "date_from": start.isoformat(),
        "date_to": end.isoformat(),
        "costs": breakdown,
        "monthly": [_row_dict(r) for r in monthly],
    }


@usage_router.get(
    "/admin/audit/export",
    dependencies=[Depends(require_permission("admin.audit_logs.view"))],
)
async def export_audit_csv(
    user_id: int | None = None,
    event_type: str | None = None,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> StreamingResponse:
    start, end = _date_range(date_from, date_to, default_days=90)
    service = await get_auth_service()
    assert service is not None
    audit = AuditRepository(service._db)
    rows = await audit.export_events(
        user_id=user_id,
        event_type=event_type,
        status=status,
        date_from=datetime.combine(start, datetime.min.time()),
        date_to=datetime.combine(end + timedelta(days=1), datetime.min.time()),
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "user_id",
            "event_type",
            "event_action",
            "resource_type",
            "resource_id",
            "status",
            "ip_address",
            "created_at",
            "metadata",
        ]
    )
    for row in rows:
        item = _audit_row(row)
        writer.writerow(
            [
                item["id"],
                item["user_id"],
                item["event_type"],
                item["event_action"],
                item.get("resource_type"),
                item.get("resource_id"),
                item["status"],
                item.get("ip_address"),
                item.get("created_at"),
                item.get("metadata"),
            ]
        )

    filename = f"audit-export-{start.isoformat()}-{end.isoformat()}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
