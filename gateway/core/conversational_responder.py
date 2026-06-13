"""Scoped conversational responder for non-Odoo turns (greetings, capabilities, off-topic).

Handles messages that must never reach the strategy planner or Odoo:
greetings/smalltalk, "what can you do" questions, and off-topic general
knowledge (politely redirected back to Elrace ERP topics).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Protocol

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent

logger = logging.getLogger(__name__)

CONVERSATIONAL_MODEL = "claude-sonnet-4-20250514"
_MAX_RESPONSE_TOKENS = 600

_GREETING_RE = re.compile(
    r"^\s*(hi+|hello|hey+|yo|good\s+(morning|afternoon|evening)|salam|"
    r"thanks?|thank\s+you|ok(ay)?|cool|great|nice|bye|goodbye|"
    r"مرحبا|اهلا|أهلا|السلام\s*عليكم|شكرا|شكراً|صباح\s+الخير|مساء\s+الخير|مع\s+السلامة)"
    r"[\s!.,؟?]*$",
    re.IGNORECASE,
)

_CAPABILITY_RE = re.compile(
    r"\b(what\s+can\s+you\s+do|what\s+do\s+you\s+do|who\s+are\s+you|"
    r"how\s+can\s+you\s+help|what\s+are\s+your\s+(features|capabilities)|"
    r"help\s+me\s+get\s+started|what\s+is\s+this|how\s+do\s+(i|you)\s+use)\b"
    r"|ماذا\s+تستطيع|ما\s+هي\s+قدراتك|من\s+انت|من\s+أنت|كيف\s+تساعد",
    re.IGNORECASE,
)

# Business signals that must always go to the full pipeline, never conversational.
_BUSINESS_SIGNAL_RE = re.compile(
    r"\b(expense|cost|revenue|profit|loss|p&l|pnl|balance|ledger|invoice|budget|"
    r"payment|receivable|payable|ageing|aging|trial|cash\s*flow|project|villa|"
    r"partner|client|vendor|customer|report|account|journal|salary|payroll|"
    r"maintenance|school|wo\b|work\s*order)\b"
    r"|مصروف|مصاريف|ايراد|إيراد|ربح|خسارة|مشروع|فاتورة|ميزانية|تقرير|عميل|مورد",
    re.IGNORECASE,
)

CONVERSATIONAL_SUGGESTIONS_EN = [
    "Show me the P&L for the last 3 months",
    "What are the expenses for a project?",
    "Show receivables ageing summary",
]

CONVERSATIONAL_SUGGESTIONS_AR = [
    "أرني الأرباح والخسائر لآخر ٣ أشهر",
    "ما هي مصاريف مشروع معين؟",
    "ملخص أعمار الذمم المدينة",
]


def is_conversational_message(message: str) -> bool:
    """Deterministic guardrail: pure greetings/capability questions, no business signal."""
    text = (message or "").strip()
    if not text:
        return False
    if _BUSINESS_SIGNAL_RE.search(text):
        return False
    if _GREETING_RE.match(text):
        return True
    if _CAPABILITY_RE.search(text):
        return True
    return False


def is_conversational_intent(intent: Intent, message: str) -> bool:
    """LLM-classified conversational turn: general subject with no business entities."""
    if _BUSINESS_SIGNAL_RE.search(message or ""):
        return False
    if intent.entities:
        return False
    if intent.subject_area not in ("general", "other"):
        return False
    return intent.primary_action in ("ask_question", "explain", "other")


def conversational_suggestions(language: str = "en") -> list[str]:
    """Capability-oriented chips for conversational turns."""
    if language == "ar":
        return list(CONVERSATIONAL_SUGGESTIONS_AR)
    return list(CONVERSATIONAL_SUGGESTIONS_EN)


class TextCompletionClient(Protocol):
    """Minimal protocol for plain-text Claude completion."""

    async def complete_text(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        max_tokens: int,
    ) -> str:
        """Return Claude's text response."""
        ...


class AnthropicTextClient:
    """Production Claude client for plain-text conversational replies."""

    async def complete_text(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        max_tokens: int = _MAX_RESPONSE_TOKENS,
    ) -> str:
        import anthropic

        def _call() -> str:
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            block = response.content[0]
            return getattr(block, "text", str(block))

        return await asyncio.to_thread(_call)


