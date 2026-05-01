"""
OOA Phase 2 — Node 9
=====================
File    : core/nodes/error_node.py
Author  : Lead Backend Developer
Version : 1.0.0

ErrorHandlerNode:
    - Translates ErrorState into user-friendly messages
    - Supports en / ar / ur output
    - NEVER wipes SessionState — context always preserved
    - RECOVERABLE errors suggest retry
    - FATAL errors suggest contacting support
    - Returns partial dict only
"""

from __future__ import annotations

import logging
from typing import Any

from core.state import (
    AgentState,
    ErrorSeverity,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# User-facing message templates (en / ar / ur)
# ---------------------------------------------------------------------------

MESSAGES = {
    ErrorSeverity.RECOVERABLE: {
        "en": "I had trouble fetching that data. Please try again.",
        "ar": "واجهت مشكلة في جلب البيانات. يرجى المحاولة مرة أخرى.",
        "ur": "ڈیٹا حاصل کرنے میں مسئلہ ہوا۔ براہ کرم دوبارہ کوشش کریں۔",
    },
    ErrorSeverity.FATAL: {
        "en": "I cannot connect to Odoo right now. Please contact support.",
        "ar": "لا يمكنني الاتصال بـ Odoo الآن. يرجى التواصل مع الدعم الفني.",
        "ur": "ابھی Odoo سے رابطہ نہیں ہو پا رہا۔ براہ کرم سپورٹ سے رابطہ کریں۔",
    },
}

DEFAULT_LANGUAGE = "en"


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class ErrorHandlerNode:
    """
    Translates technical errors into user-friendly multilingual messages.

    Approved behaviors:
        - RECOVERABLE → friendly retry message in user language
        - FATAL       → support contact message in user language
        - SessionState NEVER modified — full context preserved
        - Returns partial dict only (turn key only)
    """

    def __call__(self, state: AgentState) -> dict[str, Any]:
        error = state.turn.error_state

        # No error in state — nothing to handle
        if error is None:
            logger.warning(
                "[ErrorHandler] Called with no error in TurnState. "
                "Check graph routing."
            )
            return {}

        # Detect language — fall back to session language then English
        language = (
            state.turn.input_language
            or state.session.user_language
            or DEFAULT_LANGUAGE
        )

        # Normalize to supported language
        if language not in ("en", "ar", "ur"):
            language = DEFAULT_LANGUAGE

        # Select message template by severity
        templates = MESSAGES.get(error.severity, MESSAGES[ErrorSeverity.RECOVERABLE])
        user_message = templates.get(language, templates[DEFAULT_LANGUAGE])

        logger.error(
            "[ErrorHandler] Turn %d | severity: %s | node: %s | message: %s",
            state.turn.turn_number,
            error.severity,
            error.source_node,
            error.message,
        )

        logger.info(
            "[ErrorHandler] User-facing message (%s): %s",
            language,
            user_message,
        )

        # Partial dict — ONLY update turn response fields
        # SessionState is intentionally never touched here
        return {
            "turn": {
                "visualization_payload": {
                    "visual_type"  : "ERROR",
                    "message"      : user_message,
                    "severity"     : error.severity.value,
                    "source_node"  : error.source_node,
                    "recoverable"  : error.severity == ErrorSeverity.RECOVERABLE,
                },
            },
        }
