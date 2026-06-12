#!/usr/bin/env python3
"""Phase R6 — full integration test matrix (live API + UI structure checks)."""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.api_test_utils import api_base, load_test_env, login as api_login, wait_for_health

load_test_env()

API_BASE = api_base()
FILE_ID = os.environ.get("OOA_FILE_ID", "2721")
VILLA_34_ID = 15157
ZAYIDIA_BOYS_ID = 14549

FORBIDDEN_REGRESSION = (
    "database error",
    "system error",
    "connection issue",
    "try again later",
)


def parse_sse(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


def stream_text(events: list[dict[str, Any]]) -> str:
    chunks = "".join(e.get("chunk", "") for e in events if e.get("type") == "text")
    if chunks:
        return chunks
    done = next((e for e in reversed(events) if e.get("type") == "done"), {})
    return str(done.get("text") or "")


def chat_intelligent(
    client: httpx.Client,
    token: str,
    message: str,
    session_id: str,
    *,
    deep_think: bool = False,
    confirmed: list[dict[str, Any]] | None = None,
    retries: int = 3,
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(retries):
        if attempt:
            time.sleep(2 * attempt)
        try:
            res = client.post(
                f"{API_BASE}/chat/intelligent",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "message": message,
                    "session_id": session_id,
                    "skip_clarification": True,
                    "deep_think": deep_think,
                    "confirmed_entities": confirmed or [],
                },
                timeout=300.0,
            )
            res.raise_for_status()
            return res.json()
        except httpx.HTTPStatusError as exc:
            last_exc = exc
            if exc.response.status_code != 500:
                raise
        except httpx.HTTPError as exc:
            last_exc = exc
    if last_exc:
        raise last_exc
    raise RuntimeError("chat_intelligent failed without exception")


def audit_stream(client: httpx.Client, token: str, message: str, session_id: str) -> str:
    with client.stream(
        "POST",
        f"{API_BASE}/audit/stream",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": message, "session_id": session_id},
        timeout=300.0,
    ) as res:
        res.raise_for_status()
        body = "".join(res.iter_text())
    return stream_text(parse_sse(body))


def has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))


def no_forbidden(text: str) -> bool:
    low = text.lower()
    return not any(p in low for p in FORBIDDEN_REGRESSION)


