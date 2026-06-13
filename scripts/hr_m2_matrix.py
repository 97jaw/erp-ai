#!/usr/bin/env python3
"""Phase M2.2 — HR module certification matrix (30 tests + 3 regression)."""

from __future__ import annotations

import json
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
VILLA_34 = [{"type": "project", "id": 15157, "name": "Villa Maintenance No. 34"}]
SPACING_S = 5.0

FORBIDDEN = (
    "database error",
    "system error",
    "connection issue",
    "try again later",
    "odoo rejected login",
    "license limit",
    "erp user license",
)


def any_in(text: str, tokens: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(t.lower() in low for t in tokens)


def has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))


def has_arabic(text: str) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", text))


def base_ok(body: dict[str, Any]) -> bool:
    text = (body.get("text") or "").strip()
    low = text.lower()
    if not text or len(text) < 12:
        return False
    if body.get("failure_mode") == "out_of_scope":
        return False
    if any(p in low for p in FORBIDDEN):
        return False
    if "activate deep think" in low and not body.get("tools_called"):
        return False
    return True


def chat(
    client: httpx.Client,
    token: str,
    message: str,
    *,
    session_id: str | None = None,
    deep_think: bool = True,
    confirmed: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
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


def pause() -> None:
    time.sleep(SPACING_S)


def snippet(text: str, n: int = 180) -> str:
    return " ".join((text or "").split())[:n]


def run_case(
    results: list[dict[str, Any]],
    case_id: str,
    category: str,
    message: str,
    judge: Callable[[dict[str, Any]], bool],
    client: httpx.Client,
    token: str,
    *,
    session_id: str | None = None,
    confirmed: list[dict[str, Any]] | None = None,
    deep_think: bool = True,
) -> dict[str, Any]:
    body = chat(
        client,
        token,
        message,
        session_id=session_id,
        deep_think=deep_think,
        confirmed=confirmed,
    )
    text = body.get("text") or ""
    tools = body.get("tools_called") or []
    ok = judge(body)
    row = {
        "id": case_id,
        "category": category,
        "message": message,
        "pass": ok,
        "tools": tools,
        "failure_mode": body.get("failure_mode"),
        "snippet": snippet(text),
    }
    results.append(row)
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {case_id}: tools={tools} | {snippet(text, 140)}")
    pause()
    return body


def fetch_sample_employee(client: httpx.Client, token: str) -> str:
    body = chat(
        client,
        token,
        "show emp_id and full name for employee AABID SADIK",
        deep_think=True,
    )
    text = body.get("text") or ""
    if "aabid" in text.lower() or "sadik" in text.lower():
        return "AABID SADIK"
    match = re.search(r"([A-Z][A-Z\s]{2,40})", text)
    if match:
        name = match.group(1).strip()
        if name.lower() not in ("hr", "civil", "aluminum workshop", "department"):
            return name.title()
    return "AABID SADIK"


def main() -> int:
    results: list[dict[str, Any]] = []
    reg_results: list[dict[str, Any]] = []

    with httpx.Client() as client:
        wait_for_health(client)
        token = api_login(client)

        sample_employee = fetch_sample_employee(client, token)
        print(f"Sample employee for dynamic tests: {sample_employee}")
        pause()

        # --- Category A ---
        run_case(
            results,
            "HR-A1",
            "A",
            "how many employees do we have",
            lambda b: base_ok(b)
            and (has_number(b.get("text") or "") or any_in(b.get("text") or "", ("employee", "employees"))),
            client,
            token,
        )
        run_case(
            results,
            "HR-A2",
            "A",
            "how many labor vs staff",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("labor", "staff", "worker", "is_labor", "labour"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-A3",
            "A",
            "employees in Civil department",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("civil", "employee", "department"))
            and (has_number(b.get("text") or "") or "found" in (b.get("text") or "").lower()),
            client,
            token,
        )
        run_case(
            results,
            "HR-A4",
            "A",
            f"show me {sample_employee} details",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("employee", "department", "job", "emp_id", sample_employee.split()[0].lower()),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-A5",
            "A",
            "employees who joined this year",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("join", "joined", "2026", "new hire", "employee"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-A6",
            "A",
            "managers in the company",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("manager", "management", "parent_id", "head", "employee", "found"))
            and "project manager" not in (b.get("text") or "").lower(),
            client,
            token,
        )
        run_case(
            results,
            "HR-A7",
            "A",
            "foremen list",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("foreman", "forman", "coach", "supervisor", "labor", "job", "found", "employee"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-A8",
            "A",
            "كم عدد الموظفين",
            lambda b: base_ok(b)
            and (has_arabic(b.get("text") or "") or has_number(b.get("text") or ""))
            and (
                has_arabic(b.get("text") or "")
                or any_in(b.get("text") or "", ("employee", "employees", "موظف", "عدد"))
            ),
            client,
            token,
        )

        # --- Category B ---
        run_case(
            results,
            "HR-B1",
            "B",
            "list all departments",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("department", "hr.department", "civil", "electrical")),
            client,
            token,
        )
        run_case(
            results,
            "HR-B2",
            "B",
            "employees per department",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("department", "employee", "per"))
            and has_number(b.get("text") or ""),
            client,
            token,
        )
        run_case(
            results,
            "HR-B3",
            "B",
            "biggest department",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("department", "largest", "biggest", "most", "civil"))
            and has_number(b.get("text") or ""),
            client,
            token,
        )
        run_case(
            results,
            "HR-B4",
            "B",
            "Civil department head",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("civil", "head", "manager", "department")),
            client,
            token,
        )
        run_case(
            results,
            "HR-B5",
            "B",
            "branches we have",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("branch", "branches", "office", "location", "al hewar", "al ain", "elrace", "auh"),
            ),
            client,
            token,
        )

        # --- Category C ---
        run_case(
            results,
            "HR-C1",
            "C",
            "pending leave requests",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("leave", "request", "pending", "draft", "submitted", "annual", "no pending"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-C2",
            "C",
            "approved resignations this month",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("resign", "termination", "approve", "request", "this month", "no "),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-C3",
            "C",
            "transfers this year",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("transfer", "request", "2026", "this year", "no ")),
            client,
            token,
        )
        run_case(
            results,
            "HR-C4",
            "C",
            "loan requests",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("loan", "advance", "request", "salary", "no ")),
            client,
            token,
        )
        run_case(
            results,
            "HR-C5",
            "C",
            "who has unresolved requests",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("request", "pending", "unresolved", "approve", "employee", "no "),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-C6",
            "C",
            "promotion requests last quarter",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("promotion", "request", "quarter", "approve", "no "),
            ),
            client,
            token,
        )

        # --- Category D ---
        run_case(
            results,
            "HR-D1",
            "D",
            "today's attendance count",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("attendance", "present", "today", "count", "employee", "no data", "no attendance"))
            and (has_number(b.get("text") or "") or "no data" in (b.get("text") or "").lower() or "no attendance" in (b.get("text") or "").lower()),
            client,
            token,
        )
        run_case(
            results,
            "HR-D2",
            "D",
            "who was absent yesterday",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("absent", "absence", "yesterday", "attendance", "no absent", "no employee"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-D3",
            "D",
            f"{sample_employee} attendance this month",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("attendance", "present", "hours", "month", sample_employee.split()[0].lower()),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-D4",
            "D",
            "total work hours by department this month",
            lambda b: base_ok(b)
            and any_in(b.get("text") or "", ("hour", "work", "department", "attendance", "present"))
            and has_number(b.get("text") or ""),
            client,
            token,
        )
        run_case(
            results,
            "HR-D5",
            "D",
            "employees on leave today",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("leave", "annual", "sick", "today", "attendance", "no employee", "on leave"),
            ),
            client,
            token,
        )

        # --- Category E ---
        run_case(
            results,
            "HR-E1",
            "E",
            "visas expiring in 30 days",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("visa", "expir", "expire", "30", "day", "no employee", "employee", "found"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-E2",
            "E",
            "expired labour cards",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("labour", "labor", "card", "expir", "expire", "no employee", "employee", "found"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-E3",
            "E",
            "employees missing documents",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("missing", "document", "required", "compliance", "no employee", "employee", "found"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-E4",
            "E",
            "passports expiring this year",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("passport", "expir", "expire", "2026", "year", "no employee"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-E5",
            "E",
            "EID renewal needed",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("eid", "emirates", "identification", "renew", "expir", "visa", "no employee", "employee", "found"),
            ),
            client,
            token,
        )

        # --- Category F ---
        run_case(
            results,
            "HR-F1",
            "F",
            "who works on Villa 34",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("villa", "employee", "project", "staff", "labor", "work"),
            ),
            client,
            token,
            confirmed=VILLA_34,
        )
        run_case(
            results,
            "HR-F2",
            "F",
            f"{sample_employee}'s assigned vehicle",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("vehicle", "fleet", "car", "plate", "assign", "no vehicle", "not assigned"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-F3",
            "F",
            f"{sample_employee}'s project history",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("project", "assignment", "transfer", "history", "villa", "no project", "employee", "found"),
            ),
            client,
            token,
        )
        run_case(
            results,
            "HR-F4",
            "F",
            "department head count by project",
            lambda b: base_ok(b)
            and any_in(
                b.get("text") or "",
                ("project", "department", "head count", "employee", "staff", "allocation"),
            ),
            client,
            token,
        )

        # --- Regression (same session R1→R2) ---
        print("\n=== REGRESSION ===")
        reg_session = f"m2-reg-{uuid.uuid4()}"
        r1 = chat(
            client,
            token,
            "Villa 34 expense",
            session_id=reg_session,
            deep_think=True,
            confirmed=VILLA_34,
        )
        r1_text = r1.get("text") or ""
        r1_tools = r1.get("tools_called") or []
        r1_ok = base_ok(r1) and any_in(
            r1_text,
            ("expense", "aed", "spent", "cost", "villa", "budget"),
        ) and ("get_project_expense" in r1_tools or has_number(r1_text))
        reg_results.append(
            {
                "id": "R1",
                "pass": r1_ok,
                "tools": r1_tools,
                "snippet": snippet(r1_text),
            }
        )
        print(f"[{'PASS' if r1_ok else 'FAIL'}] R1: tools={r1_tools} | {snippet(r1_text, 140)}")
        pause()

        r2 = chat(
            client,
            token,
            "show breakdown",
            session_id=reg_session,
            deep_think=True,
            confirmed=VILLA_34,
        )
        r2_text = r2.get("text") or ""
        r2_tools = r2.get("tools_called") or []
        r2_ok = base_ok(r2) and any_in(
            r2_text,
            ("breakdown", "account", "gl", "expense", "category", "material", "trade"),
        )
        reg_results.append(
            {
                "id": "R2",
                "pass": r2_ok,
                "tools": r2_tools,
                "snippet": snippet(r2_text),
            }
        )
        print(f"[{'PASS' if r2_ok else 'FAIL'}] R2: tools={r2_tools} | {snippet(r2_text, 140)}")
        pause()

        r3 = chat(
            client,
            token,
            "P&L this year",
            session_id=str(uuid.uuid4()),
            deep_think=True,
        )
        r3_text = r3.get("text") or ""
        r3_tools = r3.get("tools_called") or []
        r3_ok = base_ok(r3) and (
            "get_financial_report" in r3_tools
            or any_in(r3_text, ("profit", "loss", "revenue", "income", "p&l", "net"))
        ) and has_number(r3_text)
        reg_results.append(
            {
                "id": "R3",
                "pass": r3_ok,
                "tools": r3_tools,
                "snippet": snippet(r3_text),
            }
        )
        print(f"[{'PASS' if r3_ok else 'FAIL'}] R3: tools={r3_tools} | {snippet(r3_text, 140)}")

    hr_pass = sum(1 for r in results if r["pass"])
    hr_total = len(results)
    reg_pass = sum(1 for r in reg_results if r["pass"])
    summary = {
        "hr_pass": hr_pass,
        "hr_total": hr_total,
        "hr_threshold_met": hr_pass >= 25,
        "regression_pass": reg_pass,
        "regression_total": len(reg_results),
        "regression_ok": reg_pass == len(reg_results),
        "sample_employee": sample_employee,
        "results": results,
        "regression": reg_results,
    }
    out = ROOT / "logs" / "hr_m2_matrix_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== SUMMARY ===")
    print(f"HR: {hr_pass}/{hr_total} PASS (need 25+)")
    print(f"Regression: {reg_pass}/{len(reg_results)} PASS")
    print(f"Written: {out}")
    if reg_pass < len(reg_results):
        return 2
    if hr_pass < 25:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
