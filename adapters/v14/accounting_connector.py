"""
OOA Phase 4 — Accounting Connector
=====================================
File    : adapters/v14/accounting_connector.py
Author  : Lead Backend Developer
Version : 1.0.0

Handles all TransientModel accounting report calls.
Pattern: CREATE wizard record → CALL computation method → RETURN data

Supports:
    ins.financial.report     → P&L, Balance Sheet, Cash Flow
    ins.general.ledger       → General Ledger
    ins.report.trial.balance → Trial Balance
    ins.partner.ledger       → Partner Ledger
    ins.partner.ageing       → Partner Ageing
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Report Type Registry
# ---------------------------------------------------------------------------

# Maps human report types to Odoo XML IDs
# These are fetched dynamically from Odoo on first use
FINANCIAL_REPORT_REFS = {
    "pandl"        : "account_dynamic_reports.ins_account_financial_report_profitandloss0",
    "profit_loss"  : "account_dynamic_reports.ins_account_financial_report_profitandloss0",
    "pl"           : "account_dynamic_reports.ins_account_financial_report_profitandloss0",
    "balance_sheet": "account_dynamic_reports.ins_account_financial_report_balancesheet0",
    "bs"           : "account_dynamic_reports.ins_account_financial_report_balancesheet0",
    "cash_flow"    : "account_dynamic_reports.ins_account_financial_report_cash_flow0",
    "cashflow"     : "account_dynamic_reports.ins_account_financial_report_cash_flow0",
}

# Default date ranges
DATE_RANGE_DEFAULTS = {
    "this_month"   : "this_month",
    "last_month"   : "last_month",
    "this_quarter" : "this_quarter",
    "last_quarter" : "last_quarter",
    "this_year"    : "this_financial_year",
    "last_year"    : "last_financial_year",
    "ytd"          : "this_financial_year",
}


class AccountingConnector:
    """
    Wraps all TransientModel accounting report calls.

    Each method follows the pattern:
        1. Resolve report parameters
        2. Create wizard record via create_record
        3. Call computation method via execute_action
        4. Normalize and return structured data
        5. Clean up wizard record
    """

    def __init__(self, adapter) -> None:
        """
        Args:
            adapter: BaseOdooAdapter instance (v14 connector)
        """
        self.adapter = adapter
        self._report_id_cache: dict[str, int] = {}

    # -----------------------------------------------------------------------
    # 1. Financial Report (P&L, Balance Sheet, Cash Flow)
    # -----------------------------------------------------------------------
    def get_financial_report(
        self,
        report_type : str = "pandl",
        date_from   : str | None = None,
        date_to     : str | None = None,
        target_move : str = "posted",
        company_id  : int | None = None,
        analytic_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        Fetches P&L, Balance Sheet, or Cash Flow via AI Gateway method.
        Calls project.financial.service.get_ai_financial_report()
        """
        date_from, date_to = self._resolve_dates(date_from, date_to)

        logger.info(
            "[AccountingConnector] Financial report: %s | %s → %s",
            report_type, date_from, date_to
        )

        raw = self.adapter.call_method(
            "project.financial.service",
            "get_ai_financial_report",
            [report_type, date_from, date_to, target_move],
        )

        return self._normalize_financial_report(raw, report_type, date_from, date_to)
        
    def backup_get_financial_report(
        self,
        report_type : str = "pandl",
        date_from   : str | None = None,
        date_to     : str | None = None,
        target_move : str = "posted",
        company_id  : int | None = None,
        analytic_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        Fetches P&L, Balance Sheet, or Cash Flow report.

        Args:
            report_type : "pandl", "balance_sheet", "cash_flow"
            date_from   : "YYYY-MM-DD" or None (defaults to month start)
            date_to     : "YYYY-MM-DD" or None (defaults to today)
            target_move : "posted" or "all"

        Returns:
            {
                "report_type" : "pandl",
                "report_name" : "Profit and Loss",
                "date_from"   : "2026-01-01",
                "date_to"     : "2026-03-31",
                "report_lines": [...],
                "kpis"        : {"total_income": ..., "total_expense": ..., "net_profit": ...}
            }
        """
        date_from, date_to = self._resolve_dates(date_from, date_to)

        # Get report ID from Odoo
        report_ref = FINANCIAL_REPORT_REFS.get(
            report_type.lower().replace(" ", "_"),
            FINANCIAL_REPORT_REFS["pandl"]
        )
        report_id = self._get_report_id(report_ref)

        logger.info(
            "[AccountingConnector] Financial report: %s | %s → %s",
            report_type, date_from, date_to
        )

        # Step 1: Build wizard values
        wizard_vals = {
            "date_from"         : date_from,
            "date_to"           : date_to,
            "account_report_id" : report_id,
            "target_move"       : target_move,
            "debit_credit"      : True,
            "strict_range"      : True,
            "enable_filter"     : False,
            # Do NOT pass analytic_ids — causes serialization error
            # analytic_ids is a Many2many that returns recordset objects
        }
        if analytic_ids:
            wizard_vals["analytic_ids"] = [(6, 0, analytic_ids)]

        # Step 2: Create wizard record
        wizard_id = self.adapter.create_record(
            "ins.financial.report", wizard_vals
        )

        try:
            # Step 3: Call computation method
            raw = self.adapter.execute_action(
                "ins.financial.report",
                "get_report_values",
                [wizard_id],
            )

            # Step 4: Normalize
            return self._normalize_financial_report(raw, report_type, date_from, date_to)

        finally:
            # Step 5: Clean up wizard record
            self._cleanup_wizard("ins.financial.report", wizard_id)

    def _normalize_financial_report(
        self,
        raw        : Any,
        report_type: str,
        date_from  : str,
        date_to    : str,
    ) -> dict[str, Any]:
        """Normalizes raw financial report data into clean structure."""
        if not isinstance(raw, dict):
            return {"error": "Invalid response from financial report"}

        report_lines = raw.get("report_lines", [])

        # Extract KPIs from report lines
        kpis = self._extract_financial_kpis(report_lines, report_type)

        # Build clean lines for visualization
        clean_lines = []
        for line in report_lines:
            clean_lines.append({
                "name"   : line.get("name", ""),
                "balance": line.get("balance", 0),
                "debit"  : line.get("debit", 0),
                "credit" : line.get("credit", 0),
                "level"  : line.get("level", 0),
                "type"   : line.get("fin_report_type", ""),
                "style"  : line.get("style_type", "main"),
            })

        return {
            "report_type"   : report_type,
            "report_name"   : self._report_type_to_name(report_type),
            "date_from"     : date_from,
            "date_to"       : date_to,
            "report_lines"  : clean_lines,
            "kpis"          : kpis,
            "currency"      : raw.get("currency"),
            "initial_balance": raw.get("initial_balance", 0),
            "current_balance": raw.get("current_balance", 0),
            "ending_balance" : raw.get("ending_balance", 0),
        }

    def _extract_financial_kpis(
        self, lines: list, report_type: str
    ) -> dict[str, float]:
        """Extracts summary KPIs from report lines — level 1 only."""
        kpis = {
            "total_income" : 0.0,
            "total_expense": 0.0,
            "net_profit"   : 0.0,
            "margin"       : 0.0,
        }
        if not lines:
            return kpis

        for line in lines:
            name    = (line.get("name") or "").lower().strip()
            balance = line.get("balance", 0) or 0
            level   = line.get("level", 0)

            # Only process level 1 lines — top sections
            if level != 1:
                continue

            if any(k in name for k in ("income", "revenue", "sales")):
                # Income in Odoo is stored as negative (credit balance)
                # Take absolute value for display
                kpis["total_income"] = abs(balance)

            elif any(k in name for k in ("expense", "cost", "expenditure")):
                kpis["total_expense"] = abs(balance)

        kpis["net_profit"] = kpis["total_income"] - kpis["total_expense"]
        kpis["margin"]     = round(
            (kpis["net_profit"] / kpis["total_income"] * 100)
            if kpis["total_income"] else 0,
            2,
        )
        return kpis
    # -----------------------------------------------------------------------
    # 2. General Ledger
    # -----------------------------------------------------------------------
    def get_general_ledger(
        self,
        date_from   : str | None = None,
        date_to     : str | None = None,
        account_ids : list[int] | None = None,
        partner_ids : list[int] | None = None,
        analytic_ids: list[int] | None = None,
        target_moves: str = "posted",
        initial_balance: bool = True,
    ) -> dict[str, Any]:
        """
        Fetches General Ledger via AI Gateway method.
        Calls project.financial.service.get_ai_general_ledger()
        """
        date_from, date_to = self._resolve_dates(date_from, date_to)

        logger.info(
            "[AccountingConnector] General Ledger: %s → %s",
            date_from, date_to
        )

        raw = self.adapter.call_method(
            "project.financial.service",
            "get_ai_general_ledger",
            [date_from, date_to, target_moves],
        )

        return raw
        
    def backup_get_general_ledger(
        self,
        date_from   : str | None = None,
        date_to     : str | None = None,
        account_ids : list[int] | None = None,
        partner_ids : list[int] | None = None,
        analytic_ids: list[int] | None = None,
        target_moves: str = "posted",
        initial_balance: bool = True,
    ) -> dict[str, Any]:
        """
        Fetches General Ledger report.

        Returns:
            {
                "accounts": {
                    "1010": {
                        "name": "Cash",
                        "debit": 50000,
                        "credit": 30000,
                        "balance": 20000,
                        "lines": [...]
                    }
                },
                "date_from": "...",
                "date_to"  : "..."
            }
        """
        date_from, date_to = self._resolve_dates(date_from, date_to)

        logger.info(
            "[AccountingConnector] General Ledger: %s → %s",
            date_from, date_to
        )

        wizard_vals = {
            "date_from"      : date_from,
            "date_to"        : date_to,
            "target_moves"   : target_moves,
            "initial_balance": initial_balance,
            "display_accounts": "all",
            "include_details": True,
        }
        if account_ids:
            wizard_vals["account_ids"] = [(6, 0, account_ids)]
        if partner_ids:
            wizard_vals["partner_ids"] = [(6, 0, partner_ids)]
        if analytic_ids:
            wizard_vals["analytic_ids"] = [(6, 0, analytic_ids)]

        wizard_id = self.adapter.create_record("ins.general.ledger", wizard_vals)

        try:
            raw_filters, raw_lines = self.adapter.execute_action(
                "ins.general.ledger",
                "get_report_datas",
                [wizard_id],
            )
            return {
                "report_type": "general_ledger",
                "report_name": "General Ledger",
                "date_from"  : date_from,
                "date_to"    : date_to,
                "accounts"   : raw_lines or {},
                "filters"    : raw_filters or {},
            }
        finally:
            self._cleanup_wizard("ins.general.ledger", wizard_id)

    # -----------------------------------------------------------------------
    # 3. Trial Balance
    # -----------------------------------------------------------------------
    def get_trial_balance(self, date_from=None, date_to=None, target_moves="posted"):
        """Requires get_ai_trial_balance() gateway method in Odoo."""
        raise NotImplementedError(
            "Add get_ai_trial_balance() to project.financial.service in Odoo first."
        )

    def get_partner_ledger(self, date_from=None, date_to=None, partner_ids=None, target_moves="posted"):
        """Requires get_ai_partner_ledger() gateway method in Odoo."""
        raise NotImplementedError(
            "Add get_ai_partner_ledger() to project.financial.service in Odoo first."
        )

    def get_partner_ageing(self, date_from=None, result_selection="customer", ageing_by="due_date", partner_ids=None):
        """Requires get_ai_partner_ageing() gateway method in Odoo."""
        raise NotImplementedError(
            "Add get_ai_partner_ageing() to project.financial.service in Odoo first."
        )
    # -----------------------------------------------------------------------
    # Helper Methods
    # -----------------------------------------------------------------------

    def _resolve_dates(
        self,
        date_from: str | None,
        date_to  : str | None,
    ) -> tuple[str, str]:
        """Resolves None dates to sensible defaults."""
        today = datetime.today()
        if not date_to:
            date_to = today.strftime("%Y-%m-%d")
        if not date_from:
            date_from = today.replace(day=1).strftime("%Y-%m-%d")
        return date_from, date_to

    def _get_report_id(self, xml_ref: str) -> int:
        """Fetches report ID from Odoo XML ref. Cached after first fetch."""
        if xml_ref in self._report_id_cache:
            return self._report_id_cache[xml_ref]

        module, ref_name = xml_ref.split(".")
        records = self.adapter.search_read(
            model  = "ir.model.data",
            domain = [
                ["module", "=", module],
                ["name",   "=", ref_name],
            ],
            fields = ["res_id"],
            limit  = 1,
        )
        if not records:
            raise ValueError(
                f"Could not find Odoo report reference: {xml_ref}"
            )
        report_id = records[0]["res_id"]
        self._report_id_cache[xml_ref] = report_id
        logger.info("[AccountingConnector] Resolved %s → id=%d", xml_ref, report_id)
        return report_id

    def _cleanup_wizard(self, model: str, wizard_id: int) -> None:
        """Deletes the TransientModel wizard record after use."""
        try:
            self.adapter.execute_action(model, "unlink", [wizard_id])
        except Exception as exc:
            logger.warning(
                "[AccountingConnector] Could not cleanup wizard %s#%d: %s",
                model, wizard_id, exc,
            )

    def _report_type_to_name(self, report_type: str) -> str:
        names = {
            "pandl"        : "Profit & Loss",
            "profit_loss"  : "Profit & Loss",
            "pl"           : "Profit & Loss",
            "balance_sheet": "Balance Sheet",
            "bs"           : "Balance Sheet",
            "cash_flow"    : "Cash Flow Statement",
            "cashflow"     : "Cash Flow Statement",
        }
        return names.get(report_type.lower(), "Financial Report")
