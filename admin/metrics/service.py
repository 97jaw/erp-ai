from __future__ import annotations

import json
import os
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

from admin.auth.service import get_auth_service
from admin.db.repositories.usage import UsageRepository
from admin.metrics.prometheus_client import (
    alertmanager_url,
    fetch_alertmanager_alerts,
    fetch_prometheus_alerts,
    instant_labelled,
    instant_scalar,
    loki_url,
    prom_query,
)
from gateway.api_credits import get_last_credit_checks


async def _usage_repo() -> UsageRepository | None:
    service = await get_auth_service()
    if service is None:
        return None
    return UsageRepository(service._db)


def _date_range(days: int) -> tuple[date, date]:
    end = date.today()
    start = end - timedelta(days=max(1, days) - 1)
    return start, end


async def get_overview(*, days: int = 1) -> dict[str, Any]:
    start, end = _date_range(days)
    usage_summary: dict[str, Any] = {}
    repo = await _usage_repo()
    if repo:
        row = await repo.system_summary(date_from=start, date_to=end)
        if row:
            usage_summary = dict(row)

    prom_ok = True
    prom_error = ""
    metrics: dict[str, float] = {}

    async def _prom_scalar(expr: str, key: str, default: float = 0.0) -> None:
        nonlocal prom_ok, prom_error
        try:
            metrics[key] = instant_scalar(await prom_query(expr), default=default)
        except Exception as exc:
            prom_ok = False
            if not prom_error:
                prom_error = str(exc)[:300]

    await _prom_scalar('up{job="ooa-gateway"}', "gateway_up")
    await _prom_scalar("sum(rate(ooa_ai_queries_total[1h]))", "queries_per_min")
    metrics["queries_per_min"] = metrics.get("queries_per_min", 0) * 60
    await _prom_scalar(
        'sum(rate(ooa_api_requests_total{status_code=~"5.."}[5m])) '
        "/ clamp_min(sum(rate(ooa_api_requests_total[5m])), 0.001)",
        "error_rate",
    )
    await _prom_scalar(
        "histogram_quantile(0.95, sum(rate(ooa_ai_response_time_seconds_bucket[1h])) by (le))",
        "p95_latency",
    )
    await _prom_scalar("ooa_ai_streaming_connections", "streaming_connections")

    providers = get_last_credit_checks()
    providers_up = sum(1 for p in providers.values() if p.get("up"))

    alerts: list[dict[str, Any]] = []
    try:
        alerts = await fetch_prometheus_alerts()
        alerts = [a for a in alerts if a.get("state") == "firing"]
    except Exception:
        pass

    return {
        "period_days": days,
        "usage": usage_summary,
        "prometheus_ok": prom_ok,
        "prometheus_error": prom_error,
        "metrics": metrics,
        "api_providers_up": providers_up,
        "api_providers_total": len(providers) or 3,
        "providers": providers,
        "firing_alerts": alerts[:10],
        "firing_alert_count": len(alerts),
    }


async def get_ai_metrics(*, days: int = 1) -> dict[str, Any]:
    window = f"{max(days, 1)}d"
    start, end = _date_range(days)
    usage: dict[str, Any] = {}
    repo = await _usage_repo()
    if repo:
        row = await repo.system_summary(date_from=start, date_to=end)
        if row:
            usage = dict(row)
        daily = await repo.daily_totals(days=days)
        usage["daily"] = [dict(r) for r in daily]

    prom: dict[str, Any] = {"ok": True}
    try:
        prom["input_tokens"] = instant_scalar(
            await prom_query(f'sum(increase(ooa_ai_tokens_consumed_total{{type="input"}}[{window}]))')
        )
        prom["output_tokens"] = instant_scalar(
            await prom_query(f'sum(increase(ooa_ai_tokens_consumed_total{{type="output"}}[{window}]))')
        )
        prom["cost_cents"] = instant_scalar(
            await prom_query(f"sum(increase(ooa_ai_cost_cents_total[{window}]))")
        )
        prom["queries_total"] = instant_scalar(
            await prom_query(f"sum(increase(ooa_ai_queries_total[{window}]))")
        )
        prom["tools"] = instant_labelled(
            await prom_query(f"topk(10, sum by (tool_name) (increase(ooa_tool_executions_total[{window}])))")
        )
        prom["tool_errors"] = instant_labelled(
            await prom_query(
                f'sum by (tool_name) (increase(ooa_tool_executions_total{{status!="success"}}[{window}]))'
            )
        )
    except Exception as exc:
        prom = {"ok": False, "error": str(exc)[:300]}

    return {"period_days": days, "usage": usage, "prometheus": prom}


