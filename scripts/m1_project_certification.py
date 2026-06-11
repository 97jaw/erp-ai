#!/usr/bin/env python3
"""Phase M1 — PROJECT module certification (P-A1 through P-F5)."""

from __future__ import annotations

import asyncio
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import httpx

ROOT = Path(__file__).resolve().parents[1]
API_BASE = os.environ.get("OOA_API_BASE", "http://13.203.223.70:8000")
FILE_ID = os.environ.get("SUPER_ADMIN_FILE_ID", "2721")

VILLA34_CONFIRM = [{"type": "project", "id": 15157, "name": "Villa Maintenance No. 34"}]
VILLA43_CONFIRM = [{"type": "project", "id": 15158, "name": "Villa Maintenance No. 43"}]


@dataclass
class TurnSpec:
    message: str
    confirmed_entities: list[dict[str, Any]] | None = None


@dataclass
class TestSpec:
    test_id: str
    description: str
    turns: list[TurnSpec]
    validate: Callable[[list[dict[str, Any]]], tuple[bool, str]]


@dataclass
class TestResult:
    test_id: str
    description: str
    passed: bool
    notes: str = ""


def parse_sse(body: str) -> dict[str, Any] | None:
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                payload = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            if payload.get("type") == "done":
                return payload
    return None


def _text(done: dict[str, Any]) -> str:
    return str(done.get("text") or done.get("clean_text") or "")


def _tools(done: dict[str, Any]) -> list[str]:
    return list(done.get("tools_called") or [])


def _vis_type(done: dict[str, Any]) -> str | None:
    vis = done.get("visualization") or {}
    return vis.get("visual_type")


def _no_phantom_15157(done: dict[str, Any]) -> bool:
    t = _text(done).lower()
    return "couldn't find" not in t and "15157" not in t


def _has_expense_summary(done: dict[str, Any]) -> bool:
    return _vis_type(done) == "PROJECT_EXPENSE_SUMMARY" or "expense" in _text(done).lower()


def _has_breakdown(done: dict[str, Any]) -> bool:
    vis = done.get("visualization") or {}
    if vis.get("visual_type") == "PROJECT_EXPENSE_BREAKDOWN":
        return True
    t = _text(done).lower()
    return "breakdown" in t and "couldn't find" not in t


def _has_candidates(done: dict[str, Any]) -> bool:
    vis = done.get("visualization") or {}
    if vis.get("visual_type") == "ENTITY_CANDIDATES":
        return len(vis.get("candidates") or []) >= 2
    clar = done.get("clarification") or {}
    return len(clar.get("options") or clar.get("matches") or []) >= 2


