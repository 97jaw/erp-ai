"""Deep Think eligibility detection.

Deep Think = predefined Odoo financial methods + AI synthesis. A query is
eligible when it asks for real ERP figures: financial reports, project
expenses, ledgers, ageing, comparisons. Keyword-based (no LLM) so the
frontend can check eligibility cheaply on keystrokes.
"""

from __future__ import annotations

import re

_FINANCIAL_REPORT_RE = re.compile(
    r"\b("
    r"p\s*&?\s*l|pnl|profit\s+(and|&)\s+loss|profit|loss|income\s+statement|"
    r"balance\s+sheet|trial\s+balance|general\s+ledger|cash\s*flow|"
    r"financial\s+report|revenue|income|turnover|"
    r"ageing|aging|receivables?|payables?|ledger|"
    r"expenses?|costs?|spend(ing)?|budget"
    r")\b"
    r"|أرباح|خسائر|ميزان|ميزانية|تقرير\s+مالي|مصروف|مصاريف|ايراد|إيراد|"
    r"دفتر|ذمم|تكلفة|تكاليف",
    re.IGNORECASE,
)

_ENTITY_DATA_RE = re.compile(
    r"\b("
    r"project|villa|school|maintenance|partner|client|vendor|customer|"
    r"invoice|payment|journal|account|wo|work\s*order|"
    r"compare|breakdown|break\s+down|drill\s*down|summary|total"
    r")\b"
    r"|مشروع|فيلا|مدرسة|صيانة|عميل|مورد|فاتورة|مقارنة|ملخص|إجمالي",
    re.IGNORECASE,
)

_CONVERSATIONAL_BLOCK_RE = re.compile(
    r"^\s*(hi+|hello|hey+|thanks?|thank\s+you|ok(ay)?|bye|goodbye|"
    r"مرحبا|اهلا|أهلا|شكرا|شكراً)[\s!.,؟?]*$",
    re.IGNORECASE,
)


def is_deep_think_eligible(message: str) -> bool:
    """True when the query warrants pulling real figures via predefined Odoo methods."""
    from gateway.core.project_profile_routing import is_project_profile_text

    text = (message or "").strip()
    if len(text) < 3:
        return False
    if _CONVERSATIONAL_BLOCK_RE.match(text):
        return False
    # Project header/profile questions are served by a direct ORM read in
    # normal mode — they never need Deep Think.
    if is_project_profile_text(text):
        return False
    if _FINANCIAL_REPORT_RE.search(text):
        return True
    return bool(_ENTITY_DATA_RE.search(text))
