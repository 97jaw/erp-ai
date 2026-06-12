#!/usr/bin/env python3
"""Phase R3.2 — audit handler HTTP smoke tests."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
FILE_ID = "2721"


def parse_sse(raw: str) -> list[dict]:
    events: list[dict] = []
    for line in raw.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            events.append(json.loads(line[6:]))
        except json.JSONDecodeError:
            pass
    return events


def summarize_stream(label: str, events: list[dict]) -> dict:
    text = "".join(event.get("chunk", "") for event in events if event.get("type") == "text")
    done = next((event for event in reversed(events) if event.get("type") == "done"), {})
    tools = []
    statuses = [event.get("message") for event in events if event.get("type") == "status"]
    errors = [event for event in events if event.get("type") == "error"]
    return {
        "label": label,
        "status_events": statuses,
        "tools_called": done.get("tools_called") or tools,
        "agent": done.get("agent"),
        "text_preview": text[:2500],
        "text_length": len(text),
        "done_text_preview": (done.get("text") or "")[:2500],
        "errors": errors,
        "event_types": [event.get("type") for event in events],
    }


def login(client: httpx.Client) -> str:
    response = client.post(
        f"{BASE}/auth/login",
        json={"file_id": FILE_ID},
        timeout=30.0,
    )
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access_token returned")
    return token


def post_stream(client: httpx.Client, path: str, message: str, token: str) -> list[dict]:
    session_id = f"r3-test-{uuid.uuid4()}"
    with client.stream(
        "POST",
        f"{BASE}{path}",
        json={"message": message, "session_id": session_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=180.0,
    ) as response:
        response.raise_for_status()
        body = "".join(response.iter_text())
    return parse_sse(body)


def main() -> int:
    tests = [
        (
            "TEST 1 — POST /audit/stream",
            "/audit/stream",
            "what changed today on Villa Maintenance No. 34",
        ),
        (
            "TEST 2 — POST /audit/stream",
            "/audit/stream",
            "what did user 4291 do today",
        ),
        (
            "TEST 3 — POST /chat/stream (regression)",
            "/chat/stream",
            "Villa 34 expense",
        ),
    ]

    results: list[dict] = []
    with httpx.Client() as client:
        try:
            health = client.get(f"{BASE}/health", timeout=10.0)
            health.raise_for_status()
        except Exception as exc:
            print(f"Server not reachable at {BASE}: {exc}")
            print("Start with: uvicorn gateway.main:app --reload --port 8000")
            return 1

        token = login(client)
        print(f"Authenticated with file_id={FILE_ID}")

        for label, path, message in tests:
            print(f"\nRunning {label}: {message!r}")
            events = post_stream(client, path, message, token)
            summary = summarize_stream(label, events)
            results.append(summary)
            print(json.dumps(summary, indent=2, ensure_ascii=False))

    ok1 = (
        results[0]["text_length"] > 80
        and "error" not in str(results[0]["errors"]).lower()
    )
    ok2 = results[1]["text_length"] > 80
    ok3 = results[2]["text_length"] > 20 and results[2].get("agent") != "audit"

    print("\n" + "=" * 72)
    print(f"TEST 1 pass: {ok1}")
    print(f"TEST 2 pass: {ok2}")
    print(f"TEST 3 pass: {ok3}")
    print("=" * 72)
    return 0 if ok1 and ok2 and ok3 else 1


if __name__ == "__main__":
    raise SystemExit(main())