async def get_infrastructure_metrics() -> dict[str, Any]:
    targets: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{os.environ.get('OOA_PROMETHEUS_URL', 'http://127.0.0.1:9090')}/api/v1/targets"
            )
            resp.raise_for_status()
            for t in resp.json().get("data", {}).get("activeTargets") or []:
                labels = t.get("labels") or {}
                targets.append(
                    {
                        "job": labels.get("job"),
                        "health": t.get("health"),
                        "last_error": (t.get("lastError") or "")[:120],
                    }
                )
    except Exception as exc:
        targets = [{"error": str(exc)[:200]}]

    gauges: dict[str, float] = {}
    try:
        gauges["postgres_up"] = instant_scalar(await prom_query('up{job="postgres"}'))
        gauges["redis_up"] = instant_scalar(await prom_query('up{job="redis"}'))
        gauges["gateway_up"] = instant_scalar(await prom_query('up{job="ooa-gateway"}'))
    except Exception:
        pass

    return {"targets": targets, "gauges": gauges}


async def get_odoo_metrics(*, days: int = 1) -> dict[str, Any]:
    window = f"{max(days, 1)}d"
    try:
        calls = instant_labelled(
            await prom_query(f"sum by (method, status) (increase(ooa_odoo_calls_total[{window}]))")
        )
        tool_calls = instant_labelled(
            await prom_query(f"topk(12, sum by (tool_name) (increase(ooa_tool_executions_total[{window}])))")
        )
        p95_tool = instant_scalar(
            await prom_query(
                "histogram_quantile(0.95, sum(rate(ooa_tool_duration_seconds_bucket[1h])) by (le))"
            )
        )
        p95_odoo = instant_scalar(
            await prom_query(
                "histogram_quantile(0.95, sum(rate(ooa_odoo_call_duration_seconds_bucket[1h])) by (le))"
            )
        )
        odoo_errors = instant_scalar(
            await prom_query(
                f'sum(increase(ooa_odoo_calls_total{{status="error"}}[{window}]))'
            )
        )
        return {
            "ok": True,
            "period_days": days,
            "odoo_calls": calls,
            "tool_executions": tool_calls,
            "tool_p95_seconds": p95_tool,
            "odoo_p95_seconds": p95_odoo,
            "odoo_errors": odoo_errors,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


async def get_user_activity_metrics(*, days: int = 30) -> dict[str, Any]:
    start, end = _date_range(days)
    repo = await _usage_repo()
    if repo is None:
        return {"users": [], "summary": {}}
    summary_row = await repo.system_summary(date_from=start, date_to=end)
    users = await repo.by_user(date_from=start, date_to=end, limit=20)
    return {
        "period_days": days,
        "summary": dict(summary_row) if summary_row else {},
        "users": [dict(u) for u in users],
    }


async def get_cost_metrics(*, days: int = 30) -> dict[str, Any]:
    start, end = _date_range(days)
    costs: dict[str, Any] = {"db": {}, "prometheus": {}}
    repo = await _usage_repo()
    if repo:
        row = await repo.system_summary(date_from=start, date_to=end)
        if row:
            costs["db"] = dict(row)
        costs["db"]["breakdown"] = await repo.cost_breakdown(
            date_from=start, date_to=end
        )

    window = f"{max(days, 1)}d"
    try:
        costs["prometheus"] = {
            "anthropic_cents": instant_scalar(
                await prom_query(
                    'sum(increase(ooa_ai_cost_cents_total{provider="anthropic"}[' + window + "]))"
                )
            ),
            "total_ai_cents": instant_scalar(
                await prom_query(f"sum(increase(ooa_ai_cost_cents_total[{window}]))")
            ),
        }
    except Exception as exc:
        costs["prometheus"] = {"error": str(exc)[:200]}

    costs["providers"] = get_last_credit_checks()
    return {"period_days": days, "costs": costs}


async def search_logs(
    *,
    limit: int = 100,
    level: str | None = None,
    query: str | None = None,
    service: str | None = None,
) -> dict[str, Any]:
    limit = min(max(1, limit), 500)
    loki_entries = await _search_logs_loki(limit=limit, level=level, query=query, service=service)
    if loki_entries is not None:
        return {"source": "loki", "entries": loki_entries, "count": len(loki_entries)}

    path = Path(os.environ.get("OOA_LOG_FILE", "logs/ooa-gateway.jsonl"))
    entries = _search_logs_file(path, limit=limit, level=level, query=query)
    return {"source": "file", "path": str(path), "entries": entries, "count": len(entries)}


async def _search_logs_loki(
    *,
    limit: int,
    level: str | None,
    query: str | None,
    service: str | None,
) -> list[dict[str, Any]] | None:
    selectors = ['job="ooa-gateway"']
    if service:
        selectors = [f'service="{service}"']
    if level:
        selectors.append(f'level="{level.upper()}"')
    logql = "{" + ",".join(selectors) + "}"
    if query:
        logql += f' |= "{query.replace(chr(34), "")}"'

    end_ns = time.time_ns()
    start_ns = end_ns - int(3600 * 1e9)
    params = {
        "query": logql,
        "limit": str(limit),
        "start": str(start_ns),
        "end": str(end_ns),
        "direction": "backward",
    }
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                f"{loki_url()}/loki/api/v1/query_range",
                params=params,
            )
            if resp.status_code != 200:
                return None
            payload = resp.json()
    except Exception:
        return None

    entries: list[dict[str, Any]] = []
    for stream in payload.get("data", {}).get("result") or []:
        labels = stream.get("stream") or {}
        for ts, line in stream.get("values") or []:
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                parsed = {"message": line}
            parsed.setdefault("labels", labels)
            parsed["timestamp_ns"] = ts
            entries.append(parsed)
    entries.sort(key=lambda e: e.get("timestamp_ns", ""), reverse=True)
    return entries[:limit]