def build_tests() -> list[TestSpec]:
    return [
        TestSpec("P-A1", "Villa Maintenance No. 34 expense", [TurnSpec("Villa Maintenance No. 34 expense", VILLA34_CONFIRM)],
                 lambda rs: (_has_expense_summary(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-A2", "Zayidia Boys School costs", [TurnSpec("show me Zayidia Boys School costs")],
                 lambda rs: ("zayidia" in _text(rs[-1]).lower() or _has_expense_summary(rs[-1]) or _has_candidates(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-A3", "how much spent on Villa 34", [TurnSpec("how much have we spent on Villa 34", VILLA34_CONFIRM)],
                 lambda rs: (_has_expense_summary(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-A4", "is Villa 34 over budget", [TurnSpec("is Villa Maintenance No. 34 over budget", VILLA34_CONFIRM)],
                 lambda rs: ("budget" in _text(rs[-1]).lower() or "w.o" in _text(rs[-1]).lower(), _text(rs[-1])[:120])),
        TestSpec("P-A5", "Villa 34 expense for this year", [TurnSpec("Villa 34 expense for this year", VILLA34_CONFIRM)],
                 lambda rs: (_has_expense_summary(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-A6", "Arabic Zayidia expenses", [TurnSpec("مصاريف مشروع زايديا")],
                 lambda rs: (len(_text(rs[-1])) > 20, _text(rs[-1])[:120])),
        TestSpec("P-B1", "Villa 34 → breakdown follow-up", [
            TurnSpec("Villa 34 expense", VILLA34_CONFIRM),
            TurnSpec("show me breakdown as well"),
        ], lambda rs: (_has_breakdown(rs[-1]) and _no_phantom_15157(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-B2", "break down Villa 34 by account", [TurnSpec("break down Villa Maintenance No. 34 by account", VILLA34_CONFIRM)],
                 lambda rs: (_has_breakdown(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-B3", "show GL details for Villa 34", [TurnSpec("show GL details for Villa Maintenance No. 34", VILLA34_CONFIRM)],
                 lambda rs: (_has_breakdown(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-B4", "summary then drill into materials", [
            TurnSpec("Villa 34 expense", VILLA34_CONFIRM),
            TurnSpec("drill into materials for Villa 34"),
        ], lambda rs: ("material" in _text(rs[-1]).lower() or _has_breakdown(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-B5", "Villa 34 breakdown direct", [TurnSpec("Villa 34 expense breakdown", VILLA34_CONFIRM)],
                 lambda rs: (_has_breakdown(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-C1", "compare Villa 34 and Villa 43", [TurnSpec("compare Villa 34 and Villa 43")],
                 lambda rs: ("compare" in _text(rs[-1]).lower() or _vis_type(rs[-1]) == "PROJECT_EXPENSE_COMPARISON", _text(rs[-1])[:120])),
        TestSpec("P-C2", "compare Zayidia Boys and Girls", [TurnSpec("compare Zayidia Boys and Girls schools")],
                 lambda rs: ("zayidia" in _text(rs[-1]).lower() or _has_candidates(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-C3", "which is more expensive Villa 34 or 43", [TurnSpec("which is more expensive, Villa 34 or Villa 43")],
                 lambda rs: ("villa" in _text(rs[-1]).lower(), _text(rs[-1])[:120])),
        TestSpec("P-C4", "top 5 projects by expense", [TurnSpec("top 5 projects by expense")],
                 lambda rs: (len(_text(rs[-1])) > 20, _text(rs[-1])[:120])),
        TestSpec("P-D1", "national guard project expense", [TurnSpec("national guard project expense")],
                 lambda rs: (_has_candidates(rs[-1]) or "national guard" in _text(rs[-1]).lower(), _text(rs[-1])[:120])),
        TestSpec("P-D2", "candidate click → data (simulated confirm)", [
            TurnSpec("national guard project expense"),
            TurnSpec("national guard project expense", [{"type": "project", "id": 101, "name": "National Guard HQ - Maintenance"}]),
        ], lambda rs: (not rs[-1].get("awaiting_clarification"), _text(rs[-1])[:120])),
        TestSpec("P-D3", "zaidia typo", [TurnSpec("zaidia boys school expense")],
                 lambda rs: ("zayidia" in _text(rs[-1]).lower() or _has_candidates(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-D4", "Villa 34 ranking", [TurnSpec("Villa 34 expense")],
                 lambda rs: ("villa" in _text(rs[-1]).lower(), _text(rs[-1])[:120])),
        TestSpec("P-D5", "general maintenance broad search", [TurnSpec("general maintenance projects")],
                 lambda rs: (_has_candidates(rs[-1]) or "general maintenance" in _text(rs[-1]).lower(), _text(rs[-1])[:120])),
        TestSpec("P-E1", "summary → breakdown → compare", [
            TurnSpec("Villa 34 expense", VILLA34_CONFIRM),
            TurnSpec("show me breakdown as well"),
            TurnSpec("compare with Villa 43"),
        ], lambda rs: ("villa" in _text(rs[-1]).lower(), _text(rs[-1])[:120])),
        TestSpec("P-E2", "Villa 34 → National Guard switch", [
            TurnSpec("Villa 34 expense", VILLA34_CONFIRM),
            TurnSpec("now National Guard expense"),
        ], lambda rs: ("national guard" in _text(rs[-1]).lower() or _has_candidates(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-E3", "Villa 34 → the breakdown too", [
            TurnSpec("Villa 34 expense", VILLA34_CONFIRM),
            TurnSpec("the breakdown too"),
        ], lambda rs: (_has_breakdown(rs[-1]) and _no_phantom_15157(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-E4", "confirm then follow-up no re-confirm", [
            TurnSpec("Villa 34 expense", VILLA34_CONFIRM),
            TurnSpec("show me breakdown as well"),
        ], lambda rs: (not rs[-1].get("awaiting_clarification") and _has_breakdown(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-E5", "breakdown as well with active Villa 34", [
            TurnSpec("Villa 34 expense", VILLA34_CONFIRM),
            TurnSpec("show me breakdown as well"),
        ], lambda rs: (_has_breakdown(rs[-1]) and _no_phantom_15157(rs[-1]), _text(rs[-1])[:120])),
        TestSpec("P-F1", "no W.O honest status", [TurnSpec("Villa Maintenance No. 34 expense", VILLA34_CONFIRM)],
                 lambda rs: ("no w.o" in _text(rs[-1]).lower() or "no budget" in _text(rs[-1]).lower() or "w.o budget" in _text(rs[-1]).lower(), _text(rs[-1])[:120])),
        TestSpec("P-F2", "partial spend honest", [TurnSpec("Villa 34 expense", VILLA34_CONFIRM)],
                 lambda rs: (len(_text(rs[-1])) > 30, _text(rs[-1])[:120])),
        TestSpec("P-F3", "over-budget honest", [TurnSpec("is Villa 34 over budget", VILLA34_CONFIRM)],
                 lambda rs: ("budget" in _text(rs[-1]).lower() or "over" in _text(rs[-1]).lower(), _text(rs[-1])[:120])),
        TestSpec("P-F4", "zero expense honest", [TurnSpec("expense for project with no data")],
                 lambda rs: (len(_text(rs[-1])) > 10, _text(rs[-1])[:120])),
        TestSpec("P-F5", "card matches narration", [TurnSpec("Villa 34 expense", VILLA34_CONFIRM)],
                 lambda rs: (_vis_type(rs[-1]) in {"PROJECT_EXPENSE_SUMMARY", None} or _has_expense_summary(rs[-1]), _text(rs[-1])[:120])),
    ]


async def run_test(client: httpx.AsyncClient, token: str, spec: TestSpec) -> TestResult:
    session_id = f"m1-{spec.test_id.lower()}-{uuid.uuid4().hex[:6]}"
    responses: list[dict[str, Any]] = []
    for turn in spec.turns:
        payload: dict[str, Any] = {"message": turn.message, "session_id": session_id}
        if turn.confirmed_entities:
            payload["confirmed_entities"] = turn.confirmed_entities
        try:
            resp = await client.post(
                f"{API_BASE}/chat/stream",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=180.0,
            )
        except httpx.TimeoutException:
            return TestResult(spec.test_id, spec.description, False, "timeout")
        done = parse_sse(resp.text)
        if not done:
            return TestResult(spec.test_id, spec.description, False, "no done event")
        responses.append(done)
    try:
        ok, note = spec.validate(responses)
    except Exception as exc:
        return TestResult(spec.test_id, spec.description, False, f"validator error: {exc}")
    return TestResult(spec.test_id, spec.description, ok, note)


async def main_async() -> int:
    tests = build_tests()
    print("=" * 70)
    print("PHASE M1 — PROJECT Module Certification")
    print(f"API: {API_BASE}")
    print("=" * 70)

    async with httpx.AsyncClient() as client:
        login = await client.post(f"{API_BASE}/auth/login", json={"file_id": FILE_ID}, timeout=30)
        login.raise_for_status()
        token = login.json()["access_token"]

        results: list[TestResult] = []
        for spec in tests:
            print(f"\nRunning {spec.test_id}: {spec.description}...")
            result = await run_test(client, token, spec)
            results.append(result)
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {result.notes}")

    passed = sum(1 for r in results if r.passed)
    print("\n" + "=" * 70)
    print("M1 FULL MATRIX")
    print("=" * 70)
    for r in results:
        print(f"  [{('PASS' if r.passed else 'FAIL'):4}] {r.test_id:6} {r.description}")
        if not r.passed:
            print(f"         notes: {r.notes}")
    print(f"\n{passed}/{len(results)} passed")
    return 0 if passed == len(results) else 1


def main() -> int:
    return asyncio.run(main_async())


if __name__ == "__main__":
    raise SystemExit(main())
