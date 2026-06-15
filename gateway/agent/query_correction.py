"""Typo-tolerant query suggestions — 'Did you mean?' for agent chat."""

from __future__ import annotations

import re
from difflib import get_close_matches
from typing import Any

from gateway.core.project_query_utils import extract_suggestion_tokens

_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")

_COMMON_TYPOS: dict[str, str] = {
    "natioanl": "national",
    "natinal": "national",
    "nationl": "national",
    "vehical": "vehicle",
    "vehcile": "vehicle",
    "vehicel": "vehicle",
    "purchse": "purchase",
    "purcahse": "purchase",
    "lpos": "lpo",
    "lpo`s": "lpo",
    "invoics": "invoices",
    "invocies": "invoices",
    "maintanence": "maintenance",
    "maintenence": "maintenance",
    "payrol": "payroll",
    "payslip": "payslip",
    "attendence": "attendance",
    "finacial": "financial",
    "trail": "trial",
    "balace": "balance",
    "natinal": "national",
    "gurad": "guard",
    "gaurd": "guard",
}

_ERP_VOCAB = frozenset(
    {
        "purchase",
        "order",
        "orders",
        "lpo",
        "lpos",
        "invoice",
        "invoices",
        "vehicle",
        "vehicles",
        "fleet",
        "project",
        "projects",
        "expense",
        "expenses",
        "payslip",
        "payroll",
        "attendance",
        "trial",
        "balance",
        "ledger",
        "financial",
        "report",
        "national",
        "guard",
        "vendor",
        "employee",
        "department",
        "timesheet",
        "procurement",
        "rfq",
    }
)

_SKIP_CORRECTION_RE = re.compile(
    r"\b(skip|use\s+default|did\s+you\s+mean)\b|—\s*\d{4}-\d{2}-\d{2}|—",
    re.I,
)


def _apply_typo_map(message: str) -> tuple[str, list[str]]:
    corrections: list[str] = []
    parts: list[str] = []
    for token in message.split():
        stripped = re.sub(r"[^\w'-]", "", token)
        lower = stripped.lower()
        if lower in _COMMON_TYPOS:
            fixed = _COMMON_TYPOS[lower]
            corrections.append(f"{stripped} → {fixed}")
            parts.append(token.replace(stripped, fixed))
        else:
            parts.append(token)
    return " ".join(parts), corrections


def _fuzzy_vocab_fixes(message: str) -> list[str]:
    suggestions: list[str] = []
    for word in _WORD_RE.findall(message):
        lower = word.lower()
        if lower in _ERP_VOCAB or lower in _COMMON_TYPOS:
            continue
        match = get_close_matches(lower, sorted(_ERP_VOCAB), n=1, cutoff=0.82)
        if match:
            suggestions.append(f"{word} → {match[0]}")
    return suggestions


def suggest_query_corrections(message: str) -> dict[str, Any] | None:
    """Return pill_select options when the query likely contains typos."""
    text = (message or "").strip()
    if len(text) < 4 or _SKIP_CORRECTION_RE.search(text):
        return None

    corrected, typo_hits = _apply_typo_map(text)
    fuzzy_hits = _fuzzy_vocab_fixes(text)
    if corrected == text and not fuzzy_hits:
        return None

    options: list[dict[str, str]] = []
    if corrected != text:
        options.append({"id": "corrected", "label": corrected})

    tokens = extract_suggestion_tokens(text)
    if tokens:
        token_hint = " ".join(tokens)
        if token_hint.lower() not in corrected.lower():
            options.append(
                {
                    "id": "token_hint",
                    "label": f"Search for {token_hint}",
                }
            )

    if not options:
        return None

    return {
        "reason": "query_correction",
        "question": "Did you mean one of these?",
        "options": options[:3],
        "original": text,
    }
