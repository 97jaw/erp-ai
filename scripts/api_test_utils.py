"""Shared helpers for live API acceptance scripts (local + EC2)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def load_test_env() -> None:
    from dotenv import load_dotenv

    for name in (".env", ".env.production"):
        path = ROOT / name
        if path.is_file():
            load_dotenv(path)


def api_base() -> str:
    return os.environ.get("OOA_API_BASE", "http://127.0.0.1:8000").rstrip("/")


def file_id() -> str:
    return os.environ.get("OOA_FILE_ID", "2721")


def wait_for_health(client: httpx.Client, *, attempts: int = 15, pause_s: float = 2.0) -> None:
    base = api_base()
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            res = client.get(f"{base}/health", timeout=15.0)
            res.raise_for_status()
            return
        except (httpx.HTTPError, OSError) as exc:
            last_exc = exc
            if attempt < attempts:
                time.sleep(pause_s)
    raise RuntimeError(f"Gateway not healthy at {base}/health after {attempts} tries") from last_exc


def login(
    client: httpx.Client,
    *,
    timeout_s: float = 90.0,
    retries: int = 3,
) -> str:
    base = api_base()
    fid = file_id()
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            res = client.post(
                f"{base}/auth/login",
                json={"file_id": fid},
                timeout=timeout_s,
            )
            res.raise_for_status()
            body = res.json()
            token = body.get("access_token") or body.get("session_id")
            if not token:
                raise RuntimeError(f"login response missing token: {body!r}")
            return str(token)
        except (httpx.HTTPError, RuntimeError) as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(3 * attempt)
    raise RuntimeError(f"login failed after {retries} attempts to {base}/auth/login") from last_exc