def _search_logs_file(
    path: Path,
    *,
    limit: int,
    level: str | None,
    query: str | None,
) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    entries: list[dict[str, Any]] = []
    for line in reversed(lines):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if level and str(row.get("level", "")).upper() != level.upper():
            continue
        if query:
            blob = json.dumps(row).lower()
            if query.lower() not in blob:
                continue
        entries.append(row)
        if len(entries) >= limit:
            break
    return entries


def _attach_runbooks(alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from admin.metrics.runbooks import runbook_for_alert

    out: list[dict[str, Any]] = []
    for a in alerts:
        row = dict(a)
        rb = runbook_for_alert(a.get("name"))
        if rb:
            row["runbook"] = rb
        out.append(row)
    return out


async def get_alerts() -> dict[str, Any]:
    from admin.metrics.runbooks import list_runbooks

    prom = _attach_runbooks(await fetch_prometheus_alerts())
    am = []
    try:
        am = _attach_runbooks(await fetch_alertmanager_alerts())
    except Exception:
        pass
    notification_configured = False
    try:
        from pathlib import Path

        gen = Path("monitoring/alertmanager/alertmanager.generated.yml")
        if gen.is_file():
            text = gen.read_text(encoding="utf-8")
            notification_configured = (
                "email_configs:" in text or "slack_configs:" in text
            ) and "Enable ALERT_" not in text
    except OSError:
        pass
    return {
        "prometheus": prom,
        "alertmanager": am,
        "alertmanager_url": alertmanager_url(),
        "runbooks": list_runbooks(),
        "notifications_configured": notification_configured,
    }


async def silence_alert(
    *,
    alertname: str,
    duration_hours: float,
    comment: str,
    created_by: str,
) -> dict[str, Any]:
    from admin.metrics.prometheus_client import create_alertmanager_silence

    return await create_alertmanager_silence(
        alertname=alertname,
        duration_hours=duration_hours,
        comment=comment,
        created_by=created_by,
    )
