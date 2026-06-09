"""Helpers for inferring project references from natural-language queries."""

from __future__ import annotations

import re

PROJECT_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "cost",
        "costs",
        "expense",
        "expenses",
        "financial",
        "financials",
        "for",
        "give",
        "how",
        "is",
        "last",
        "me",
        "month",
        "much",
        "my",
        "of",
        "project",
        "projects",
        "show",
        "spending",
        "the",
        "this",
        "total",
        "what",
        "year",
    },
)

_PROJECT_COST_SIGNALS = (
    "cost",
    "costs",
    "expense",
    "expenses",
    "spending",
    "budget",
    "spend",
    "spent",
    "money",
)

_LEADING_PREFIXES = (
    "show me ",
    "give me ",
    "get me ",
    "get ",
    "tell me ",
    "what are ",
    "what is ",
    "how much ",
)

_TRAILING_SUFFIXES = (
    r"\s+costs?\s*$",
    r"\s+expenses?\s*$",
    r"\s+financials?\s*$",
    r"\s+spending\s*$",
    r"\s+for\s+last\s+month\s*$",
    r"\s+for\s+this\s+month\s*$",
    r"\s+for\s+last\s+\d+\s+months?\s*$",
    r"\s+for\s+this\s+year\s*$",
    r"\s+for\s+ytd\s*$",
)


def extract_project_name_hint(message: str) -> str | None:
    """Strip command words and return the likely project name fragment."""
    text = (message or "").strip()
    if not text:
        return None

    lowered = text.lower()
    for prefix in _LEADING_PREFIXES:
        if lowered.startswith(prefix):
            text = text[len(prefix) :]
            lowered = text.lower()
            break

    for pattern in _TRAILING_SUFFIXES:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    text = text.strip(" .,?")
    if len(text) < 3:
        return None

    words = [word for word in text.split() if word.lower() not in PROJECT_STOP_WORDS]
    if not words:
        return None
    return " ".join(words)


def meaningful_project_words(query: str) -> list[str]:
    """Return non-stop-word tokens for project search domains."""
    return [
        word
        for word in query.split()
        if word and word.lower() not in PROJECT_STOP_WORDS and len(word) > 1
    ]


_EXPENSE_FOLLOW_UP_SIGNALS = (
    "break down",
    "breakdown",
    "cost breakdown",
    "cost break down",
    "breakdown as well",
    "as well",
    "drill down",
    "drill into",
    "by account",
    "gl detail",
    "gl details",
    "full breakdown",
    "show breakdown",
    "where did the money",
    "where exactly",
)

_BREAKDOWN_HINT_WORDS = frozenset(
    {
        "break",
        "down",
        "breakdown",
        "well",
        "also",
        "cost",
        "account",
        "gl",
        "show",
        "me",
        "the",
        "as",
    },
)


def is_project_expense_follow_up(message: str) -> bool:
    """True when the user is drilling into the last discussed project expense."""
    blob = (message or "").lower().strip()
    if not blob:
        return False
    if not any(signal in blob for signal in _EXPENSE_FOLLOW_UP_SIGNALS):
        return False
    hint = extract_project_name_hint(message)
    if hint is None:
        return True
    words = [word.lower() for word in hint.split()]
    if not words:
        return True
    return all(word in _BREAKDOWN_HINT_WORDS or word in PROJECT_STOP_WORDS for word in words)


def looks_like_project_cost_query(message: str, *, subject_area: str = "") -> bool:
    """Return True when the user is likely asking for project cost data."""
    message_blob = message.lower()
    has_cost_signal = any(token in message_blob for token in _PROJECT_COST_SIGNALS)
    has_project_subject = subject_area.lower() == "project"
    has_project_signal = any(
        token in message_blob
        for token in (
            "project",
            "school",
            "boys",
            "girls",
            "zayidia",
            "national guard",
            "ngc",
            "villa",
            "maintenance",
        )
    )
    hint = extract_project_name_hint(message)
    return has_cost_signal and (has_project_subject or has_project_signal or hint is not None)
