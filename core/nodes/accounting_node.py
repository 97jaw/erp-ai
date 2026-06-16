"""
OOA Phase 4 — Accounting Node
================================
File    : core/nodes/accounting_node.py
Author  : Lead Backend Developer
Version : 1.0.0

Handles ACCOUNTING intent — routes to correct report via AccountingConnector.

Supports:
    P&L, Balance Sheet, Cash Flow → ins.financial.report
    General Ledger                → ins.general.ledger
    Trial Balance                 → ins.report.trial.balance
    Partner Ledger                → ins.partner.ledger
    Partner Ageing                → ins.partner.ageing
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from gateway.model_config import AGENT_MODEL

from core.base_adapter import BaseOdooAdapter
from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
    VisualType,
)

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parameter Extraction Prompt
# ---------------------------------------------------------------------------

ACCOUNTING_EXTRACTION_PROMPT = """You are an accounting report parameter extractor for Odoo.

User input    : "{raw_input}"
User language : {language}
Today's date  : {today}

Classify the report type and extract parameters.

Report types:
- pandl          : Profit & Loss statement
- balance_sheet  : Balance Sheet
- cash_flow      : Cash Flow Statement
- general_ledger : General Ledger (transactions per account)
- trial_balance  : Trial Balance (debit/credit summary per account)
- partner_ledger : Partner Ledger (transactions per customer/vendor)
- partner_ageing : Partner Ageing (overdue amounts by bucket)

Respond with ONLY this JSON:
{{
  "report_type"     : "pandl|balance_sheet|cash_flow|general_ledger|trial_balance|partner_ledger|partner_ageing",
  "date_from"       : "YYYY-MM-DD or null",
  "date_to"         : "YYYY-MM-DD or null",
  "target_move"     : "posted",
  "result_selection": "customer|supplier|customer_supplier",
  "analytic_ids"    : [],
  "partner_name"    : null
}}

