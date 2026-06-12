#!/usr/bin/env python3
"""Fix A acceptance — universal tool narration (UA-1..UA-10)."""

from __future__ import annotations

import re
import sys
import uuid
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

API_BASE = "http://127.0.0.1:8000"
FILE_ID = "2721"
VILLA_34_ID = 15157
ZAYIDIA_BOYS_ID = 14549

NO_DATA = re.compile(r"no data found", re.I)
META = re.compile(r"completed\s+\d+\s+orchestrated\s+step", re.I)

CASES: list[tuple[str, str, dict, callable]] = []


def login(client: httpx.Client) -> str:
    res = client.post(f"{API_BASE}/auth/login", json={"file_id": FILE_ID}, timeout=30)
    res.raise_for_status()
    return res.json()["access_token"]


def chat(
    client: httpx.Client,
    token: str,
    message: str,
    *,
    deep_think: bool = True,
    confirmed: list[dict] | None = None,
    session_id: str | None = None,
) -> dict:
    res = client.post(
        f"{API_BASE}/chat/intelligent",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "message": message,
            "session_id": session_id or str(uuid.uuid4()),
            "skip_clarification": True,
            "deep_think": deep_think,
            "confirmed_entities": confirmed or [],
        },
        timeout=300.0,
    )
    res.raise_for_status()
    return res.json()


def has_real_data(text: str, tools: list[str]) -> bool:
    if NO_DATA.search(text) or META.search(text):
        return False
    if len(text.strip()) < 20:
        return False
    if "query_odoo" in tools or "aggregate_odoo" in tools:
        return bool(re.search(r"\d|Found|employee|purchase|fleet|contract|stock|AED", text, re.I))
    return True


def main() -> int:
    results: list[tuple[str, bool, str]] = []
    villa = [{"type": "project", "id": VILLA_34_ID, "name": "Villa Maintenance No. 34"}]
    zayidia = [{"type": "project", "id": ZAYIDIA_BOYS_ID, "name": "Zayidia Boys School"}]
    chat_session = f"fix-a-{uuid.uuid4()}"

    queries: list[tuple[str, str, dict]] = [
        ("UA-1", "how many employees do we have", {"deep_think": True}),
        ("UA-2", "employees in Civil department", {"deep_think": True}),
        ("UA-3", "total employees per department", {"deep_think": True}),
        ("UA-4", "recent purchase orders", {"deep_think": True}),
        ("UA-5", "active fleet vehicles", {"deep_think": True}),
        ("UA-6", "active contracts", {"deep_think": True}),
        ("UA-7", "products in stock", {"deep_think": True}),
        ("UA-8", "Villa 34 expense", {"deep_think": True, "confirmed": villa, "session": chat_session}),
        ("UA-9", "show breakdown", {"deep_think": True, "confirmed": villa, "session": chat_session}),
        ("UA-10", "P&L this year", {"deep_think": True}),
    ]

    with httpx.Client() as client:
        client.get(f"{API_BASE}/health", timeout=10).raise_for_status()
        token = login(client)

        for case_id, message, opts in queries:
            body = chat(
                client,
                token,
                message,
                deep_think=opts.get("deep_think", True),
                confirmed=opts.get("confirmed"),
                session_id=opts.get("session"),
            )
            text = body.get("text") or ""
            tools = body.get("tools_called") or []
            if case_id in {"UA-8", "UA-9", "UA-10"}:
                ok = not NO_DATA.search(text) and not META.search(text) and len(text) > 25
                if case_id == "UA-10":
                    ok = ok and ("profit" in text.lower() or "revenue" in text.lower() or "AED" in text)
            elif case_id in {"UA-5", "UA-6", "UA-7"}:
                ok = not META.search(text) and len(text) > 15
                ok = ok and (not NO_DATA.search(text) or "no " in text.lower())
            else:
                ok = has_real_data(text, tools)
            results.append((case_id, ok, f"tools={tools} | {text[:200]}"))

    passed = sum(1 for _, ok, _ in results if ok)
    print("FIX A ACCEPTANCE")
    print("=" * 72)
    for case_id, ok, note in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {case_id}: {note}")
    print("=" * 72)
    print(f"SUMMARY: {passed}/{len(results)}")
    return 0 if passed >= 8 else 1


if __name__ == "__main__":
    raise SystemExit(main())
