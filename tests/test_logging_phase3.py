from __future__ import annotations

import json
import logging

from gateway.logging_config import OoaJsonFormatter, request_id_var, setup_logging


def test_json_formatter_includes_context_fields() -> None:
    token = request_id_var.set("req-test-123")
    try:
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello",
            args=(),
            exc_info=None,
        )
        record.user_id = "user-42"
        record.category = "api"
        line = OoaJsonFormatter().format(record)
        payload = json.loads(line)
        assert payload["message"] == "hello"
        assert payload["service"] == "ooa-gateway"
        assert payload["request_id"] == "req-test-123"
        assert payload["user_id"] == "user-42"
        assert payload["category"] == "api"
        assert "timestamp" in payload
    finally:
        request_id_var.reset(token)


def test_setup_logging_json_stdout(capsys) -> None:
    import os

    os.environ["OOA_LOG_JSON"] = "true"
    os.environ["OOA_LOG_FILE"] = ""
    root = logging.getLogger()
    if hasattr(root, "_ooa_logging_configured"):
        delattr(root, "_ooa_logging_configured")
    root.handlers.clear()

    setup_logging()
    logging.getLogger("ooa.test").info(
        "structured event",
        extra={"event": "test_event", "category": "system"},
    )
    out = capsys.readouterr().err.strip().splitlines()[-1]
    payload = json.loads(out)
    assert payload["event"] == "test_event"
    assert payload["category"] == "system"
