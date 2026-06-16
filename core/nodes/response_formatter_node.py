"""
OOA Phase 2 — Node 10 (Final Node)
====================================
File    : core/nodes/response_formatter_node.py
Author  : Lead Backend Developer
Version : 1.0.0

ResponseFormatterNode:
    - Generates natural language response in user's language (en/ar/ur)
    - Attaches visualization payload alongside text response
    - Appends both user input and assistant response to conversation history
    - Last node before END — closes the conversation loop
    - Returns partial dict only
"""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from gateway.model_config import AGENT_MODEL

from core.state import AgentState, ErrorSeverity

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

FORMAT_PROMPT = """You are a helpful ERP assistant for an Odoo system.

The user asked: "{raw_input}"
User language : {language}
Data received : {data}

Instructions:
1. Write a clear, concise response summarizing the data
2. Respond ONLY in {language_name} — no other language
3. If the data contains numbers, format them naturally
4. If currency is present, include the currency symbol
5. Keep the response under 3 sentences
6. Be professional but conversational
7. Do not mention technical field names or model names
8. No markdown formatting — plain text only"""

LANGUAGE_NAMES = {
    "en": "English",
    "ar": "Arabic",
    "ur": "Urdu",
}

NO_DATA_MESSAGES = {
    "en": "I could not find any data matching your request.",
    "ar": "لم أتمكن من العثور على أي بيانات تطابق طلبك.",
    "ur": "آپ کی درخواست سے ملتا جلتا کوئی ڈیٹا نہیں ملا۔",
}

AMBIGUOUS_MESSAGES = {
    "en": "I am not sure what you are looking for. Could you please clarify?",
    "ar": "لست متأكداً مما تبحث عنه. هل يمكنك التوضيح؟",
    "ur": "مجھے سمجھ نہیں آیا آپ کیا ڈھونڈ رہے ہیں۔ کیا آپ وضاحت کر سکتے ہیں؟",
}


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class ResponseFormatterNode:
    """
    Final node. Generates natural language response and closes the turn.

    Approved behaviors:
        - Natural language response in detected user language
        - Visualization payload attached to final response
        - Appends user input + assistant response to conversation history
        - Session persisted after history update
        - Returns partial dict only
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for ResponseFormatterNode."
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def __call__(self, state: AgentState) -> dict[str, Any]:
        language = (
            state.turn.input_language
            or state.session.user_language
            or "en"
        )

        # Normalize to supported language
        if language not in ("en", "ar", "ur"):
            language = "en"

        # --- Determine response text ---
        text_response = self._generate_response(state, language)

        logger.info(
            "[ResponseFormatter] Turn %d | language: %s | response: '%s...'",
            state.turn.turn_number,
            language,
            text_response[:60],
        )

        # --- Append both turns to conversation history ---
        # We mutate session directly here since this is the designated
        # history-writing node (approved Suggestion 2)
        state.session.append_turn(
            role     = "user",
            content  = state.turn.raw_input,
            language = language,
        )
        state.session.append_turn(
            role     = "assistant",
            content  = text_response,
            language = language,
        )

        # --- Build final response payload ---
        final_response = {
            "text"                : text_response,
            "language"            : language,
            "visualization"       : state.turn.visualization_payload,
            "turn_number"         : state.turn.turn_number,
        }

        return {
            "turn": {
                "last_odoo_response": final_response,
            },
            "session": {
                "conversation_history": state.session.conversation_history,
                "last_visual_type"    : state.session.last_visual_type,
            },
        }

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    def _generate_response(self, state: AgentState, language: str) -> str:

        # Clarification response — return directly, no Claude call needed
        if state.turn.requires_clarification:
            odoo = state.turn.last_odoo_response
            if isinstance(odoo, str):
                return odoo
            payload = state.turn.visualization_payload or {}
            return payload.get("message", AMBIGUOUS_MESSAGES.get(language))

        # Error state
        if state.turn.error_state:
            payload = state.turn.visualization_payload or {}
            return payload.get(
                "message",
                NO_DATA_MESSAGES.get(language, NO_DATA_MESSAGES["en"]),
            )

        # Ambiguous intent — ask for clarification
        if (
            state.turn.turn_intent is not None
            and state.turn.turn_intent.intent_type.value == "AMBIGUOUS"
        ):
            return AMBIGUOUS_MESSAGES.get(language, AMBIGUOUS_MESSAGES["en"])

        # No data returned from Odoo
        if not state.turn.last_odoo_response:
            return NO_DATA_MESSAGES.get(language, NO_DATA_MESSAGES["en"])

        # Normal path — call Claude for natural language summary
        try:
            return self._call_claude(state, language)
        except Exception as exc:
            logger.error("[ResponseFormatter] Claude call failed: %s", exc)
            return NO_DATA_MESSAGES.get(language, NO_DATA_MESSAGES["en"])

    def _call_claude(self, state: AgentState, language: str) -> str:
        """Generates a natural language summary of the Odoo data."""
        data = state.turn.last_odoo_response

        # For accounting reports — extract only KPIs for summary
        # Full report goes to visualization, not to text
        if isinstance(data, dict) and "report_lines" in data:
            summary_data = {
                "report_name"    : data.get("report_name"),
                "date_from"      : data.get("date_from"),
                "date_to"        : data.get("date_to"),
                "kpis"           : data.get("kpis", {}),
                "current_balance": data.get("current_balance", 0),
            }
            data = summary_data

        elif isinstance(data, dict) and "accounts" in data:
            # General Ledger / Trial Balance — summarize totals only
            accounts = data.get("accounts", {})
            total_debit   = sum(
                v.get("debit", 0) or 0
                for v in accounts.values()
                if isinstance(v, dict)
            )
            total_credit  = sum(
                v.get("credit", 0) or 0
                for v in accounts.values()
                if isinstance(v, dict)
            )
            total_balance = sum(
                v.get("balance", 0) or 0
                for v in accounts.values()
                if isinstance(v, dict)
            )
            summary_data = {
                "report_name"  : data.get("report_name"),
                "date_from"    : data.get("date_from"),
                "date_to"      : data.get("date_to"),
                "account_count": len(accounts),
                "total_debit"  : total_debit,
                "total_credit" : total_credit,
                "total_balance": total_balance,
            }
            data = summary_data

        # Truncate large datasets
        if isinstance(data, list) and len(data) > 10:
            data = data[:10]

        # Build smart prompt based on what user asked
        original_question = state.turn.raw_input

        prompt = f"""The user asked: "{original_question}"
    User language: {language} ({LANGUAGE_NAMES.get(language, "English")})
    Data available: {str(data)}

    Instructions:
    1. Answer ONLY what the user asked — not the full report
    2. Be concise — maximum 2 sentences
    3. Use the currency AED and format numbers with commas
    4. Respond ONLY in {LANGUAGE_NAMES.get(language, "English")}
    5. If they asked about income → give income number
    6. If they asked about profit → give profit number and margin
    7. Never dump the full report in text — that goes in the visualization
    8. No markdown formatting — plain text only"""

        message = self.client.messages.create(
            model      = AGENT_MODEL,
            max_tokens = 150,
            messages   = [{"role": "user", "content": prompt}],
        )

        return message.content[0].text.strip()