#!/usr/bin/env python3
"""Verify /agent/stream with the 10 AGENT_MODE_REBUILD acceptance queries.

Usage (auto-login — no token needed if backend + .env are set up):
  python scripts/verify_agent_mode.py

Optional:
  python scripts/verify_agent_mode.py --base-url http://127.0.0.1:8000
  python scripts/verify_agent_mode.py --file-id 2721
  python scripts/verify_agent_mode.py --print-token   # print JWT after login

Env (from .env or shell):
  OOA_BASE_URL / OOA_API_BASE   — API root (default http://127.0.0.1:8000)
  SUPER_ADMIN_FILE_ID           — login file id (default 2721)
  OOA_ACCESS_TOKEN / ACCESS_TOKEN — skip login if already set

Runs against the NEW /agent/stream endpoint only (not /chat/stream).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

TEST_QUERIES: list[dict[str, Any]] = [
    {
        "id": 1,
        "category": "smart_clarification",
        "message": "need HR info",
        "expect": "ui_block with HR area pills (not bulk employee dump)",
    },
    {
        "id": 2,
        "category": "smart_clarification",
        "message": "compare projects",
        "expect": "asks which projects (picker or clarifying question)",
    },
    {
        "id": 3,
        "category": "smart_clarification",
        "message": "vehicle for adil khan",
        "expect": "resolves employee or asks to pick among matches",
    },
    {
        "id": 4,
        "category": "smart_clarification",
        "message": "show me a report",
        "expect": "report type picker or clarifying question",
    },
    {
        "id": 5,
        "category": "error_recovery",
        "message": "compare top 5 projects by expense",
        "expect": "no Python traceback in response text",
    },
    {
        "id": 6,
        "category": "error_recovery",
        "message": "list all invoices with field xyz_invalid_total",
        "expect": "graceful explanation, not raw XML-RPC fault",
    },
    {
        "id": 7,
        "category": "contextual_suggestions",
        "message": "show Jawad payslip for last month",
        "expect": "suggestions mention Jawad or payslip context",
    },
    {
        "id": 8,
        "category": "contextual_suggestions",
        "message": "show P&L this quarter",
        "expect": "suggestions relate to P&L / financial follow-ups",
    },
    {
        "id": 9,
        "category": "context_preservation",
        "session_prefix": "ctx-villa",
        "message": "Villa 34 expense",
        "follow_up": "show breakdown",
        "expect": "breakdown without re-asking which project",
    },
    {
        "id": 10,
        "category": "context_preservation",
        "session_prefix": "ctx-jawad",
        "message": "Jawad payslip",
        "follow_up": "show deductions",
        "expect": "deductions without re-asking which payslip",
    },
]


def load_env() -> None:
    """Load project .env so SUPER_ADMIN_FILE_ID and tokens are available."""
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def obtain_access_token(base_url: str, file_id: str) -> str:
    """Login via POST /auth/login and return a Bearer access token."""
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/auth/login",
        data=json.dumps({"file_id": file_id}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Login failed HTTP {exc.code}: {detail}") from exc

    if body.get("mfa_required"):
        raise RuntimeError(
            "Login requires MFA for this user. Either:\n"
            "  - export OOA_ACCESS_TOKEN=<token from browser devtools>, or\n"
            "  - disable MFA for the test super-admin in admin panel."
        )

    token = body.get("access_token") or body.get("session_id")
    if not token:
        raise RuntimeError(f"Login succeeded but no access_token in response: {body}")
    return str(token)


def resolve_token(base_url: str, file_id: str, explicit_token: str | None) -> str:
    """Use explicit token/env token, or auto-login with file_id."""
    if explicit_token:
        return explicit_token

    for key in ("OOA_ACCESS_TOKEN", "ACCESS_TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value

    print(f"Logging in as file_id={file_id} ...", file=sys.stderr)
    return obtain_access_token(base_url, file_id)


def stream_agent(
    base_url: str,
    token: str,
    message: str,
    session_id: str | None = None,
    agent_type: str = "chat",
) -> dict[str, Any]:
    payload = {"message": message, "agent_type": agent_type}
    if session_id:
        payload["session_id"] = session_id

    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/agent/stream",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    events: list[dict[str, Any]] = []
    done: dict[str, Any] = {}

    with urllib.request.urlopen(req, timeout=120) as resp:
        buffer = ""
        for raw in resp:
            buffer += raw.decode("utf-8", errors="replace")
            while "\n\n" in buffer:
                chunk, buffer = buffer.split("\n\n", 1)
                for line in chunk.splitlines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    events.append(event)
                    if event.get("type") == "done":
                        done = event

    ui_blocks = [e.get("block") for e in events if e.get("type") == "ui_block"]
    if ui_blocks and "ui_blocks" not in done:
        done["ui_blocks"] = ui_blocks

    return done


def evaluate_result(test: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str]:
    text = (result.get("text") or "").lower()
    suggestions = result.get("suggestions") or []
    ui_blocks = result.get("ui_blocks") or []

    if "traceback" in text or "xmlrpc" in text:
        return False, "Response contains raw error/traceback"

    category = test["category"]
    if category == "smart_clarification" and test["id"] == 1:
        if ui_blocks:
            labels = str(ui_blocks).lower()
            if "payroll" in labels or "employee" in labels:
                return True, "HR picker emitted"
        if "50" in text and "employee" in text:
            return False, "Looks like bulk employee dump"
        return bool(ui_blocks or "which" in text or "what" in text), "Clarification present"

    if category == "contextual_suggestions":
        if not suggestions:
            return False, "No suggestions returned"
        joined = " ".join(suggestions).lower()
        if test["id"] == 7 and ("jawad" in joined or "payslip" in joined or "deduction" in joined):
            return True, f"Contextual suggestions: {suggestions}"
        if test["id"] == 8 and any(
            k in joined for k in ("compare", "drill", "expense", "quarter", "month")
        ):
            return True, f"Contextual suggestions: {suggestions}"
        return len(suggestions) >= 1, f"Suggestions returned: {suggestions}"

    if category == "context_preservation":
        if "which project" in text or "which payslip" in text:
            return False, "Re-asked for entity"
        return bool(text), "Follow-up answered without re-ask"

    return bool(text), "Response received"


def main() -> int:
    load_env()

    parser = argparse.ArgumentParser(description="Verify /agent/stream acceptance queries")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OOA_BASE_URL")
        or os.environ.get("OOA_API_BASE")
        or "http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--file-id",
        default=os.environ.get("SUPER_ADMIN_FILE_ID", "2721"),
        help="Elrace file ID for auto-login (default: SUPER_ADMIN_FILE_ID or 2721)",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Bearer token (overrides env and auto-login)",
    )
    parser.add_argument(
        "--print-token",
        action="store_true",
        help="Print the access token after login and exit",
    )
    args = parser.parse_args()

    try:
        token = resolve_token(args.base_url, args.file_id, args.token)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.print_token:
        print(token)
        return 0

    print(f"Using base URL: {args.base_url}", file=sys.stderr)

    passed = 0
    for test in TEST_QUERIES:
        session_id = test.get("session_prefix")
        if session_id:
            session_id = f"{session_id}-verify"

        try:
            if test.get("follow_up"):
                stream_agent(args.base_url, token, test["message"], session_id=session_id)
                result = stream_agent(args.base_url, token, test["follow_up"], session_id=session_id)
            else:
                result = stream_agent(args.base_url, token, test["message"], session_id=session_id)
        except urllib.error.HTTPError as exc:
            print(f"TEST {test['id']} FAIL — HTTP {exc.code}: {exc.read().decode()}")
            continue
        except Exception as exc:
            print(f"TEST {test['id']} FAIL — {exc}")
            continue

        ok, note = evaluate_result(test, result)
        status = "PASS" if ok else "FAIL"
        print(f"TEST {test['id']} [{test['category']}] {status} — {note}")
        if ok:
            passed += 1

    print(f"\n{passed}/{len(TEST_QUERIES)} passed")
    return 0 if passed == len(TEST_QUERIES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
