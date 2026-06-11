"""Project Model Phase 1 — project profile lane tests.

Covers: profile query detection + focus, Deep Think carve-out, payload
normalization (verified live field map), narration, synthesizer dispatch,
visualization card, quality pipeline meaningful-data, and entity gate
requirements for get_project_profile.
"""

from __future__ import annotations

from typing import Any

from gateway.core.deep_think import is_deep_think_eligible
from gateway.core.entity_gate import EntityGate
from gateway.core.intent_analyzer import Intent
from gateway.core.project_profile_routing import (
    derive_profile_focus,
    is_project_profile_query,
    is_project_profile_text,
)
from gateway.core.quality_pipeline import has_meaningful_tool_data
from gateway.quality_narrative import narrate_project_profile
from gateway.tools.project_profile import (
    execute_get_project_profile,
    normalize_project_profile,
)
from gateway.visualization_builder import (
    build_visualization_from_tool_results,
    is_renderable_visualization,
)


# Mirrors the live Villa Maintenance No. 48 record (id 15162), trimmed.
VILLA_48_RECORD: dict[str, Any] = {
    "id": 15162,
    "name": "Villa Maintenance No . 48",
    "project_name_arabic": False,
    "wo_ref_no": "1420240098-35",
    "project_code": "91-1 / 2024 - RCC - Al Ain",
    "project_number": False,
    "contract_no": False,
    "partner_id": [11380, "Abu Dhabi Police"],
    "client_shortname": "AD Police",
    "partner_email": "test@elra.com",
    "partner_phone": False,
    "agreement_id": [126, "91-1 / 2024 - RCC - Al Ain"],
    "city_id": [25, "Al Ain"],
    "city": False,
    "state_id": [546, "Abu Dhabi"],
    "country_id": [2, "United Arab Emirates"],
    "operating_unit_id": [6, "RCC"],
    "latitude": False,
    "longitude": False,
    "date_start": "2026-06-01",
    "date": "2026-07-30",
    "estimated_duration": 60.0,
    "compliation_date": False,
    "pending_days": 49.0,
    "last_extend_date": False,
    "extend_duration": False,
    "wo_amount": 463189.58,
    "estimation_amount": 463189.58,
    "extended_amount": False,
    "extension_total_amount": 0.0,
    "project_eng_amount": 359762.606,
    "mechanical_eng_amount": 64248.975,
    "electrical_eng_amount": 39178.0,
    "it_eng_amount": 0.0,
    "plumber_amount": False,
    "branch_manager_amount": 0.0,
    "project_manager_amount": 0.0,
    "invoice_total_amount": 103370.72,
    "total_client_invoice": 0.0,
    "purchase_total_amount": 0.0,
    "total_cost": 206741.44,
    "project_cost": 0.0,
    "profit": 0.0,
    "user_id": [1060, "Mohammed W E Abuyousef"],
    "projects_manager": [881, "Hassan Mohamed M Abuebeid"],
    "branch_manager_id": False,
    "project_eng_id": False,
    "mechanical_eng_id": False,
    "electrical_eng_id": False,
    "it_eng_id": False,
    "plumber_id": False,
    "architect": False,
    "document_controller": False,
    "state": "progress",
    "project_status": [2, "In Progress"],
    "project_status_compute": "in_progress",
    "wo_type": "active",
    "active": True,
    "progress_overall_percent": 0.0,
    "progress_last_update": False,
    "progress_delayed_weeks": 0,
    "progress_on_time_weeks": 0,
    "create_uid": [4962, "Eiman Ateeq Abdulla Ahmed Alsayyad"],
    "create_date": "2026-06-02 06:28:32",
    "write_uid": [874, "Haroon Atta"],
    "write_date": "2026-06-09 08:37:06",
}


class _StubAdapter:
    def __init__(self, record: dict[str, Any] | None) -> None:
        self.record = record
        self.calls: list[int] = []

    def read_project_profile(self, project_id: int) -> dict[str, Any] | None:
        self.calls.append(project_id)
        return self.record


def _profile_intent(message: str, subject_area: str = "project") -> Intent:
    return Intent(
        primary_action="fetch_data",
        subject_area=subject_area,
        specific_intent=message,
    )


# ---------------------------------------------------------------------------
# Detection + focus
# ---------------------------------------------------------------------------


def test_engineers_amount_query_is_profile() -> None:
    message = "tell me engineers amount of project national guard"
    assert is_project_profile_text(message)
    assert derive_profile_focus(message) == "amounts"


def test_trade_amount_variants_are_profile_amounts() -> None:
    for message in (
        "civil amount for Villa 48",
        "what is the mechanical amount of project national guard",
        "show wo amount distribution for Villa Maintenance 48",
        "w.o amount of project national guard",
    ):
        assert is_project_profile_text(message), message
        assert derive_profile_focus(message) == "amounts", message


def test_team_and_schedule_focus() -> None:
    assert derive_profile_focus("who is the project manager of Villa 48") == "team"
    assert derive_profile_focus("start date of project national guard") == "schedule"
    assert derive_profile_focus("what's the status of project national guard") == "status"


def test_expense_queries_are_not_profile() -> None:
    for message in (
        "show me expenses for Villa Maintenance 48",
        "how much did we spend on project national guard",
        "break down project national guard by account",
        "Show me the P&L for the last 3 months",
        "show invoices for project national guard",
    ):
        assert not is_project_profile_text(message), message


