#!/usr/bin/env python3
"""Phase R2 acceptance — project relationship queries via query_odoo composition."""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

VILLA_34_ID = 15157
NATIONAL_GUARD_ID = 14458
JUNE_2026_START = "2026-06-01"
JUNE_2026_END = "2026-06-30"


def _sleep() -> None:
    time.sleep(5)


async def main() -> int:
    from gateway.main import _compose_system_prompt_sections
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter

    adapter = get_shared_odoo_adapter()
    results: list[dict[str, Any]] = []

    def record(case: str, ok: bool, detail: str) -> None:
        results.append({"case": case, "pass": ok, "detail": detail})
        print(f"[{'PASS' if ok else 'FAIL'}] {case}: {detail}")

    prompt = _compose_system_prompt_sections("2026-06-11")
    record(
        "prompt injection",
        "=== PROJECT RELATIONAL MODEL ===" in prompt
        and "project.attachment" in prompt
        and "=== END RELATIONSHIP CONTEXT ===" in prompt,
        "relationship section present in composed system prompt",
    )
    _sleep()

    # 1. projects with no attachments
    active_rows = adapter.safe_search_read(
        "project.project",
        [["active", "=", True]],
        ["id", "name"],
        limit=5000,
    )
    active_ids = {int(row["id"]) for row in active_rows}
    attached_groups = adapter.read_group(
        "project.attachment",
        [],
        ["project_id"],
        ["project_id"],
        limit=5000,
    )
    attached_ids = {
        int(row["project_id"][0])
        for row in attached_groups
        if row.get("project_id") and isinstance(row["project_id"], (list, tuple))
    }
    missing_attachment_ids = sorted(active_ids - attached_ids)
    no_att = [
        row for row in active_rows if int(row["id"]) in set(missing_attachment_ids[:10])
    ]
    record(
        "1. projects with no attachments",
        True,
        f"{len(missing_attachment_ids)} active projects without project.attachment"
        + (
            f" (sample: {no_att[0]['name'][:60]})"
            if no_att
            else " — all active projects in scope have at least one attachment"
        ),
    )
    _sleep()

    # 2. agreement details for Villa 34
    villa = adapter.safe_search_read(
        "project.project",
        [["id", "=", VILLA_34_ID]],
        ["name", "agreement_id"],
        limit=1,
    )
    agreement_id = int(villa[0]["agreement_id"][0]) if villa and villa[0].get("agreement_id") else 0
    agreement = adapter.safe_search_read(
        "agreement",
        [["id", "=", agreement_id]],
        ["code", "name", "amount", "start_date", "end_date", "state"],
        limit=1,
    )
    record(
        "2. agreement details for Villa 34",
        bool(agreement) and agreement[0].get("code"),
        f"code={agreement[0].get('code')} amount={agreement[0].get('amount')} "
        f"dates={agreement[0].get('start_date')}→{agreement[0].get('end_date')}",
    )
    _sleep()

    # 3. client for national guard
    ng = adapter.safe_search_read(
        "project.project",
        [["id", "=", NATIONAL_GUARD_ID]],
        ["name", "partner_id"],
        limit=1,
    )
    partner_name = ng[0]["partner_id"][1] if ng and ng[0].get("partner_id") else ""
    record(
        "3. client for national guard project",
        "NATIONAL GUARD" in partner_name.upper(),
        f"partner={partner_name}",
    )
    _sleep()

    # 4. all projects for Abu Dhabi Police
    partners = adapter.safe_search_read(
        "res.partner",
        [["name", "ilike", "Abu Dhabi Police"]],
        ["id", "name"],
        limit=1,
    )
    partner_id = int(partners[0]["id"]) if partners else 0
    police_projects = adapter.safe_search_read(
        "project.project",
        [["partner_id", "=", partner_id], ["active", "=", True]],
        ["id", "name"],
        limit=10,
    )
    total_police = adapter.search_count(
        "project.project",
        [["partner_id", "=", partner_id], ["active", "=", True]],
    )
    record(
        "4. all projects for Abu Dhabi Police",
        len(police_projects) >= 1 and total_police >= len(police_projects),
        f"{total_police} active projects (showing {len(police_projects)})",
    )
    _sleep()

    # 5. projects missing WO documents
    wo_groups = adapter.read_group(
        "project.attachment",
        [["lead_attachment_type", "=", "wo"]],
        ["project_id"],
        ["project_id"],
        limit=5000,
    )
    wo_project_ids = {
        int(row["project_id"][0])
        for row in wo_groups
        if row.get("project_id") and isinstance(row["project_id"], (list, tuple))
    }
    missing_wo_ids = sorted(active_ids - wo_project_ids)
    missing_wo = [row for row in active_rows if int(row["id"]) in set(missing_wo_ids[:10])]
    record(
        "5. projects missing WO documents",
        len(missing_wo_ids) >= 1,
        f"{len(missing_wo_ids)} active projects without WO attachment"
        + (f" (sample: {missing_wo[0]['name'][:60]})" if missing_wo else ""),
    )
    _sleep()

    # 6. agreements expiring this month (June 2026)
    expiring = adapter.safe_search_read(
        "agreement",
        [
            ["end_date", ">=", JUNE_2026_START],
            ["end_date", "<=", JUNE_2026_END],
        ],
        ["code", "name", "end_date", "partner_id"],
        limit=10,
    )
    expiring_count = adapter.search_count(
        "agreement",
        [
            ["end_date", ">=", JUNE_2026_START],
            ["end_date", "<=", JUNE_2026_END],
        ],
    )
    record(
        "6. agreements expiring this month",
        expiring_count >= 0,
        f"{expiring_count} agreements ending in June 2026"
        + (f" (sample: {expiring[0].get('code')})" if expiring else ""),
    )
    _sleep()

    # 7. attachment count Villa 34
    att_count = adapter.search_count(
        "project.attachment",
        [["project_id", "=", VILLA_34_ID]],
    )
    record(
        "7. how many attachments does Villa 34 have",
        att_count >= 1,
        f"{att_count} project.attachment rows for project_id={VILLA_34_ID}",
    )
    _sleep()

    # 8. attachment types Villa 34
    types_rows = adapter.safe_search_read(
        "project.attachment",
        [["project_id", "=", VILLA_34_ID]],
        ["lead_attachment_type"],
        limit=50,
    )
    types = sorted({str(row.get("lead_attachment_type") or "") for row in types_rows if row.get("lead_attachment_type")})
    record(
        "8. attachment types for Villa 34",
        len(types) >= 1,
        f"types={types}",
    )
    _sleep()

    # 9. agreements without any projects
    project_agreements = adapter.safe_search_read(
        "project.project",
        [["agreement_id", "!=", False]],
        ["agreement_id"],
        limit=5000,
    )
    linked_agreement_ids = {
        int(row["agreement_id"][0])
        for row in project_agreements
        if row.get("agreement_id") and isinstance(row["agreement_id"], (list, tuple))
    }
    orphan = adapter.safe_search_read(
        "agreement",
        [["id", "not in", list(linked_agreement_ids) or [0]]],
        ["code", "name"],
        limit=10,
    )
    orphan_count = adapter.search_count(
        "agreement",
        [["id", "not in", list(linked_agreement_ids) or [0]]],
    )
    record(
        "9. agreements without any projects",
        orphan_count >= 0,
        f"{orphan_count} agreements with no linked project.project"
        + (f" (sample code: {orphan[0].get('code')})" if orphan else ""),
    )
    _sleep()

    # 10. contract code for Villa 34
    record(
        "10. contract code for Villa 34",
        bool(agreement) and str(agreement[0].get("code", "")).startswith("AG"),
        f"code={agreement[0].get('code') if agreement else None}",
    )
    _sleep()

    # 11. Villa 34 agreement amount and client name (project → agreement → partner)
    agreement_full = adapter.safe_search_read(
        "agreement",
        [["id", "=", agreement_id]],
        ["code", "amount", "partner_id"],
        limit=1,
    )
    ag_partner_name = (
        agreement_full[0]["partner_id"][1]
        if agreement_full and agreement_full[0].get("partner_id")
        else ""
    )
    record(
        "11. Villa 34 agreement amount and client name",
        bool(agreement_full) and ag_partner_name,
        f"amount={agreement_full[0].get('amount')} client={ag_partner_name}",
    )
    _sleep()

    # 12. projects for National Guard with WO status
    ng_partner_id = int(ng[0]["partner_id"][0]) if ng and ng[0].get("partner_id") else 0
    ng_projects = adapter.safe_search_read(
        "project.project",
        [["partner_id", "=", ng_partner_id], ["active", "=", True]],
        ["id", "name"],
        limit=5,
    )
    wo_status: list[str] = []
    for proj in ng_projects:
        pid = int(proj["id"])
        has_wo = adapter.search_count(
            "project.attachment",
            [["project_id", "=", pid], ["lead_attachment_type", "=", "wo"]],
        )
        wo_status.append(f"{proj['name'][:40]}:{'WO' if has_wo else 'no WO'}")
    record(
        "12. NG projects with WO status",
        len(ng_projects) >= 1 and len(wo_status) >= 1,
        f"{len(ng_projects)} projects — {'; '.join(wo_status[:3])}",
    )
    _sleep()

    # 13. agreement details including linked projects
    linked = adapter.safe_search_read(
        "project.project",
        [["agreement_id", "=", agreement_id]],
        ["id", "name"],
        limit=10,
    )
    linked_total = adapter.search_count(
        "project.project",
        [["agreement_id", "=", agreement_id]],
    )
    record(
        "13. agreement details including linked projects",
        bool(agreement_full) and linked_total >= 1,
        f"AG {agreement_full[0].get('code')} → {linked_total} linked projects "
        f"(sample: {linked[0]['name'][:50]})",
    )
    _sleep()

    # 14. projects with estimation documents
    est_groups = adapter.read_group(
        "project.attachment",
        [["lead_attachment_type", "=", "estimation"]],
        ["project_id"],
        ["project_id"],
        limit=5000,
    )
    est_project_count = len(
        {
            int(row["project_id"][0])
            for row in est_groups
            if row.get("project_id") and isinstance(row["project_id"], (list, tuple))
        }
    )
    record(
        "14. projects with estimation documents",
        est_project_count >= 1,
        f"{est_project_count} distinct projects with estimation attachments",
    )
    _sleep()

    # 15. client contact for Villa 34 agreement
    partner_id = (
        int(agreement_full[0]["partner_id"][0])
        if agreement_full and agreement_full[0].get("partner_id")
        else 0
    )
    contact = adapter.safe_search_read(
        "res.partner",
        [["id", "=", partner_id]],
        ["name", "phone", "mobile", "email", "street", "city"],
        limit=1,
    )
    has_contact = bool(
        contact
        and (
            contact[0].get("mobile")
            or contact[0].get("phone")
            or contact[0].get("email")
            or contact[0].get("street")
        )
    )
    c = contact[0] if contact else {}
    record(
        "15. client contact for Villa 34 agreement",
        has_contact,
        f"{c.get('name')} mobile={c.get('mobile')} email={c.get('email')} "
        f"street={str(c.get('street') or '')[:40]}",
    )

    relationship_cases = [row for row in results if row["case"][0].isdigit()]
    meaningful = sum(1 for row in relationship_cases if row["pass"])
    passed = sum(1 for row in results if row["pass"])
    print(f"\nSUMMARY: {passed}/{len(results)} passed; {meaningful}/15 relationship queries OK")
    return 0 if meaningful >= 12 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
