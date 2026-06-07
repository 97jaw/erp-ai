"""Monitoring Phase 6 — runbooks, alertmanager render, silence API."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_runbooks_cover_all_alert_rules():
    from admin.metrics.runbooks import RUNBOOKS

    rules_path = ROOT / "monitoring" / "prometheus" / "rules" / "ooa-alerts.yml"
    text = rules_path.read_text(encoding="utf-8")
    import re

    names = set(re.findall(r"alert:\s+(\w+)", text))
    missing = names - set(RUNBOOKS.keys())
    assert not missing, f"Missing runbooks for: {missing}"


def test_render_alertmanager_config_writes_file(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("ALERT_EMAIL_ENABLED", "false")
    monkeypatch.setenv("ALERT_SLACK_ENABLED", "false")
    out = ROOT / "monitoring" / "alertmanager" / "alertmanager.generated.yml"
    if out.exists():
        out.unlink()
    import scripts.render_alertmanager_config as rac

    monkeypatch.setattr(rac, "OUT", out)
    assert rac.main() == 0
    assert out.is_file()
    body = out.read_text(encoding="utf-8")
    assert "critical-alerts" in body
    assert "high-alerts" in body


@pytest.mark.asyncio
async def test_get_alerts_includes_runbooks():
    from admin.metrics.service import get_alerts

    with patch(
        "admin.metrics.service.fetch_prometheus_alerts",
        new_callable=AsyncMock,
        return_value=[{"name": "OoaGatewayDown", "state": "firing"}],
    ), patch(
        "admin.metrics.service.fetch_alertmanager_alerts",
        new_callable=AsyncMock,
        return_value=[],
    ):
        data = await get_alerts()
    assert "runbooks" in data
    assert len(data["runbooks"]) >= 10
    assert data["prometheus"][0].get("runbook", {}).get("title")


@pytest.mark.asyncio
async def test_silence_alert_calls_alertmanager():
    from admin.metrics.service import silence_alert

    with patch(
        "admin.metrics.prometheus_client.create_alertmanager_silence",
        new_callable=AsyncMock,
        return_value={"ok": True, "silence_id": "abc"},
    ) as mock:
        result = await silence_alert(
            alertname="OoaGatewayDown",
            duration_hours=1,
            comment="test",
            created_by="admin",
        )
    assert result["ok"] is True
    mock.assert_awaited_once()