def test_project_attribute_intent_counts_as_profile() -> None:
    intent = _profile_intent("who manages it", subject_area="project_attribute")
    assert is_project_profile_query("who manages it", intent)


# ---------------------------------------------------------------------------
# Deep Think carve-out
# ---------------------------------------------------------------------------


def test_profile_queries_not_deep_think_eligible() -> None:
    assert not is_deep_think_eligible("tell me engineers amount of project national guard")
    assert not is_deep_think_eligible("who is the project manager of Villa 48")
    assert not is_deep_think_eligible("wo amount distribution for Villa Maintenance 48")


def test_spend_queries_remain_deep_think_eligible() -> None:
    assert is_deep_think_eligible("show me expenses for Villa Maintenance 48")
    assert is_deep_think_eligible("Show me the P&L for the last 3 months")


# ---------------------------------------------------------------------------
# Normalization (live-verified field map)
# ---------------------------------------------------------------------------


def test_normalize_maps_trade_amounts() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="amounts")
    distribution = profile["amounts"]["distribution"]
    assert distribution["civil"] == 359762.606
    assert distribution["electrical"] == 39178.0
    assert distribution["mechanical"] == 64248.975
    assert distribution["ict"] == 0.0  # real zero stays zero
    assert distribution["plumbing"] is None  # Odoo False -> not set
    assert profile["amounts"]["wo_amount"] == 463189.58
    assert profile["_source"] == "project_profile"
    assert profile["status"] == "success"


def test_normalize_maps_team_and_audit() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD)
    assert profile["team"]["project_manager"] == {"id": 1060, "name": "Mohammed W E Abuyousef"}
    assert profile["team"]["civil_engineer"] is None
    assert profile["audit"]["last_updated_by"]["name"] == "Haroon Atta"
    assert profile["client_contract"]["client"]["name"] == "Abu Dhabi Police"
    assert profile["project_status"]["status"]["name"] == "In Progress"


def test_execute_tool_handles_missing_project() -> None:
    adapter = _StubAdapter(None)
    result = execute_get_project_profile({"project_id": 999}, adapter)
    assert result["status"] == "error"
    assert "not found" in result["message"].lower()
    assert adapter.calls == [999]


def test_execute_tool_returns_normalized_profile() -> None:
    adapter = _StubAdapter(VILLA_48_RECORD)
    result = execute_get_project_profile({"project_id": 15162, "focus": "amounts"}, adapter)
    assert result["status"] == "success"
    assert result["focus"] == "amounts"
    assert result["project_name"] == "Villa Maintenance No . 48"


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------


def test_narrate_amounts_focus_lists_distribution() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="amounts")
    text = narrate_project_profile(profile)
    assert "Villa Maintenance No . 48" in text
    assert "359,762.61" in text
    assert "39,178.00" in text
    assert "64,248.97" in text
    # Plumbing unset must not be fabricated as zero
    assert "Plumbing" not in text


def test_narrate_all_null_distribution_is_honest() -> None:
    record = dict(VILLA_48_RECORD)
    record.update(
        project_eng_amount=False,
        electrical_eng_amount=False,
        mechanical_eng_amount=False,
        it_eng_amount=False,
        plumber_amount=False,
    )
    profile = normalize_project_profile(record, focus="amounts")
    text = narrate_project_profile(profile)
    assert "not set in Odoo" in text


def test_narrate_team_focus() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="team")
    text = narrate_project_profile(profile)
    assert "Project Manager: Mohammed W E Abuyousef" in text
    assert "Hassan Mohamed M Abuebeid" in text
    assert "359,762" not in text  # focused: no amounts


# ---------------------------------------------------------------------------
# Synthesizer + quality pipeline + visualization
# ---------------------------------------------------------------------------


def test_result_synthesizer_dispatches_profile() -> None:
    from types import SimpleNamespace

    from gateway.core.result_synthesizer import ResultSynthesizer

    profile = normalize_project_profile(VILLA_48_RECORD, focus="amounts")
    execution_result = SimpleNamespace(
        results={1: profile},
        failures=[],
        strategy_used=SimpleNamespace(steps=[]),
    )
    intent = _profile_intent("tell me engineers amount of Villa 48")
    synthesized = ResultSynthesizer().synthesize(execution_result, intent)
    assert "359,762.61" in synthesized.text


def test_profile_payload_is_meaningful_even_when_amounts_unset() -> None:
    record = dict(VILLA_48_RECORD)
    record.update(
        wo_amount=False,
        estimation_amount=False,
        project_eng_amount=False,
        electrical_eng_amount=False,
        mechanical_eng_amount=False,
        it_eng_amount=False,
        invoice_total_amount=False,
        total_cost=False,
    )
    profile = normalize_project_profile(record, focus="amounts")
    assert has_meaningful_tool_data([profile])


def test_profile_visualization_card() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="amounts")
    visual = build_visualization_from_tool_results(["get_project_profile"], [profile])
    assert visual is not None
    assert visual["visual_type"] == "DATA_TABLE"
    assert is_renderable_visualization(visual)
    rows = dict((row[0], row[1]) for row in visual["data"]["rows"])
    assert rows["Civil Amount"] == 359762.61
    assert rows["Plumbing Amount"] == "Not set"


# ---------------------------------------------------------------------------
# Entity gate requirements
# ---------------------------------------------------------------------------


def test_entity_gate_requires_project_for_profile_tool() -> None:
    assert EntityGate.tool_requires_entity("get_project_profile") == ["project"]
    assert EntityGate.is_entity_bound_financial_tool("get_project_profile")
