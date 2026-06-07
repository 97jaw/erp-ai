#!/usr/bin/env python3
"""Phase 10 performance baseline — sequential /chat/stream samples + DB telemetry."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

API_BASE = os.environ.get("OOA_API_BASE", "http://127.0.0.1:8000")
FILE_ID = os.environ.get("SUPER_ADMIN_FILE_ID", "2721")
P50_TARGET_MS = 3000
P95_TARGET_MS = 8000
COST_TARGET_CENTS = 50  # $0.50

BASELINE_QUERIES = [
    ("entity_confirm_simple", "show me Zayidia Boys School costs"),
    ("project_cost_simple", "show me National Guard project costs last month"),
    ("payslip_honest", "what is my last payslip"),
    ("financial_pandl", "show me profit and loss for last quarter"),
    ("forecast_oos", "Forecast next month's cash position"),
    ("empty_entity", "show me XYZNONEXISTENT999 project costs"),
    ("arabic_pandl", "أرني تقرير الأرباح والخسائر لهذا الشهر"),
]


@dataclass
class Sample:
    query_label: str
    query_text: str
    duration_ms: int
    http_status: int
    stream_status: str
    failure_mode: str | None
    cost_cents: int | None
    interaction_id: str | None


async def login(client: httpx.AsyncClient) -> str:
    if token := os.environ.get("OOA_JWT"):
        return token
    response = await client.post(f"{API_BASE}/auth/login", json={"file_id": FILE_ID})
    response.raise_for_status()
    body = response.json()
    if body.get("mfa_required"):
        raise RuntimeError("MFA required — set OOA_JWT from a completed login")
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"Login failed: {body}")
    return str(token)


def parse_sse(body: str) -> tuple[str, dict | None, str | None]:
    done_payload: dict | None = None
    error_message: str | None = None
    for line in body.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            payload = json.loads(line[6:])
        except json.JSONDecodeError:
            continue
        if payload.get("type") == "error":
            error_message = str(payload.get("message") or "error")
        if payload.get("type") == "done":
            done_payload = payload
    status = "error" if error_message else ("ok" if done_payload else "incomplete")
    return status, done_payload, error_message


async def chat_stream(
    client: httpx.AsyncClient,
    token: str,
    query_label: str,
    message: str,
) -> Sample:
    session_id = f"baseline-{uuid.uuid4()}"
    started = time.perf_counter()
    try:
        response = await client.post(
            f"{API_BASE}/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": message, "session_id": session_id},
            timeout=120.0,
        )
    except httpx.TimeoutException:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return Sample(
            query_label=query_label,
            query_text=message,
            duration_ms=duration_ms,
            http_status=0,
            stream_status="timeout",
            failure_mode="timeout",
            cost_cents=None,
            interaction_id=None,
        )
    duration_ms = int((time.perf_counter() - started) * 1000)
    stream_status, done_payload, _error = parse_sse(response.text)
    return Sample(
        query_label=query_label,
        query_text=message,
        duration_ms=duration_ms,
        http_status=response.status_code,
        stream_status=stream_status if response.status_code == 200 else "http_error",
        failure_mode=None,
        cost_cents=None,
        interaction_id=(
            str(done_payload["interaction_id"])
            if done_payload and done_payload.get("interaction_id")
            else None
        ),
    )


async def enrich_costs(samples: list[Sample]) -> None:
    if not os.environ.get("OOA_DB_URL"):
        return
    from admin.db.connection import close_admin_db, init_admin_db

    db = await init_admin_db()
    try:
        ids = [
            sample.interaction_id
            for sample in samples
            if sample.interaction_id and sample.interaction_id != "None"
        ]
        if not ids:
            return
        rows = await db.fetch(
            """
            SELECT id::text, cost_cents, failure_mode
            FROM ai_interactions
            WHERE id = ANY($1::uuid[])
            """,
            ids,
        )
        by_id = {row["id"]: row for row in rows}
        for sample in samples:
            if not sample.interaction_id or sample.interaction_id == "None":
                continue
            row = by_id.get(sample.interaction_id)
            if not row:
                continue
            sample.cost_cents = int(row["cost_cents"] or 0)
            sample.failure_mode = row["failure_mode"]
    finally:
        await close_admin_db()


async def persist_samples(run_id: str, run_label: str, samples: list[Sample]) -> None:
    if not os.environ.get("OOA_DB_URL"):
        print("SKIP DB persist: OOA_DB_URL not set")
        return
    from admin.db.connection import close_admin_db, init_admin_db

    db = await init_admin_db()
    try:
        for sample in samples:
            await db.execute(
                """
                INSERT INTO phase10_query_telemetry (
                    run_id, run_label, query_label, query_text,
                    duration_ms, cost_cents, failure_mode,
                    http_status, stream_status, interaction_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10::uuid)
                """,
                uuid.UUID(run_id),
                run_label,
                sample.query_label,
                sample.query_text,
                sample.duration_ms,
                sample.cost_cents,
                sample.failure_mode,
                sample.http_status,
                sample.stream_status,
                uuid.UUID(sample.interaction_id) if sample.interaction_id else None,
            )
    finally:
        await close_admin_db()


def percentile(values: list[int], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(round((pct / 100) * (len(ordered) - 1)))))
    return float(ordered[index])


async def run_baseline(run_label: str, repeats: int) -> int:
    run_id = str(uuid.uuid4())
    samples: list[Sample] = []

    print(f"API base: {API_BASE}")
    print(f"Run ID: {run_id}")
    print(f"Repeats per query: {repeats}\n")

    async with httpx.AsyncClient() as client:
        token = await login(client)
        for repeat in range(repeats):
            for query_label, message in BASELINE_QUERIES:
                print(f"  [{repeat + 1}/{repeats}] {query_label} ...", flush=True)
                sample = await chat_stream(client, token, query_label, message)
                samples.append(sample)
                print(
                    f"      {sample.duration_ms}ms status={sample.stream_status} "
                    f"http={sample.http_status}",
                )
                await asyncio.sleep(2)

    await enrich_costs(samples)
    await persist_samples(run_id, run_label, samples)

    durations = [sample.duration_ms for sample in samples if sample.stream_status == "ok"]
    costs = [sample.cost_cents for sample in samples if sample.cost_cents is not None]
    p50 = percentile(durations, 50)
    p95 = percentile(durations, 95)
    median_cost = statistics.median(costs) if costs else None
    max_cost = max(costs) if costs else None

    report = {
        "run_id": run_id,
        "run_label": run_label,
        "sample_count": len(samples),
        "ok_count": len(durations),
        "p50_ms": p50,
        "p95_ms": p95,
        "median_cost_cents": median_cost,
        "max_cost_cents": max_cost,
        "pass_p50": p50 < P50_TARGET_MS,
        "pass_p95": p95 < P95_TARGET_MS,
        "pass_cost": (max_cost or 0) <= COST_TARGET_CENTS,
        "samples": [sample.__dict__ for sample in samples],
    }

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / "phase10_baseline.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Phase 10 baseline ===")
    print(f"p50: {p50:.0f}ms (target < {P50_TARGET_MS}) — {'PASS' if report['pass_p50'] else 'FAIL'}")
    print(f"p95: {p95:.0f}ms (target < {P95_TARGET_MS}) — {'PASS' if report['pass_p95'] else 'FAIL'}")
    if costs:
        print(
            f"cost: median {median_cost:.0f}c max {max_cost}c "
            f"(target <= {COST_TARGET_CENTS}c) — {'PASS' if report['pass_cost'] else 'FAIL'}",
        )
    else:
        print("cost: no ai_interactions rows linked (check OOA_DB_URL + telemetry)")
    print(f"Report: {report_path}")

    if not (report["pass_p50"] and report["pass_p95"]):
        return 1
    if costs and not report["pass_cost"]:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 10 performance baseline")
    parser.add_argument("--label", default="baseline", help="Run label stored in DB")
    parser.add_argument("--repeats", type=int, default=1, help="Repeats per query")
    args = parser.parse_args()
    return asyncio.run(run_baseline(args.label, max(1, args.repeats)))


if __name__ == "__main__":
    raise SystemExit(main())