class ConversationalResponder:
    """Generate scoped conversational replies without tools or Odoo access."""

    def __init__(
        self,
        client: TextCompletionClient | None = None,
        model: str = CONVERSATIONAL_MODEL,
    ) -> None:
        self._client = client or AnthropicTextClient()
        self._model = model

    async def respond(
        self,
        message: str,
        context: ContextStack,
        *,
        language: str = "en",
    ) -> str:
        """Return a conversational reply; falls back to a static reply on failure."""
        try:
            text = await self._client.complete_text(
                model=self._model,
                system=self._build_system_prompt(context, language),
                prompt=message,
                max_tokens=_MAX_RESPONSE_TOKENS,
            )
            cleaned = (text or "").strip()
            if cleaned:
                return cleaned
        except Exception as exc:
            logger.warning("[ConversationalResponder] Claude call failed: %s", exc)
        return self._fallback_reply(context, language)

    def _build_system_prompt(self, context: ContextStack, language: str) -> str:
        capabilities = ", ".join(
            capability.description for capability in context.capability_manifest.available
        )
        user = context.user
        language_rule = (
            "Respond in Arabic." if language == "ar" else "Respond in English."
        )
        return (
            "You are the Odoo Omni-Agent, the AI assistant for Elrace Cos. & Gen. Cont. CO., "
            "a UAE construction and facilities management company. You help staff query their "
            "Odoo ERP: financial reports, project expenses, partner ledgers, and more.\n\n"
            f"You are talking to {user.name} ({user.primary_role}).\n\n"
            f"Your capabilities: {capabilities}.\n\n"
            "Rules:\n"
            "- Warm, professional UAE business tone. Concise — 1-4 sentences for greetings.\n"
            "- For greetings or thanks: reply briefly and offer help with ERP queries.\n"
            "- For capability questions: summarize what you can do in 3-5 bullet points.\n"
            "- For off-topic general-knowledge questions (weather, news, sports, recipes): "
            "politely decline and redirect to Elrace ERP topics — do not answer the off-topic "
            "content itself.\n"
            "- Never fabricate data or claim you already fetched figures. You are not running "
            "any data query in this reply.\n"
            "- No emojis.\n"
            f"- {language_rule}"
        )

    @staticmethod
    def _fallback_reply(context: ContextStack, language: str) -> str:
        name = (context.user.name or "").split(" ")[0]
        if language == "ar":
            return (
                f"مرحباً{' ' + name if name else ''}! أنا مساعد Elrace الذكي. "
                "يمكنني مساعدتك في التقارير المالية ومصاريف المشاريع وكشوف الشركاء. "
                "كيف يمكنني مساعدتك اليوم؟"
            )
        greeting = f"Hello{' ' + name if name else ''}!"
        return (
            f"{greeting} I'm the Elrace AI assistant. I can help you with financial reports "
            "(P&L, balance sheet, trial balance, general ledger), project expenses, and "
            "partner ledgers. What would you like to look at?"
        )


def build_conversational_meta(message: str, intent: Intent | None) -> dict[str, Any]:
    """Telemetry payload describing why the turn was routed conversationally."""
    return {
        "conversational": True,
        "matched_guardrail": is_conversational_message(message),
        "intent_subject": intent.subject_area if intent else None,
        "intent_action": intent.primary_action if intent else None,
    }


