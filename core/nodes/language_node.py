"""
OOA Phase 2 — Node 3
=====================
File    : core/nodes/language_node.py
Author  : Lead Backend Developer
Version : 1.0.0

LanguageDetectionNode:
    - Detects language from raw user input
    - Supports ONLY: English (en), Arabic (ar), Urdu (ur)
    - Defaults to English if unsure or API fails
    - Stores detected language + script direction in TurnState
    - Updates SessionState.user_language for persistence
"""

from __future__ import annotations

import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv

from core.state import AgentState

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_LANGUAGES = {"en", "ar", "ur"}
DEFAULT_LANGUAGE    = "en"
RTL_LANGUAGES       = {"ar", "ur"}

DETECTION_PROMPT = """The user sent this message: "{input}"

Classify the language as exactly one of these three options:
- en  (English)
- ar  (Arabic)
- ur  (Urdu)

Rules:
- If the message contains Arabic script → ar
- If the message contains Urdu script → ur
- If the message is in English or you are unsure → en
- If the message is mixed, pick the dominant language

Reply with ONLY the two-letter code. No explanation. No punctuation."""


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class LanguageDetectionNode:
    """
    Classifies user input into en / ar / ur using Claude.
    Falls back to English on any failure — never blocks the turn.

    Dependency injection:
        api_key : Anthropic API key — injected at construction
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for LanguageDetectionNode. "
                "Add it to your .env file."
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def __call__(self, state: AgentState) -> dict[str, Any]:
        raw_input = state.turn.raw_input

        # Empty input — default to session language
        if not raw_input.strip():
            logger.warning("[LangDetect] Empty input — defaulting to session language.")
            return self._build_result(state.session.user_language)

        try:
            detected = self._detect(raw_input)
        except Exception as exc:
            # API failure is RECOVERABLE — default to English, never crash
            logger.error("[LangDetect] API call failed: %s — defaulting to 'en'", exc)
            detected = DEFAULT_LANGUAGE

        logger.info(
            "[LangDetect] Turn %d | input: '%s...' | detected: %s",
            state.turn.turn_number,
            raw_input[:30],
            detected,
        )

        return self._build_result(detected)

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    def _detect(self, text: str) -> str:
        """
        Calls Claude with a minimal classification prompt.
        Returns one of: 'en', 'ar', 'ur'.
        """
        message = self.client.messages.create(
            model      = "claude-sonnet-4-20250514",
            max_tokens = 5,       # We only need 2 characters back
            messages   = [
                {
                    "role"   : "user",
                    "content": DETECTION_PROMPT.format(input=text),
                }
            ],
        )

        raw = message.content[0].text.strip().lower()

        # Validate response is one of our supported languages
        if raw in SUPPORTED_LANGUAGES:
            return raw

        # Claude returned something unexpected — default to English
        logger.warning(
            "[LangDetect] Unexpected response '%s' — defaulting to 'en'", raw
        )
        return DEFAULT_LANGUAGE

    def _build_result(self, language: str) -> dict[str, Any]:
        """
        Builds the partial dict returned to LangGraph.
        Updates BOTH turn (ephemeral) and session (persistent) language fields.
        """
        direction = "rtl" if language in RTL_LANGUAGES else "ltr"

        return {
            # Partial update to turn — only touch language fields
            "turn": {
                "input_language": language,
            },
            # Partial update to session — persist language for future turns
            "session": {
                "user_language": language,
            },
            # Store direction as turn metadata
            "_language_direction": direction,
        }
