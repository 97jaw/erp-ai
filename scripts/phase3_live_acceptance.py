#!/usr/bin/env python3
"""Phase 3 live acceptance checks via the chat API."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

import httpx

API_BASE = os.environ.get("OOA_API_BASE", "http://localhost:8000")
FILE_ID = os.environ.get("SUPER_ADMIN_FILE_ID", "2721")

LIVE_SCENARIOS = [
    {
        "name": "National Guard scenario",
        "message": "give me national guard project expense report for last month",
        "must_not_contain": ["which project do you mean", "please specify the project"],
        "must_contain_any": ["national guard", "expense", "project"],
    },
    {
        "name": "NGC acronym",
        "message": "show me NGC project costs this month",
        "must_not_contain": ["which project", "clarify which project"],
        "must_contain_any": ["ngc", "national guard", "project", "cost"],
    },
    {
        "name": "Payslip honesty",
        "message": "what is my payslip",
        "must_not_contain": ["database error", "try again", "system error", "connection issue"],
        "must_contain_any": ["hr", "payroll", "payslip", "portal", "not available", "unavailable"],
    },
]


async def login(client: httpx.AsyncClient) -> str:
    response = await client.post(f"{API_BASE}/auth/login", json={"file_id": FILE_ID})
    response.raise_for_status()
    body = response.json()
    if body.get("mfa_required"):
        raise RuntimeError("MFA required — complete login manually in the UI for live tests")
    token = body.get("access_token")
    if not token:
        raise RuntimeError(f"Login failed: {body}")
    return token


async def chat(client: httpx.AsyncClient, token: str, message: str) -> str:
    session_id = str(uuid.uuid4())
    response = await client.post(
        f"{API_BASE}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "session_id": session_id, "skip_clarification": True},
        timeout=600.0,
    )
    response.raise_for_status()
    body = response.json()
    return str(body.get("text") or "")


async def main() -> int:
    print(f"API base: {API_BASE}")
    print(f"File ID: {FILE_ID}")
    failures = 0

    async with httpx.AsyncClient() as client:
        token = await login(client)
        print("Login OK\n")

        for scenario in LIVE_SCENARIOS:
            print("=" * 60)
            print(scenario["name"])
            print("Query:", scenario["message"])
            text = await chat(client, token, scenario["message"])
            lowered = text.lower()
            print("\nResponse:\n", text[:2000])
            if len(text) > 2000:
                print("\n... [truncated]")

            for forbidden in scenario["must_not_contain"]:
                if forbidden.lower() in lowered:
                    print(f"FAIL: forbidden phrase found: {forbidden!r}")
                    failures += 1

            if not any(token.lower() in lowered for token in scenario["must_contain_any"]):
                print(f"FAIL: expected one of {scenario['must_contain_any']}")
                failures += 1
            else:
                print("PASS")

            print()

    if failures:
        print(f"{failures} assertion(s) failed")
        return 1
    print("All Phase 3 live API scenarios passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
