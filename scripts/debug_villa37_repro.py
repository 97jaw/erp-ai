#!/usr/bin/env python3
"""Local repro for villa maintenance 37 entity gate (debug session bdd48d)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gateway.core.entity_gate import EntityGate
from gateway.core.entity_resolver import EntityResolver
from gateway.core.intent_analyzer import EntityReference, Intent
from tests.core.test_context_stack import _make_context_stack
from tests.core.test_entity_resolver import MockProjectSearch

VILLA_CATALOG = [
    {
        "id": 17001,
        "name": "General maintenance for Villa 17 - Officers' Villas, Falaj Hazza, Villa 7",
        "wo_ref_no": "W.O 1420230065-90",
    },
    {
        "id": 19019,
        "name": "Falej Hazza Villas – Al Ain, Villa No. – Housing Department – Al Ain Region",
        "wo_ref_no": "1420240098-19",
    },
    {
        "id": 15157,
        "name": "Villa Maintenance No. 34",
        "wo_ref_no": "1420240098-38",
    },
    {
        "id": 15158,
        "name": "Villa Maintenance No. 37",
        "wo_ref_no": "1420240098-37",
    },
    {
        "id": 15159,
        "name": "Villa Maintenance No . 48",
        "wo_ref_no": "1420240098-35",
    },
    {
        "id": 16202,
        "name": "Comprehensive building maintenance - Al Waqan Police Station",
        "wo_ref_no": "1420200102-162",
    },
]


async def main() -> None:
    message = "expense for villa maintanence 37"
    # Simulate LLM stripping the number from the entity fragment.
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent=message,
        entities=[EntityReference(type="project", value="villa maintanence", confidence=0.9)],
    )
    intent = EntityGate.infer_entity_hints(message, intent)
    gate = EntityGate(object())
    gate._project_resolver = EntityResolver(MockProjectSearch(VILLA_CATALOG))
    result = await gate.evaluate(intent, _make_context_stack(), message)
    print("status:", result.status)
    if result.status == "confirmed":
        project = result.confirmed.get("project") or {}
        print("confirmed:", project.get("name"), f"(id={project.get('id')})")
    else:
        print("options:", [o.get("label") for o in result.options])


if __name__ == "__main__":
    asyncio.run(main())
