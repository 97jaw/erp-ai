"""Detect project activity queries and route them to get_project_activity.

Project Model Phase 3. Attachments, chatter summary, progress, and audit
trail for a project — direct ORM reads (+ LLM summary for chatter). No Deep
Think. Financial aggregations and record lists use their own lanes.
"""

from __future__ import annotations

import re

from gateway.core.project_records_routing import records_disqualified

_ACTIVITY_TYPE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("attachments", re.compile(
        r"attachments?|documents?|files?|uploads?"
        r"|مرفق|مرفقات|مستند",
        re.IGNORECASE,
    )),
    ("chatter_summary", re.compile(
        r"chatter|messages?|activity\s+summary|communication|"
        r"what(?:'s|\s+is)\s+(?:the\s+)?latest|recent\s+(?:notes?|updates?|activity)"
        r"|notes?\s+on\s+the\s+project"
        # Arabic: ملخص محادثات (summary of conversations/chats), ملخص النشاط (activity summary), رسائل (messages)
        r"|ملخص\s+(?:محادثات?|النشاط|الرسائل?|الأنشطة)|محادثات?\s+(?:المشروع|الفريق)?"
        r"|رسائل|أحدث\s+(?:نشاط|تحديث|رسائل)",
        re.IGNORECASE,
    )),
    ("progress", re.compile(
        r"\bprogress\b|completion\s*(%|percent|percentage)?|"
        r"delayed\s+weeks?|on\s*time\s+weeks?|percent\s+complete"
        r"|تقدم|نسبة\s+الإنجاز",
        re.IGNORECASE,
    )),
    ("audit", re.compile(
        r"last\s+updated|updated\s+by|created\s+by|created\s+on|"
        r"audit\s+trail|who\s+(?:last\s+)?(?:updated?|modified?|changed?|edit)"
        r"|who\s+did\s+(?:update|modify|change)"
        r"|what\s+(?:changed?|was\s+modif)"
        r"|آخر\s+تحديث|من\s+(?:حدّ?ث|عدّل|غيّر)|من\s+آخر\s+تعديل",
        re.IGNORECASE,
    )),
)

_LEADING_ACTIVITY_QUALIFIER_RE = re.compile(
    r"^\s*(?:show\s+(?:me\s+)?|list\s+|give\s+me\s+|get\s+|tell\s+me\s+)?"
    r"(?:all\s+|the\s+|latest\s+|recent\s+)*"
    r"(?:attachments?|documents?|files?|chatter|messages?|progress|audit(?:\s+trail)?"
    r"|ملخص\s+(?:محادثات?|النشاط|الرسائل?)|محادثات?|مرفقات?)"
    r"\s*(?:of|for|on|ل|من|عن|\s)\s*",
    re.IGNORECASE,
)

_AGREEMENT_CONTEXT_RE = re.compile(
    r"\bagreement\b|\bcontract\b|\بعقد\b",
    re.IGNORECASE,
)


def derive_activity_type(message: str) -> str | None:
    """Map the question to an activity_type, or None."""
    text = message or ""
    for activity_type, pattern in _ACTIVITY_TYPE_PATTERNS:
        if pattern.search(text):
            return activity_type
    return None


def is_project_activity_text(message: str) -> bool:
    """Text-only activity detection — covers project AND agreement attachment queries."""
    text = (message or "").strip()
    if len(text) < 4:
        return False
    if records_disqualified(text):
        return False
    if derive_activity_type(text) is None:
        return False
    from gateway.core.project_profile_routing import has_project_context

    if has_project_context(text):
        return True
    if _AGREEMENT_CONTEXT_RE.search(text):
        return True
    return bool(_LEADING_ACTIVITY_QUALIFIER_RE.search(text))


def is_project_activity_query(message: str, intent) -> bool:
    del intent
    return is_project_activity_text(message)


def extract_activity_project_hint(message: str) -> str | None:
    from gateway.core.project_query_utils import extract_project_name_hint

    text = (message or "").strip()
    stripped = _LEADING_ACTIVITY_QUALIFIER_RE.sub("", text, count=1)
    if stripped and stripped != text:
        return extract_project_name_hint(stripped)
    return extract_project_name_hint(text)
