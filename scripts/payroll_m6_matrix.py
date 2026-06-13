#!/usr/bin/env python3
"""Phase M6.2 — Payroll module certification matrix (25 tests + perm + regression)."""

from __future__ import annotations

import asyncio
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
LATEST_BATCH = "June 2026 - Elrace - Al Ain - Staff"

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


def extract_aed(text: str) -> float | None:
    match = re.search(r"(?:AED|aed)\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text or "")
    if not match:
        match = re.search(r"([0-9][0-9,]*(?:\.[0-9]+)?)\s*(?:AED|aed)", text or "")
    if not match:
        return None
    return float(match.group(1).replace(",", ""))


def base_ok(body: dict[str, Any]) -> bool:
    text = (body.get("text") or "").strip()
    low = text.lower()
    if not text or len(text) < 10:
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
    confirmed: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body = chat(client, token, message, confirmed=confirmed)
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


def odoo_villa_labor_cost_this_month() -> float | None:
    """Ground-truth aggregate for PR-E1 cross-check."""
    from gateway.core.payroll_query_routing import _allocation_month_year
    from gateway.core.intent_analyzer import Intent
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter
    from gateway.tools.universal_odoo import build_universal_context, execute_aggregate_odoo

    intent = Intent(
        primary_action="fetch_data",
        subject_area="payroll",
        specific_intent="labor cost for Villa Maintenance No. 34 this month",
        entities=[],
        implicit_requirements=[],
        ambiguities=[],
        expected_output="number",
        urgency="normal",
        estimated_complexity="simple",
        requires_clarification=False,
        clarification_question=None,
        out_of_scope=False,
        out_of_scope_reason=None,
    )
    month, year, _extra = _allocation_month_year(
        "labor cost for Villa Maintenance No. 34 this month",
        intent,
        None,
    )

    async def _run() -> float | None:
        adapter = get_shared_odoo_adapter()
        ctx = build_universal_context()
        result = await execute_aggregate_odoo(
            adapter,
            {
                "model": "hr.payslip.cost.allocation",
                "domain": [
                    ["project_id", "=", 15157],
                    ["month", "=", month],
                    ["year", "=", year],
                ],
                "group_by": ["project_id"],
                "aggregates": ["amount:sum"],
                "limit": 10,
            },
            ctx,
        )
        groups = result.get("groups") or []
        if not groups:
            return None
        amount = groups[0].get("amount")
        return float(amount) if amount is not None else None

    return asyncio.run(_run())


def run_permission_test() -> dict[str, Any]:
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter
    from gateway.tools.search_entities import minimal_search_context
    from gateway.tools.universal_odoo import execute_query_odoo

    async def _run() -> dict[str, Any]:
        adapter = get_shared_odoo_adapter()
        ctx = minimal_search_context()
        ctx.user.level = 50
        result = await execute_query_odoo(
            adapter,
            {
                "model": "hr.payslip",
                "domain": [],
                "fields": ["name", "net_salary", "employee_id"],
                "limit": 3,
            },
            ctx,
        )
        records = result.get("records") or []
        redacted = any(
            record.get("net_salary") == "***restricted***" for record in records if isinstance(record, dict)
        )
        return {
            "id": "PR-PERM",
            "pass": result.get("status") == "success" and redacted,
            "status": result.get("status"),
            "sample": records[:1],
        }

    return asyncio.run(_run())


def main() -> int:
    from gateway.tool_cache import ToolResultCache

    ToolResultCache.clear()

    results: list[dict[str, Any]] = []
    reg_results: list[dict[str, Any]] = []
    sample_employee = "AABID SADIK"

    with httpx.Client() as client:
        wait_for_health(client)
        token = api_login(client)
        print(f"Sample employee: {sample_employee}")
        print(f"Latest batch: {LATEST_BATCH}")
        pause()

        # Category A
        run_case(
            results,
            "PR-A1",
            "A",
            f"{sample_employee} payslips",
            lambda b: base_ok(b)
            and "query_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("payslip", "salary slip", "slip", sample_employee.split()[0].lower(), "found")),
            client,
            token,
        )
        run_case(
            results,
            "PR-A2",
            "A",
            f"{sample_employee}'s payslip last month",
            lambda b: base_ok(b)
            and "query_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("payslip", "salary", "slip", "last month", sample_employee.split()[0].lower(), "found", "no data")),
            client,
            token,
        )
        run_case(
            results,
            "PR-A3",
            "A",
            f"payslips for {LATEST_BATCH}",
            lambda b: base_ok(b)
            and "query_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("payslip", "salary", "slip", "june", "found", "no data")),
            client,
            token,
        )
        run_case(
            results,
            "PR-A4",
            "A",
            "draft payslips count",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and has_number(b.get("text") or "")
            and any_in(b.get("text") or "", ("draft", "payslip", "count", "employee")),
            client,
            token,
        )
        run_case(
            results,
            "PR-A5",
            "A",
            "finalized payslips this month",
            lambda b: base_ok(b)
            and "query_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("payslip", "finance", "paid", "verify", "final", "found", "no data")),
            client,
            token,
        )

        # Category B
        run_case(
            results,
            "PR-B1",
            "B",
            "total payroll cost last month",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and has_number(b.get("text") or "")
            and any_in(b.get("text") or "", ("payroll", "salary", "net", "aed", "total", "cost")),
            client,
            token,
        )
        run_case(
            results,
            "PR-B2",
            "B",
            "payroll by department",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("department", "payroll", "salary", "group", "employee")),
            client,
            token,
        )
        run_case(
            results,
            "PR-B3",
            "B",
            "labor vs staff payroll cost",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("labor", "staff", "payroll", "salary", "snapshot")),
            client,
            token,
        )
        run_case(
            results,
            "PR-B4",
            "B",
            "overtime cost this month",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("overtime", "over time", "ot", "cost", "hour", "no data", "0")),
            client,
            token,
        )
        run_case(
            results,
            "PR-B5",
            "B",
            "sick leave cost this year",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("sick", "leave", "cost", "paid", "unpaid", "no data")),
            client,
            token,
        )

        # Category C
        run_case(
            results,
            "PR-C1",
            "C",
            "total fines this month",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("fine", "deduction", "no data", "0", "aed")),
            client,
            token,
        )
        run_case(
            results,
            "PR-C2",
            "C",
            "who has advances pending",
            lambda b: base_ok(b)
            and "query_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("advance", "pending", "employee", "payslip", "no data", "no employee")),
            client,
            token,
        )
        run_case(
            results,
            "PR-C3",
            "C",
            "highest deductions this month",
            lambda b: base_ok(b)
            and "query_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("deduction", "fine", "advance", "employee", "payslip", "no data")),
            client,
            token,
        )
        run_case(
            results,
            "PR-C4",
            "C",
            "average deductions per employee",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("deduction", "average", "avg", "employee", "no data")),
            client,
            token,
        )

        # Category D
        run_case(
            results,
            "PR-D1",
            "D",
            "total job mission hours this year",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("job mission", "jm", "hour", "mission", "no data"))
            and has_number(b.get("text") or ""),
            client,
            token,
        )
        run_case(
            results,
            "PR-D2",
            "D",
            "annual leave salary paid this year",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("annual", "leave", "salary", "paid", "amount", "no data"))
            and has_number(b.get("text") or ""),
            client,
            token,
        )
        run_case(
            results,
            "PR-D3",
            "D",
            "sick leave usage by employee",
            lambda b: base_ok(b)
            and "query_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("sick", "leave", "employee", "usage", "day", "sl_", "no data", "found")),
            client,
            token,
        )

        # Category E — flagship
        e1_body = run_case(
            results,
            "PR-E1",
            "E",
            "labor cost for Villa Maintenance No. 34 this month",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("labor", "cost", "aed", "villa", "project"))
            and has_number(b.get("text") or ""),
            client,
            token,
            confirmed=VILLA_34,
        )
        run_case(
            results,
            "PR-E2",
            "E",
            "labor cost for Villa 34 last 6 months",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("labor", "cost", "month", "villa", "project", "aed", "trend"))
            and has_number(b.get("text") or "")
            and "no data found" not in (b.get("text") or "").lower(),
            client,
            token,
            confirmed=VILLA_34,
        )
        run_case(
            results,
            "PR-E3",
            "E",
            "most expensive project by labor cost",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("project", "labor", "cost", "expensive", "top", "aed"))
            and has_number(b.get("text") or ""),
            client,
            token,
        )
        run_case(
            results,
            "PR-E4",
            "E",
            "labor cost breakdown by employee for Villa 34",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("employee", "labor", "cost", "breakdown", "villa", "project", "aed"))
            and "no data found" not in (b.get("text") or "").lower(),
            client,
            token,
            confirmed=VILLA_34,
        )
        run_case(
            results,
            "PR-E5",
            "E",
            "monthly labor cost trend for Villa 34",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("labor", "cost", "month", "trend", "villa", "project", "aed"))
            and "no data found" not in (b.get("text") or "").lower(),
            client,
            token,
            confirmed=VILLA_34,
        )
        run_case(
            results,
            "PR-E6",
            "E",
            f"{sample_employee} cost across projects this year",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("project", "cost", "employee", sample_employee.split()[0].lower(), "aed", "labor")),
            client,
            token,
        )
        run_case(
            results,
            "PR-E7",
            "E",
            "average labor cost per project",
            lambda b: base_ok(b)
            and "aggregate_odoo" in (b.get("tools_called") or [])
            and any_in(b.get("text") or "", ("average", "project", "labor", "cost", "aed", "per project")),
            client,
            token,
        )

        # Regression
        print("\n=== REGRESSION ===")
        reg_session = f"m6-reg-{uuid.uuid4()}"
        r1 = chat(client, token, "how many employees do we have", deep_think=True)
        r1_ok = base_ok(r1) and has_number(r1.get("text") or "")
        reg_results.append({"id": "R-CHAT", "pass": r1_ok, "tools": r1.get("tools_called"), "snippet": snippet(r1.get("text") or "")})
        print(f"[{'PASS' if r1_ok else 'FAIL'}] R-CHAT: tools={r1.get('tools_called')} | {snippet(r1.get('text') or '', 120)}")

    perm = run_permission_test()
    print(f"[{'PASS' if perm['pass'] else 'FAIL'}] PR-PERM: redaction sample={perm.get('sample')}")

    payroll_pass = sum(1 for row in results if row["pass"])
    e_pass = sum(1 for row in results if row["id"].startswith("PR-E") and row["pass"])
    e_total = sum(1 for row in results if row["id"].startswith("PR-E"))

    truth = odoo_villa_labor_cost_this_month()
    e1_text = e1_body.get("text") or ""
    e1_aed = extract_aed(e1_text)
    number_match = None
    if truth is not None and e1_aed is not None:
        number_match = abs(truth - e1_aed) <= max(1.0, truth * 0.01)

    summary = {
        "payroll_pass": payroll_pass,
        "payroll_total": len(results),
        "payroll_threshold_met": payroll_pass >= 20,
        "flagship_pass": e_pass,
        "flagship_total": e_total,
        "flagship_all_pass": e_pass == e_total,
        "permission_pass": perm["pass"],
        "regression_pass": sum(1 for row in reg_results if row["pass"]),
        "regression_total": len(reg_results),
        "pr_e1_odoo_truth_aed": truth,
        "pr_e1_response_aed": e1_aed,
        "pr_e1_number_match": number_match,
        "sample_employee": sample_employee,
        "latest_batch": LATEST_BATCH,
        "results": results,
        "permission": perm,
        "regression": reg_results,
    }

    out = ROOT / "logs" / "payroll_m6_matrix_results.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== SUMMARY ===")
    print(f"Payroll: {payroll_pass}/{len(results)} PASS (need 20+)")
    print(f"Flagship PR-E: {e_pass}/{e_total} PASS (need ALL)")
    print(f"PR-PERM: {'PASS' if perm['pass'] else 'FAIL'}")
    print(f"Regression: {summary['regression_pass']}/{summary['regression_total']} PASS")
    print(f"PR-E1 Odoo truth: AED {truth:,.2f}" if truth else "PR-E1 Odoo truth: (no data)")
    print(f"PR-E1 Response:    AED {e1_aed:,.2f}" if e1_aed else "PR-E1 Response: (no AED parsed)")
    print(f"PR-E1 Number match: {number_match}")
    print(f"Written: {out}")
    return 0 if payroll_pass >= 20 and e_pass == e_total and perm["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
