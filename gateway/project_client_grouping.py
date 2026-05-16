from __future__ import annotations

import json
import re
from typing import Any

from adapters.v14.connector import OdooV14Adapter
from gateway.analytics_tools import get_project_counts_by_client

CLIENT_GROUP_KEYWORDS = re.compile(
    r"\b(?:projects?\s+)?(?:by|per|grouped by|group by)\s+client\b"
    r"|\bclient\s+project\s+counts?\b"
    r"|\bprojects?\s+(?:for|per|by)\s+client\b",
    re.IGNORECASE,
)
YEAR_RE = re.compile(r"\b(20\d{2})\b")


def parse_projects_by_client_request(message: str) -> dict[str, Any] | None:
    text = message or ""
    if not CLIENT_GROUP_KEYWORDS.search(text):
        return None

    year_match = YEAR_RE.search(text)
    if not year_match:
        return None

    return {
        "year": int(year_match.group(1)),
        "limit": 100,
    }


def prefetch_projects_by_client(
    adapter: OdooV14Adapter,
    message: str,
) -> dict[str, Any] | None:
    request = parse_projects_by_client_request(message)
    if not request:
        return None
    return get_project_counts_by_client(adapter, request)


def prefetch_system_block(payload: dict[str, Any]) -> str:
    return (
        "\n\nAUTHORITATIVE PROJECT COUNTS BY CLIENT (already fetched from Odoo read_group):\n"
        f"{json.dumps(payload, default=str)}\n"
        "Use only this payload for the grouped client project answer. "
        "Do not call sql_aggregate, search_odoo, calculate, or compose_report for the same summary."
    )
