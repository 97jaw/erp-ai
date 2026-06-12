#!/usr/bin/env python3
"""Phase R3.3 — audit conversation memory (4-turn sequence, one session)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx

BASE = "http://127.0.0.1:8000"
FILE_ID = "2721"

TURNS = [
    "what changed on Villa 34 today",
    "who made those changes",
    "show me yesterday instead",
    "now check project National Guard",
]


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


def stream_text(events: list[dict]) -> str:
    return "".join(event.get("chunk", "") for event in events if event.get("type") == "text")


def login(client: httpx.Client) -> str:
    response = client.post(f"{BASE}/auth/login", json={"file_id": FILE_ID}, timeout=30.0)
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Login succeeded but no access_token returned")
    return token


def post_turn(
    client: httpx.Client,
    *,
    message: str,
    session_id: str,
    token: str,
) -> dict:
    with client.stream(
        "POST",
        f"{BASE}/audit/stream",
        json={"message": message, "session_id": session_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=180.0,
    ) as response:
        response.raise_for_status()
        body = "".join(response.iter_text())
    events = parse_sse(body)
    done = next((event for event in reversed(events) if event.get("type") == "done"), {})
    text = stream_text(events) or done.get("text", "")
    return {
        "message": message,
        "tools_called": done.get("tools_called") or [],
        "text": text,
        "errors": [event for event in events if event.get("type") == "error"],
    }


def main() -> int:
    session_id = f"r3-memory-{uuid.uuid4()}"
    results: list[dict] = []

    with httpx.Client() as client:
        client.get(f"{BASE}/health", timeout=10.0).raise_for_status()
        token = login(client)
        print(f"Session: {session_id}\n")

        for index, message in enumerate(TURNS, start=1):
            print("=" * 72)
            print(f"TURN {index}: {message!r}")
            print("=" * 72)
            result = post_turn(client, message=message, session_id=session_id, token=token)
            results.append(result)
            print(f"Tools: {result['tools_called']}")
            if result["errors"]:
                print(f"Errors: {result['errors']}")
            print()
            print(result["text"])
            print()

    ok1 = any(k in results[0]["text"].lower() for k in ("villa", "15157", "change", "no change"))
    ok2 = any(
        k in results[1]["text"].lower()
        for k in ("mohamad", "farah", "author", "user", "who", "made")
    ) and results[1]["tools_called"] in ([], ["get_audit_trail"])  # may reuse context
    ok3 = "yesterday" in results[2]["text"].lower() or "2026-06-11" in results[2]["text"]
    ok4 = any(k in results[4 - 1]["text"].lower() for k in ("national guard", "14458", "guard"))

    print("=" * 72)
    print(f"TURN 1 pass: {ok1}")
    print(f"TURN 2 pass: {ok2}")
    print(f"TURN 3 pass: {ok3}")
    print(f"TURN 4 pass: {ok4}")
    print("=" * 72)
    return 0 if all((ok1, ok2, ok3, ok4)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
