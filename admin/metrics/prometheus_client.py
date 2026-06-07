from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_PROMETHEUS = "http://127.0.0.1:9090"
DEFAULT_ALERTMANAGER = "http://127.0.0.1:9093"
DEFAULT_LOKI = "http://127.0.0.1:3100"


def prometheus_url() -> str:
    return os.environ.get("OOA_PROMETHEUS_URL", DEFAULT_PROMETHEUS).rstrip("/")


def alertmanager_url() -> str:
    return os.environ.get("OOA_ALERTMANAGER_URL", DEFAULT_ALERTMANAGER).rstrip("/")


def loki_url() -> str:
    return os.environ.get("OOA_LOKI_URL", DEFAULT_LOKI).rstrip("/")


async def prom_query(expr: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"{prometheus_url()}/api/v1/query",
            params={"query": expr},
        )
        resp.raise_for_status()
        return resp.json()


async def prom_query_range(
    expr: str,
    *,
    start: float,
    end: float,
    step: str = "3600",
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            f"{prometheus_url()}/api/v1/query_range",
            params={"query": expr, "start": start, "end": end, "step": step},
        )
        resp.raise_for_status()
        return resp.json()


def instant_scalar(data: dict[str, Any], default: float = 0.0) -> float:
    results = data.get("data", {}).get("result") or []
    if not results:
        return default
    try:
        return float(results[0]["value"][1])
    except (IndexError, KeyError, TypeError, ValueError):
        return default


def instant_labelled(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in data.get("data", {}).get("result") or []:
        metric = item.get("metric") or {}
        try:
            value = float(item["value"][1])
        except (KeyError, TypeError, ValueError):
            value = 0.0
        rows.append({"labels": metric, "value": value})
    return rows


async def fetch_prometheus_alerts() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{prometheus_url()}/api/v1/alerts")
        if resp.status_code != 200:
            return []
        payload = resp.json()
    alerts: list[dict[str, Any]] = []
    for item in payload.get("data", {}).get("alerts") or []:
        labels = item.get("labels") or {}
        alerts.append(
            {
                "state": item.get("state"),
                "name": labels.get("alertname"),
                "severity": labels.get("severity"),
                "summary": (item.get("annotations") or {}).get("summary"),
                "description": (item.get("annotations") or {}).get("description"),
                "active_at": item.get("activeAt"),
                "labels": labels,
            }
        )
    return alerts


async def alertmanager_status() -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{alertmanager_url()}/api/v2/status")
        if resp.status_code != 200:
            return {"ok": False, "error": f"HTTP {resp.status_code}"}
        return {"ok": True, "data": resp.json()}


async def create_alertmanager_silence(
    *,
    alertname: str,
    duration_hours: float,
    comment: str,
    created_by: str,
) -> dict[str, Any]:
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    ends = now + timedelta(hours=max(0.25, duration_hours))
    body = {
        "matchers": [
            {"name": "alertname", "value": alertname, "isRegex": False, "isEqual": True}
        ],
        "startsAt": now.isoformat().replace("+00:00", "Z"),
        "endsAt": ends.isoformat().replace("+00:00", "Z"),
        "createdBy": created_by,
        "comment": comment or f"Silenced via OOA admin for {duration_hours}h",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{alertmanager_url()}/api/v2/silences",
            json=body,
        )
        if resp.status_code not in (200, 201):
            return {"ok": False, "status": resp.status_code, "detail": resp.text}
        return {"ok": True, "silence_id": resp.json().get("silenceID")}


async def fetch_alertmanager_alerts() -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{alertmanager_url()}/api/v2/alerts")
        if resp.status_code != 200:
            return []
        payload = resp.json()
    alerts: list[dict[str, Any]] = []
    for item in payload:
        labels = item.get("labels") or {}
        annotations = item.get("annotations") or {}
        alerts.append(
            {
                "state": (item.get("status") or {}).get("state"),
                "name": labels.get("alertname"),
                "severity": labels.get("severity"),
                "summary": annotations.get("summary"),
                "description": annotations.get("description"),
                "starts_at": item.get("startsAt"),
                "labels": labels,
            }
        )
    return alerts