Rules:
1. Default date range is current month if not specified
2. For ageing reports, date_from is today
3. result_selection only applies to partner_ledger and partner_ageing
4. No explanation, no markdown — JSON only"""


# ---------------------------------------------------------------------------
# Visualization Builder for Accounting Reports
# ---------------------------------------------------------------------------

class AccountingVisualizationBuilder:
    """Builds visualization payloads for accounting reports."""

    def build(
        self,
        report_data: dict,
        report_type: str,
    ) -> dict[str, Any]:
        """Routes to correct visualization builder."""
        builders = {
            "pandl"         : self._financial_report_viz,
            "profit_loss"   : self._financial_report_viz,
            "balance_sheet" : self._financial_report_viz,
            "cash_flow"     : self._financial_report_viz,
            "general_ledger": self._ledger_viz,
            "trial_balance" : self._ledger_viz,
            "partner_ledger": self._partner_ledger_viz,
            "partner_ageing": self._ageing_viz,
        }
        builder = builders.get(report_type, self._financial_report_viz)
        return builder(report_data)

    def _financial_report_viz(self, data: dict) -> dict:
        """P&L / Balance Sheet / Cash Flow visualization."""
        kpis  = data.get("kpis", {})
        lines = data.get("report_lines", [])

        # Build rows for the hierarchy
        # Only include top-level summary rows (level 0, 1, 2) in API response
        # Level 3+ detail goes to raw_data for drill-down only
        summary_rows = []
        detail_rows  = []

        for line in lines:
            level        = line.get("level", 0)
            balance      = line.get("balance", 0) or 0
            name_lower   = (line.get("name") or "").lower()

            # Fix sign for income lines
            display_balance = balance
            if any(k in name_lower for k in ("income", "revenue", "gross profit", "operating income")):
                display_balance = abs(balance)

            row = {
                "name"   : line.get("name", ""),
                "balance": display_balance,
                "debit"  : line.get("debit", 0) or 0,
                "credit" : line.get("credit", 0) or 0,
                "style"  : line.get("style", "main"),
                "level"  : level,
            }

            if level <= 2:
                summary_rows.append(row)
            else:
                detail_rows.append(row)

        return {
            "visual_type"  : VisualType.FINANCIAL_REPORT.value,
            "report_name"  : data.get("report_name", "Financial Report"),
            "date_from"    : data.get("date_from"),
            "date_to"      : data.get("date_to"),
            "kpis"         : kpis,
            "rows"         : summary_rows,      # Clean summary — level 0,1,2 only
            # "detail_rows"  : detail_rows,       # Full detail for drill-down
            "columns"      : ["Name", "Debit", "Credit", "Balance"],
            "label"        : data.get("report_name", "Financial Report"),
            "value"        : kpis.get("net_profit", 0),
            "unit"         : "AED",
        }

    def _ledger_viz(self, data: dict) -> dict:
        """General Ledger / Trial Balance visualization."""
        accounts     = data.get("accounts", {})
        rows         = []
        total_debit  = 0
        total_credit = 0
        total_balance= 0

        for code, account in accounts.items():
            debit   = account.get("debit", 0) or 0
            credit  = account.get("credit", 0) or 0
            balance = account.get("balance", 0) or 0
            total_debit   += debit
            total_credit  += credit
            total_balance += balance
            rows.append({
                "code"   : code,
                "name"   : account.get("name", ""),
                "debit"  : debit,
                "credit" : credit,
                "balance": balance,
            })

        return {
            "visual_type": VisualType.LEDGER_TABLE.value,
            "report_name": data.get("report_name"),
            "date_from"  : data.get("date_from"),
            "date_to"    : data.get("date_to"),
            "columns"    : ["Code", "Account Name", "Debit", "Credit", "Balance"],
            "rows"       : rows,
            "totals"     : {
                "debit"  : total_debit,
                "credit" : total_credit,
                "balance": total_balance,
            },
            "label"      : data.get("report_name"),
            "value"      : total_balance,
            "unit"       : "AED",
            "raw_data"   : data,
        }

    def _partner_ledger_viz(self, data: dict) -> dict:
        """Partner Ledger visualization."""
        partners = data.get("partners", {})
        rows     = []

        for partner_name, pdata in partners.items():
            rows.append({
                "partner": partner_name,
                "debit"  : pdata.get("debit", 0) or 0,
                "credit" : pdata.get("credit", 0) or 0,
                "balance": pdata.get("balance", 0) or 0,
            })

        return {
            "visual_type": VisualType.LEDGER_TABLE.value,
            "report_name": "Partner Ledger",
            "date_from"  : data.get("date_from"),
            "date_to"    : data.get("date_to"),
            "columns"    : ["Partner", "Debit", "Credit", "Balance"],
            "rows"       : rows,
            "label"      : "Partner Ledger",
            "value"      : sum(r.get("balance", 0) for r in rows),
            "unit"       : "AED",
            "raw_data"   : data,
        }

    def _ageing_viz(self, data: dict) -> dict:
        """Partner Ageing visualization."""
        partners    = data.get("partners", {})
        period_list = data.get("period_list", [])
        rows        = []

        for partner_key, pdata in partners.items():
            row = {"partner": pdata.get("partner_name") or partner_key}
            for period in period_list:
                row[period] = pdata.get(period, 0) or 0
            row["total"] = pdata.get("total", 0) or 0
            rows.append(row)

        columns = ["Partner"] + list(period_list) + ["Total"]

        return {
            "visual_type": VisualType.AGEING_TABLE.value,
            "report_name": "Partner Ageing",
            "date_from"  : data.get("date_from"),
            "columns"    : columns,
            "rows"       : rows,
            "label"      : "Partner Ageing",
            "value"      : sum(r.get("total", 0) for r in rows),
            "unit"       : "AED",
            "raw_data"   : data,
        }


# ---------------------------------------------------------------------------
# AccountingNode
# ---------------------------------------------------------------------------

class AccountingNode:
    """
    Routes ACCOUNTING intent to the correct report via AccountingConnector.

    Flow:
        1. Extract report parameters via Claude
        2. Route to correct AccountingConnector method
        3. Build visualization payload
        4. Return partial dict
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required for AccountingNode.")
        self.client  = anthropic.Anthropic(api_key=self.api_key)
        self.viz_builder = AccountingVisualizationBuilder()

    def __call__(
        self,
        state  : AgentState,
        adapter: BaseOdooAdapter,
    ) -> dict[str, Any]:

        # Parameters already extracted by IntentClassifierNode
        params      = state.turn.extracted_params or {}
        report_type = params.get("report_type") or "pandl"
        raw_input   = state.turn.raw_input

        logger.info(
            "[Accounting] report_type: %s | %s → %s | params: %s",
            report_type,
            params.get("date_from"),
            params.get("date_to"),
            params,
        )

        # Call correct report
        try:
            report_data = self._call_report(adapter, report_type, params)
        except NotImplementedError as exc:
            return self._error_result(str(exc))
        except Exception as exc:
            logger.error("[Accounting] Report call failed: %s", exc)
            return self._error_result(f"Accounting report failed: {exc}")

        # Build visualization
        viz = self.viz_builder.build(report_data, report_type)

        # Store only KPIs in last_odoo_response — formatter uses this for text summary
        # Full data goes in visualization_payload for frontend rendering
        kpis = report_data.get("kpis", {})
        summary_for_formatter = {
            "report_name"    : report_data.get("report_name"),
            "report_type"    : report_type,
            "date_from"      : report_data.get("date_from"),
            "date_to"        : report_data.get("date_to"),
            "kpis"           : kpis,
            "current_balance": report_data.get("current_balance", 0),
            "ending_balance" : report_data.get("ending_balance", 0),
            # For ledger reports
            "account_count"  : len(report_data.get("accounts", {})),
            "totals"         : viz.get("totals", {}),
        }

        return {
            "turn": {
                "extracted_params"      : params,
                "last_odoo_response"    : summary_for_formatter,
                "last_odoo_model"       : f"accounting.{report_type}",
                "visualization_payload" : viz,
            },
            "session": {
                "last_visual_type": VisualType(
                    viz.get("visual_type", VisualType.DATA_TABLE.value)
                ),
                "active_domain"   : f"accounting.{report_type}",
            },
        }

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    def _extract_params(
        self,
        raw_input: str,
        state    : AgentState,
    ) -> dict[str, Any]:
        """Extracts accounting report parameters using Claude."""
        from datetime import date
        today = date.today().strftime("%Y-%m-%d")

        prompt = ACCOUNTING_EXTRACTION_PROMPT.format(
            raw_input = raw_input,
            language  = state.session.user_language,
            today     = today,
        )
        message = self.client.messages.create(
            model      = AGENT_MODEL,
            max_tokens = 200,
            messages   = [{"role": "user", "content": prompt}],
        )
        raw_json = message.content[0].text.strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
        return json.loads(raw_json)

    def _call_report(
        self,
        adapter    : BaseOdooAdapter,
        report_type: str,
        params     : dict,
    ) -> dict[str, Any]:
        """Routes to correct AccountingConnector method."""
        ac = adapter.accounting

        date_from = params.get("date_from")
        date_to   = params.get("date_to")

        if report_type in ("pandl", "profit_loss", "pl",
                           "balance_sheet", "bs",
                           "cash_flow", "cashflow"):
            return ac.get_financial_report(
                report_type = report_type,
                date_from   = date_from,
                date_to     = date_to,
                target_move = params.get("target_move", "posted"),
            )

        if report_type == "general_ledger":
            return ac.get_general_ledger(
                date_from = date_from,
                date_to   = date_to,
            )

        if report_type == "trial_balance":
            return ac.get_trial_balance(
                date_from = date_from,
                date_to   = date_to,
            )

        if report_type == "partner_ledger":
            return ac.get_partner_ledger(
                date_from = date_from,
                date_to   = date_to,
                target_moves = params.get("target_move", "posted"),
            )

        if report_type == "partner_ageing":
            return ac.get_partner_ageing(
                date_from        = date_from,
                result_selection = params.get("result_selection", "customer"),
            )

        if report_type == "cost_analysis":
            return ac.get_cost_analysis(
                date_from = date_from,
                date_to   = date_to,
            )

        raise ValueError(f"Unknown accounting report type: {report_type}")

    def _error_result(self, message: str) -> dict[str, Any]:
        return {
            "turn": {
                "error_state": ErrorState(
                    severity    = ErrorSeverity.RECOVERABLE,
                    source_node = "AccountingNode",
                    message     = message,
                ),
            },
        }
