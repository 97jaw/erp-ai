"""Minimal result synthesis for orchestrated multi-step queries (Phase 4 stub)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gateway.core.execution_orchestrator import ExecutionResult
from gateway.core.intent_analyzer import Intent
from gateway.core.project_expense_routing import is_project_expense_tool_result
from gateway.quality_narrative import (
    narrate_financial_report,
    narrate_project_expense_breakdown,
    narrate_project_expense_comparison,
    narrate_project_expense_summary,
    narrate_project_activity,
    narrate_project_profile,
    narrate_project_records,
    narrate_universal_aggregate,
    narrate_universal_query,
)
from gateway.tools.project_activity import ACTIVITY_SOURCE
from gateway.tools.project_expense import PROJECT_EXPENSE_TOOL_NAMES, SUMMARY_SOURCES
from gateway.tools.project_profile import PROFILE_SOURCE
from gateway.tools.project_records import RECORDS_SOURCE

BREAKDOWN_SOURCE = "project_expense_breakdown_mobile"


@dataclass
class SynthesizedResult:
    """User-facing text and optional visualization from orchestration output."""

    text: str
    visualization: dict[str, Any] | None = None


class ResultSynthesizer:
    """Combine orchestrator outputs into a concise response."""

    def synthesize(self, execution_result: ExecutionResult, intent: Intent) -> SynthesizedResult:
        """Build narrative text and visualization payload from execution results."""
        profile = self._find_project_profile(execution_result.results, intent)
        if profile is not None:
            return profile

        records = self._find_project_records(execution_result.results, intent)
        if records is not None:
            return records

        activity = self._find_project_activity(execution_result.results, intent)
        if activity is not None:
            return activity

        composed = self._find_composed_report(execution_result.results)
        if composed is not None:
            return self._from_composed_report(composed, intent)

        universal = self._find_universal_tool_result(execution_result.results, intent)
        if universal is not None:
            return universal

        financial = self._find_financial_report(execution_result.results, intent)
        if financial is not None:
            return financial

        comparison = self._find_project_expense_comparison(execution_result.results, intent)
        if comparison is not None:
            return comparison

        aggregate_tables = self._collect_aggregate_tables(execution_result.results)
        if len(aggregate_tables) >= 2:
            return self._from_parallel_aggregates(aggregate_tables, intent)
        if len(aggregate_tables) == 1:
            return self._from_single_aggregate(aggregate_tables[0], intent)

        mobile_summary = self._find_project_expense_breakdown(execution_result.results, intent)
        if mobile_summary is not None:
            return mobile_summary

        mobile_summary = self._find_project_expense_summary(execution_result.results, intent)
        if mobile_summary is not None:
            return mobile_summary

        payslip_payload = self._find_hr_payslip_payload(execution_result.results, intent)
        if payslip_payload is not None:
            return payslip_payload

        payslip_detail = self._find_hr_payslip_detail(execution_result.results, intent)
        if payslip_detail is not None:
            return payslip_detail

        hr_requests = self._find_hr_requests_payload(execution_result.results, intent)
        if hr_requests is not None:
            return hr_requests

        entity_candidates = self._find_entity_candidates(execution_result.results, intent)
        if entity_candidates is not None:
            return entity_candidates

        if not self._used_project_expense_tools(execution_result):
            project_summary = self._find_legacy_project_expense_kpi(execution_result.results)
            if project_summary is not None:
                return project_summary

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
    def _find_project_profile(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if payload.get("_source") != PROFILE_SOURCE:
                continue
            if payload.get("status") != "success":
                continue
            text = narrate_project_profile(
                payload,
                user_message=intent.specific_intent,
            )
            return SynthesizedResult(text=text, visualization=None)
        return None

    @staticmethod
    def _find_project_records(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if payload.get("_source") != RECORDS_SOURCE:
                continue
            if payload.get("status") != "success":
                continue
            text = narrate_project_records(
                payload,
                user_message=intent.specific_intent,
            )
            return SynthesizedResult(text=text, visualization=None)
        return None

    @staticmethod
    def _find_project_activity(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if payload.get("_source") != ACTIVITY_SOURCE:
                continue
            if payload.get("status") != "success":
                continue
            text = narrate_project_activity(
                payload,
                user_message=intent.specific_intent,
            )
            return SynthesizedResult(text=text, visualization=None)
        return None

    @staticmethod
    def _find_project_expense_breakdown(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if payload.get("_source") != BREAKDOWN_SOURCE:
                continue
            if payload.get("status") != "success":
                continue
            text = narrate_project_expense_breakdown(
                payload,
                user_message=intent.specific_intent,
            )
            return SynthesizedResult(text=text, visualization=None)
        return None

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
    def _find_hr_payslip_payload(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        """Narrate get_employee_payslips / get_my_payslips tool payloads."""
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if "payslips" not in payload:
                continue
            payslips = payload.get("payslips") or []
            file_id = payload.get("file_id") or ""
            employee_name = payload.get("employee_name") or ""
            if not payslips:
                label = employee_name or (f"File ID {file_id}" if file_id else "that employee")
                return SynthesizedResult(
                    text=(
                        f"No payslip found for {label} for the requested period. "
                        "The slip may not be generated yet, or try last month."
                    ),
                )
            lines = []
            for row in payslips[:5]:
                if not isinstance(row, dict):
                    continue
                title = str(row.get("name") or row.get("number") or "Payslip").strip()
                amount = row.get("amount") or row.get("net_wage") or row.get("net_salary")
                period = ""
                if row.get("date_from") and row.get("date_to"):
                    period = f" ({row['date_from']} to {row['date_to']})"
                if amount is not None:
                    lines.append(f"- {title}{period}: AED {amount:,.2f}")
                else:
                    lines.append(f"- {title}{period}")
            header = f"Found {len(payslips)} payslip record(s)"
            if employee_name:
                header += f" for **{employee_name}**"
            elif file_id:
                header += f" for File ID **{file_id}**"
            return SynthesizedResult(text=f"{header}.\n" + "\n".join(lines))

        return None

    @staticmethod
    def _find_hr_payslip_detail(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if payload.get("_source") != "get_payslip_detail":
                continue
            ambiguous = payload.get("ambiguous_employees") or []
            if ambiguous:
                names = ", ".join(
                    f"{row.get('name')} (File ID {row.get('emp_id')})"
                    for row in ambiguous[:5]
                    if isinstance(row, dict)
                )
                return SynthesizedResult(
                    text=(
                        f"Multiple employees match **{payload.get('employee_name') or 'that name'}**. "
                        f"Which one: {names}?"
                    ),
                )
            note = str(payload.get("note") or "").strip()
            if note and not payload.get("lines") and not payload.get("allocations") and not payload.get("payslip"):
                return SynthesizedResult(text=note)
            employee_name = payload.get("employee_name") or "Employee"
            payslip = payload.get("payslip") or {}
            title = str(payslip.get("name") or "Payslip")
            deductions = payload.get("deductions_summary") or {}
            if payload.get("detail_type") == "header":
                summary_bits = []
                for key, label in (
                    ("net_salary", "Net salary"),
                    ("gross_wage", "Gross salary"),
                    ("total_deductions", "Total deductions"),
                    ("fine", "Fine"),
                    ("advance", "Advance"),
                ):
                    value = deductions.get(key) or payslip.get(key)
                    if value is not None:
                        summary_bits.append(f"{label}: AED {abs(float(value)):,.2f}")
                period = ""
                if payslip.get("date_from") and payslip.get("date_to"):
                    period = f" ({payslip['date_from']} to {payslip['date_to']})"
                header = f"Payslip for **{employee_name}**{period} — {title}."
                if summary_bits:
                    return SynthesizedResult(text=header + "\n" + " | ".join(summary_bits))
                amount = payslip.get("amount") or payslip.get("net_wage")
                if amount is not None:
                    return SynthesizedResult(
                        text=header + f"\nNet salary: AED {abs(float(amount)):,.2f}",
                    )
                return SynthesizedResult(text=header)
            if payload.get("detail_type") == "distribution":
                allocations = payload.get("allocations") or []
                if not allocations:
                    return SynthesizedResult(
                        text=f"No project payslip distribution found for **{employee_name}** in that period.",
                    )
                lines = []
                for row in allocations[:10]:
                    project = row.get("project_name") or "Project"
                    amount = row.get("amount")
                    alloc = row.get("allocation")
                    if amount is not None:
                        pct = f" ({float(alloc) * 100:.0f}%)" if alloc else ""
                        lines.append(f"- {project}{pct}: AED {float(amount):,.2f}")
                    else:
                        lines.append(f"- {project}")
                extra = f"\n…and {len(allocations) - 10} more." if len(allocations) > 10 else ""
                return SynthesizedResult(
                    text=(
                        f"Payslip distribution for **{employee_name}** — {title}.\n"
                        + "\n".join(lines)
                        + extra
                    ),
                )
            return SynthesizedResult(
                text=ResultSynthesizer._format_payslip_detail_text(payload, employee_name, title),
            )
        return None

    @staticmethod
    def _format_payslip_detail_text(
        payload: dict[str, Any],
        employee_name: str,
        title: str,
    ) -> str:
        detail_type = str(payload.get("detail_type") or "lines")
        payroll = payload.get("payroll_summary") or payload.get("deductions_summary") or {}
        payslip = payload.get("payslip") or {}
        period = ""
        if payslip.get("date_from") and payslip.get("date_to"):
            period = f" ({payslip['date_from']} to {payslip['date_to']})"

        if detail_type == "worked_days":
            header = f"Worked days for **{employee_name}**{period} — {title}."
        elif detail_type == "full":
            header = f"Salary calculation for **{employee_name}**{period} — {title}."
        else:
            line_filter = payload.get("line_filter")
            filter_label = {
                "basic": "Basic salary lines",
                "deductions": "Deduction lines",
                "overtime": "Overtime lines",
            }.get(str(line_filter or ""), "Salary lines")
            header = f"{filter_label} for **{employee_name}**{period} — {title}."

        summary_bits: list[str] = []
        for key, label in (
            ("net_salary", "Net salary"),
            ("total_salary", "Total salary"),
            ("gross_wage", "Gross salary"),
            ("total_deductions", "Total deductions"),
            ("total_over_time", "Total overtime"),
            ("normal_ot_hours", "Normal OT hours"),
            ("weekend_ot_hours", "Weekend OT hours"),
            ("fine", "Fine"),
            ("advance", "Advance"),
        ):
            value = payroll.get(key)
            if value is None:
                continue
            if "hour" in key:
                summary_bits.append(f"{label}: {float(value):,.2f}")
            else:
                summary_bits.append(f"{label}: AED {abs(float(value)):,.2f}")

        sections: list[str] = [header]
        if summary_bits and detail_type in {"full", "header", "worked_days", "lines"}:
            sections.append(" | ".join(summary_bits[:8]))

        worked_days = payload.get("worked_days") or []
        if worked_days and detail_type in {"full", "worked_days"}:
            wd_lines = []
            for row in worked_days[:12]:
                if not isinstance(row, dict):
                    continue
                name = row.get("name") or row.get("code") or "Worked day"
                code = row.get("code") or ""
                days = row.get("number_of_days")
                hours = row.get("number_of_hours")
                amount = row.get("amount")
                bits = []
                if days is not None:
                    bits.append(f"{float(days):,.2f} days")
                if hours is not None:
                    bits.append(f"{float(hours):,.2f} hrs")
                if amount is not None:
                    bits.append(f"AED {float(amount):,.2f}")
                suffix = f" ({', '.join(bits)})" if bits else ""
                wd_lines.append(f"- {name} [{code}]{suffix}".strip())
            if wd_lines:
                sections.append("**Worked days & inputs**")
                sections.extend(wd_lines)

        lines_payload = payload.get("lines") or []
        if lines_payload and detail_type in {"full", "lines"}:
            body_lines = []
            for row in lines_payload[:20]:
                if not isinstance(row, dict):
                    continue
                code = row.get("code") or ""
                name = row.get("name") or code or "Line"
                category = row.get("category")
                amount = row.get("amount")
                cat_suffix = f", {category}" if category else ""
                if amount is not None:
                    body_lines.append(f"- {name} ({code}{cat_suffix}): AED {float(amount):,.2f}")
                else:
                    body_lines.append(f"- {name} ({code}{cat_suffix})")
            if body_lines:
                sections.append("**Salary computation**")
                sections.extend(body_lines)
            extra = len(lines_payload) - 20
            if extra > 0:
                sections.append(f"…and {extra} more line(s).")
        elif detail_type in {"full", "lines"} and not lines_payload:
            sections.append("No matching payslip line detail for that filter.")

        return "\n".join(sections)

    @staticmethod
    def _find_hr_requests_payload(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if payload.get("_source") != "list_employee_requests":
                continue
            ambiguous = payload.get("ambiguous_employees") or []
            if ambiguous:
                names = ", ".join(
                    f"{row.get('name')} (File ID {row.get('emp_id')})"
                    for row in ambiguous[:5]
                    if isinstance(row, dict)
                )
                return SynthesizedResult(
                    text=(
                        f"Multiple employees match **{payload.get('employee_name') or 'that name'}**. "
                        f"Which one: {names}?"
                    ),
                )
            requests = payload.get("requests") or []
            employee_name = payload.get("employee_name") or ""
            if not requests:
                note = str(payload.get("note") or "No HR requests found for that criteria.")
                return SynthesizedResult(text=note)
            lines = []
            for row in requests[:10]:
                req_type = row.get("request_type") or "Request"
                status = row.get("status") or ("Approved" if row.get("is_approve") else "Pending")
                created = str(row.get("create_date") or "")[:10]
                title = row.get("name") or req_type
                lines.append(f"- {title} ({req_type}, {status}, {created})")
            header = f"Found {len(requests)} HR request(s)"
            if employee_name:
                header += f" for **{employee_name}**"
            extra = f"\n…and {len(requests) - 10} more." if len(requests) > 10 else ""
            return SynthesizedResult(text=f"{header}.\n" + "\n".join(lines) + extra)
        return None

    @staticmethod
    def _find_entity_candidates(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        import logging
        import traceback

        trace_logger = logging.getLogger(__name__)
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if payload.get("_source") != "search_entities":
                continue
            if payload.get("status") != "success":
                continue
            candidates = payload.get("candidates") or []
            query = str(payload.get("query") or intent.specific_intent)
            trace_logger.info(
                "[TRACE resolve] about to search for query=%r — WHO CALLED ME",
                query,
            )
            trace_logger.info(traceback.format_stack()[-3])
            if not candidates:
                return SynthesizedResult(
                    text=f"I couldn't find any matching records for {query!r}. Try a different name or WO number.",
                )
            return SynthesizedResult(
                text=(
                    f"I found {len(candidates)} matching record(s) for {query!r}. "
                    "Pick the one you mean to continue."
                ),
            )
        return None

    @staticmethod
    def _find_universal_tool_result(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            source = str(payload.get("_source") or "")
            if source == "universal_odoo_query" and payload.get("status") == "success":
                return SynthesizedResult(
                    text=narrate_universal_query(payload, user_message=intent.specific_intent),
                )
            if source == "universal_odoo_aggregate" and payload.get("status") == "success":
                return SynthesizedResult(
                    text=narrate_universal_aggregate(payload, user_message=intent.specific_intent),
                )
        return None

    @staticmethod
    def _find_financial_report(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if not isinstance(payload.get("kpis"), dict):
                continue
            text = narrate_financial_report(payload, user_message=intent.specific_intent)
            if text:
                return SynthesizedResult(text=text)
        return None

    @staticmethod
    def _find_project_expense_comparison(
        results: dict[int, Any],
        intent: Intent,
    ) -> SynthesizedResult | None:
        for step_number in sorted(results.keys()):
            payload = results[step_number]
            if not isinstance(payload, dict) or payload.get("error"):
                continue
            if payload.get("_source") != "compare_project_expenses":
                continue
            if payload.get("status") != "success":
                continue
            text = narrate_project_expense_comparison(payload, user_message=intent.specific_intent)
            if text:
                return SynthesizedResult(text=text)
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
            if payload.get("_source") in {"universal_odoo_query", "universal_odoo_aggregate"}:
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
