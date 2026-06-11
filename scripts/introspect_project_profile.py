#!/usr/bin/env python3
"""Introspect project.project on live Odoo to derive the Project Profile field map.

Reads fields_get + fully-populated records (Villa Maintenance No. 48 from the
screenshot, plus National Guard) and reports which fields back the UI labels:
W.O Amount Distribution (Civil/Electrical/Mechanical/ICT), engineer role
amounts, header attributes. Phase 1 of the Project Model.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

# Values visible in the Villa Maintenance No. 48 screenshot.
SCREENSHOT_VALUES = {
    "civil": 359762.61,
    "electrical": 39178.00,
    "mechanical": 64248.97,
    "ict": 0.00,
    "wo_amount": 463189.58,
    "estimation": 463189.58,
}

INTERESTING_RE = re.compile(
    r"amount|wo_|estimat|civil|mech|elect|ict|it_|eng|manager|plumber|architect|"
    r"duration|date|partner|client|contract|agreement|city|state|status|stage|"
    r"progress|cost|profit|pending|code|project_number|operating_unit|write_|create_",
    re.IGNORECASE,
)


def main() -> int:
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter

    adapter = get_shared_odoo_adapter()

    print("=" * 70)
    print("1) fields_get(project.project)")
    fields = adapter.call_method(
        "project.project",
        "fields_get",
        [],
        {"attributes": ["string", "type", "relation"]},
    )
    print(f"   total fields: {len(fields)}")
    out_dir = ROOT / ".cache" / "introspection"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "project_project_fields.json").write_text(json.dumps(fields, indent=2))
    print(f"   saved -> {out_dir / 'project_project_fields.json'}")

    interesting = {
        name: meta
        for name, meta in fields.items()
        if INTERESTING_RE.search(name) or INTERESTING_RE.search(str(meta.get("string", "")))
    }
    print(f"\n2) Interesting fields ({len(interesting)}):")
    for name in sorted(interesting):
        meta = interesting[name]
        rel = f" -> {meta.get('relation')}" if meta.get("relation") else ""
        print(f"   {name:38s} {meta.get('type', ''):10s} {meta.get('string', '')!r}{rel}")

    def read_full(label: str, domain: list[Any]) -> dict[str, Any] | None:
        # Read one record at a time: broken Elrace computed fields (e.g.
        # pending_days) raise singleton errors on multi-record full reads.
        ids = adapter.call_method("project.project", "search", [domain], {"limit": 1})
        if not ids:
            print(f"\n   [{label}] NOT FOUND for domain {domain}")
            return None
        recs = adapter.call_method("project.project", "read", [ids], {})
        rec = recs[0]
        print(f"\n3) [{label}] id={rec.get('id')} name={rec.get('name')!r}")
        record_path = out_dir / f"record_{rec.get('id')}.json"
        record_path.write_text(json.dumps(rec, indent=2, default=str))
        print(f"   saved -> {record_path}")
        return rec

    villa = read_full("Villa 48 (screenshot)", [["wo_ref_no", "=", "1420240098-35"]])
    ng = read_full("National Guard", [["name", "ilike", "national guard"]])

    if villa:
        print("\n4) Fields on Villa 48 matching screenshot values:")
        for key, target in SCREENSHOT_VALUES.items():
            hits = [
                fname
                for fname, value in villa.items()
                if isinstance(value, (int, float))
                and not isinstance(value, bool)
                and abs(float(value) - target) < 0.01
                and (target != 0.0 or INTERESTING_RE.search(fname))
            ]
            print(f"   {key:12s} = {target:>12,.2f} -> {hits}")

        print("\n5) Non-empty interesting values on Villa 48:")
        for fname in sorted(interesting):
            value = villa.get(fname)
            if value not in (None, False, 0.0, "", []):
                print(f"   {fname:38s} = {value!r}")

    if ng:
        print("\n6) Non-empty interesting values on National Guard:")
        for fname in sorted(interesting):
            value = ng.get(fname)
            if value not in (None, False, 0.0, "", []):
                print(f"   {fname:38s} = {value!r}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
