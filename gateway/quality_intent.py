from __future__ import annotations

import re
from typing import Any

COMPARISON_RE = re.compile(
    r"\b(?:compar(?:e|ison)|versus|vs\.?|rank|ranked|top\s+\d+|highest|lowest|most|least)\b",
    re.IGNORECASE,
)
TREND_RE = re.compile(
    r"\b(?:trend|over time|monthly|weekly|quarterly|yearly|by month|by quarter|by year)\b",
    re.IGNORECASE,
)
GROUP_RE = re.compile(
    r"\b(?:group(?:ed)? by|breakdown|per client|per project|per partner|by client|by partner)\b",
    re.IGNORECASE,
)
TOTAL_RE = re.compile(
    r"\b(?:total|how much|sum of|overall)\b",
    re.IGNORECASE,
)
LIST_RE = re.compile(
    r"\b(?:list|show me|display|all)\b",
    re.IGNORECASE,
)
REVENUE_RE = re.compile(
    r"\b(?:revenue|sales|income|invoice amount)\b",
    re.IGNORECASE,
)


def detect_query_intent(user_message: str) -> dict[str, Any]:
    text = user_message or ""
    lowered = text.lower()
    intent: dict[str, Any] = {
        "comparison": bool(COMPARISON_RE.search(text)),
        "trend": bool(TREND_RE.search(text)),
        "grouped": bool(GROUP_RE.search(text)),
        "total": bool(TOTAL_RE.search(text)),
        "list": bool(LIST_RE.search(text)),
        "revenue": bool(REVENUE_RE.search(text)),
        "visual_type": "DATA_TABLE",
    }

    if intent["trend"]:
        intent["visual_type"] = "LINE_CHART"
    elif intent["comparison"] or "top " in lowered:
        intent["visual_type"] = "BAR_CHART"
    elif intent["grouped"] and not intent["comparison"]:
        intent["visual_type"] = "GROUPED_TABLE"
    elif intent["total"] and not intent["grouped"] and not intent["list"]:
        intent["visual_type"] = "KPI_CARD"
    elif intent["list"]:
        intent["visual_type"] = "DATA_TABLE"

    return intent
