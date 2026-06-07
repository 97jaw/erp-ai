"""Odoo XML-RPC Prometheus instrumentation (Monitoring Phase 5)."""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from gateway.metrics import REGISTRY, record_odoo_call


def test_record_odoo_call_updates_metrics() -> None:
    from prometheus_client import generate_latest

    record_odoo_call("project.project.search_read", 0.5, status="success")
    record_odoo_call("project.project.search_read", 0.2, status="error")
    body = generate_latest(REGISTRY).decode()
    assert "ooa_odoo_calls_total" in body
    assert 'method="project.project.search_read"' in body
    assert 'status="success"' in body
    assert "ooa_odoo_call_duration_seconds" in body


def test_execute_records_success_and_error() -> None:
    from adapters.v14.connector import OdooV14Adapter
    from core.base_adapter import OdooConnectionConfig
    from core.state import OdooVersion

    config = OdooConnectionConfig(
        url="https://example.com",
        database="db",
        username="u",
        api_key="k",
        version=OdooVersion.V14,
    )
    adapter = OdooV14Adapter(config)
    adapter._uid = 1
    adapter._object = MagicMock()
    adapter._object.execute_kw.return_value = [{"id": 1}]

    with patch("gateway.metrics.record_odoo_call") as mock_record:
        adapter._execute("res.partner", "search", [[]])
        mock_record.assert_called_once()
        assert mock_record.call_args.kwargs.get("status") == "success"

    adapter._object.execute_kw.side_effect = RuntimeError("fail")
    with patch("gateway.metrics.record_odoo_call") as mock_record:
        with pytest.raises(RuntimeError):
            adapter._execute("res.partner", "search", [[]])
        mock_record.assert_called_once()
        assert mock_record.call_args[1].get("status") == "error"
