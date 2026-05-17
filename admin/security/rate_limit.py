from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException

LOGIN_LIMIT = int(os.environ.get("AUTH_LOGIN_LIMIT", "5"))
LOGIN_WINDOW_SECONDS = int(os.environ.get("AUTH_LOGIN_WINDOW_SECONDS", str(15 * 60)))
ADMIN_LIMIT_PER_MIN = int(os.environ.get("AUTH_ADMIN_LIMIT_PER_MIN", "60"))

ROLE_LIMITS_PER_MIN: dict[str, int | None] = {
    "super_admin": None,
    "admin": int(os.environ.get("AUTH_RATE_ADMIN", "200")),
    "top_management": int(os.environ.get("AUTH_RATE_TOP_MGMT", "150")),
    "manager": int(os.environ.get("AUTH_RATE_MANAGER", "100")),
    "user": int(os.environ.get("AUTH_RATE_USER", "60")),
    "auditor": int(os.environ.get("AUTH_RATE_AUDITOR", "30")),
    "guest": int(os.environ.get("AUTH_RATE_GUEST", "10")),
}


class RateLimitExceeded(HTTPException):
    def __init__(self, detail: str = "Rate limit exceeded") -> None:
        super().__init__(status_code=429, detail=detail)


class _SlidingWindow:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


_login = _SlidingWindow()
_api = _SlidingWindow()
_admin = _SlidingWindow()


def check_login_ip(ip: str | None) -> None:
    address = ip or "unknown"
    if not _login.allow(f"login:{address}", limit=LOGIN_LIMIT, window_seconds=LOGIN_WINDOW_SECONDS):
        raise RateLimitExceeded(
            f"Too many login attempts. Try again in {LOGIN_WINDOW_SECONDS // 60} minutes.",
        )


def check_admin_rate(key: str) -> None:
    if not _admin.allow(f"admin:{key}", limit=ADMIN_LIMIT_PER_MIN, window_seconds=60):
        raise RateLimitExceeded("Admin API rate limit exceeded.")


def check_api_rate_for_role(*, role: str | None, key: str) -> None:
    role_name = role or "guest"
    limit = ROLE_LIMITS_PER_MIN.get(role_name, ROLE_LIMITS_PER_MIN["guest"])
    if limit is None:
        return
    if not _api.allow(f"api:{role_name}:{key}", limit=limit, window_seconds=60):
        raise RateLimitExceeded(f"API rate limit exceeded for role '{role_name}'.")


def primary_role_for_limits(roles: list[str], *, is_super_admin: bool = False) -> str:
    if is_super_admin:
        return "super_admin"
    order = [
        "super_admin",
        "admin",
        "top_management",
        "manager",
        "user",
        "auditor",
        "guest",
    ]
    role_set = set(roles)
    for name in order:
        if name in role_set:
            return name
    return "guest"
