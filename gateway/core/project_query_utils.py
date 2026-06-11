"""Helpers for inferring project references from natural-language queries."""

from __future__ import annotations

import re
from typing import Any

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

# Leading allocation/amount qualifiers that are NOT part of a project name,
# e.g. "civil amount of <project>", "engineers amount of <project>",
# "w.o amount of <project>". Strip them so the project name resolves cleanly.
_LEADING_AMOUNT_QUALIFIER_RE = re.compile(
    r"^\s*(?:"
    r"civil|electrical|mechanical|ict|it|plumbing|plumber|"
    r"branch\s+manager|project\s+manager|"
    r"engineers?|engineering|"
    r"w\.?\s*o\.?|work\s+order|estimation|extended"
    r")\s+(?:engineer(?:ing)?\s+)?amounts?\s+(?:of\s+)?",
    re.IGNORECASE,
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


def extract_broad_project_search_term(message: str) -> str | None:
    """Extract the search token from 'show all projects containing civil'."""
    text = (message or "").strip()
    if not text:
        return None
    match = re.search(
        r"(?:show\s+)?(?:all\s+)?projects?\s+(?:containing|with|matching|like)\s+"
        r"[\"']?(.+?)[\"']?\s*$",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        term = match.group(1).strip(" .,\"'")
        return term or None
    return None


def is_broad_project_search(message: str) -> bool:
    """True when the user wants a project name search list (not financial data)."""
    return extract_broad_project_search_term(message) is not None


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

    # Drop a leading "<trade/role/engineers/w.o> amount of" qualifier.
    stripped = _LEADING_AMOUNT_QUALIFIER_RE.sub("", text, count=1)
    if stripped.strip():
        text = stripped
        lowered = text.lower()

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


_MAINTENANCE_TYPO_FORMS = frozenset(
    {"maintanence", "maintanance", "maintainance", "maintenence", "maintainence"},
)


def normalize_project_search_tokens(query: str) -> list[str]:
    """Expand typo variants (e.g. maintanence→maintenance) for Odoo ilike search."""
    tokens: list[str] = []
    for word in meaningful_project_words(query):
        tokens.append(word)
        if word.lower() in _MAINTENANCE_TYPO_FORMS:
            tokens.append("maintenance")
    return list(dict.fromkeys(tokens))


def extract_project_number_hint(query: str) -> str | None:
    """Extract a villa/project number like 37 from 'villa maintenance 37'."""
    text = (query or "").strip()
    if not text:
        return None

    match = re.search(
        r"\bvilla\s+(?:maint\w*\s+)?(\d{1,3})\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1)

    match = re.search(r"\bno\.?\s*(\d{1,3})\b", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)

    words = meaningful_project_words(text)
    if words and words[-1].isdigit():
        return words[-1]
    return None


def project_record_matches_number(record: dict[str, Any], number: str) -> bool:
    """True when project name or WO ref contains the requested villa/project number."""
    if not number:
        return False
    name = str(record.get("name") or "").lower()
    wo_ref = str(record.get("wo_ref_no") or "").lower()
    if re.search(rf"\bno\.?\s*{re.escape(number)}\b", name):
        return True
    if re.search(rf"\bno\s*\.\s*{re.escape(number)}\b", name):
        return True
    if re.search(rf"\bvilla\s+{re.escape(number)}\b", name):
        return True
    if re.search(rf"maintenance\s+no\.?\s*{re.escape(number)}\b", name):
        return True
    if re.search(rf"maintenance\s+no\s*\.\s*{re.escape(number)}\b", name):
        return True
    return False


def query_mentions_maintenance(query: str) -> bool:
    """True when the user query refers to maintenance work (incl. common typos)."""
    blob = (query or "").lower()
    return "maintenance" in blob or "maint" in blob


_SUGGESTION_TOKEN_STOP = frozenset({"no"})


def extract_suggestion_tokens(query: str, *, min_len: int = 3, max_tokens: int = 2) -> list[str]:
    """Meaningful name tokens (3+ chars) for broad related-project search (max 2 words)."""
    from gateway.core.entity_resolver import GENERIC_BROAD_WORDS

    expanded = normalize_project_search_tokens(query)
    tokens: list[str] = []
    for word in expanded:
        cleaned = re.sub(r"[^\w]", "", word).lower()
        if not cleaned or cleaned in _SUGGESTION_TOKEN_STOP:
            continue
        if cleaned.isdigit():
            continue
        if len(cleaned) < min_len:
            continue
        if cleaned in GENERIC_BROAD_WORDS:
            continue
        tokens.append(cleaned)

    if "maintenance" in tokens:
        tokens = [token for token in tokens if token not in _MAINTENANCE_TYPO_FORMS]

    return list(dict.fromkeys(tokens))[:max_tokens]


def rank_related_project(
    entity: dict[str, Any],
    tokens: list[str],
    *,
    maintenance_query: bool = False,
) -> float:
    """Score how well a project name matches suggestion tokens (higher is better)."""
    name = str(entity.get("name") or "").lower()
    if not name or not tokens:
        return -1.0
    score = 0.0
    for token in tokens:
        if token in name:
            score += 1.0
    if score <= 0:
        return -1.0
    if maintenance_query:
        if "villa maintenance" in name:
            score += 2.0
        elif "maintenance" in name:
            score += 0.5
    return score


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
