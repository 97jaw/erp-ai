from __future__ import annotations

from gateway.core.result_synthesizer import ResultSynthesizer
from gateway.core.execution_orchestrator import ExecutionResult
from gateway.core.intent_analyzer import Intent
from gateway.quality_narrative import narrate_project_expense_summary, user_asked_for_calendar_period


def test_user_asked_for_calendar_period_detects_this_year() -> None:
    assert user_asked_for_calendar_period("Villa Maintenance No. 34 expense for this year") is True
    assert user_asked_for_calendar_period("Villa Maintenance No. 34 expense") is False


def test_narrate_project_expense_summary_includes_wo_context() -> None:
    text = narrate_project_expense_summary(
        {
            "project_name": "Villa Maintenance No. 34",
            "wo_amount": 500000,
            "total_expenses": 12120.16,
            "spend_percent_of_wo": 2.4,
            "top_expenses": [{"name": "Maintenance", "amount": 8000, "percent": 66.0}],
            "is_over_budget": False,
        },
        user_message="Villa Maintenance No. 34 expense for this year",
    )
    assert "Villa Maintenance No. 34" in text
    assert "12,120" in text
    assert "W.O" in text
    assert "Maintenance" in text
    assert "selected period" not in text.lower()
    assert "calendar period" in text.lower()


def test_result_synthesizer_mobile_expense_summary_text() -> None:
    from gateway.core.execution_orchestrator import ExecutionResult, VerificationResult
    from gateway.core.strategy_planner import ExecutionStep, Strategy

    intent = Intent(
        primary_action="fetch_data",
        subject_area="project",
        specific_intent="Villa Maintenance No. 34 expense for this year",
    )
    execution = ExecutionResult(
        results={
            1: {
                "status": "success",
                "project_name": "Villa Maintenance No. 34",
                "wo_amount": 500000,
                "total_expenses": 12120.16,
                "spend_percent_of_wo": 2.4,
                "top_expenses": [{"name": "Maintenance", "amount": 8000, "percent": 66.0}],
                "is_over_budget": False,
                "_source": "project_expense_summary",
            },
        },
        failures=[],
        verification=VerificationResult(passed=True),
        strategy_used=Strategy(
            steps=[
                ExecutionStep(
                    step_number=1,
                    description="summary",
                    tool="get_project_expense_summary",
                    tool_input={"project_id": 31034},
                ),
            ],
            synthesis_approach="summary",
            quality_checks=[],
            estimated_duration_ms=1000,
        ),
    )
    synthesized = ResultSynthesizer().synthesize(execution, intent)
    assert "selected period" not in synthesized.text.lower()
    assert "12,120" in synthesized.text
