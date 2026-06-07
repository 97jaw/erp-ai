#!/usr/bin/env python3
"""Phase 5 acceptance — quality gate live tests."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_BASE = os.environ.get("OOA_API_BASE", "http://localhost:8000")
FILE_ID = os.environ.get("SUPER_ADMIN_FILE_ID", "2721")
LOG_FILE = Path(os.environ.get("OOA_LOG_FILE", ROOT / "logs" / "ooa-gateway.jsonl"))

QUERY_RAW_SYNTAX = "show me revenue by client last quarter"
QUERY_NO_DATA = "Show revenue by client for January 2099"
QUERY_QUALITY_LOG = "show me revenue by client last quarter"

RAW_FORBIDDEN = (
    "amount_total:sum",
    "__count",
)
M2O_PATTERN = re.compile(r"\[\s*\d+\s*,\s*['\"]")
SNAKE_CASE_PATTERN = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")
INVENTED_NUMBER = re.compile(r"(?:AED\s*)?\d{1,3}(?:,\d{3})+|\d{4,}")
QUALITY_GATE_PATTERN = re.compile(r"Quality gate: (\d+)/(\d+) checks passed")
QUALITY_RETRY_PATTERN = re.compile(r"retries=(\d+)")


async def login(client: httpx.AsyncClient) -> str:
    response = await client.post(f"{API_BASE}/auth/login", json={"file_id": FILE_ID})
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Login failed")
    return token


def response_blob(body: dict) -> str:
    return json.dumps(body, default=str)


def user_facing_text(body: dict) -> str:
    parts = [body.get("text") or ""]
    visualization = body.get("visualization") or {}
    parts.append(str(visualization.get("label") or ""))
    data = visualization.get("data") or {}
    for header in data.get("headers") or []:
        parts.append(str(header))
    for row in data.get("rows") or []:
        if isinstance(row, (list, tuple)):
            parts.extend(str(cell) for cell in row)
        elif isinstance(row, dict):
            parts.extend(str(value) for value in row.values())
    for label in data.get("labels") or []:
        parts.append(str(label))
    return "\n".join(parts)


def assert_no_raw_syntax(body: dict) -> list[str]:
    blob = user_facing_text(body)
    failures: list[str] = []
    for token in RAW_FORBIDDEN:
        if token in blob:
            failures.append(f"Forbidden raw syntax found: {token}")
    if M2O_PATTERN.search(blob):
        failures.append("Forbidden [ID, 'Name'] tuple found in response")
    if SNAKE_CASE_PATTERN.search(blob):
        failures.append("Underscore field names found in user-facing response")
    return failures


def assert_no_fabrication(body: dict) -> list[str]:
    text = body.get("text") or ""
    failures: list[str] = []
    if "No data found for" not in text:
        failures.append("Expected honest no-data message starting with 'No data found for'")
    for match in INVENTED_NUMBER.finditer(text):
        failures.append(f"Response appears to invent numeric data: {match.group(0)}")
    return failures


def scan_logs_since(start_size: int) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    raw = LOG_FILE.read_text(encoding="utf-8")
    chunk = raw[start_size:]
    entries: list[dict] = []
    for line in chunk.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def assert_quality_logs(entries: list[dict]) -> list[str]:
    failures: list[str] = []
    messages = [entry.get("message", "") for entry in entries if entry.get("logger") == "gateway.core.quality_gate"]
    quality_lines = [message for message in messages if "Quality gate:" in message]
    if not quality_lines:
        failures.append("No quality gate log lines found")
        return failures

    retry_counts = []
    for line in quality_lines:
        match = QUALITY_GATE_PATTERN.search(line)
        if not match:
            failures.append(f"Malformed quality gate log line: {line}")
            continue
        passed, total = int(match.group(1)), int(match.group(2))
        if total != 8:
            failures.append(f"Expected 8 checks logged, got {total}")
        retry_match = QUALITY_RETRY_PATTERN.search(line)
        if retry_match:
            retry_counts.append(int(retry_match.group(1)))

    if retry_counts and max(retry_counts) > 2:
        failures.append("Quality gate exceeded maximum retries")
    return failures


async def call_intelligent(client: httpx.AsyncClient, token: str, message: str) -> dict:
    session_id = str(uuid.uuid4())
    response = await client.post(
        f"{API_BASE}/chat/intelligent",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "session_id": session_id, "skip_clarification": True},
    )
    response.raise_for_status()
    return response.json()


async def run_live() -> int:
    failures: list[str] = []
    log_start = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            health = await client.get(f"{API_BASE}/health", timeout=5.0)
            health.raise_for_status()
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            print(f"Gateway not reachable at {API_BASE}: {exc}")
            return 1

        token = await login(client)

        print("LIVE TEST 1: Raw syntax filter")
        body1 = await call_intelligent(client, token, QUERY_RAW_SYNTAX)
        print("Response text:", body1.get("text", "")[:240])
        failures.extend(assert_no_raw_syntax(body1))

        print("\nLIVE TEST 2: Fabrication prevention")
        body2 = await call_intelligent(client, token, QUERY_NO_DATA)
        print("Response text:", body2.get("text", ""))
        failures.extend(assert_no_fabrication(body2))

        print("\nLIVE TEST 3: Quality gate logging")
        await call_intelligent(client, token, QUERY_QUALITY_LOG)
        log_entries = scan_logs_since(log_start)
        failures.extend(assert_quality_logs(log_entries))
        for entry in log_entries:
            message = entry.get("message", "")
            if "Quality gate:" in message:
                print("Log:", message)

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1

    print("\nPhase 5 live acceptance PASSED")
    return 0


async def run_offline() -> int:
    from admin.auth.principal import CurrentUser
    from gateway.core.intent_analyzer import Intent
    from gateway.core.quality_gate import QualityGate
    from gateway.core.quality_pipeline import build_quality_response
    from gateway.core.strategy_fixtures import build_revenue_by_client_strategy
    from gateway.intelligent_handler import IntelligentQueryHandler
    from tests.core.test_execution_orchestrator import MockToolExecutor
    from tests.core.test_intelligent_handler import FixedIntentAnalyzer

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
        primary_action="fetch_data",
        subject_area="financial",
        specific_intent="Show revenue by client for January 2099",
        estimated_complexity="simple",
        expected_output="table",
    )
    executor = MockToolExecutor(
        responses={
            ("group_and_aggregate", 1): {"groups": []},
        },
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(intent))
    response = await handler.handle(
        QUERY_NO_DATA,
        user,
        adapter=object(),
        strategy_override=build_revenue_by_client_strategy(
            date_from="2099-01-01",
            date_to="2099-01-31",
        ),
        executor=executor,
    )
    assert "No data found for" in response.text
    assert response.quality_checks_total == 8

    polished = build_quality_response(
        message=QUERY_RAW_SYNTAX,
        text="Client amount_total:sum totals",
        visualization=None,
        tool_names=["group_and_aggregate"],
        tool_results=[{"groups": [{"partner_id": [1, "Client"], "amount_total:sum": 1000.0}]}],
        language="en",
        intent=intent,
    )
    review = await QualityGate().review(
        polished,
        intent,
        _make_context_stack(),
    )
    assert any(check.name == "no_raw_syntax" and not check.passed for check in review.checks) or review.passed

    print("Phase 5 offline acceptance PASSED")
    return 0


def _make_context_stack():
    from tests.core.test_context_stack import _make_context_stack as make_stack
    return make_stack()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 5 quality gate acceptance")
    parser.add_argument("--live", action="store_true", help="Run live tests against gateway")
    args = parser.parse_args()
    if args.live:
        raise SystemExit(asyncio.run(run_live()))
    raise SystemExit(asyncio.run(run_offline()))


if __name__ == "__main__":
    main()
