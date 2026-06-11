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

import os
import xmlrpc.client

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

    def test_get_uid_authenticates_once_across_many_executes(self):
        with patch("xmlrpc.client.ServerProxy") as mock_proxy:
            mock_common = MagicMock()
            mock_common.authenticate.return_value = 4291
            adapter = OdooV14Adapter(make_config())
            adapter._common = mock_common
            adapter._object = MagicMock()
            adapter._object.execute_kw.return_value = []

            for _ in range(10):
                adapter.search_read("project.project", [], ["name"], limit=1)

            mock_common.authenticate.assert_called_once()

    def test_access_denied_fault_does_not_reauthenticate(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.side_effect = xmlrpc.client.Fault(
            2,
            "Access Denied",
        )
        adapter.authenticate = MagicMock(return_value=adapter._uid)

        with pytest.raises(xmlrpc.client.Fault):
            adapter.search_read("project.project", [], ["name"])

        adapter.authenticate.assert_not_called()
        assert adapter._uid == 1

    def test_session_expired_fault_reauthenticates_once(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.side_effect = [
            xmlrpc.client.Fault(2, "Session expired"),
            [{"id": 1, "name": "Project Alpha"}],
        ]
        def _reauth() -> int:
            adapter._uid = 99
            return 99

        adapter.authenticate = MagicMock(side_effect=_reauth)
        adapter._uid = 1

        records = adapter.search_read("project.project", [], ["name"])

        assert records == [{"id": 1, "name": "Project Alpha"}]
        adapter.authenticate.assert_called_once()
        assert adapter._uid == 99

    def test_env_uid_skips_authenticate_rpc(self, monkeypatch):
        monkeypatch.setenv("ODOO_V14_UID", "4291")
        with patch("xmlrpc.client.ServerProxy") as mock_proxy:
            mock_common = MagicMock()
            adapter = OdooV14Adapter(make_config())
            adapter._common = mock_common
            adapter._object = MagicMock()
            adapter._object.execute_kw.return_value = []

            adapter.search_read("project.project", [], ["name"])

            mock_common.authenticate.assert_not_called()
            assert adapter._uid == 4291


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


class TestSafeSearchRead:

    def test_safe_search_read_uses_search_then_read(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.side_effect = [
            [14549, 14610],
            [
                {"id": 14549, "name": "Zayidia Boys School", "partner_id": [1, "MOE"]},
                {"id": 14610, "name": "Zayidia Girls School- Al Ain", "partner_id": [1, "MOE"]},
            ],
        ]
        records = adapter.safe_search_read(
            model="project.project",
            domain=[["name", "ilike", "Zayidia"]],
            fields=["id", "name", "partner_id"],
            limit=20,
        )
        assert [record["id"] for record in records] == [14549, 14610]
        search_call = adapter._object.execute_kw.call_args_list[0]
        read_call = adapter._object.execute_kw.call_args_list[1]
        assert search_call[0][4] == "search"
        assert read_call[0][4] == "read"
        assert read_call[0][5] == [[14549, 14610]]

    def test_safe_search_read_empty_when_search_returns_no_ids(self):
        adapter = make_adapter()
        adapter._object = MagicMock()
        adapter._object.execute_kw.return_value = []
        records = adapter.safe_search_read(
            model="project.project",
            domain=[["name", "ilike", "Zayidia"]],
            fields=["id", "name"],
            limit=20,
        )
        assert records == []
        assert adapter._object.execute_kw.call_count == 1


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


# ---------------------------------------------------------------------------
# Purchase Order Tests
# ---------------------------------------------------------------------------

class TestGetPurchaseOrders:

    def _domain_has_field(self, domain, field_name: str) -> bool:
        return any(
            isinstance(clause, (list, tuple))
            and len(clause) >= 3
            and clause[0] == field_name
            for clause in domain
        )

    def test_queries_client_field_not_supplier(self):
        adapter = make_adapter()
        adapter._model_fields_cache = {
            "purchase.order": {
                "client"     : {"type": "many2one"},
                "project_id" : {"type": "many2one"},
                "partner_id" : {"type": "many2one"},
            },
        }

        def fake_search_read(
            model,
            domain,
            fields,
            limit=80,
            offset=0,
            order=None,
        ):
            if model == "res.partner":
                return [{"id": 11, "name": "COLORS", "is_company": True}]
            if model == "project.project":
                return [{
                    "id"        : 21,
                    "name"      : "Warehouse project",
                    "partner_id": [11, "COLORS"],
                    "wo_ref_no" : "WO-1",
                    "active"    : True,
                }]
            if model == "purchase.order":
                if self._domain_has_field(domain, "client"):
                    return [{
                        "id"          : 101,
                        "name"        : "PO001",
                        "partner_id"  : [99, "Vendor"],
                        "client"      : [11, "COLORS"],
                        "date_order"  : "2026-01-01",
                        "amount_total": 100.0,
                        "state"       : "purchase",
                        "project_id"  : False,
                        "create_date" : "2026-01-01",
                    }]
                if self._domain_has_field(domain, "project_id"):
                    return []
            return []

        adapter.search_read = MagicMock(side_effect=fake_search_read)

        result = adapter.get_purchase_orders(client_name="COLORS", limit=20)

        assert result["count"] == 1
        assert result["orders"][0]["po_number"] == "PO001"
        assert result["orders"][0]["supplier_name"] == "Vendor"
        assert result["orders"][0]["client_name"] == "COLORS"
        assert "purchase.order.client" in result["strategies"]

    def test_merges_project_and_client_matches(self):
        adapter = make_adapter()
        adapter._model_fields_cache = {
            "purchase.order": {
                "client"     : {"type": "many2one"},
                "project_id" : {"type": "many2one"},
                "partner_id" : {"type": "many2one"},
            },
        }

        def fake_search_read(
            model,
            domain,
            fields,
            limit=80,
            offset=0,
            order=None,
        ):
            if model == "res.partner":
                return [{"id": 11, "name": "COLORS", "is_company": True}]
            if model == "project.project":
                return [{
                    "id"        : 21,
                    "name"      : "Warehouse project",
                    "partner_id": [11, "COLORS"],
                    "wo_ref_no" : "WO-1",
                    "active"    : True,
                }]
            if model == "purchase.order":
                orders = []
                if self._domain_has_field(domain, "client"):
                    orders.append({
                        "id"          : 101,
                        "name"        : "PO001",
                        "partner_id"  : [99, "Vendor"],
                        "client"      : [11, "COLORS"],
                        "date_order"  : "2026-01-01",
                        "amount_total": 100.0,
                        "state"       : "purchase",
                        "project_id"  : False,
                        "create_date" : "2026-01-01",
                    })
                if self._domain_has_field(domain, "project_id"):
                    orders.append({
                        "id"          : 102,
                        "name"        : "PO002",
                        "partner_id"  : [98, "Other Vendor"],
                        "client"      : [11, "COLORS"],
                        "date_order"  : "2026-02-01",
                        "amount_total": 200.0,
                        "state"       : "done",
                        "project_id"  : [21, "Warehouse project"],
                        "create_date" : "2026-02-01",
                    })
                return orders

        adapter.search_read = MagicMock(side_effect=fake_search_read)

        result = adapter.get_purchase_orders(client_name="COLORS", limit=20)

        assert result["count"] == 2
        assert [order["po_number"] for order in result["orders"]] == ["PO002", "PO001"]

    def test_uses_explicit_partner_ids(self):
        adapter = make_adapter()
        adapter._model_fields_cache = {
            "purchase.order": {
                "client"     : {"type": "many2one"},
                "project_id" : {"type": "many2one"},
                "partner_id" : {"type": "many2one"},
            },
        }

        def fake_search_read(
            model,
            domain,
            fields,
            limit=80,
            offset=0,
            order=None,
        ):
            if model == "res.partner":
                return [{"id": 18, "name": "COLORS FOR CONTRACTING", "is_company": True}]
            if model == "project.project":
                return []
            if model == "purchase.order":
                return [{
                    "id"          : 201,
                    "name"        : "PO201",
                    "partner_id"  : [99, "Vendor"],
                    "client"      : [18, "COLORS FOR CONTRACTING"],
                    "date_order"  : "2026-03-01",
                    "amount_total": 300.0,
                    "state"       : "purchase",
                    "project_id"  : False,
                    "create_date" : "2026-03-01",
                }]
            return []

        adapter.search_read = MagicMock(side_effect=fake_search_read)

        result = adapter.get_purchase_orders(partner_ids=[18, 15481], limit=20)

        assert result["count"] == 1
        assert result["orders"][0]["po_number"] == "PO201"
        assert set(result["partner_ids"]) == {18, 15481}

    def test_matches_client_name_on_purchase_order_field(self):
        adapter = make_adapter()
        adapter._model_fields_cache = {
            "purchase.order": {
                "client"     : {"type": "many2one"},
                "project_id" : {"type": "many2one"},
                "partner_id" : {"type": "many2one"},
            },
        }

        def fake_search_read(
            model,
            domain,
            fields,
            limit=80,
            offset=0,
            order=None,
        ):
            if model == "res.partner":
                return []
            if model == "project.project":
                return []
            if model == "purchase.order":
                if self._domain_has_field(domain, "client"):
                    return [{
                        "id"          : 301,
                        "name"        : "CCT-PO-133",
                        "partner_id"  : [99, "Vendor"],
                        "client"      : [18, "COLORS FOR CONTRACTING"],
                        "date_order"  : "2025-10-30",
                        "amount_total": 1000.0,
                        "state"       : "locked",
                        "project_id"  : [21, "Private Villa"],
                        "create_date" : "2025-10-30",
                    }]
            return []

        adapter.search_read = MagicMock(side_effect=fake_search_read)

        result = adapter.get_purchase_orders(
            client_name="COLORS FOR CONTRACTING TRADE AND TRANSPORTATION ESTABLISHMENT",
            limit=20,
        )

        assert result["count"] == 1
        assert result["orders"][0]["po_number"] == "CCT-PO-133"
        assert result["orders"][0]["state"] == "locked"
