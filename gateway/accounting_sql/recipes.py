from __future__ import annotations

from typing import Any

REPORT_RECIPES: dict[str, dict[str, Any]] = {
    "trial_balance": {
        "implemented": True,
        "requires_date_range": True,
        "order_by": "aa.code ASC",
    },
    "pandl": {
        "implemented": True,
        "requires_date_range": True,
        "internal_groups": ["income", "expense"],
        "order_by": "aa.code ASC",
    },
    "balance_sheet": {
        "implemented": True,
        "requires_as_of_date": True,
        "internal_groups": ["asset", "liability", "equity"],
        "order_by": "aa.code ASC",
    },
    "general_ledger": {
        "implemented": True,
        "requires_date_range": True,
        "include_details": True,
        "order_by": "aml.date ASC, aml.id ASC",
    },
    "partner_ageing": {
        "implemented": True,
        "requires_as_of_date": True,
        "order_by": "rp.name ASC",
    },
    "cost_analysis": {
        "implemented": False,
        "requires_date_range": True,
        "internal_groups": ["expense"],
        "order_by": "debit_sum DESC",
    },
}

SUPPORTED_REPORT_TYPES = tuple(REPORT_RECIPES.keys())
