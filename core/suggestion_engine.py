"""
OOA Core — Suggestion Engine
==============================
File    : core/suggestion_engine.py
Author  : Lead Backend Developer
Version : 1.0.0

Generates 2-3 contextual follow-up suggestions after every response.
Rule-based for known contexts, Claude-powered for dynamic contexts.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from core.state import IntentType, VisualType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixed suggestion rules by context
# ---------------------------------------------------------------------------

FIXED_SUGGESTIONS = {

    # Project financial queries
    ("KPI", "project.financial.service", "get_project_expense_dashboard"): [
        "Show cost breakdown by category",
        "Compare actual cost with budget",
        "Show weekly spending trend",
    ],
    ("KPI", "project.financial.service", "get_project_financial_data"): [
        "Show cost distribution (LPO, Petty Cash, Labor)",
        "Show top expense accounts",
        "Compare income vs expenses",
    ],

    # Sales queries
    ("KPI", "sale.order", None): [
        "Show sales by month",
        "Compare with previous period",
        "Show top customers by revenue",
    ],
    ("RAG", "sale.order", None): [
        "Show total value of these orders",
        "Filter by date range",
        "Show overdue orders only",
    ],

    # HR queries
    ("KPI", "hr.payslip", None): [
        "Show payroll breakdown by department",
        "Compare with last month",
        "Show individual employee payslips",
    ],
    ("RAG", "hr.employee", None): [
        "Show employee count by department",
        "Show employees on leave",
        "Show payroll summary",
    ],

    # Accounting queries
    ("KPI", "account.move", None): [
        "Show unpaid invoices",
        "Break down by customer",
        "Show monthly trend",
    ],
    ("RAG", "account.move", None): [
        "Show total amount of these invoices",
        "Filter by payment status",
        "Show overdue invoices only",
    ],

    # Project list queries
    ("RAG", "project.project", None): [
        "Show financial summary for a specific project",
        "Filter projects by client",
        "Show projects exceeding budget",
    ],
    ("ACCOUNTING", "ins.financial.report", "get_report_values"): [
        "Show balance sheet",
        "Show general ledger",
        "Compare with last month",
    ],
    ("ACCOUNTING", "ins.general.ledger", "get_report_datas"): [
        "Show trial balance",
        "Filter by specific account",
        "Show profit and loss",
    ],
    ("ACCOUNTING", "ins.partner.ageing", "get_report_datas"): [
        "Show partner ledger details",
        "Show overdue invoices only",
        "Show profit and loss",
    ],
}

# Fallback suggestions when no rule matches
FALLBACK_SUGGESTIONS = {
    "en": [
        "Show more details",
        "Filter by date range",
        "Export this data",
    ],
    "ar": [
        "عرض مزيد من التفاصيل",
        "تصفية حسب نطاق التاريخ",
        "تصدير هذه البيانات",
    ],
    "ur": [
        "مزید تفصیلات دکھائیں",
        "تاریخ کی حد کے مطابق فلٹر کریں",
        "یہ ڈیٹا ایکسپورٹ کریں",
    ],
}


# ---------------------------------------------------------------------------
# Suggestion Engine
# ---------------------------------------------------------------------------

class SuggestionEngine:
    """
    Generates contextual follow-up suggestions.

    Strategy:
        1. Check fixed rules by (intent, domain, method)
        2. Check fixed rules by (intent, domain, None)
        3. Fall back to language-aware generic suggestions
    """

    def generate(
        self,
        intent_type  : str,
        active_domain: str | None,
        method       : str | None = None,
        language     : str = "en",
        response_data: Any = None,
    ) -> list[str]:
        """
        Generates 2-3 contextual suggestions.

        Args:
            intent_type   : "KPI", "RAG", "WRITE", "AMBIGUOUS"
            active_domain : Odoo model name
            method        : Specific method called (optional)
            language      : User language for translation
            response_data : The actual response data (for dynamic suggestions)

        Returns:
            List of 2-3 suggestion strings in user's language.
        """
        # --- Try exact match with method ---
        key = (intent_type, active_domain, method)
        suggestions = FIXED_SUGGESTIONS.get(key)

        # --- Try match without method ---
        if not suggestions:
            key = (intent_type, active_domain, None)
            suggestions = FIXED_SUGGESTIONS.get(key)

        # --- Fallback ---
        if not suggestions:
            lang = language if language in ("en", "ar", "ur") else "en"
            suggestions = FALLBACK_SUGGESTIONS.get(lang, FALLBACK_SUGGESTIONS["en"])

        # Translate to user language if suggestions are in English
        if language in ("ar", "ur") and suggestions:
            suggestions = self._translate_suggestions(
                suggestions, language
            )

        return suggestions[:3]

    def _translate_suggestions(
        self,
        suggestions: list[str],
        language   : str,
    ) -> list[str]:
        """Translates English suggestions to Arabic or Urdu."""
        try:
            import anthropic
            client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY")
            )
            joined  = "\n".join(f"{i+1}. {s}" for i, s in enumerate(suggestions))
            lang_name = "Arabic" if language == "ar" else "Urdu"

            message = client.messages.create(
                model      = "claude-sonnet-4-20250514",
                max_tokens = 200,
                messages   = [{
                    "role"   : "user",
                    "content": (
                        f"Translate these suggestions to {lang_name}. "
                        f"Keep them short and actionable. "
                        f"Reply with ONLY the numbered translations:\n{joined}"
                    ),
                }],
            )

            lines = message.content[0].text.strip().split("\n")
            translated = []
            for line in lines:
                # Strip number prefix
                clean = line.strip()
                if clean and clean[0].isdigit():
                    clean = clean[2:].strip() if len(clean) > 2 else clean
                if clean:
                    translated.append(clean)

            return translated[:3] if translated else suggestions

        except Exception as exc:
            logger.error("[SuggestionEngine] Translation failed: %s", exc)
            return suggestions
