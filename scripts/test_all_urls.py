#!/usr/bin/env python3
"""Smoke-test OOA HTTP endpoints (Phases 1–8). Run with API on BASE_URL (default http://127.0.0.1:8000)."""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

load_dotenv()

BASE = os.environ.get("OOA_TEST_BASE", "http://127.0.0.1:8000").rstrip("/")
FILE_ID = os.environ.get("SUPER_ADMIN_FILE_ID", os.environ.get("OOA_TEST_FILE_ID", "2721"))


@dataclass
class Result:
    method: str
    path: str
    status: int | str
    ok: bool
    note: str = ""

    def line(self) -> str:
        mark = "PASS" if self.ok else "FAIL"
        return f"[{mark}] {self.method:6} {self.path:45} -> {self.status} {self.note}"


@dataclass
class Context:
    token: str = ""
    refresh: str = ""
    user_id: int | None = None
    role_id: int | None = None
    dept_id: int | None = None
    flag_id: int | None = None
    conv_id: str | None = None
    audit_id: int | None = None
    results: list[Result] = field(default_factory=list)


def req(
    ctx: Context,
    method: str,
    path: str,
    *,
    body: dict | None = None,
    auth: bool = True,
    expect: set[int] | None = None,
    note: str = "",
) -> tuple[int, Any]:
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    if auth and ctx.token:
        headers["Authorization"] = f"Bearer {ctx.token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8") or "{}"
            try:
                payload = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload = raw
    except urllib.error.HTTPError as exc:
        status = exc.code
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except Exception:
            payload = {"detail": str(exc)}
    except urllib.error.URLError as exc:
        ctx.results.append(Result(method, path, "CONN", False, str(exc.reason)))
        return 0, {}

    allowed = expect or {200, 201, 204}
    ok = status in allowed
    ctx.results.append(Result(method, path, status, ok, note))
    return status, payload


def wait_for_server(max_wait: int = 30) -> bool:
    for _ in range(max_wait):
        try:
            urllib.request.urlopen(f"{BASE}/health", timeout=2)
            return True
        except Exception:
            time.sleep(1)
    return False


def main() -> int:
    if not wait_for_server():
        print(f"ERROR: API not reachable at {BASE}/health — start uvicorn first.")
        return 1

    ctx = Context()
    print(f"Testing {BASE} (file_id={FILE_ID})\n")

    # --- Public / health ---
    req(ctx, "GET", "/health", auth=False)
    req(ctx, "GET", "/quality/metrics", auth=False)

    # --- Auth ---
    st, body = req(ctx, "POST", "/auth/login", body={"file_id": FILE_ID}, auth=False, expect={200})
    if st != 200:
        print("Login failed — cannot continue admin tests.")
        for r in ctx.results:
            print(r.line())
        return 1

    if body.get("mfa_required"):
        print("NOTE: User has MFA enabled — complete MFA manually or reset MFA for automated tests.")
        ctx.results.append(Result("POST", "/auth/login", st, True, "mfa_required"))
    else:
        ctx.token = body.get("access_token") or body.get("session_id") or ""
        ctx.refresh = body.get("refresh_token") or ""

    if ctx.token:
        st, prof = req(ctx, "GET", "/auth/me")
        if st == 200:
            ctx.user_id = prof.get("id")

        req(ctx, "GET", "/user/profile", note="legacy profile")

        st, pr = req(ctx, "GET", "/profile/security")
        if st == 200:
            pass

        if ctx.refresh:
            st, ref = req(
                ctx,
                "POST",
                "/auth/refresh",
                body={"refresh_token": ctx.refresh},
                auth=False,
                expect={200},
            )
            if st == 200 and ref.get("access_token"):
                ctx.token = ref["access_token"]

    # --- Chat (light) ---
    req(ctx, "POST", "/chat", body={"message": "What is today's date?", "session_id": None}, expect={200, 401, 503})

    # --- Conversations ---
    st, conv = req(ctx, "GET", "/conversations?limit=5")
    if st == 200 and conv.get("conversations"):
        ctx.conv_id = conv["conversations"][0]["id"]

    if ctx.conv_id:
        req(ctx, "GET", f"/conversations/{ctx.conv_id}")
        req(ctx, "POST", f"/conversations/{ctx.conv_id}/archive?archived=true", body={})
        req(ctx, "POST", f"/conversations/{ctx.conv_id}/archive?archived=false", body={})

    # --- Admin read APIs ---
    req(ctx, "GET", "/admin/users?limit=10")
    req(ctx, "GET", "/admin/roles")
    req(ctx, "GET", "/admin/permissions")
    req(ctx, "GET", "/admin/departments")
    req(ctx, "GET", "/admin/feature-flags")
    req(ctx, "GET", "/admin/audit?limit=5")
    req(ctx, "GET", "/admin/usage")
    req(ctx, "GET", "/admin/usage/by-user?limit=5")
    req(ctx, "GET", "/admin/usage/by-department")
    req(ctx, "GET", "/admin/usage/costs")
    req(ctx, "GET", "/admin/security/summary")

    st, roles = req(ctx, "GET", "/admin/roles")
    if st == 200 and roles.get("roles"):
        ctx.role_id = roles["roles"][0]["id"]
        req(ctx, "GET", f"/admin/roles/{ctx.role_id}/permissions")

    st, depts = req(ctx, "GET", "/admin/departments")
    if st == 200 and depts.get("departments"):
        ctx.dept_id = depts["departments"][0]["id"]
        req(ctx, "GET", f"/admin/departments/{ctx.dept_id}/users")

    st, flags = req(ctx, "GET", "/admin/feature-flags")
    if st == 200 and flags.get("feature_flags"):
        ctx.flag_id = flags["feature_flags"][0]["id"]

    st, audit = req(ctx, "GET", "/admin/audit?limit=1")
    if st == 200 and audit.get("events"):
        ctx.audit_id = audit["events"][0]["id"]
        req(ctx, "GET", f"/admin/audit/{ctx.audit_id}")

    if ctx.user_id:
        req(ctx, "GET", f"/admin/users/{ctx.user_id}")
        req(ctx, "GET", f"/admin/users/{ctx.user_id}/sessions")

    # --- Security write (non-destructive where possible) ---
    req(
        ctx,
        "POST",
        "/auth/password/reset/request",
        body={"file_id": FILE_ID},
        auth=False,
        expect={200},
    )

    # --- Logout ---
    if ctx.token:
        req(ctx, "POST", "/auth/logout", body={"session_id": ctx.token}, expect={200})

    # --- Summary ---
    passed = sum(1 for r in ctx.results if r.ok)
    failed = [r for r in ctx.results if not r.ok]
    print("\n".join(r.line() for r in ctx.results))
    print(f"\n{passed}/{len(ctx.results)} passed")
    if failed:
        print("\nFailed:")
        for r in failed:
            print(f"  - {r.method} {r.path}: {r.status} {r.note}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
