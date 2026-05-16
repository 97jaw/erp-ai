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
    ins.trial.balance → Trial Balance (account_dynamic_reports)
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
        operating_unit_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        """
        Fetches P&L, Balance Sheet, or Cash Flow via AI Gateway method.
        Prefers project.financial.service.get_ai_financial_report(), then ins.financial.report wizard.
        """
        date_from, date_to = self._resolve_dates(date_from, date_to)
        company_id = company_id or 1

        logger.info(
            "[AccountingConnector] Financial report: %s | %s → %s",
            report_type, date_from, date_to
        )

        try:
            raw = self._call_get_ai_financial_report(
                report_type,
                date_from,
                date_to,
                target_move,
                operating_unit_ids,
            )
            return self._normalize_financial_report(raw, report_type, date_from, date_to)
        except Exception as exc:
            logger.info(
                "[AccountingConnector] get_ai_financial_report failed, trying ins wizard: %s",
                exc,
            )

        return self._get_financial_report_via_ins_wizard(
            report_type,
            date_from,
            date_to,
            target_move,
            company_id=company_id,
            analytic_ids=analytic_ids,
            operating_unit_ids=operating_unit_ids,
        )
        
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
        from gateway.pandl_normalize import normalize_pandl_report

        if not isinstance(raw, dict):
            return {"error": "Invalid response from financial report"}

        report_lines = raw.get("report_lines", [])
        clean_lines = []
        for line in report_lines:
            clean_lines.append({
                "name": line.get("name", ""),
                "balance": line.get("balance", 0),
                "debit": line.get("debit", 0),
                "credit": line.get("credit", 0),
                "level": line.get("level", 0),
                "type": line.get("type") or line.get("fin_report_type", ""),
                "style": line.get("style") or line.get("style_type", "main"),
            })

        if report_type in {"pandl", "pl", "profit_loss"}:
            return normalize_pandl_report(
                report_lines=clean_lines,
                date_from=date_from,
                date_to=date_to,
                source="project.financial.service",
                initial_balance=float(raw.get("initial_balance", 0) or 0),
                current_balance=float(raw.get("current_balance", 0) or 0),
                ending_balance=float(raw.get("ending_balance", 0) or 0),
                currency=raw.get("currency"),
            )

        if report_type in {"balance_sheet", "bs"}:
            from gateway.balance_sheet_normalize import normalize_balance_sheet_report

            return normalize_balance_sheet_report(
                report_lines=clean_lines,
                as_of_date=date_to,
                source="project.financial.service",
                initial_balance=float(raw.get("initial_balance", 0) or 0),
                current_balance=float(raw.get("current_balance", 0) or 0),
                ending_balance=float(raw.get("ending_balance", 0) or 0),
            )

        kpis = self._extract_financial_kpis(clean_lines, report_type)
        return {
            "report_type": report_type,
            "report_name": self._report_type_to_name(report_type),
            "date_from": date_from,
            "date_to": date_to,
            "report_lines": clean_lines,
            "kpis": kpis,
            "currency": raw.get("currency"),
            "initial_balance": raw.get("initial_balance", 0),
            "current_balance": raw.get("current_balance", 0),
            "ending_balance": raw.get("ending_balance", 0),
            "source": "project.financial.service",
        }

    def _call_get_ai_financial_report(
        self,
        report_type: str,
        date_from: str,
        date_to: str,
        target_move: str,
        operating_unit_ids: list[int] | None,
    ) -> dict[str, Any]:
        """XML-RPC cannot pass None — use [] for operating units."""
        base_args = [report_type, date_from, date_to, target_move]
        ou_args = operating_unit_ids if operating_unit_ids else []
        try:
            return self.adapter.call_method(
                "project.financial.service",
                "get_ai_financial_report",
                base_args + [ou_args],
            )
        except Exception:
            return self.adapter.call_method(
                "project.financial.service",
                "get_ai_financial_report",
                base_args,
            )

    def _get_financial_report_via_ins_wizard(
        self,
        report_type: str,
        date_from: str,
        date_to: str,
        target_move: str = "posted",
        *,
        company_id: int = 1,
        analytic_ids: list[int] | None = None,
        operating_unit_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        from gateway.pandl_normalize import normalize_pandl_report

        report_ref = FINANCIAL_REPORT_REFS.get(
            report_type.lower().replace(" ", "_"),
            FINANCIAL_REPORT_REFS["pandl"],
        )
        report_id = self._get_report_id(report_ref)
        strict_range = self._company_strict_range(company_id)
        journals = self.adapter.search_read(
            model="account.journal",
            domain=[["company_id", "=", company_id]],
            fields=["id"],
            limit=500,
        )
        journal_ids = [row["id"] for row in journals]
        all_ou_ids: list[int] = []
        try:
            ou_rows = self.adapter.search_read(
                model="operating.unit",
                domain=[["company_id", "=", company_id]],
                fields=["id"],
                limit=500,
            )
            all_ou_ids = [row["id"] for row in ou_rows]
        except Exception as exc:
            logger.info("[AccountingConnector] operating.unit lookup skipped: %s", exc)
        effective_ou_ids = operating_unit_ids if operating_unit_ids else all_ou_ids

        wizard_id = self.adapter.create_record("ins.financial.report", {})
        write_vals: dict[str, Any] = {
            "date_range": False,
            "date_from": date_from,
            "date_to": date_to,
            "account_report_id": report_id,
            "target_move": target_move,
            "debit_credit": True,
            "strict_range": strict_range,
            "enable_filter": False,
            "company_id": company_id,
            "journal_ids": [(6, 0, journal_ids)],
        }
        if analytic_ids:
            write_vals["analytic_ids"] = [(6, 0, analytic_ids)]
        if operating_unit_ids is not None:
            write_vals["operating_unit_ids"] = [(6, 0, operating_unit_ids)]
        else:
            write_vals["operating_unit_ids"] = [(5, 0, 0)]

        read_fields = [
            "date_from",
            "date_to",
            "date_range",
            "account_report_id",
            "target_move",
            "view_format",
            "journal_ids",
            "analytic_ids",
            "analytic_tag_ids",
            "strict_range",
            "company_id",
            "debit_credit",
            "enable_filter",
            "date_from_cmp",
            "date_to_cmp",
            "label_filter",
            "filter_cmp",
        ]

        try:
            self.adapter.write_record("ins.financial.report", [wizard_id], write_vals)
            wizard_rows = self.adapter.search_read(
                model="ins.financial.report",
                domain=[["id", "=", wizard_id]],
                fields=read_fields,
                limit=1,
            )
            if not wizard_rows:
                raise ValueError(f"Wizard ins.financial.report#{wizard_id} not found after write")

            form_data = dict(wizard_rows[0])
            account_report = form_data.get("account_report_id")
            if isinstance(account_report, (list, tuple)):
                form_data["account_report_id"] = account_report[0]
            company_val = form_data.get("company_id")
            if isinstance(company_val, (list, tuple)):
                form_data["company_id"] = company_val[0]

            used_context = {
                "date_from": date_from,
                "date_to": date_to,
                "strict_range": strict_range,
                "company_id": company_id,
                "journal_ids": journal_ids,
                "analytic_account_ids": analytic_ids or [],
                "analytic_tag_ids": [],
                "operating_unit_ids": effective_ou_ids,
                "x_operating_unit_ids": effective_ou_ids,
                "state": target_move,
            }
            form_data["used_context"] = used_context
            form_data["comparison_context"] = {
                "strict_range": strict_range,
                "company_id": company_id,
                "journal_ids": journal_ids,
                "date_from": False,
                "date_to": False,
                "state": target_move,
                "operating_unit_ids": [],
                "x_operating_unit_ids": [],
            }
            form_data["enable_filter"] = False

            # get_report_values embeds Odoo recordsets — not XML-RPC safe.
            # get_account_lines returns plain dicts (same as get_ai_financial_report).
            raw_lines = self.adapter._execute(
                "ins.financial.report",
                "get_account_lines",
                [[wizard_id], form_data],
            )
            if not isinstance(raw_lines, (list, tuple)) or len(raw_lines) < 4:
                raise ValueError(f"Unexpected get_account_lines response: {raw_lines!r}")

            report_lines, initial_balance, current_balance, ending_balance = (
                raw_lines[0],
                raw_lines[1],
                raw_lines[2],
                raw_lines[3],
            )
            clean_lines = []
            for line in report_lines or []:
                clean_lines.append({
                    "name": line.get("name", ""),
                    "balance": line.get("balance", 0),
                    "debit": line.get("debit", 0),
                    "credit": line.get("credit", 0),
                    "level": line.get("level", 0),
                    "type": line.get("fin_report_type", ""),
                    "style": line.get("style_type", "main"),
                })

            raw = {
                "report_lines": clean_lines,
                "initial_balance": initial_balance,
                "current_balance": current_balance,
                "ending_balance": ending_balance,
            }

            if report_type in {"pandl", "pl", "profit_loss"}:
                return normalize_pandl_report(
                    report_lines=clean_lines,
                    date_from=date_from,
                    date_to=date_to,
                    source="ins.financial.report",
                    initial_balance=float(initial_balance or 0),
                    current_balance=float(current_balance or 0),
                    ending_balance=float(ending_balance or 0),
                    applied_filters={
                        "company_id": company_id,
                        "strict_range": strict_range,
                        "operating_unit_ids": effective_ou_ids,
                    },
                )

            if report_type in {"balance_sheet", "bs"}:
                from gateway.balance_sheet_normalize import normalize_balance_sheet_report

                return normalize_balance_sheet_report(
                    report_lines=clean_lines,
                    as_of_date=date_to,
                    source="ins.financial.report",
                    initial_balance=float(initial_balance or 0),
                    current_balance=float(current_balance or 0),
                    ending_balance=float(ending_balance or 0),
                    applied_filters={
                        "company_id": company_id,
                        "strict_range": strict_range,
                        "operating_unit_ids": effective_ou_ids,
                    },
                )

            return self._normalize_financial_report(raw, report_type, date_from, date_to)
        finally:
            self._cleanup_wizard("ins.financial.report", wizard_id)

    def _extract_financial_kpis(
        self, lines: list, report_type: str
    ) -> dict[str, float]:
        from gateway.pandl_normalize import extract_pandl_kpis

        return extract_pandl_kpis(lines)
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
        *,
        company_id: int = 1,
        operating_unit_ids: list[int] | None = None,
        display_accounts: str | None = None,
        include_details: bool = True,
    ) -> dict[str, Any]:
        """
        Fetches General Ledger via AI Gateway or ins.general.ledger wizard.
        """
        from gateway.general_ledger_normalize import normalize_general_ledger

        date_from, date_to = self._resolve_dates(date_from, date_to)
        target = "posted_only" if target_moves in ("posted", "posted_only") else "all_entries"
        if display_accounts is None:
            # Faster default for company-wide GL (matches Odoo wizard default).
            display_accounts = "balance_not_zero" if not account_ids else "all"

        logger.info(
            "[AccountingConnector] General Ledger: %s → %s | accounts=%s display=%s",
            date_from,
            date_to,
            account_ids or "all",
            display_accounts,
        )

        # Prefer server-side get_ai (sanitized for XML-RPC). Raw get_report_datas over RPC
        # fails on company-wide data when line dicts contain None.
        ai_result = self._get_general_ledger_via_ai(
            date_from,
            date_to,
            target,
            company_id=company_id,
            account_ids=account_ids,
            operating_unit_ids=operating_unit_ids,
            display_accounts=display_accounts,
            include_details=include_details,
            initial_balance=initial_balance,
        )
        if ai_result is not None:
            return ai_result

        if not account_ids and not partner_ids and not analytic_ids:
            return {
                "error": True,
                "message": (
                    "Company-wide General Ledger requires "
                    "project.financial.service.get_ai_general_ledger on Odoo "
                    "(deploy elrace_dashboard update). Raw ins.general.ledger wizard "
                    "responses cannot be returned over XML-RPC."
                ),
            }

        return self._get_general_ledger_via_ins_wizard(
            date_from,
            date_to,
            target,
            company_id=company_id,
            account_ids=account_ids,
            partner_ids=partner_ids,
            analytic_ids=analytic_ids,
            operating_unit_ids=operating_unit_ids,
            display_accounts=display_accounts,
            include_details=include_details,
            initial_balance=initial_balance,
        )

    def _get_general_ledger_via_ai(
        self,
        date_from: str,
        date_to: str,
        target_moves: str,
        *,
        company_id: int = 1,
        account_ids: list[int] | None = None,
        operating_unit_ids: list[int] | None = None,
        display_accounts: str = "all",
        include_details: bool = True,
        initial_balance: bool = True,
    ) -> dict[str, Any] | None:
        from gateway.general_ledger_normalize import normalize_general_ledger

        skip_ai = os.environ.get("OOA_GL_SKIP_AI", "").lower() in {"1", "true", "yes"}
        if skip_ai:
            return None

        kwargs: dict[str, Any] = {
            "display_accounts": display_accounts,
            "include_details": include_details,
            "initial_balance": initial_balance,
            "company_id": company_id,
        }
        if account_ids:
            kwargs["account_ids"] = account_ids
        if operating_unit_ids:
            kwargs["operating_unit_ids"] = operating_unit_ids

        raw: Any = None
        for use_kwargs in (True, False):
            if use_kwargs and not kwargs:
                continue
            try:
                raw = self.adapter.call_method(
                    "project.financial.service",
                    "get_ai_general_ledger",
                    [date_from, date_to, target_moves],
                    kwargs if use_kwargs else None,
                )
                break
            except Exception as exc:
                if use_kwargs:
                    if account_ids or operating_unit_ids:
                        logger.info(
                            "[AccountingConnector] get_ai_general_ledger (filtered) "
                            "unavailable — need Odoo deploy: %s",
                            exc,
                        )
                        return None
                    logger.info(
                        "[AccountingConnector] get_ai_general_ledger (kwargs) failed, "
                        "retrying legacy signature: %s",
                        exc,
                    )
                    continue
                logger.warning(
                    "[AccountingConnector] get_ai_general_ledger failed: %s",
                    exc,
                )
                return None

        if not isinstance(raw, dict) or raw.get("accounts") is None:
            return None

        return normalize_general_ledger(
            raw.get("accounts") or {},
            date_from=date_from,
            date_to=date_to,
            source="project.financial.service",
            applied_filters={
                "company_id": company_id,
                "display_accounts": display_accounts,
                "include_details": include_details,
                "initial_balance": initial_balance,
                "account_ids": account_ids,
                "operating_unit_ids": operating_unit_ids,
            },
        )

    def _get_general_ledger_via_ins_wizard(
        self,
        date_from: str,
        date_to: str,
        target_moves: str = "posted_only",
        *,
        company_id: int = 1,
        account_ids: list[int] | None = None,
        partner_ids: list[int] | None = None,
        analytic_ids: list[int] | None = None,
        operating_unit_ids: list[int] | None = None,
        display_accounts: str = "all",
        include_details: bool = True,
        initial_balance: bool = True,
    ) -> dict[str, Any]:
        from gateway.general_ledger_normalize import normalize_general_ledger

        if account_ids:
            account_ids = self._validate_ids(
                "account.account",
                account_ids,
                label="account_ids",
            )
        if partner_ids:
            partner_ids = self._validate_ids("res.partner", partner_ids, label="partner_ids")
        if analytic_ids:
            analytic_ids = self._validate_ids(
                "account.analytic.account",
                analytic_ids,
                label="analytic_ids",
            )
        if operating_unit_ids:
            operating_unit_ids = self._validate_ids(
                "operating.unit",
                operating_unit_ids,
                label="operating_unit_ids",
            )

        wizard_vals: dict[str, Any] = {
            "date_range": False,
            "date_from": date_from,
            "date_to": date_to,
            "target_moves": target_moves,
            "initial_balance": initial_balance,
            "include_details": include_details,
            "display_accounts": display_accounts,
            "company_id": company_id,
        }
        if account_ids:
            wizard_vals["account_ids"] = [(6, 0, account_ids)]
        if partner_ids:
            wizard_vals["partner_ids"] = [(6, 0, partner_ids)]
        if analytic_ids:
            wizard_vals["analytic_ids"] = [(6, 0, analytic_ids)]
        if operating_unit_ids:
            wizard_vals["operating_unit_ids"] = [(6, 0, operating_unit_ids)]

        wizard_id = self.adapter.create_record("ins.general.ledger", wizard_vals)
        try:
            raw = self.adapter.execute_action(
                "ins.general.ledger",
                "get_report_datas",
                [wizard_id],
            )
            if not isinstance(raw, (list, tuple)) or len(raw) < 2:
                raise ValueError(f"Unexpected get_report_datas response: {raw!r}")

            filters, account_lines = raw[0], raw[1]
            return normalize_general_ledger(
                account_lines or {},
                date_from=date_from,
                date_to=date_to,
                source="ins.general.ledger",
                filters=filters if isinstance(filters, dict) else {},
                applied_filters={
                    "company_id": company_id,
                    "display_accounts": display_accounts,
                    "include_details": include_details,
                    "initial_balance": initial_balance,
                },
            )
        finally:
            self._cleanup_wizard("ins.general.ledger", wizard_id)
        
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
    def get_trial_balance(
        self,
        date_from=None,
        date_to=None,
        target_moves="posted",
        *,
        company_id: int = 1,
        display_accounts: str = "all",
        operating_unit_ids: list[int] | None = None,
        journal_ids: list[int] | None = None,
        account_ids: list[int] | None = None,
        strict_range: bool | None = None,
        show_hierarchy: bool = False,
    ):
        date_from, date_to = self._resolve_dates(date_from, date_to)
        try:
            from gateway.accounting_sql.connection import accounting_sql_enabled
            from gateway.accounting_sql.query_accounting import execute_query_accounting

            if accounting_sql_enabled():
                sql_result = execute_query_accounting({
                    "report_type": "trial_balance",
                    "date_from": date_from,
                    "date_to": date_to,
                    "company_id": 1,
                })
                if not sql_result.get("error"):
                    return sql_result
                logger.warning(
                    "[AccountingConnector] SQL trial balance unavailable, falling back: %s",
                    sql_result.get("message"),
                )
        except Exception as exc:
            logger.info("[AccountingConnector] SQL trial balance path skipped: %s", exc)

        try:
            return self._get_trial_balance_via_ins_wizard(
                date_from,
                date_to,
                target_moves,
                company_id=company_id,
                display_accounts=display_accounts,
                operating_unit_ids=operating_unit_ids,
                journal_ids=journal_ids,
                account_ids=account_ids,
                strict_range=strict_range,
                show_hierarchy=show_hierarchy,
            )
        except Exception as exc:
            logger.info("[AccountingConnector] ins.trial.balance wizard failed: %s", exc)

        try:
            api_result = self.adapter.call_method(
                "project.financial.service",
                "get_ai_trial_balance",
                [date_from, date_to, target_moves],
            )
            return self._normalize_ai_trial_balance_api(api_result, date_from, date_to)
        except Exception as exc:
            logger.info("[AccountingConnector] Falling back to synthesized trial balance: %s", exc)
            from gateway.aggregate_tools import synthesize_trial_balance

            return synthesize_trial_balance(self.adapter, date_from, date_to)

    def _get_trial_balance_via_ins_wizard(
        self,
        date_from: str,
        date_to: str,
        target_moves: str = "posted",
        *,
        company_id: int = 1,
        display_accounts: str = "all",
        operating_unit_ids: list[int] | None = None,
        journal_ids: list[int] | None = None,
        account_ids: list[int] | None = None,
        strict_range: bool | None = None,
        show_hierarchy: bool = False,
    ) -> dict[str, Any]:
        """Uses account_dynamic_reports ins.trial.balance — same engine as Odoo UI."""
        from gateway.trial_balance_normalize import normalize_ins_trial_balance

        target = "posted_only" if target_moves in ("posted", "posted_only") else "all_entries"
        if strict_range is None:
            strict_range = self._company_strict_range(company_id)

        # Create empty wizard, then write filters like the UI "Apply" button (dynamic.tb).
        wizard_id = self.adapter.create_record("ins.trial.balance", {})
        write_vals: dict[str, Any] = {
            "date_range": False,
            "date_from": date_from,
            "date_to": date_to,
            "target_moves": target,
            "display_accounts": display_accounts,
            "company_id": company_id,
            "strict_range": strict_range,
            "show_hierarchy": show_hierarchy,
        }
        if operating_unit_ids is not None:
            write_vals["operating_unit_ids"] = [(6, 0, operating_unit_ids)]
        if journal_ids is not None:
            write_vals["journal_ids"] = [(6, 0, journal_ids)]
        if account_ids is not None:
            write_vals["account_ids"] = [(6, 0, account_ids)]

        try:
            self.adapter.write_record("ins.trial.balance", [wizard_id], write_vals)
            raw = self.adapter.execute_action(
                "ins.trial.balance",
                "get_report_datas",
                [wizard_id],
            )
            if not isinstance(raw, (list, tuple)) or len(raw) < 4:
                raise ValueError(f"Unexpected get_report_datas response: {raw!r}")

            filters, account_lines, retained, subtotal = raw[0], raw[1], raw[2], raw[3]
            result = normalize_ins_trial_balance(
                date_from=date_from,
                date_to=date_to,
                filters=filters,
                account_lines=account_lines,
                retained=retained,
                subtotal=subtotal,
            )
            result["applied_filters"] = {
                "company_id": company_id,
                "display_accounts": display_accounts,
                "strict_range": strict_range,
                "show_hierarchy": show_hierarchy,
                "operating_unit_ids": operating_unit_ids,
                "journal_ids": journal_ids,
                "account_ids": account_ids,
                "odoo_filters": filters,
            }
            return result
        finally:
            self._cleanup_wizard("ins.trial.balance", wizard_id)

    def _validate_ids(self, model: str, ids: list[int], *, label: str) -> list[int]:
        if not ids:
            return []
        rows = self.adapter.search_read(
            model=model,
            domain=[["id", "in", ids]],
            fields=["id"],
            limit=len(ids),
        )
        found = {row["id"] for row in rows}
        missing = [value for value in ids if value not in found]
        if missing:
            raise ValueError(
                f"Invalid {label}: no records in {model} for id(s) {missing}. "
                "Use a real Odoo database id (from account.account), not the account code."
            )
        return ids

    def _company_strict_range(self, company_id: int) -> bool:
        rows = self.adapter.search_read(
            model="res.company",
            domain=[["id", "=", company_id]],
            fields=["strict_range"],
            limit=1,
        )
        if rows:
            return bool(rows[0].get("strict_range"))
        return False

    def _normalize_ai_trial_balance_api(
        self,
        raw: dict[str, Any],
        date_from: str,
        date_to: str,
    ) -> dict[str, Any]:
        accounts = raw.get("accounts") or {}
        rows: list[list[Any]] = []
        total_debit = 0.0
        total_credit = 0.0
        for code, acc in accounts.items():
            debit = float(acc.get("debit", 0) or 0)
            credit = float(acc.get("credit", 0) or 0)
            balance = float(acc.get("balance", 0) or 0)
            if debit == 0 and credit == 0 and balance == 0:
                continue
            label = acc.get("name") or code
            rows.append([f"{code} {label}".strip(), round(debit, 2), round(credit, 2), round(balance, 2)])
            total_debit += debit
            total_credit += credit
        rows.append(["Total", round(total_debit, 2), round(total_credit, 2), round(total_debit - total_credit, 2)])
        return {
            "report_type": "trial_balance",
            "report_name": "Trial Balance",
            "date_from": date_from,
            "date_to": date_to,
            "row_count": max(len(rows) - 1, 0),
            "totals": {
                "debit": round(total_debit, 2),
                "credit": round(total_credit, 2),
                "difference": round(total_debit - total_credit, 2),
                "balanced": abs(total_debit - total_credit) < 0.05,
            },
            "rows": rows,
            "data": {
                "headers": ["Account", "Debit", "Credit", "Balance"],
                "rows": rows,
            },
            "accounts": accounts,
            "source": "project.financial.service",
            "synthesized": False,
        }

    def get_partner_ledger(self, date_from=None, date_to=None, partner_ids=None, target_moves="posted"):
        """Requires get_ai_partner_ledger() gateway method in Odoo."""
        raise NotImplementedError(
            "Add get_ai_partner_ledger() to project.financial.service in Odoo first."
        )

    def get_partner_ageing(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        as_of_date: str | None = None,
        result_selection: str = "customer",
        ageing_by: str = "due_date",
        partner_ids: list[int] | None = None,
        *,
        company_id: int = 1,
        operating_unit_ids: list[int] | None = None,
        include_details: bool = False,
    ) -> dict[str, Any]:
        """
        Partner Ageing (receivable / payable buckets) via AI Gateway or ins wizard.
        """
        from gateway.accounting_sql.dates import resolve_as_of_date
        from gateway.partner_ageing_normalize import normalize_partner_ageing

        as_on = resolve_as_of_date(as_of_date or date_to, date_from)
        logger.info(
            "[AccountingConnector] Partner Ageing: as_of=%s selection=%s partners=%s",
            as_on,
            result_selection,
            partner_ids or "all",
        )

        if partner_ids:
            partner_ids = self._validate_ids(
                "res.partner",
                partner_ids,
                label="partner_ids",
            )
        if operating_unit_ids:
            operating_unit_ids = self._validate_ids(
                "operating.unit",
                operating_unit_ids,
                label="operating_unit_ids",
            )

        applied_filters = {
            "as_of_date": as_on,
            "result_selection": result_selection,
            "ageing_by": ageing_by,
            "company_id": company_id,
            "partner_ids": partner_ids,
            "operating_unit_ids": operating_unit_ids,
            "include_details": include_details,
        }

        call_kwargs: dict[str, Any] = {
            "as_on_date": as_on,
            "result_selection": result_selection,
            "company_id": company_id,
            "include_details": include_details,
        }
        if partner_ids:
            call_kwargs["partner_ids"] = partner_ids
        if operating_unit_ids:
            call_kwargs["operating_unit_ids"] = operating_unit_ids

        legacy_kwargs = {
            "date_from": as_on,
            "result_selection": result_selection,
        }

        raw: Any = None
        for attempt_kwargs in (call_kwargs, legacy_kwargs):
            try:
                # Pass date only via kwargs — positional [as_on] duplicates as_on_date on Odoo.
                raw = self.adapter.call_method(
                    "project.financial.service",
                    "get_ai_partner_ageing",
                    [],
                    attempt_kwargs,
                )
                break
            except Exception as exc:
                if attempt_kwargs is call_kwargs:
                    logger.info(
                        "[AccountingConnector] get_ai_partner_ageing (full) failed, "
                        "retrying legacy signature: %s",
                        exc,
                    )
                    continue
                logger.warning(
                    "[AccountingConnector] get_ai_partner_ageing failed: %s",
                    exc,
                )
                return {
                    "error": True,
                    "message": (
                        "Partner Ageing requires project.financial.service.get_ai_partner_ageing "
                        f"on Odoo (deploy elrace_dashboard). {exc}"
                    ),
                }

        if not isinstance(raw, dict):
            return {
                "error": True,
                "message": f"Unexpected partner ageing response: {raw!r}",
            }

        return normalize_partner_ageing(
            raw,
            source="project.financial.service",
            applied_filters=applied_filters,
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
