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
    assert derive_profile_focus(message) == "engineers"


def test_single_trade_amount_focus() -> None:
    assert derive_profile_focus("civil amount for Villa 48") == "civil"
    assert derive_profile_focus("what is the mechanical amount of project x") == "mechanical"
    assert derive_profile_focus("electrical engineer amount of Villa 48") == "electrical"
    assert derive_profile_focus("ict amount for national guard") == "ict"


def test_wo_amount_focus_is_single_value() -> None:
    for message in (
        "w.o amount of project national guard",
        "wo amount of Villa 48",
        "work order amount for national guard",
    ):
        assert is_project_profile_text(message), message
        assert derive_profile_focus(message) == "wo_amount", message


def test_estimation_amount_focus_is_single_value() -> None:
    assert derive_profile_focus("estimation amount of Villa 48") == "estimation"


def test_distribution_wording_keeps_full_amounts() -> None:
    assert derive_profile_focus("show wo amount distribution for Villa Maintenance 48") == "amounts"


def test_trade_amount_hint_drops_trade_word() -> None:
    from gateway.core.project_query_utils import extract_project_name_hint

    assert extract_project_name_hint("civil amount of Villa Maintenance 48") == "Villa Maintenance 48"
    assert extract_project_name_hint("engineers amount of project national guard") == "national guard"
    assert extract_project_name_hint("w.o amount of project national guard") == "national guard"


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


def test_out_of_scope_general_knowledge_is_not_profile() -> None:
    from dataclasses import replace

    intent = replace(
        _profile_intent("who is the King of UAE right now", subject_area="project_attribute"),
        out_of_scope=True,
        out_of_scope_reason="General knowledge outside ERP scope",
    )
    assert not is_project_profile_query("who is the King of UAE right now", intent)
    assert not is_project_profile_text("who is the King of UAE right now")


def test_extract_project_name_hint_requires_project_context() -> None:
    from gateway.core.project_query_utils import extract_project_name_hint

    assert extract_project_name_hint("who is the King of UAE right now") is None


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


def test_narrate_engineers_focus_only_four_disciplines() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="engineers")
    text = narrate_project_profile(profile)
    assert "Civil AED 359,762.61" in text
    assert "Electrical AED 39,178.00" in text
    assert "Mechanical AED 64,248.97" in text
    assert "ICT AED 0.00" in text
    assert "W.O Amount" not in text
    assert "Estimation" not in text
    assert "Plumbing" not in text
    assert "Branch Manager" not in text
    assert "Project Manager" not in text


def test_narrate_single_trade_focus() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="civil")
    text = narrate_project_profile(profile)
    assert "Civil AED 359,762.61" in text
    assert "Electrical" not in text
    assert "Mechanical" not in text
    assert "ICT" not in text


def test_narrate_engineers_all_unset_is_honest() -> None:
    record = dict(VILLA_48_RECORD)
    record.update(
        project_eng_amount=False,
        electrical_eng_amount=False,
        mechanical_eng_amount=False,
        it_eng_amount=False,
    )
    profile = normalize_project_profile(record, focus="engineers")
    text = narrate_project_profile(profile)
    assert "not set in Odoo" in text


def test_narrate_wo_amount_focus_only_wo() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="wo_amount")
    text = narrate_project_profile(profile)
    assert "W.O Amount: AED 463,189.58" in text
    assert "Civil" not in text
    assert "Electrical" not in text
    assert "Estimation" not in text
    assert "distribution" not in text.lower()


def test_wo_amount_visualization_single_row() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="wo_amount")
    visual = build_visualization_from_tool_results(["get_project_profile"], [profile])
    assert visual is not None
    assert [row[0] for row in visual["data"]["rows"]] == ["W.O Amount"]
    assert "W.O Amount" in visual["label"]


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


def test_engineers_visualization_card_only_four_rows() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="engineers")
    visual = build_visualization_from_tool_results(["get_project_profile"], [profile])
    assert visual is not None
    labels = [row[0] for row in visual["data"]["rows"]]
    assert labels == ["Civil Amount", "Electrical Amount", "Mechanical Amount", "ICT Amount"]
    assert "Engineer Amounts" in visual["label"]
    assert visual.get("disclosure_exempt") is True


