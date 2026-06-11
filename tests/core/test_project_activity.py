"""Project Model Phase 3 — activity lane + profile routing regression tests."""

from __future__ import annotations

from gateway.core.deep_think import is_deep_think_eligible
from gateway.core.project_activity_routing import (
    derive_activity_type,
    is_project_activity_text,
)
from gateway.core.project_profile_routing import derive_profile_focus
from gateway.core.project_query_utils import (
    extract_broad_project_search_term,
    extract_project_name_hint,
    is_broad_project_search,
)
from gateway.core.quality_pipeline import has_meaningful_tool_data
from gateway.quality_narrative import narrate_project_activity
from gateway.tool_cache import build_tool_cache_key
from gateway.tools.project_activity import execute_get_project_activity


def test_profile_focus_cache_keys_differ() -> None:
    base = {"project_id": 14458}
    engineers = build_tool_cache_key(1, "get_project_profile", {**base, "focus": "engineers"})
    wo = build_tool_cache_key(1, "get_project_profile", {**base, "focus": "wo_amount"})
    schedule = build_tool_cache_key(1, "get_project_profile", {**base, "focus": "schedule"})
    assert len({engineers, wo, schedule}) == 3


def test_derive_profile_focus_wo_and_schedule() -> None:
    assert derive_profile_focus("w.o amount of project national guard") == "wo_amount"
    assert derive_profile_focus("start date and duration of project national guard") == "schedule"


def test_civil_amount_hint_strips_trade() -> None:
    assert extract_project_name_hint("civil amount of Villa Maintenance 48") == "Villa Maintenance 48"


def test_broad_project_search_detection() -> None:
    assert is_broad_project_search("show all projects containing civil")
    assert extract_broad_project_search_term("show all projects containing civil") == "civil"
    assert not is_deep_think_eligible("show all projects containing civil")


def test_activity_type_derivation() -> None:
    assert derive_activity_type("attachments of project national guard") == "attachments"
    assert derive_activity_type("chatter summary of national guard") == "chatter_summary"
    assert derive_activity_type("project progress of national guard") == "progress"
    assert derive_activity_type("last updated by for national guard") == "audit"
    assert is_project_activity_text("attachments of project national guard")


class _StubAdapter:
    def safe_search_read(self, model, domain, fields, limit=1, **kwargs):
        del model, domain, fields, kwargs
        return [{"name": "NG Al Nouf Center"}]

    def read_project_attachments(self, project_id, *, limit=20, offset=0):
        del project_id, limit, offset
        return {
            "rows": [{"name": "doc.pdf", "mimetype": "application/pdf", "file_size": 1024,
                       "create_date": "2026-05-01", "create_uid": [1, "User"], "description": False}],
            "total_count": 1,
        }

    def read_project_chatter_messages(self, project_id, *, limit=25):
        del project_id, limit
        return {"rows": [], "total_count": 0}

    def read_project_progress_audit(self, project_id):
        del project_id
        return {
            "progress_overall_percent": 4.26,
            "progress_last_update": "2026-05-08",
            "progress_delayed_weeks": 93,
            "progress_on_time_weeks": 0,
            "project_status": [2, "In Progress"],
            "project_status_compute": "in_progress",
            "state": "progress",
            "create_uid": [870, "Creator"],
            "create_date": "2025-09-07 12:07:12",
            "write_uid": [5351, "Updater"],
            "write_date": "2026-05-18 11:18:37",
        }


def test_execute_attachments_and_progress() -> None:
    adapter = _StubAdapter()
    att = execute_get_project_activity(
        {"project_id": 14458, "activity_type": "attachments"},
        adapter,
    )
    assert att["status"] == "success"
    assert att["total_count"] == 1
    prog = execute_get_project_activity(
        {"project_id": 14458, "activity_type": "progress"},
        adapter,
    )
    assert prog["progress_audit"]["progress_percent"] == 4.26
    text = narrate_project_activity(prog)
    assert "4.26%" in text or "4.3" in text


def test_activity_payload_is_meaningful_even_when_empty_chatter() -> None:
    payload = {
        "status": "success",
        "_source": "project_activity",
        "activity_type": "chatter_summary",
        "summary": "No recent notes.",
        "total_count": 0,
    }
    assert has_meaningful_tool_data([payload])
