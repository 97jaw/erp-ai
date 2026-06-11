#!/usr/bin/env python3
"""Introspect project activity models on live Odoo (Phase 3).

Attachments (ir.attachment), chatter (mail.message), progress/audit fields on
project.project.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

OUT_DIR = ROOT / ".cache" / "introspection"


def main() -> int:
    from gateway.odoo_adapter_pool import get_shared_odoo_adapter

    adapter = get_shared_odoo_adapter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Sample project: NG Al Nouf
    project_id = 14458
    report: dict[str, Any] = {"project_id": project_id}

    att_domain = [
        ["res_model", "=", "project.project"],
        ["res_id", "=", project_id],
    ]
    att_count = adapter.search_count("ir.attachment", att_domain)
    att_rows = adapter.safe_search_read(
        "ir.attachment",
        att_domain,
        ["name", "mimetype", "file_size", "create_date", "create_uid", "description"],
        limit=3,
        order="create_date desc, id desc",
    )
    report["attachments"] = {"count": att_count, "sample": att_rows}

    msg_domain = [
        ["model", "=", "project.project"],
        ["res_id", "=", project_id],
    ]
    msg_count = adapter.search_count("mail.message", msg_domain)
    msg_rows = adapter.safe_search_read(
        "mail.message",
        msg_domain,
        [
            "date", "author_id", "subject", "body", "message_type",
            "subtype_id", "email_from",
        ],
        limit=5,
        order="date desc, id desc",
    )
    report["chatter"] = {"count": msg_count, "sample": msg_rows}

    profile = adapter.read_project_profile(project_id)
    if profile:
        report["progress_audit"] = {
            k: profile.get(k)
            for k in (
                "progress_overall_percent",
                "progress_last_update",
                "progress_delayed_weeks",
                "progress_on_time_weeks",
                "project_status",
                "project_status_compute",
                "state",
                "create_uid",
                "create_date",
                "write_uid",
                "write_date",
            )
        }

    out_path = OUT_DIR / "project_activity_introspection.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
