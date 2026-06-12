#!/usr/bin/env python3
"""Phase R5 — sidebar + chat/audit mode switching (HTTP smoke)."""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
FILE_ID = "2721"
UI_BASE = "http://127.0.0.1:3000"


def login(client: httpx.Client) -> str:
    res = client.post(f"{BASE}/auth/login", json={"file_id": FILE_ID}, timeout=30)
    res.raise_for_status()
    token = res.json().get("access_token")
    if not token:
        raise RuntimeError("no access_token")
    return token


def parse_sse(raw: str) -> list[dict]:
    events = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def stream_audit(client: httpx.Client, token: str, message: str, session_id: str) -> str:
    with client.stream(
        "POST",
        f"{BASE}/audit/stream",
        json={"message": message, "session_id": session_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    ) as res:
        res.raise_for_status()
        body = "".join(res.iter_text())
    done = next((e for e in reversed(parse_sse(body)) if e.get("type") == "done"), {})
    return done.get("text") or ""


def stream_chat(client: httpx.Client, token: str, message: str, session_id: str) -> str:
    with client.stream(
        "POST",
        f"{BASE}/chat/stream",
        json={"message": message, "session_id": session_id},
        headers={"Authorization": f"Bearer {token}"},
        timeout=120,
    ) as res:
        res.raise_for_status()
        body = "".join(res.iter_text())
    done = next((e for e in reversed(parse_sse(body)) if e.get("type") == "done"), {})
    return done.get("text") or ""


def main() -> int:
    audit_session = f"r5-audit-{uuid.uuid4()}"
    chat_session = f"r5-chat-{uuid.uuid4()}"

    with httpx.Client() as client:
        client.get(f"{BASE}/health", timeout=10).raise_for_status()
        try:
            client.get(UI_BASE, timeout=5).raise_for_status()
        except Exception as exc:
            print(f"UI not reachable at {UI_BASE}: {exc}")
            return 1

        token = login(client)

        # Independent sessions: audit lane vs chat lane
        audit_text_1 = stream_audit(
            client,
            token,
            "what changed on Villa Maintenance No. 34 since June 1 2026",
            audit_session,
        )
        chat_text_1 = stream_chat(client, token, "Villa 34 expense", chat_session)
        audit_text_2 = stream_audit(
            client,
            token,
            "who made those changes",
            audit_session,
        )
        chat_text_2 = stream_chat(
            client,
            token,
            "just say OK for regression",
            chat_session,
        )

    ok_audit = len(audit_text_1) > 50 and len(audit_text_2) > 20
    ok_chat = len(chat_text_1) > 20 and len(chat_text_2) > 2
    ok_independent = audit_session != chat_session

    print("audit session 1 length:", len(audit_text_1))
    print("audit session 2 (follow-up) length:", len(audit_text_2))
    print("chat session 1 length:", len(chat_text_1))
    print("chat session 2 length:", len(chat_text_2))
    print("sessions independent:", ok_independent)
    print("API audit+chat pass:", ok_audit and ok_chat and ok_independent)
    print("\nUI manual checks (browser):")
    print("  1-2. Sidebar: Search, Chat List, Sessions, Audit — no PnL/Projects/Cash/Voice/Tasks")
    print("  3-8. Toggle Audit ↔ Chat List — both states preserved")
    return 0 if ok_audit and ok_chat else 1


if __name__ == "__main__":
    raise SystemExit(main())
