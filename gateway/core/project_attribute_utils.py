"""Detect non-financial project attribute questions (PM, deadline, status, etc.)."""

from __future__ import annotations

FINANCIAL_QUERY_SIGNALS = (
    "expense",
    "expenses",
    "cost",
    "costs",
    "spend",
    "spent",
    "spending",
    "budget",
    "revenue",
    "financial",
    "breakdown",
    "break down",
    "invoice",
    "payment",
    "money",
    "aed",
    "wo amount",
    "over budget",
)

NON_FINANCIAL_ATTRIBUTE_SIGNALS = (
    "who is",
    "who's",
    "whos",
    "manager",
    " pm ",
    "project manager",
    "deadline",
    "due date",
    "start date",
    "end date",
    "progress",
    "completion",
    "stage",
    "location",
    "address",
    "team",
    "members",
    "assigned to",
    "name the",
    "can you name",
)

# Standalone "status" / "client" only when not paired with financial wording.
_ATTRIBUTE_STATUS_SIGNALS = ("status", "client", "customer")


def is_project_attribute_query(query: str) -> bool:
    """Return True when the user asks about project metadata, not finances."""
    lowered = f" {query.lower()} "
    if "validation status" in lowered or "validation" in lowered and "approval" in lowered:
        return False
    if any(signal in lowered for signal in FINANCIAL_QUERY_SIGNALS):
        return False
    if any(signal in lowered for signal in NON_FINANCIAL_ATTRIBUTE_SIGNALS):
        return True
    if any(signal in lowered for signal in _ATTRIBUTE_STATUS_SIGNALS):
        return True
    return False


def build_project_attribute_response_text(project_ref: str) -> str:
    """Honest deferral until Omni-Agent attribute tools ship."""
    return (
        f"I can see we're talking about {project_ref}. "
        "I don't have access to project manager, deadline, or status "
        "data yet — I can currently show financial and expense data. "
        "Broader project details are coming soon. For now, you can find "
        "the project manager in Odoo under the project form.\n\n"
        f"Is there any expense or cost information about {project_ref} "
        "I can help with?"
    )
