"""
OOA Phase 2 — KPI Node Tests
==============================
File   : tests/test_kpi_node.py
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from core.nodes.kpi_node import KPINode, VisualizationSelector
from core.base_adapter import KPIResponse
from core.state import (
    AgentState,
    ErrorSeverity,
    OdooVersion,
    SessionState,
    TurnState,
    VisualType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_state(
    raw_input    : str = "",
    active_domain: str = "sale.order",
    company_ids  : list = None,
) -> AgentState:
    session = SessionState(
        odoo_user_id  = 1,
        odoo_version  = OdooVersion.V14,
        odoo_url      = "http://localhost:8069",
        active_domain = active_domain,
        company_ids   = company_ids or [1],
    )
    turn = TurnState(raw_input=raw_input, turn_number=3)
    return AgentState(session=session, turn=turn)


def make_node() -> KPINode:
    return KPINode(api_key="sk-ant-fake-test-key")


def make_adapter(kpi_response: KPIResponse) -> MagicMock:
    adapter = MagicMock()
    adapter.get_kpi_data.return_value = kpi_response
    return adapter


def mock_claude_extraction(
    kpi_type: str = "total_sales",
    model   : str = "sale.order",
    method  : str = "get_ai_kpi",
    filters : dict = None,
) -> MagicMock:
    payload = json.dumps({
        "kpi_type": kpi_type,
        "model"   : model,
        "method"  : method,
        "filters" : filters or {"date_from": "2026-01-01", "date_to": "2026-03-31"},
    })
    mock_content      = MagicMock()
    mock_content.text = payload
    mock_response     = MagicMock()
    mock_response.content = [mock_content]
    return mock_response


# ---------------------------------------------------------------------------
# VisualizationSelector Tests
# ---------------------------------------------------------------------------

class TestVisualizationSelector:

    def setup_method(self):
        self.selector = VisualizationSelector()

    def test_scalar_value_returns_kpi_card(self):
        response = KPIResponse(label="Total Sales", value=50000.0)
        assert self.selector.select(response) == VisualType.KPI_CARD

    def test_list_with_time_returns_line_chart(self):
        response = KPIResponse(
            label    = "Monthly Sales",
            value    = 0,
            raw_data = [
                {"month": "Jan", "value": 1000},
                {"month": "Feb", "value": 1500},
            ],
        )
        assert self.selector.select(response) == VisualType.LINE_CHART

    def test_list_with_category_returns_bar_chart(self):
        response = KPIResponse(
            label    = "Sales by Region",
            value    = 0,
            raw_data = [
                {"region": "Karachi", "value": 5000},
                {"region": "Dubai",   "value": 8000},
            ],
        )
        assert self.selector.select(response) == VisualType.BAR_CHART

    def test_two_dimensions_returns_pivot_table(self):
        response = KPIResponse(
            label    = "Sales by Region and Month",
            value    = 0,
            raw_data = [
                {"region": "Karachi", "month": "Jan", "value": 5000},
            ],
        )
        assert self.selector.select(response) == VisualType.PIVOT_TABLE

    def test_plain_list_returns_data_table(self):
        response = KPIResponse(
            label    = "Top Vendors",
            value    = 0,
            raw_data = [
                {"name": "Vendor A", "total": 1000},
                {"name": "Vendor B", "total": 2000},
            ],
        )
        assert self.selector.select(response) == VisualType.DATA_TABLE

    def test_empty_list_returns_kpi_card(self):
        response = KPIResponse(
            label    = "Empty Result",
            value    = 0,
            raw_data = [],
        )
        assert self.selector.select(response) == VisualType.KPI_CARD


# ---------------------------------------------------------------------------
# KPINode Tests
# ---------------------------------------------------------------------------

class TestKPINode:

    @patch("core.nodes.kpi_node.anthropic.Anthropic")
    def test_successful_kpi_call(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction()
        )
        kpi_response = KPIResponse(
            label="Total Sales", value=125000.0, unit="PKR", trend="up"
        )
        adapter = make_adapter(kpi_response)
        node    = make_node()
        state   = make_state("What is our total sales this quarter?")
        result  = node(state, adapter)

        assert result["turn"]["last_odoo_response"] is not None
        assert result["turn"]["visualization_payload"]["visual_type"] == "KPI_CARD"
        assert result["session"]["last_visual_type"] == VisualType.KPI_CARD

    @patch("core.nodes.kpi_node.anthropic.Anthropic")
    def test_adapter_called_with_correct_kpi_request(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction(kpi_type="net_profit_margin", model="account.move")
        )
        kpi_response = KPIResponse(label="Net Profit", value=12.5, unit="%")
        adapter = make_adapter(kpi_response)
        node    = make_node()
        state   = make_state("What is our net profit margin?")
        node(state, adapter)

        call_args = adapter.get_kpi_data.call_args[0][0]
        assert call_args.kpi_type == "net_profit_margin"
        assert call_args.model    == "account.move"
        assert call_args.method   == "get_ai_kpi"

    @patch("core.nodes.kpi_node.anthropic.Anthropic")
    def test_line_chart_for_time_series(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction(kpi_type="monthly_trend")
        )
        kpi_response = KPIResponse(
            label    = "Monthly Sales",
            value    = 0,
            raw_data = [
                {"month": "Jan", "value": 10000},
                {"month": "Feb", "value": 15000},
                {"month": "Mar", "value": 12000},
            ],
        )
        adapter = make_adapter(kpi_response)
        result  = make_node()(make_state("Show monthly sales trend"), adapter)

        assert result["turn"]["visualization_payload"]["visual_type"] == "LINE_CHART"

    @patch("core.nodes.kpi_node.anthropic.Anthropic")
    def test_extraction_failure_returns_recoverable_error(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.side_effect = (
            Exception("API timeout")
        )
        adapter = make_adapter(KPIResponse(label="x", value=0))
        result  = make_node()(make_state("Show sales"), adapter)

        assert result["turn"]["error_state"].severity == ErrorSeverity.RECOVERABLE

    @patch("core.nodes.kpi_node.anthropic.Anthropic")
    def test_odoo_kpi_failure_returns_recoverable_error(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction()
        )
        adapter = make_adapter(KPIResponse(label="x", value=0))
        adapter.get_kpi_data.side_effect = Exception("Odoo method not found")
        result  = make_node()(make_state("Show sales"), adapter)

        assert result["turn"]["error_state"].severity == ErrorSeverity.RECOVERABLE

    @patch("core.nodes.kpi_node.anthropic.Anthropic")
    def test_returns_partial_dict_only(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction()
        )
        kpi_response = KPIResponse(label="Total", value=1000.0)
        adapter = make_adapter(kpi_response)
        result  = make_node()(make_state("Total sales"), adapter)

        assert isinstance(result, dict)
        assert set(result.keys()) == {"turn", "session"}

    @patch("core.nodes.kpi_node.anthropic.Anthropic")
    def test_company_id_passed_to_kpi_request(self, mock_anthropic):
        mock_anthropic.return_value.messages.create.return_value = (
            mock_claude_extraction()
        )
        kpi_response = KPIResponse(label="Sales", value=5000.0)
        adapter = make_adapter(kpi_response)
        state   = make_state("Total sales", company_ids=[3])
        make_node()(state, adapter)

        call_args = adapter.get_kpi_data.call_args[0][0]
        assert call_args.company_id == 3