def test_single_trade_visualization_card() -> None:
    profile = normalize_project_profile(VILLA_48_RECORD, focus="ict")
    visual = build_visualization_from_tool_results(["get_project_profile"], [profile])
    assert visual is not None
    assert [row[0] for row in visual["data"]["rows"]] == ["ICT Amount"]
    assert "ICT Amount" in visual["label"]


def test_profile_card_exempt_from_progressive_disclosure() -> None:
    from gateway.progressive_disclosure import apply_progressive_disclosure

    profile = normalize_project_profile(VILLA_48_RECORD, focus="amounts")
    visual = build_visualization_from_tool_results(["get_project_profile"], [profile])
    enriched = apply_progressive_disclosure(
        visual,
        "tell me engineers amount of project national guard",
        [profile],
    )
    assert enriched["can_expand"] is False
    # Rows survive intact — no summary-chart stripping, no "See all N records"
    assert enriched["data"]["rows"] == visual["data"]["rows"]


def test_profile_suggestions_have_no_expense_chips() -> None:
    from types import SimpleNamespace

    from gateway.core.smart_suggestions import SmartSuggestionsGenerator
    from tests.core.test_context_stack import _make_context_stack

    context = _make_context_stack()
    context.working_memory.set_active_project(14458, "NATIONAL GUARD COMMAND - Al Nouf Center", confirmed=True)
    profile = normalize_project_profile(VILLA_48_RECORD, focus="engineers")
    synthesized = SimpleNamespace(text="profile answer", visualization=None)
    suggestions = SmartSuggestionsGenerator().generate(
        synthesized,
        _profile_intent("tell me engineers amount"),
        context,
        tool_names=["get_project_profile"],
        tool_results=[profile],
    )
    assert suggestions, "profile answers should still offer follow-ups"
    joined = " ".join(suggestions).lower()
    assert "export" not in joined
    assert "previous period" not in joined
    assert "break down" not in joined
    assert "filter" not in joined
    assert any("schedule" in item.lower() or "project manager" in item.lower() for item in suggestions)
    assert any("expenses" in item.lower() for item in suggestions)  # the Deep Think handoff


# ---------------------------------------------------------------------------
# Entity gate requirements
# ---------------------------------------------------------------------------


def test_entity_gate_requires_project_for_profile_tool() -> None:
    assert EntityGate.tool_requires_entity("get_project_profile") == ["project"]
    assert EntityGate.is_entity_bound_financial_tool("get_project_profile")


# ---------------------------------------------------------------------------
# Confirmation wording for profile queries
# ---------------------------------------------------------------------------


def test_profile_entity_clarification_wording_not_financial() -> None:
    import time

    from gateway.core.interaction_telemetry import InteractionTelemetry
    from gateway.core.telemetry_capture import InMemoryTelemetryStore, TelemetryCapture
    from gateway.intelligent_handler import EntityResolutionMeta, IntelligentQueryHandler
    from tests.core.test_context_stack import _make_context_stack

    handler = IntelligentQueryHandler(
        telemetry_capture=TelemetryCapture(repository=InMemoryTelemetryStore()),
    )
    telemetry = InteractionTelemetry.start(
        user_id=4291,
        session_id="profile-wording",
        user_query="start date and duration of project national guard",
    )
    options = [
        {"id": "14458", "label": "NATIONAL GUARD COMMAND - Al Nouf Center",
         "entity_type": "project", "entity_id": 14458, "action": "confirm_entity"},
        {"id": "14071", "label": "National Guard Ambulance",
         "entity_type": "project", "entity_id": 14071, "action": "confirm_entity"},
    ]
    meta = EntityResolutionMeta(
        needs_clarification=True,
        clarification_options=options,
        clarification_matches=options,
    )
    response = handler._finalize_entity_clarification(
        entity_meta=meta,
        context=_make_context_stack(),
        telemetry=telemetry,
        resolved_session="profile-wording",
        language="en",
        message="start date and duration of project national guard",
        started=time.perf_counter(),
        intent=None,
        profile_query=True,
    )
    assert "financial data" not in response.text.lower()
    assert "which project" in response.text.lower()
    assert response.awaiting_clarification