class NormalModeResponder:
    """AI-prepared answer for data/financial queries when Deep Think is OFF.

    The AI itself composes the reply: interprets the request, asks narrowing
    questions (date range, specific project) when under-specified, and points
    the user to Deep Think for actual figures. Never runs Odoo methods and
    never fabricates numbers.
    """

    def __init__(
        self,
        client: TextCompletionClient | None = None,
        model: str = CONVERSATIONAL_MODEL,
    ) -> None:
        self._client = client or AnthropicTextClient()
        self._model = model

    async def respond(
        self,
        message: str,
        context: ContextStack,
        intent: Intent | None,
        *,
        language: str = "en",
    ) -> str:
        """Return an AI-prepared reply; falls back to a static reply on failure."""
        try:
            text = await self._client.complete_text(
                model=self._model,
                system=self._build_system_prompt(context, intent, language),
                prompt=message,
                max_tokens=_MAX_RESPONSE_TOKENS,
            )
            cleaned = (text or "").strip()
            if cleaned:
                return cleaned
        except Exception as exc:
            logger.warning("[NormalModeResponder] Claude call failed: %s", exc)
        return self._fallback_reply(language)

    def _build_system_prompt(
        self,
        context: ContextStack,
        intent: Intent | None,
        language: str,
    ) -> str:
        capabilities = ", ".join(
            capability.description for capability in context.capability_manifest.available
        )
        user = context.user
        active = context.working_memory.get_active_project()
        memory_lines = ""
        if active is not None and active.project_name:
            memory_lines = (
                f"\nConversation context: the user was last discussing project "
                f"'{active.project_name}' (id {active.project_id})."
            )
        intent_line = ""
        if intent is not None:
            intent_line = (
                f"\nDetected intent: {intent.primary_action} / {intent.subject_area} "
                f"— {intent.specific_intent}"
            )
        default_range = context.temporal_context.last_3_months
        language_rule = "Respond in Arabic." if language == "ar" else "Respond in English."
        return (
            "You are the Odoo Omni-Agent, the AI assistant for Elrace Cos. & Gen. Cont. CO. "
            "(UAE construction and facilities management). The user asked a business/data "
            "question, but live data fetching (Deep Think) is NOT active for this turn.\n\n"
            f"You are talking to {user.name} ({user.primary_role}).\n"
            f"Your data capabilities (via Deep Think): {capabilities}."
            f"{memory_lines}{intent_line}\n"
            f"Default reporting period when unspecified: {default_range[0]} to {default_range[1]}.\n\n"
            "Your job in THIS reply:\n"
            "1. Show you understood the request: restate it precisely in one line.\n"
            "2. If the request is under-specified, ask at most ONE narrowing question "
            "(date range, specific project, or scope) and propose a sensible default.\n"
            "3. Explain briefly which report/data would answer it (e.g. P&L, project "
            "expense breakdown, partner ageing).\n"
            "4. Tell the user to activate Deep Think (the button next to the send button) "
            "to pull the actual figures from Odoo, which you will then analyze for them.\n\n"
            "HARD RULES:\n"
            "- NEVER output any financial figures, totals, or amounts — you have not "
            "fetched any data. Do not estimate or guess numbers.\n"
            "- Never claim data was fetched or that a query is running.\n"
            "- Concise: 2-6 sentences. Professional UAE business tone. No emojis.\n"
            f"- {language_rule}"
        )

    @staticmethod
    def _fallback_reply(language: str) -> str:
        if language == "ar":
            return (
                "فهمت طلبك. للحصول على الأرقام الفعلية من Odoo، فعّل زر Deep Think "
                "بجانب زر الإرسال وسأقوم بسحب البيانات وتحليلها لك."
            )
        return (
            "I understand what you're asking for. To pull the actual figures from Odoo, "
            "activate Deep Think (the button next to send) and I'll fetch the data and "
            "analyze it for you. If you'd like, tell me the date range or project to "
            "narrow the scope first."
        )


def normal_mode_suggestions(message: str, context: ContextStack, language: str = "en") -> list[str]:
    """Refinement chips for normal-mode data turns — each chip is a full next query."""
    suggestions: list[str] = []
    pending = context.working_memory.session_facts.get("pending_entity_clarification") or {}
    if pending.get("payroll_context"):
        return [
            "Show payslip for last month",
            "Total payroll cost last month",
            "Draft payslips count",
        ][:3]

    base = (message or "").strip().rstrip("?.!")
    if base:
        lowered = base.lower()
        has_period = any(
            token in lowered
            for token in ("month", "year", "quarter", "q1", "q2", "q3", "q4", "20", "last", "ytd")
        )
        if not has_period:
            if language == "ar":
                suggestions.append(f"{base} لآخر ٣ أشهر")
            else:
                suggestions.append(f"{base} for the last 3 months")
    active = context.working_memory.get_active_project()
    if active is not None and active.project_name:
        if language == "ar":
            suggestions.append(f"مصاريف مشروع {active.project_name}")
        else:
            suggestions.append(f"Expenses for {active.project_name}")
    if language == "ar":
        suggestions.append("أرني الأرباح والخسائر لآخر ٣ أشهر")
    else:
        suggestions.append("Show me the P&L for the last 3 months")
    deduped = list(dict.fromkeys(suggestion for suggestion in suggestions if suggestion))
    return deduped[:3]
