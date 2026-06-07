"""
OOA Phase 3 — LIVE Integration Test
=====================================
File   : tests/test_live_v14.py

IMPORTANT: This test makes REAL calls to your Odoo 14 staging instance.
           Run ONLY when connected and credentials are set in .env

Run with:
    pytest tests/test_live_v14.py -v -s

Skip in normal test runs:
    pytest tests/ --ignore=tests/test_live_v14.py
"""

import os
import pytest
from dotenv import load_dotenv

load_dotenv()


def _odoo_reachable() -> bool:
    url = os.environ.get("ODOO_V14_URL")
    if not url:
        return False
    try:
        import socket
        from urllib.parse import urlparse

        host = urlparse(url).hostname
        if not host:
            return False
        socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False


# Skip entire file if staging credentials not set or host unreachable (CI/sandbox).
pytestmark = pytest.mark.skipif(
    not _odoo_reachable(),
    reason="ODOO_V14_URL not set or Odoo host unreachable — skipping live tests",
)

from adapters.v14.connector import OdooV14Adapter
from core.base_adapter import KPIRequest, OdooConnectionConfig
from core.state import OdooVersion

# ---------------------------------------------------------------------------
# Config from .env
# ---------------------------------------------------------------------------

PROJECT_ID = int(os.environ.get("ODOO_V14_TEST_PROJECT_ID", "1"))


def make_live_adapter() -> OdooV14Adapter:
    config = OdooConnectionConfig(
        url      = os.environ["ODOO_V14_URL"],
        database = os.environ["ODOO_V14_DB"],
        username = os.environ["ODOO_V14_USER"],
        api_key  = os.environ["ODOO_V14_PASSWORD"],
        version  = OdooVersion.V14,
    )
    adapter = OdooV14Adapter(config)
    adapter.authenticate()
    return adapter


# ---------------------------------------------------------------------------
# Live Tests
# ---------------------------------------------------------------------------

class TestLiveV14:

    def test_authentication(self):
        """Verifies credentials work against staging."""
        adapter = make_live_adapter()
        assert adapter._uid is not None
        assert adapter._uid > 0
        print(f"\n✓ Authenticated — uid: {adapter._uid}")

    def test_search_read_projects(self):
        """Fetches real projects from staging."""
        adapter = make_live_adapter()
        records = adapter.search_read(
            model  = "project.project",
            domain = [["active", "=", True]],
            fields = ["name", "date_start"],
            limit  = 5,
        )
        assert isinstance(records, list)
        print(f"\n✓ Projects found: {len(records)}")
        for r in records:
            print(f"  - [{r['id']}] {r['name']}")

    def test_project_expense_dashboard(self):
        """
        Calls get_project_expense_dashboard on your real staging data.
        PROJECT_ID set via ODOO_V14_TEST_PROJECT_ID in .env
        """
        adapter = make_live_adapter()
        result  = adapter.call_method(
            "project.financial.service",
            "get_project_expense_dashboard",
            [PROJECT_ID],
        )
        assert isinstance(result, dict)
        assert "kpis" in result
        assert "cost_distribution" in result

        kpis = result["kpis"]
        print(f"\n✓ Project: {result.get('project_name')}")
        print(f"  Total Cost    : {kpis.get('total_cost')}")
        print(f"  Budget        : {kpis.get('budget')}")
        print(f"  Exceed %      : {kpis.get('exceed_percent')}")
        print(f"  Status        : {kpis.get('status')}")

    def test_kpi_response_normalization_live(self):
        """Verifies KPIResponse normalized correctly from live data."""
        adapter = make_live_adapter()
        request = KPIRequest(
            kpi_type = "project_expense_dashboard",
            model    = "project.financial.service",
            method   = "get_project_expense_dashboard",
            filters  = {"project_id": PROJECT_ID},
        )
        response = adapter.get_kpi_data(request)

        assert response.value is not None
        assert response.label is not None
        assert response.color_code in ["#22c55e", "#f59e0b", "#ef4444", "#6b7280"]
        print(f"\n✓ KPI Response:")
        print(f"  Label      : {response.label}")
        print(f"  Value      : {response.value}")
        print(f"  Trend      : {response.trend}")
        print(f"  Color      : {response.color_code}")

    def test_field_discovery_project(self):
        """Verifies ir.model.fields cache works on staging."""
        adapter = make_live_adapter()
        fields  = adapter.get_model_fields("project.project", force_refresh=True)

        assert "name" in fields
        assert "date_start" in fields
        print(f"\n✓ project.project has {len(fields)} fields")
        print(f"  wo_amount exists: {'wo_amount' in fields}")
