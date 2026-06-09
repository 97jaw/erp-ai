"""Minimal result synthesis for orchestrated multi-step queries (Phase 4 stub)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gateway.core.execution_orchestrator import ExecutionResult
from gateway.core.intent_analyzer import Intent
from gateway.core.project_expense_routing import is_project_expense_tool_result
from gateway.quality_narrative import narrate_project_expense_summary
from gateway.tools.project_expense import PROJECT_EXPENSE_TOOL_NAMES, SUMMARY_SOURCES


@dataclass
class SynthesizedResult:
    """User-facing text and optional visualization from orchestration output."""

    text: str
    visualization: dict[str, Any] | None = None


class ResultSynthesizer:
    """Combine orchestrator outputs into a concise response."""

    def synthesize(self, execution_result: ExecutionResult, intent: Intent) -> SynthesizedResult:
        """Build narrative text and visualization payload from execution results."""
        composed = self._find_composed_report(execution_result.results)
        if composed is not None:
            return self._from_composed_report(composed, intent)

        aggregate_tables = self._collect_aggregate_tables(execution_result.results)
        if len(aggregate_tables) >= 2:
            return self._from_parallel_aggregates(aggregate_tables, intent)
        if len(aggregate_tables) == 1:
            return self._from_single_aggregate(aggregate_tables[0], intent)

        mobile_summary = self._find_project_expense_summary(execution_result.results, intent)
        if mobile_summary is not None:
            return mobile_summary

        if not self._used_project_expense_tools(execution_result):
            project_summary = self._find_legacy_project_expense_kpi(execution_result.results)
            if project_summary is not None:
                return project_summary

        if execution_result.results:
            step_count = len(execution_result.results)
            failure_count = len(execution_result.failures)
            return SynthesizedResult(
                text=(
                    f"Completed {step_count} orchestrated step(s) for: {intent.specific_intent}. "
                    f"{failure_count} step(s) failed."
                ),
            )

        return SynthesizedResult(
            text="No data found for that request. Please try narrowing the period or filters.",
        )

    @staticmethod
    def _used_project_expense_tools(execution_result: ExecutionResult) -> bool:
        for step in execution_result.strategy_used.steps:
            if step.tool in PROJECT_EXPENSE_TOOL_NAMES:
                return True
        return False

    @staticmethod
    def _find_project_expense_summary(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if payload.get("_source") not in SUMMARY_SOURCES:
                continue
            if payload.get("status") != "success":
                continue
            text = narrate_project_expense_summary(
                payload,
                user_message=intent.specific_intent,
            )
            return SynthesizedResult(text=text, visualization=None)
        return None

    @staticmethod
    def _find_legacy_project_expense_kpi(results: dict[int, Any]) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if is_project_expense_tool_result(payload):
                continue
            project_name = (
                payload.get("project_name")
                or payload.get("project")
                or "the project"
            )
            total = None
            for key in ("total_expenses", "total_cost", "expense_total", "total_expense"):
                if key in payload:
                    try:
                        total = float(payload[key] or 0)
                        break
                    except (TypeError, ValueError):
                        continue
            if total is None:
                continue
            text = (
                f"{project_name}: total expenses are AED {total:,.2f} "
                "for the selected period."
            )
            return SynthesizedResult(
                text=text,
                visualization={
                    "visual_type": "KPI_CARD",
                    "title": str(project_name),
                    "data": {
                        "label": "Total Expenses (AED)",
                        "value": round(total, 2),
                    },
                },
            )
        return None

    @staticmethod
    def _find_composed_report(results: dict[int, Any]) -> dict[str, Any] | None:
        for step_number in sorted(results.keys(), reverse=True):
            payload = results[step_number]
            if isinstance(payload, dict) and payload.get("columns") and payload.get("rows"):
                return payload
        return None

    @staticmethod
    def _collect_aggregate_tables(results: dict[int, Any]) -> list[dict[str, Any]]:
        tables: list[dict[str, Any]] = []
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict):
                continue
            rows = payload.get("rows") or payload.get("groups") or payload.get("data")
            if isinstance(rows, list) and rows:
                tables.append({"step_number": step_number, "payload": payload, "rows": rows})
        return tables

    def _from_composed_report(
        self,
        composed: dict[str, Any],
        intent: Intent,
    ) -> SynthesizedResult:
        title = str(composed.get("title") or intent.specific_intent)
        columns = [str(column) for column in composed.get("columns") or []]
        rows = composed.get("rows") or []
        text = (
            f"{title}: comparison ready across {len(rows)} row(s). "
            "See the table for Q1 period values and variance."
        )
        visualization = {
            "visual_type": "DATA_TABLE",
            "label": title,
            "data": {
                "headers": columns,
                "rows": [
                    [row.get(column) for column in columns]
                    for row in rows
                    if isinstance(row, dict)
                ],
            },
            "suggestions": [],
        }
        return SynthesizedResult(text=text, visualization=visualization)

    def _from_parallel_aggregates(
        self,
        tables: list[dict[str, Any]],
        intent: Intent,
    ) -> SynthesizedResult:
        columns = ["Client", "Period 1 Revenue (AED)", "Period 2 Revenue (AED)", "Change (AED)"]
        merged_rows: list[dict[str, Any]] = []
        left_rows = tables[0]["rows"][:5]
        right_rows = tables[1]["rows"][:5] if len(tables) > 1 else []
        right_by_client = {
            self._client_key(row): self._revenue_value(row)
            for row in right_rows
            if isinstance(row, dict)
        }

        for row in left_rows:
            if not isinstance(row, dict):
                continue
            client = self._client_label(row)
            left_value = self._revenue_value(row)
            right_value = right_by_client.get(self._client_key(row), 0.0)
            merged_rows.append({
                "Client": client,
                "Period 1 Revenue (AED)": left_value,
                "Period 2 Revenue (AED)": right_value,
                "Change (AED)": round(right_value - left_value, 2),
            })

        composed = {
            "title": intent.specific_intent,
            "columns": columns,
            "rows": merged_rows,
        }
        return self._from_composed_report(composed, intent)

    def _from_single_aggregate(
        self,
        table: dict[str, Any],
        intent: Intent,
    ) -> SynthesizedResult:
        rows = table["rows"][:5]
        if not rows or not any(self._revenue_value(row) for row in rows if isinstance(row, dict)):
            return SynthesizedResult(text=no_data_text(intent))

        headers = ["Client", "Revenue (AED)"]
        table_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            table_rows.append({
                "Client": self._client_label(row),
                "Revenue (AED)": self._revenue_value(row),
            })

        composed = {
            "title": intent.specific_intent,
            "columns": headers,
            "rows": table_rows,
        }
        return self._from_composed_report(composed, intent)

    @staticmethod
    def _client_label(row: dict[str, Any]) -> str:
        for key in ("partner_id", "client", "name", "group"):
            value = row.get(key)
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                return str(value[1])
            if value not in (None, ""):
                return str(value)
        return "Unknown"

    @staticmethod
    def _client_key(row: dict[str, Any]) -> str:
        return ResultSynthesizer._client_label(row).lower()

    @staticmethod
    def _revenue_value(row: dict[str, Any]) -> float:
        for key in ("amount_total:sum", "revenue", "balance", "amount_total", "credit", "debit"):
            if key in row:
                try:
                    return round(float(row[key] or 0), 2)
                except (TypeError, ValueError):
                    continue
        return 0.0


def no_data_text(intent: Intent) -> str:
    subject = intent.specific_intent.strip().rstrip(".")
    return (
        f"No data found for {subject}. "
        "Try a wider date range or confirm the filters match posted records in Odoo."
    )
