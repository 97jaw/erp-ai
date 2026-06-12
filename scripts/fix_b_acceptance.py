#!/usr/bin/env python3
"""Fix B acceptance — relationship query composition (RQ-1..RQ-10)."""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import os

from scripts.api_test_utils import api_base, load_test_env, login as api_login, wait_for_health

load_test_env()

API_BASE = api_base()
FILE_ID = os.environ.get("OOA_FILE_ID", "2721")
VILLA_34 = [{"type": "project", "id": 15157, "name": "Villa Maintenance No. 34"}]

CASES = [
    ("RQ-1", "projects with no attachments", ["attachment", "project"], 1),
    ("RQ-2", "agreement for Villa 34", ["agreement", "villa", "abu dhabi", "police", "91-1"], 1),
    ("RQ-3", "all projects for Abu Dhabi Police", ["project", "abu dhabi", "police"], 1),
    ("RQ-4", "Villa 34 attachment types", ["attachment", "villa", "estimation", "wo", "type"], 1),
    ("RQ-5", "agreements expiring this month", ["agreement", "expir", "end date", "month"], 1),
    ("RQ-6", "client name for national guard project", ["client", "national guard", "partner"], 1),
    ("RQ-7", "how many projects have WO documents", ["wo", "work order", "project", "document", "count"], 1),
    ("RQ-8", "agreements without projects", ["agreement", "without", "project"], 1),
    ("RQ-9", "project count per client", ["client", "project", "count"], 1),
    ("RQ-10", "Villa 34 agreement amount and client", ["villa", "agreement", "client", "amount", "aed"], 1),
]


def chat(client: httpx.Client, token: str, message: str, *, confirmed: list | None = None) -> dict:
    res = client.post(
        f"{API_BASE}/chat/intelligent",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": message,
            "session_id": str(uuid.uuid4()),
            "skip_clarification": True,
            "deep_think": True,
            "confirmed_entities": confirmed or [],
        },
        timeout=300.0,
    )
    res.raise_for_status()
    return res.json()


def judge(text: str, tokens: list[str]) -> bool:
    low = text.lower()
    if re.search(r"completed\s+\d+\s+orchestrated\s+step", low):
        return False
    if "database error" in low or "try again later" in low:
        return False
    return any(t in low for t in tokens) and len(text) > 30


def main() -> int:
    results: list[tuple[str, bool, str, list]] = []
    with httpx.Client() as client:
        wait_for_health(client)
        token = api_login(client)
        for case_id, message, tokens, _ in CASES:
            confirmed = VILLA_34 if "Villa 34" in message else None
            body = chat(client, token, message, confirmed=confirmed)
            text = body.get("text") or ""
            tools = body.get("tools_called") or []
            ok = judge(text, tokens)
            results.append((case_id, ok, text[:220], tools))

    passed = sum(1 for _, ok, _, _ in results if ok)
    print("FIX B ACCEPTANCE")
    print("=" * 72)
    for case_id, ok, note, tools in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {case_id} tools={tools}: {note}")
    print("=" * 72)
    print(f"SUMMARY: {passed}/10 (need 7+)")
    return 0 if passed >= 7 else 1


if __name__ == "__main__":
    raise SystemExit(main())
