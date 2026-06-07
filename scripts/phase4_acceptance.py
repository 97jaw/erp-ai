#!/usr/bin/env python3
"""Phase 4 acceptance — orchestrated revenue comparison query."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_BASE = os.environ.get("OOA_API_BASE", "http://localhost:8000")
FILE_ID = os.environ.get("SUPER_ADMIN_FILE_ID", "2721")
QUERY = "Compare revenue Q1 2026 vs Q1 2025 by top 5 clients"
# Two sequential Odoo group queries under the adapter lock typically take ~11s live.
MAX_ORCHESTRATION_MS = int(os.environ.get("PHASE4_MAX_ORCHESTRATION_MS", "12000"))


async def login(client: httpx.AsyncClient) -> str:
    response = await client.post(f"{API_BASE}/auth/login", json={"file_id": FILE_ID})
    response.raise_for_status()
    body = response.json()
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"Login failed: {body}")
    return token


async def run_live() -> int:
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            health = await client.get(f"{API_BASE}/health", timeout=5.0)
            health.raise_for_status()
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            print(f"Gateway not reachable at {API_BASE} — start it first:")
            print("  uvicorn gateway.main:app --reload --port 8000")
            print(f"Error: {exc}")
            return 1

        try:
            token = await login(client)
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            print(f"Login timed out — is the gateway running at {API_BASE}?")
            print(f"Error: {exc}")
            return 1
        session_id = str(uuid.uuid4())
        response = await client.post(
            f"{API_BASE}/chat/intelligent",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": QUERY, "session_id": session_id, "skip_clarification": True},
        )
        response.raise_for_status()
        body = response.json()

    print("Query:", QUERY)
    print("\nResponse text:\n", body.get("text", ""))
    print("\nExecution duration (ms):", body.get("execution_duration_ms"))
    print("Orchestration duration (ms):", body.get("orchestration_duration_ms"))
    print("Strategy steps:", body.get("strategy_step_count"))
    print("Tools called:", body.get("tools_called"))
    print("\nOrchestration log:")
    print(json.dumps(body.get("orchestration_log") or [], indent=2))

    if body.get("visualization"):
        print("\nVisualization:")
        print(json.dumps(body["visualization"], indent=2))

    failures: list[str] = []
    if body.get("strategy_step_count", 0) < 2:
        failures.append("Expected at least 2 orchestrated steps")
    orchestration_ms = int(body.get("orchestration_duration_ms") or 0)
    if not orchestration_ms:
        orchestration_ms = sum(
            int(entry.get("duration_ms") or 0)
            for entry in (body.get("orchestration_log") or [])
        )
    if orchestration_ms > MAX_ORCHESTRATION_MS:
        failures.append(
            f"Expected orchestration under {MAX_ORCHESTRATION_MS}ms (got {orchestration_ms}ms)",
        )
    tools = body.get("tools_called") or []
    if tools.count("group_and_aggregate") < 2 and len(tools) < 2:
        failures.append("Expected multiple tool calls including parallel period fetches")
    if not body.get("orchestration_log"):
        failures.append("Expected non-empty orchestration_log")
    if not body.get("visualization"):
        failures.append("Expected comparison visualization")

    if failures:
        for item in failures:
            print("FAIL:", item)
        return 1

    print("\nPhase 4 live acceptance PASSED")
    return 0


async def run_offline() -> int:
    from admin.auth.principal import CurrentUser
    from gateway.core.intent_analyzer import Intent
    from gateway.core.strategy_fixtures import build_revenue_comparison_strategy
    from gateway.intelligent_handler import IntelligentQueryHandler
    from tests.core.test_execution_orchestrator import MockToolExecutor
    from tests.core.test_intelligent_handler import FixedIntentAnalyzer, _aggregate_rows

    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"rows": [_aggregate_rows("National Guard", 1200000)]},
            ("group_and_aggregate", 2): {"rows": [_aggregate_rows("National Guard", 980000)]},
        },
    )
    user = CurrentUser(
        id=4291,
        file_id=FILE_ID,
        name="Super Admin",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"data.all_projects"}),
        department_ids=(1,),
    )
    intent = Intent(
        primary_action="compare",
        subject_area="financial",
        specific_intent=QUERY,
        estimated_complexity="complex",
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(intent))
    response = await handler.handle(
        QUERY,
        user,
        adapter=object(),
        strategy_override=build_revenue_comparison_strategy(),
        executor=executor,
    )

    print("Query:", QUERY)
    print("\nResponse text:\n", response.text)
    print("\nExecution duration (ms):", response.execution_duration_ms)
    print("Strategy steps:", response.strategy_step_count)
    print("Tools called:", response.tools_called)
    print("\nOrchestration log:")
    print(json.dumps(response.orchestration_log, indent=2))
    if response.visualization:
        print("\nVisualization:")
        print(json.dumps(response.visualization, indent=2))

    assert response.strategy_step_count >= 2
    assert response.orchestration_log
    assert response.visualization is not None
    print("\nPhase 4 offline acceptance PASSED")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 4 orchestration acceptance")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Call /chat/intelligent against a running gateway",
    )
    args = parser.parse_args()
    if args.live:
        raise SystemExit(asyncio.run(run_live()))
    raise SystemExit(asyncio.run(run_offline()))


if __name__ == "__main__":
    main()
