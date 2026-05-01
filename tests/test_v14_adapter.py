"""
OOA Phase 3 — Odoo 14 Adapter Tests
======================================
File   : tests/test_v14_adapter.py

Tests cover:
    - Authentication (success + failure)
    - search_read
    - search_count
    - call_method (custom engine)
    - get_kpi_data normalization
    - field_exists cache
    - Error handling

All tests use mocking — no real Odoo connection needed.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from adapters.v14.connector import OdooV14Adapter
from core.base_adapter import KPIRequest, OdooConnectionConfig
from core.state import OdooVersion


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_config() -> OdooConnectionConfig:
    return OdooConnectionConfig(
        url      = "http://localhost:8069",
        database = "test_db",
        username = "admin",
        api_key  = "admin",
        version  = OdooVersion.V14,
    )


def make_adapter() -> OdooV14Adapter:
    with patch("xmlrpc.client.ServerProxy"):
        adapter = OdooV14Adapter(make_config())
        adapter._uid = 1  # Pre-authenticated
    return adapter


# ---------------------------------------------------------------------------
# Authentication Tests
# ---------------------------------------------------------------------------

class TestAuthentication:

    def test_successful_auth_stores_uid(self):
        with patch("xmlrpc.client.ServerProxy") as mock_proxy:
            mock_proxy.return_value.authenticate.return_value = 7
            adapter = OdooV14Adapter(make_config())
            adapter._common = mock_proxy.return_value
            uid = adapter.authenticate()
            assert uid == 7
            assert adapter._uid == 7

    def test_failed_auth_raises_error(self):
        with patch("xmlrpc.client.ServerProxy") as mock_proxy:
            mock_proxy.return_value.authenticate.return_value = False
            adapter = OdooV14Adapter(make_config())
            adapter._common = mock_proxy.return_value
            with pytest.raises(ConnectionError):
                adapter.authenticate()

    def test_version_is_v14(self):
        adapter = make_adapter()
        assert adapter.version == OdooVersion.V14


# ---------------------------------------------------------------------------
# search_read Tests
# ---------------------------------------------------------------------------

class TestSearchRead:

    def test_search_read_returns_records(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = [
            {"id": 1, "name": "Project Alpha"},
            {"id": 2, "name": "Project Beta"},
        ]
        records = adapter.search_read(
            model  = "project.project",
            domain = [["active", "=", True]],
            fields = ["name", "date_start"],
            limit  = 10,
        )
        assert len(records) == 2
        assert records[0]["name"] == "Project Alpha"

    def test_search_read_passes_correct_args(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = []
        adapter.search_read(
            model  = "sale.order",
            domain = [["state", "=", "sale"]],
            fields = ["name", "amount_total"],
            limit  = 5,
            order  = "date_order desc",
        )
        # kwargs is always passed as last positional arg to execute_kw
        call_args = adapter._object.execute_kw.call_args[0]
        # Find the kwargs dict — it is the last argument
        call_kwargs = call_args[-1]
        assert call_kwargs["limit"]  == 5
        assert call_kwargs["order"]  == "date_order desc"
        assert call_kwargs["fields"] == ["name", "amount_total"]
        

    def test_search_count_returns_integer(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = 42
        count = adapter.search_count("project.project", [])
        assert count == 42


# ---------------------------------------------------------------------------
# call_method Tests
# ---------------------------------------------------------------------------

class TestCallMethod:

    def test_call_method_project_dashboard(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = {
            "project_name" : "Test Project",
            "kpis"         : {
                "total_cost"    : 50000.0,
                "budget"        : 40000.0,
                "exceed_percent": 25.0,
                "status"        : "critical",
            },
            "cost_distribution": [],
            "weekly_trend"     : [],
        }
        result = adapter.call_method(
            "project.financial.service",
            "get_project_expense_dashboard",
            [5],
        )
        assert result["project_name"] == "Test Project"
        assert result["kpis"]["status"] == "critical"

    def test_call_method_passes_args_correctly(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = {}
        adapter.call_method(
            "project.financial.service",
            "get_project_expense_dashboard",
            [42],
        )
        call_args = adapter._object.execute_kw.call_args[0]
        assert call_args[3] == "project.financial.service"
        assert call_args[4] == "get_project_expense_dashboard"
        assert call_args[5] == [42]


# ---------------------------------------------------------------------------
# KPI Normalization Tests
# ---------------------------------------------------------------------------

class TestKPINormalization:

    def test_dashboard_response_normalized_correctly(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = {
            "project_name": "Al Barsha Tower",
            "kpis": {
                "total_cost"    : 125000.0,
                "budget"        : 100000.0,
                "exceed_percent": 25.0,
                "status"        : "critical",
            },
            "weekly_trend"     : [],
            "cost_distribution": [],
        }
        request = KPIRequest(
            kpi_type = "project_expense_dashboard",
            model    = "project.financial.service",
            method   = "get_project_expense_dashboard",
            filters  = {"project_id": 5},
        )
        response = adapter.get_kpi_data(request)

        assert response.label      == "Al Barsha Tower"
        assert response.value      == 125000.0
        assert response.trend      == "critical"
        assert response.delta      == 25.0
        assert response.color_code == "#ef4444"

    def test_financial_data_response_normalized(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = {
            "project"  : "Marina Heights",
            "kpis"     : {
                "net_profit": 35000.0,
                "margin"    : 28.0,
            },
            "hierarchy": [],
        }
        request = KPIRequest(
            kpi_type = "project_financial_data",
            model    = "project.financial.service",
            method   = "get_project_financial_data",
            filters  = {
                "project_id": 3,
                "date_from" : "2026-01-01",
                "date_to"   : "2026-03-31",
            },
        )
        response = adapter.get_kpi_data(request)

        assert response.label == "Marina Heights"
        assert response.value == 35000.0
        assert response.delta == 28.0
        assert response.trend == "up"

    def test_status_to_color_mapping(self):
        adapter = make_adapter()
        assert adapter._status_to_color("normal")   == "#22c55e"
        assert adapter._status_to_color("warning")  == "#f59e0b"
        assert adapter._status_to_color("critical") == "#ef4444"
        assert adapter._status_to_color("unknown")  == "#6b7280"


# ---------------------------------------------------------------------------
# Field Discovery Tests
# ---------------------------------------------------------------------------

class TestFieldDiscovery:

    def test_field_exists_returns_true_for_cached_field(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = {
            "name"       : {"string": "Name",   "type": "char"},
            "date_start" : {"string": "Start",  "type": "date"},
            "wo_amount"  : {"string": "WO Amt", "type": "float"},
        }
        # Force a fresh fetch
        result = adapter.field_exists("project.project", "wo_amount")
        assert result is True

    def test_field_exists_returns_false_for_missing_field(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = {
            "name": {"string": "Name", "type": "char"},
        }
        result = adapter.field_exists("project.project", "nonexistent_field")
        assert result is False
