"""
OOA Phase 2 — Intent Classifier Node (Production Rewrite)
===========================================================
File    : core/nodes/intent_node.py
Author  : Lead Backend Developer
Version : 2.0.0

Single Claude call that classifies intent AND extracts all parameters.
Works for any phrasing in English or Arabic — no phrase matching.

Intent types:
    RAG        : Fetch/search specific records
    KPI        : Project analytics via project.financial.service
    ACCOUNTING : Financial reports via ins.financial.report and related
    WRITE      : Create/update records
    AMBIGUOUS  : Needs clarification
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from gateway.model_config import AGENT_MODEL

from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
    IntentRecord,
    IntentType,
)

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_CONFIDENCE_THRESHOLD = 0.75

# ---------------------------------------------------------------------------
# Master Classification Prompt
# ---------------------------------------------------------------------------

MASTER_PROMPT = """You are the intent classifier for an Odoo ERP AI assistant.
Company: Construction & Facilities Management company in UAE.
Today: {today}
User language: {user_language}
Active domain: {active_domain}
Last intent: {last_intent}
Turn: {turn_number}

Conversation history:
{history}

User input: "{raw_input}"

INTENT TYPES:

1. RAG — Fetch or search specific records from Odoo
   Examples: "show me invoices", "find employee Ahmed", "list active projects",
             "أظهر الفواتير", "ابحث عن موظف", "قائمة المشاريع"

2. KPI — Project financial analytics (uses project.financial.service)
   Examples: "total cost for project X", "expense report for project Y",
             "profit margin of Al Barsha Tower", "cost breakdown for project Z",
             "weekly spending trend", "budget status",
             "تكاليف مشروع", "تقرير مصروفات المشروع", "هامش الربح للمشروع"
   NOTE: KPI always requires a SPECIFIC PROJECT to be mentioned or in context.

3. ACCOUNTING — Company-wide financial reports (NOT project-specific)
   Examples: "profit and loss", "P&L", "balance sheet", "cash flow statement",
             "general ledger", "trial balance", "partner ageing", "partner ledger",
             "who owes us money", "outstanding receivables", "income statement",
             "الأرباح والخسائر", "قائمة الدخل", "الميزانية العمومية",
             "التدفق النقدي", "دفتر الأستاذ", "ميزان المراجعة",
             "تقادم الذمم", "كشف حساب الشركاء", "المستحقات"
   Report types: pandl, balance_sheet, cash_flow, general_ledger,
                 trial_balance, partner_ledger, partner_ageing

4. WRITE — Create or update records
   Examples: "create invoice", "confirm delivery", "إنشاء فاتورة"

5. AMBIGUOUS — Cannot determine intent clearly

6. GENERAL — Questions Claude can answer directly without Odoo
   Examples: "what is today's date", "hello", "what can you do",
             "who are you", "what time is it", "thank you",
             "ما هو التاريخ", "مرحبا", "ماذا تستطيع أن تفعل",
             "شكراً", "من أنت"
   NOTE: For GENERAL intent, put the direct answer in the
         "direct_answer" field of parameters

ROUTING RULES:
- If user asks about financials WITHOUT mentioning a specific project → ACCOUNTING
- If user asks about financials WITH a specific project → KPI
- "profit and loss" alone → ACCOUNTING (company-wide)
- "profit and loss for Project X" → KPI (project-specific)
- Follow-up questions inherit the last intent if no new domain signal

DATE RESOLUTION (today is {today}):
- "this month" → first day to last day of current month
- "last month" → first day to last day of previous month
- "this quarter" → current quarter dates
- "this year" → Jan 1 to Dec 31 of current year
- "last year" → Jan 1 to Dec 31 of previous year
- No date mentioned → use current month as default for ACCOUNTING
- No date mentioned → leave null for RAG/KPI (let Odoo handle)

ACCOUNTING REPORT TYPES:
- "profit and loss" / "P&L" / "income statement" / "الأرباح والخسائر" / "قائمة الدخل" → pandl
- "balance sheet" / "الميزانية العمومية" → balance_sheet
- "cash flow" / "التدفق النقدي" → cash_flow
- "general ledger" / "دفتر الأستاذ" → general_ledger
- "trial balance" / "ميزان المراجعة" → trial_balance
- "partner ledger" / "كشف حساب" → partner_ledger
- "partner ageing" / "تقادم الذمم" / "who owes" / "المستحقات" → partner_ageing

