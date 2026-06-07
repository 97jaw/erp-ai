#!/usr/bin/env python3
"""Phase 6 acceptance — honest failure handling (payslip scenario)."""

from __future__ import annotations

import argparse
import asyncio
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

PAYSLIP_QUERIES = (
    "what is my payslip",
    "what is my last payslip",
)

FORBIDDEN_PHRASES = (
    "database error",
    "database issue",
    "try again",
    "system error",
    "connection issue",
    "temporary",
)

REQUIRED_ANY = (
    "payslip",
    "payroll",
    "hr portal",
    "hr.elrace.com",
    "not available",
    "isn't available",
    "unavailable",
)

ROADMARKERS = ("q3 2026", "roadmap")


async def login(client: httpx.AsyncClient) -> str:
    response = await client.post(f"{API_BASE}/auth/login", json={"file_id": FILE_ID})
    response.raise_for_status()
    body = response.json()
    if body.get("mfa_required"):
        raise RuntimeError("MFA required — complete login manually for live tests")
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"Login failed: {body}")
    return token


async def call_intelligent(client: httpx.AsyncClient, token: str, message: str) -> dict:
    session_id = str(uuid.uuid4())
    response = await client.post(
        f"{API_BASE}/chat/intelligent",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "session_id": session_id, "skip_clarification": True},
    )
    response.raise_for_status()
    return response.json()


def assert_payslip_honesty(body: dict, *, label: str) -> list[str]:
    failures: list[str] = []
    text = (body.get("text") or "").lower()

    if not any(marker in text for marker in REQUIRED_ANY):
        failures.append(f"{label}: response missing honest payslip/HR wording")

    if not any(marker in text for marker in ROADMARKERS):
        failures.append(f"{label}: response should mention roadmap (Q3 2026)")

    if "hr.elrace.com" not in text and "hr portal" not in text:
        failures.append(f"{label}: response should suggest HR portal alternative")

    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            failures.append(f"{label}: forbidden phrase found: {phrase!r}")

    failure_mode = body.get("failure_mode")
    if failure_mode not in {"tool_not_available", "out_of_scope", "feature_coming_soon"}:
        failures.append(
            f"{label}: expected failure_mode tool_not_available, got {failure_mode!r}"
        )

    if body.get("strategy_step_count", 0) != 0:
        failures.append(f"{label}: payslip should not run orchestration steps")

    return failures


async def run_live() -> int:
    failures: list[str] = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            health = await client.get(f"{API_BASE}/health", timeout=5.0)
            health.raise_for_status()
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as exc:
            print(f"Gateway not reachable at {API_BASE}: {exc}")
            return 1

        token = await login(client)

        for index, message in enumerate(PAYSLIP_QUERIES, start=1):
            print(f"\nLIVE TEST {index}: Payslip honesty — {message!r}")
            body = await call_intelligent(client, token, message)
            print("Response text:", body.get("text", ""))
            print("failure_mode:", body.get("failure_mode"))
            failures.extend(assert_payslip_honesty(body, label=message))

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1

    print("\nPhase 6 live acceptance PASSED")
    return 0


async def run_offline() -> int:
    from admin.auth.principal import CurrentUser
    from gateway.core.failure_handler import FailureMode, HonestFailureResponder, contains_fabricated_excuse
    from gateway.core.intent_analyzer import Intent
    from gateway.intelligent_handler import IntelligentQueryHandler
    from tests.core.test_context_stack import _make_context_stack
    from tests.core.test_intelligent_handler import FixedIntentAnalyzer

    failures: list[str] = []
    responder = HonestFailureResponder()
    context = _make_context_stack()

    print("OFFLINE TEST 1: All failure mode templates render")
    for mode in FailureMode:
        from gateway.core.failure_handler import Failure

        failure = Failure(
            mode=mode,
            user_message="test query",
            capability_code="hr.payslips" if mode == FailureMode.TOOL_NOT_AVAILABLE else None,
            details={"query_label": "test query", "strategies_tried": ["search"]},
        )
        try:
            rendered = responder.respond(failure, context)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"Template render failed for {mode.value}: {exc}")
            continue
        if not rendered.text.strip():
            failures.append(f"Empty template for {mode.value}")
        if contains_fabricated_excuse(rendered.text):
            failures.append(f"Fabricated excuse in {mode.value}: {rendered.text[:120]}")

    print("OFFLINE TEST 2: Payslip via IntelligentQueryHandler")
    intent = Intent(
        primary_action="fetch_data",
        subject_area="hr",
        specific_intent="what is my payslip",
        out_of_scope=True,
        out_of_scope_reason="hr.payslips is unavailable. Use the HR portal directly at hr.elrace.com",
    )
    handler = IntelligentQueryHandler(intent_analyzer=FixedIntentAnalyzer(intent))
    user = CurrentUser(
        id=4291,
        file_id="2721",
        name="Super Admin",
        language="en",
        is_super_admin=True,
        is_active=True,
        roles=("super_admin",),
        permissions=frozenset({"data.all_projects"}),
        department_ids=(1,),
    )
    response = await handler.handle("what is my payslip", user, adapter=object())
    body = {
        "text": response.text,
        "failure_mode": response.failure_mode,
        "strategy_step_count": response.strategy_step_count,
    }
    failures.extend(assert_payslip_honesty(body, label="offline handler"))

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1

    print("\nPhase 6 offline acceptance PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 6 failure handling acceptance")
    parser.add_argument("--live", action="store_true", help="Run live payslip tests against gateway")
    args = parser.parse_args()
    if args.live:
        return asyncio.run(run_live())
    return asyncio.run(run_offline())


if __name__ == "__main__":
    raise SystemExit(main())
