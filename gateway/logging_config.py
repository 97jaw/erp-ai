"""
Structured JSON logging for OOA (MONITORING_PLAN Phase 3).
Logs to stdout and optionally logs/ooa-gateway.jsonl for Promtail.
"""
from __future__ import annotations

import json
import logging
import os
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str | None] = ContextVar("ooa_request_id", default=None)

_RESERVED_LOG_ATTRS = frozenset(
    logging.LogRecord(
        "", 0, "", 0, "", (), None
    ).__dict__
) | {
    "message",
    "asctime",
    "args",
    "exc_info",
    "exc_text",
    "stack_info",
    "taskName",
}


class OoaJsonFormatter(logging.Formatter):
    """One JSON object per log line (Loki / Promtail friendly)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "service": "ooa-gateway",
            "logger": record.name,
            "message": record.getMessage(),
        }

        rid = getattr(record, "request_id", None) or request_id_var.get()
        if rid:
            payload["request_id"] = rid

        for key, value in record.__dict__.items():
            if key in _RESERVED_LOG_ATTRS or key.startswith("_"):
                continue
            if value is not None and key not in payload:
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str, ensure_ascii=False)


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """Attach request_id and emit one access log per HTTP request."""

    _SKIP_PATHS = {"/metrics"}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self._SKIP_PATHS:
            return await call_next(request)

        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        token = request_id_var.set(request_id)
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            duration_ms = (time.perf_counter() - start) * 1000.0
            user_id: str | None = None
            try:
                from admin.rbac.context import get_request_user

                user = get_request_user()
                if user is not None:
                    user_id = str(user.id)
            except Exception:
                pass

            logging.getLogger("ooa.access").info(
                "request completed",
                extra={
                    "event": "http_request",
                    "category": "api",
                    "request_id": request_id,
                    "user_id": user_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                },
            )
            request_id_var.reset(token)


def setup_logging() -> None:
    """Configure root logger once (JSON to stdout + optional file)."""
    level_name = os.getenv("OOA_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    use_json = os.getenv("OOA_LOG_JSON", "true").lower() in ("1", "true", "yes")

    root = logging.getLogger()
    if getattr(root, "_ooa_logging_configured", False):
        return

    root.handlers.clear()
    root.setLevel(level)

    formatter: logging.Formatter
    if use_json:
        formatter = OoaJsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    log_file = os.getenv("OOA_LOG_FILE", "logs/ooa-gateway.jsonl")
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(OoaJsonFormatter())
        root.addHandler(file_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    root._ooa_logging_configured = True  # type: ignore[attr-defined]

    logging.getLogger(__name__).info(
        "logging configured",
        extra={
            "event": "logging_ready",
            "category": "system",
            "json": use_json,
            "log_file": log_file or None,
        },
    )