Respond with ONLY this JSON — no explanation, no markdown:
{{
  "intent_type"     : "RAG|KPI|ACCOUNTING|WRITE|AMBIGUOUS",
  "confidence_score": 0.0-1.0,
  "odoo_domain"     : "technical.model.name or accounting.report_type",
  "reasoning"       : "one sentence in English",
  "parameters"      : {{
    "report_type"     : "pandl|balance_sheet|cash_flow|general_ledger|trial_balance|partner_ledger|partner_ageing|null",
    "date_from"       : "YYYY-MM-DD or null",
    "date_to"         : "YYYY-MM-DD or null",
    "project_name"    : "project name or null",
    "project_id"      : null,
    "target_move"     : "posted",
    "result_selection": "customer|supplier|customer_supplier|null",
    "model"           : "odoo.model.name or null",
    "method"          : "method_name or null",
    "kpi_type"        : "kpi_type_snake_case or null",
    "search_domain"   : [],
    "search_fields"   : [],
    "limit"           : 10
  }}
}}"""


# ---------------------------------------------------------------------------
# Pydantic model for Claude response
# ---------------------------------------------------------------------------

class ClassificationResult(BaseModel):
    intent_type      : IntentType
    confidence_score : float = Field(..., ge=0.0, le=1.0)
    odoo_domain      : str
    reasoning        : str
    parameters       : dict[str, Any] = Field(default_factory=dict)

    @field_validator("odoo_domain")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        return v.lower().strip() if v else "unknown"


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class IntentClassifierNode:
    """
    Production-grade intent classifier.
    Single Claude call — classifies AND extracts parameters.
    No phrase matching. Works for any language, any phrasing.
    """

    def __init__(
        self,
        api_key              : str | None = None,
        confidence_threshold : float      = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY required.")
        self.client               = anthropic.Anthropic(api_key=self.api_key)
        self.confidence_threshold = confidence_threshold

    def __call__(self, state: AgentState) -> dict[str, Any]:
        raw_input = state.turn.raw_input

        if not raw_input.strip():
            return self._ambiguous_result(state)

        try:
            result = self._classify(state)
        except Exception as exc:
            logger.error("[IntentClassifier] Failed: %s", exc)
            return self._error_result(state, str(exc))

        # Confidence gate
        if result.confidence_score < self.confidence_threshold:
            logger.info(
                "[IntentClassifier] Low confidence %.2f → AMBIGUOUS",
                result.confidence_score,
            )
            result = ClassificationResult(
                intent_type      = IntentType.AMBIGUOUS,
                confidence_score = result.confidence_score,
                odoo_domain      = result.odoo_domain,
                reasoning        = f"Low confidence: {result.reasoning}",
                parameters       = result.parameters,
            )

        # Sticky domain for follow-ups
        inherited = False
        if (result.odoo_domain in ("unknown", "") and
                state.session.active_domain):
            result = ClassificationResult(
                intent_type      = result.intent_type,
                confidence_score = result.confidence_score,
                odoo_domain      = state.session.active_domain,
                reasoning        = result.reasoning,
                parameters       = result.parameters,
            )
            inherited = True

        intent_record = IntentRecord(
            intent_type        = result.intent_type,
            confidence_score   = result.confidence_score,
            classified_at_turn = state.turn.turn_number,
            inherited          = inherited,
            raw_utterance      = raw_input,
        )

        logger.info(
            "[IntentClassifier] %s (%.0f%%) | domain: %s | inherited: %s | params: %s",
            result.intent_type,
            result.confidence_score * 100,
            result.odoo_domain,
            inherited,
            {k: v for k, v in result.parameters.items() if v is not None},
        )

        return {
            "turn": {
                "turn_intent"     : intent_record,
                "extracted_params": result.parameters,
            },
            "session": {
                "active_intent" : intent_record,
                "active_domain" : result.odoo_domain,
            },
        }

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _classify(self, state: AgentState) -> ClassificationResult:
        today   = date.today().strftime("%Y-%m-%d")
        history = self._format_history(state)

        prompt = MASTER_PROMPT.format(
            today         = today,
            user_language = state.session.user_language,
            active_domain = state.session.active_domain or "None",
            last_intent   = (
                state.session.active_intent.intent_type
                if state.session.active_intent else "None"
            ),
            turn_number   = state.turn.turn_number,
            history       = history,
            raw_input     = state.turn.raw_input,
        )

        message = self.client.messages.create(
            model      = AGENT_MODEL,
            max_tokens = 400,
            messages   = [{"role": "user", "content": prompt}],
        )

        raw_json = message.content[0].text.strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]

        parsed = json.loads(raw_json)
        return ClassificationResult(**parsed)

    def _format_history(self, state: AgentState) -> str:
        history = state.session.conversation_history[-3:]
        if not history:
            return "No prior conversation."
        return "\n".join(
            f"  {t.role.upper()}: {t.content[:100]}" for t in history
        )

    def _ambiguous_result(self, state: AgentState) -> dict[str, Any]:
        intent_record = IntentRecord(
            intent_type        = IntentType.AMBIGUOUS,
            confidence_score   = 0.0,
            classified_at_turn = state.turn.turn_number,
            inherited          = False,
            raw_utterance      = state.turn.raw_input,
        )
        return {
            "turn"   : {"turn_intent": intent_record, "extracted_params": {}},
            "session": {"active_intent": intent_record},
        }

    def _error_result(self, state: AgentState, message: str) -> dict[str, Any]:
        error = ErrorState(
            severity    = ErrorSeverity.RECOVERABLE,
            source_node = "IntentClassifierNode",
            message     = f"Classification failed: {message}",
        )
        intent_record = IntentRecord(
            intent_type        = IntentType.AMBIGUOUS,
            confidence_score   = 0.0,
            classified_at_turn = state.turn.turn_number,
            inherited          = False,
            raw_utterance      = state.turn.raw_input,
        )
        return {
            "turn": {
                "turn_intent" : intent_record,
                "error_state" : error,
                "extracted_params": {},
            },
            "session": {"active_intent": intent_record},
        }