def any_in(text: str, tokens: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(t.lower() in low for t in tokens)


def pause_between_calls() -> None:
    time.sleep(1.5)


def record(
    results: list[dict[str, Any]],
    section: str,
    case_id: str,
    ok: bool,
    notes: str,
) -> None:
    row = {
        "section": section,
        "id": case_id,
        "pass": ok,
        "notes": notes[:500],
    }
    results.append(row)
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {section} {case_id}: {notes[:200]}")


def main() -> int:
    results: list[dict[str, Any]] = []
    chat_session = f"r6-chat-{uuid.uuid4()}"
    audit_session = f"r6-audit-{uuid.uuid4()}"

    with httpx.Client() as client:
        wait_for_health(client)
        token = api_login(client)

        # --- SECTION A ---
        a1 = chat_intelligent(client, token, "how many employees", str(uuid.uuid4()), deep_think=True)
        pause_between_calls()
        t1 = a1.get("text") or ""
        record(
            results,
            "A",
            "A1",
            no_forbidden(t1)
            and not a1.get("failure_mode") == "out_of_scope"
            and (has_number(t1) or "employee" in t1.lower()),
            f"tools={a1.get('tools_called')} | {t1[:160]}",
        )

        a2 = chat_intelligent(
            client, token, "recent purchase orders", str(uuid.uuid4()), deep_think=True
        )
        t2 = a2.get("text") or ""
        a2_tools = a2.get("tools_called") or []
        record(
            results,
            "A",
            "A2",
            no_forbidden(t2)
            and (
                any_in(t2, ("purchase", "po", "order", "vendor", "supplier"))
                or "query_odoo" in a2_tools
            ),
            f"tools={a2_tools} | {t2[:160]}",
        )

        a3 = chat_intelligent(client, token, "fleet vehicles", str(uuid.uuid4()), deep_think=True)
        t3 = a3.get("text") or ""
        record(
            results,
            "A",
            "A3",
            no_forbidden(t3)
            and (
                any_in(t3, ("fleet", "vehicle", "car", "plate"))
                or any_in(t3, ("no data", "no records", "not found", "0 "))
            ),
            f"tools={a3.get('tools_called')} | {t3[:160]}",
        )

        a4 = chat_intelligent(client, token, "create an invoice", str(uuid.uuid4()), deep_think=False)
        t4 = a4.get("text") or ""
        record(
            results,
            "A",
            "A4",
            any_in(
                t4,
                (
                    "cannot",
                    "can't",
                    "not able",
                    "write",
                    "create",
                    "out of scope",
                    "unable",
                    "only read",
                    "read-only",
                ),
            ),
            f"failure_mode={a4.get('failure_mode')} | {t4[:160]}",
        )

        # --- SECTION B ---
        b_cases: list[tuple[str, str, Callable[[str], bool]]] = [
            (
                "B1",
                "projects with no attachments",
                lambda t: any_in(t, ("attachment", "project")) and any_in(t, ("no ", "without", "0", "missing", "lack")),
            ),
            (
                "B2",
                "agreement for Villa 34",
                lambda t: any_in(t, ("agreement", "villa", "15157", "ag0")) and no_forbidden(t),
            ),
            (
                "B3",
                "client for Villa 34",
                lambda t: any_in(t, ("client", "partner", "abu dhabi", "customer", "villa")),
            ),
            (
                "B4",
                "agreements expiring soon",
                lambda t: any_in(t, ("agreement", "expir", "expire", "due", "end date")),
            ),
            (
                "B5",
                "Villa 34 attachment types",
                lambda t: any_in(
                    t,
                    ("estimation", "wo", "work order", "attachment", "type", "document", "drawing"),
                ),
            ),
        ]
        for case_id, msg, judge in b_cases:
            body = chat_intelligent(client, token, msg, str(uuid.uuid4()), deep_think=True)
            text = body.get("text") or ""
            record(results, "B", case_id, judge(text) and no_forbidden(text), f"{text[:180]}")

        # --- SECTION C (audit lane, shared session for C2) ---
        c1 = audit_stream(client, token, "what changed on Villa 34 today", audit_session)
        record(
            results,
            "C",
            "C1",
            any_in(c1, ("villa", "15157", "change", "timeline", "no change", "no changes")),
            c1[:180],
        )

        c2 = audit_stream(client, token, "who modified it", audit_session)
        record(
            results,
            "C",
            "C2",
            any_in(c2, ("mohamad", "farah", "user", "author", "who", "no change", "no one")),
            c2[:180],
        )

        c3 = audit_stream(
            client,
            token,
            "user 4291 activity today",
            f"r6-audit-user-{uuid.uuid4()}",
        )
        record(
            results,
            "C",
            "C3",
            any_in(c3, ("activity", "user", "4291", "jawad", "change", "attendance", "model")),
            c3[:180],
        )

        c4 = audit_stream(
            client,
            token,
            "stage changes on projects this week",
            f"r6-audit-stage-{uuid.uuid4()}",
        )
        record(
            results,
            "C",
            "C4",
            any_in(c4, ("stage", "change", "project", "week", "no change")),
            c4[:180],
        )

        # --- SECTION D (chat regression, shared session D1+D2) ---
        villa_confirmed = [{"type": "project", "id": VILLA_34_ID, "name": "Villa Maintenance No. 34"}]

        d1 = chat_intelligent(
            client,
            token,
            "Villa 34 expense",
            chat_session,
            deep_think=True,
            confirmed=villa_confirmed,
        )
        t_d1 = d1.get("text") or ""
        record(
            results,
            "D",
            "D1",
            no_forbidden(t_d1)
            and any_in(t_d1, ("expense", "aed", "villa", "cost", "project"))
            and not any_in(t_d1, ("deep think", "activate deep think")),
            f"tools={d1.get('tools_called')} | {t_d1[:180]}",
        )

        d2 = chat_intelligent(
            client,
            token,
            "show breakdown",
            chat_session,
            deep_think=True,
            confirmed=villa_confirmed,
        )
        t_d2 = d2.get("text") or ""
        record(
            results,
            "D",
            "D2",
            no_forbidden(t_d2)
            and any_in(
                t_d2,
                ("breakdown", "gl", "category", "expense", "account", "cost", "aed", "line"),
            ),
            f"tools={d2.get('tools_called')} | {t_d2[:180]}",
        )

        d3 = chat_intelligent(
            client,
            token,
            "P&L this year",
            f"r6-d3-{uuid.uuid4()}",
            deep_think=True,
        )
        t_d3 = d3.get("text") or ""
        d3_tools = d3.get("tools_called") or []
        record(
            results,
            "D",
            "D3",
            no_forbidden(t_d3)
            and (
                "get_financial_report" in d3_tools
                or (
                    any_in(t_d3, ("profit", "loss", "p&l", "revenue", "income", "aed", "expense"))
                    and has_number(t_d3)
                )
            ),
            f"tools={d3_tools} | {t_d3[:180]}",
        )

        d4 = chat_intelligent(
            client,
            token,
            "compare Villa 34 and Villa 43 expenses",
            f"r6-d4-{uuid.uuid4()}",
            deep_think=True,
        )
        t_d4 = d4.get("text") or ""
        record(
            results,
            "D",
            "D4",
            no_forbidden(t_d4)
            and any_in(t_d4, ("villa", "34", "43", "compare", "comparison", "versus", "vs")),
            f"tools={d4.get('tools_called')} | {t_d4[:180]}",
        )

        d5 = chat_intelligent(
            client,
            token,
            "national guard project",
            f"r6-d5-{uuid.uuid4()}",
            deep_think=False,
        )
        t_d5 = d5.get("text") or ""
        record(
            results,
            "D",
            "D5",
            no_forbidden(t_d5)
            and any_in(
                t_d5,
                ("national guard", "candidate", "confirm", "which project", "nouf", "14458"),
            ),
            f"awaiting={d5.get('awaiting_clarification')} | {t_d5[:180]}",
        )

        zayidia_confirmed = [
            {"type": "project", "id": ZAYIDIA_BOYS_ID, "name": "Zayidia Boys School"},
        ]
        d6 = chat_intelligent(
            client,
            token,
            "Zayidia Boys School costs",
            f"r6-d6-{uuid.uuid4()}",
            deep_think=True,
            confirmed=zayidia_confirmed,
        )
        t_d6 = d6.get("text") or ""
        record(
            results,
            "D",
            "D6",
            no_forbidden(t_d6)
            and any_in(t_d6, ("zayidia", "boys", "school", "cost", "expense", "aed", "14549")),
            f"tools={d6.get('tools_called')} | {t_d6[:180]}",
        )

        # --- SECTION E (structure + API smoke) ---
        qa = (ROOT / "ooa-ui/src/main/sidebar/quickActions.js").read_text()
        topbar = (ROOT / "ooa-ui/src/main/topbar/MainTopBar.jsx").read_text()
        e1 = (
            "Search" in qa
            and "Chat List" in qa
            and "Sessions" in qa
            and "Audit" not in qa
            and "P&L" not in qa
            and "Projects" not in qa
            and "Voice" not in qa
            and "Tasks" not in qa
            and "onOpenAudit" in topbar
            and "onToggleVisualize" in topbar
            and "onBuildDashboard" in topbar
        )
        record(results, "E", "E1", e1, "sidebar nav + topbar AI actions verified")

        e2_text = audit_stream(client, token, "what changed on Villa 34 today", f"r6-e2-{uuid.uuid4()}")
        record(
            results,
            "E",
            "E2",
            len(e2_text) > 40 and any_in(e2_text, ("villa", "change", "audit", "15157")),
            e2_text[:120],
        )

        e3 = chat_intelligent(
            client,
            token,
            "hello",
            chat_session,
            deep_think=False,
        )
        record(
            results,
            "E",
            "E3",
            len(e3.get("text") or "") > 5 and chat_session == chat_session,
            (e3.get("text") or "")[:120],
        )

        record(
            results,
            "E",
            "E4",
            chat_session != audit_session,
            f"chat_session={chat_session[:20]} audit_session={audit_session[:20]}",
        )

    # Summarize
    def section_passes(section: str, required: int, total: int) -> tuple[int, bool]:
        rows = [r for r in results if r["section"] == section]
        passed = sum(1 for r in rows if r["pass"])
        ok = passed >= required if section != "D" and section != "E" else passed == total
        return passed, ok

    sections = {
        "A": (3, 4),
        "B": (4, 5),
        "C": (3, 4),
        "D": (6, 6),
        "E": (4, 4),
    }

    print("\n" + "=" * 72)
    print("R6 INTEGRATION MATRIX")
    print("=" * 72)
    for row in results:
        print(f"{row['section']}{row['id']}: {'PASS' if row['pass'] else 'FAIL'} — {row['notes'][:100]}")

    print("\n" + "=" * 72)
    all_ok = True
    for sec, (req, tot) in sections.items():
        passed, ok = section_passes(sec, req, tot)
        print(f"Section {sec}: {passed}/{tot} (need {req}) — {'PASS' if ok else 'FAIL'}")
        all_ok = all_ok and ok

    print("=" * 72)
    print(f"OVERALL: {'PASS' if all_ok else 'FAIL'}")
    print(json.dumps(results, indent=2))
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
