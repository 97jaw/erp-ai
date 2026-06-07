from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from admin.metrics.prometheus_client import instant_scalar
from admin.metrics.service import _search_logs_file, get_overview, search_logs


def test_instant_scalar_empty() -> None:
    assert instant_scalar({"data": {"result": []}}, default=-1.0) == -1.0


def test_instant_scalar_value() -> None:
    data = {"data": {"result": [{"value": [1, "42.5"]}]}}
    assert instant_scalar(data) == 42.5


def test_search_logs_file_filter(tmp_path: Path) -> None:
    log = tmp_path / "test.jsonl"
    log.write_text(
        "\n".join(
            [
                json.dumps({"level": "INFO", "message": "hello world"}),
                json.dumps({"level": "ERROR", "message": "boom"}),
            ]
        ),
        encoding="utf-8",
    )
    rows = _search_logs_file(log, limit=10, level="ERROR", query=None)
    assert len(rows) == 1
    assert rows[0]["message"] == "boom"


@pytest.mark.asyncio
async def test_get_overview_without_db() -> None:
    prom_payload = {"data": {"result": [{"value": [1, "1"]}]}}

    async def fake_prom(expr: str):  # noqa: ARG001
        return prom_payload

    with patch("admin.metrics.service._usage_repo", AsyncMock(return_value=None)):
        with patch("admin.metrics.service.prom_query", side_effect=fake_prom):
            with patch("admin.metrics.service.get_last_credit_checks", return_value={}):
                with patch(
                    "admin.metrics.service.fetch_prometheus_alerts",
                    AsyncMock(return_value=[]),
                ):
                    out = await get_overview(days=1)
    assert out["prometheus_ok"] is True
    assert "usage" in out


@pytest.mark.asyncio
async def test_search_logs_file_source(tmp_path: Path, monkeypatch) -> None:
    log = tmp_path / "gateway.jsonl"
    log.write_text(json.dumps({"level": "INFO", "message": "ok"}) + "\n", encoding="utf-8")
    monkeypatch.setenv("OOA_LOG_FILE", str(log))
    with patch("admin.metrics.service._search_logs_loki", AsyncMock(return_value=None)):
        out = await search_logs(limit=5)
    assert out["source"] == "file"
    assert out["count"] >= 1
