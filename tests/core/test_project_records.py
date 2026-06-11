"""Project Model Phase 2 — project records lane tests.

Covers: record-list query detection + record_type derivation, Deep Think
carve-out, project hint extraction, tool execution/normalization (default
period, missing analytic, zero rows), narration, synthesizer dispatch,
visualization columns, quality-pipeline meaningful-data, entity gate
requirements, and the records suggestion chips.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from gateway.core.deep_think import is_deep_think_eligible
from gateway.core.entity_gate import EntityGate
from gateway.core.intent_analyzer import Intent
from gateway.core.project_records_routing import (
    derive_record_type,
    extract_records_project_hint,
    is_project_records_text,
)
from gateway.core.quality_pipeline import has_meaningful_tool_data
from gateway.quality_narrative import narrate_project_records
from gateway.tools.project_records import (
    RECORD_TYPE_VALUES,
    execute_get_project_records,
)
from gateway.visualization_builder import (
    build_visualization_from_tool_results,
    is_renderable_visualization,
)

NG_PROJECT_ID = 14458

_LPO_ROWS = [
    {
        "id": 50001,
        "name": "BILL/2026/0101",
        "invoice_date": "2026-05-30",
        "partner_id": [13044, "SUKOON TAKAFUL P.J.S.C."],
        "amount_total": 482.36,
        "amount_residual": 0.0,
        "payment_state": "paid",
        "state": "posted",
        "ref": "OPD10-125002103",
        "invoice_origin": False,
    },
    {
        "id": 50002,
        "name": "BILL/2026/0102",
        "invoice_date": "2026-05-12",
        "partner_id": [10426, "Bin Moosa Trading"],
        "amount_total": 7363.23,
        "amount_residual": 7363.23,
        "payment_state": "not_paid",
        "state": "posted",
        "ref": False,
        "invoice_origin": "RCC-PO-27329",
    },
]

_STAFF_ROWS = [
    {
        "id": 41430,
        "emp_code": "1173",
        "emp_name": "Ahmed A A Alhamayda",
        "employee_id": [709, "Ahmed A A Alhamayda"],
        "job_id": [256, "Civil Engineer"],
        "status": "on_duty",
        "access": "allow",
        "write_date": "2025-10-01 07:20:23",
    },
]


class _StubAdapter:
    """Mimics V14 adapter read_project_records + project name lookup."""

    def __init__(
        self,
        rows: list[dict[str, Any]],
        total_count: int,
        total_amount: float | None = None,
        missing_analytic: bool = False,
    ) -> None:
        self.rows = rows
        self.total_count = total_count
        self.total_amount = total_amount
        self.missing_analytic = missing_analytic
        self.calls: list[dict[str, Any]] = []

    def read_project_records(self, record_type, project_id, **kwargs):
        self.calls.append({"record_type": record_type, "project_id": project_id, **kwargs})
        if self.missing_analytic:
            return {"rows": [], "total_count": 0, "total_amount": None,
                    "missing_analytic": True}
        return {
            "rows": self.rows,
            "total_count": self.total_count,
            "total_amount": self.total_amount,
        }

    def safe_search_read(self, model, domain, fields, limit=100, offset=0, order=None):
        assert model == "project.project"
        return [{"id": NG_PROJECT_ID, "name": "NATIONAL GUARD COMMAND - Al Nouf Center"}]


def _records_payload(record_type: str = "lpo_invoices", **overrides: Any) -> dict[str, Any]:
    adapter = _StubAdapter(_LPO_ROWS, total_count=283, total_amount=1234567.89)
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": record_type},
        adapter,
    )
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Detection + record type derivation
# ---------------------------------------------------------------------------


def test_records_detection_per_type() -> None:
    cases = {
        "show me invoices of project national guard": "invoices",
        "client invoices of national guard": "client_invoices",
        "LPO invoices for Villa 48": "lpo_invoices",
        "purchase orders of project national guard": "purchase_orders",
        "timesheets for Villa Maintenance 48": "timesheets",
        "petty cash of national guard": "petty_cash",
        "petty cash sheets for national guard": "petty_cash_sheets",
        "staff list of project national guard": "staff",
        "supervisors of Villa 48": "supervisors",
    }
    for message, expected in cases.items():
        assert is_project_records_text(message), message
        assert derive_record_type(message) == expected, message


def test_analysis_queries_stay_out_of_records_lane() -> None:
    for message in (
        "expense breakdown of national guard",
        "show me the P&L for last 3 months",
        "compare invoices of villa 48 vs villa 34",
        "show me expenses for Villa 48",
    ):
        assert not is_project_records_text(message), message


def test_records_hint_drops_record_keyword() -> None:
    assert extract_records_project_hint("invoices of project national guard") == "national guard"
    assert extract_records_project_hint("staff list of project national guard") == "national guard"
    assert extract_records_project_hint("timesheets for Villa Maintenance 48") == "Villa Maintenance 48"


def test_records_query_not_deep_think_eligible() -> None:
    assert not is_deep_think_eligible("show me invoices of project national guard")
    assert not is_deep_think_eligible("staff list of project national guard")
    assert is_deep_think_eligible("show me expenses for Villa 48")


# ---------------------------------------------------------------------------
# Tool execution + normalization
# ---------------------------------------------------------------------------


def test_execute_records_normalizes_rows_and_defaults_period() -> None:
    adapter = _StubAdapter(_LPO_ROWS, total_count=283, total_amount=1234567.89)
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": "lpo_invoices"},
        adapter,
    )
    assert payload["status"] == "success"
    assert payload["_source"] == "project_records"
    assert payload["project_name"] == "NATIONAL GUARD COMMAND - Al Nouf Center"
    assert payload["total_count"] == 283
    assert payload["returned_count"] == 2
    assert payload["period"]["defaulted"] is True
    assert payload["period"]["date_from"] is not None
    first = payload["rows"][0]
    assert first["number"] == "BILL/2026/0101"
    assert first["partner"] == "SUKOON TAKAFUL P.J.S.C."
    assert first["total"] == 482.36
    # Adapter received the defaulted dates
    assert adapter.calls[0]["date_from"] is not None


def test_execute_records_staff_is_undated() -> None:
    adapter = _StubAdapter(_STAFF_ROWS, total_count=27)
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": "staff"},
        adapter,
    )
    assert payload["period"]["date_from"] is None
    assert payload["period"]["defaulted"] is False
    row = payload["rows"][0]
    assert row["code"] == "1173"
    assert row["job"] == "Civil Engineer"


def test_execute_records_unknown_type_errors() -> None:
    adapter = _StubAdapter([], total_count=0)
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": "payslips"},
        adapter,
    )
    assert payload["status"] == "error"


def test_execute_records_missing_analytic() -> None:
    adapter = _StubAdapter([], total_count=0, missing_analytic=True)
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": "client_invoices"},
        adapter,
    )
    assert payload["status"] == "success"
    assert payload["missing_analytic"] is True
    text = narrate_project_records(payload)
    assert "analytic account" in text


# ---------------------------------------------------------------------------
# Narration
# ---------------------------------------------------------------------------


def test_narrate_records_counts_total_and_period() -> None:
    payload = _records_payload()
    text = narrate_project_records(payload)
    assert "283 LPO invoices" in text
    assert "AED 1,234,567.89" in text
    assert "last 3 months by default" in text
    assert "Showing the latest 2" in text


def test_narrate_records_zero_state_is_honest() -> None:
    adapter = _StubAdapter([], total_count=0)
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": "timesheets"},
        adapter,
    )
    text = narrate_project_records(payload)
    assert "no timesheet entries recorded" in text


def test_narrate_timesheets_uses_hours() -> None:
    adapter = _StubAdapter(
        [{"date": "2026-06-01", "employee_id": [1, "X"], "name": "work",
          "unit_amount": 8.0, "task_id": False, "department_id": False}],
        total_count=10667,
        total_amount=85336.0,
    )
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": "timesheets"},
        adapter,
    )
    text = narrate_project_records(payload)
    assert "85,336.0 hours" in text
    assert "AED" not in text


# ---------------------------------------------------------------------------
# Synthesizer dispatch
# ---------------------------------------------------------------------------


def test_result_synthesizer_dispatches_records() -> None:
    from gateway.core.result_synthesizer import ResultSynthesizer

    payload = _records_payload()
    execution_result = SimpleNamespace(
        results={1: payload},
        strategy_used=SimpleNamespace(steps=[]),
    )
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="LPO invoices of national guard",
    )
    synthesized = ResultSynthesizer().synthesize(execution_result, intent)
    assert "283 LPO invoices" in synthesized.text


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------


def test_records_visualization_table() -> None:
    payload = _records_payload()
    visual = build_visualization_from_tool_results(["get_project_records"], [payload])
    assert visual is not None
    assert visual["visual_type"] == "DATA_TABLE"
    assert is_renderable_visualization(visual)
    assert visual.get("disclosure_exempt") is True
    assert visual["data"]["headers"][0] == "Bill"
    assert "latest 2 of 283" in visual["label"]
    assert visual["data"]["rows"][0][0] == "BILL/2026/0101"


def test_records_visualization_staff_columns() -> None:
    adapter = _StubAdapter(_STAFF_ROWS, total_count=27)
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": "staff"},
        adapter,
    )
    visual = build_visualization_from_tool_results(["get_project_records"], [payload])
    assert visual is not None
    assert visual["data"]["headers"] == ["Code", "Name", "Job", "Status", "Access"]


# ---------------------------------------------------------------------------
# Quality pipeline + entity gate
# ---------------------------------------------------------------------------


def test_records_payload_is_meaningful_even_when_empty() -> None:
    adapter = _StubAdapter([], total_count=0)
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": "petty_cash"},
        adapter,
    )
    assert has_meaningful_tool_data([payload])


def test_entity_gate_requires_project_for_records_tool() -> None:
    assert EntityGate.tool_requires_entity("get_project_records") == ["project"]
    assert EntityGate.is_entity_bound_financial_tool("get_project_records")


# ---------------------------------------------------------------------------
# Adapter spec coverage
# ---------------------------------------------------------------------------


def test_adapter_spec_covers_every_record_type() -> None:
    from adapters.v14.connector import OdooV14Adapter

    for record_type in RECORD_TYPE_VALUES:
        assert record_type in OdooV14Adapter.PROJECT_RECORD_SPECS, record_type


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------


def test_records_suggestions_cross_type_no_export_chips() -> None:
    from gateway.core.smart_suggestions import SmartSuggestionsGenerator
    from tests.core.test_context_stack import _make_context_stack

    context = _make_context_stack()
    payload = _records_payload()
    synthesized = SimpleNamespace(text="records answer", visualization=None)
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="LPO invoices of national guard",
    )
    suggestions = SmartSuggestionsGenerator().generate(
        synthesized,
        intent,
        context,
        tool_names=["get_project_records"],
        tool_results=[payload],
    )
    assert suggestions
    joined = " ".join(suggestions).lower()
    assert "export" not in joined
    assert "previous period" not in joined
    assert "client invoices" in joined  # sibling chip for lpo_invoices
    assert any("expenses" in item.lower() for item in suggestions)


def test_staff_supervisors_cross_suggest() -> None:
    from gateway.core.smart_suggestions import SmartSuggestionsGenerator
    from tests.core.test_context_stack import _make_context_stack

    context = _make_context_stack()
    adapter = _StubAdapter(_STAFF_ROWS, total_count=27)
    payload = execute_get_project_records(
        {"project_id": NG_PROJECT_ID, "record_type": "staff"},
        adapter,
    )
    synthesized = SimpleNamespace(text="staff answer", visualization=None)
    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="staff list of national guard",
    )
    suggestions = SmartSuggestionsGenerator().generate(
        synthesized,
        intent,
        context,
        tool_names=["get_project_records"],
        tool_results=[payload],
    )
    assert any("supervisors" in item.lower() for item in suggestions)
