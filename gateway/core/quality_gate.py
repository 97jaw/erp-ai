"""Quality gate — self-critique before responses reach the user (Phase 5)."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol

from gateway.core.context_stack import ContextStack
from gateway.core.intent_analyzer import Intent

logger = logging.getLogger(__name__)

MIN_PASS_RATE = 0.85
MAX_QUALITY_RETRIES = 2

QUALITY_CHECKS: tuple[str, ...] = (
    "no_fabrication",
    "data_consistency",
    "no_raw_syntax",
    "appropriate_detail",
    "honest_about_uncertainty",
    "actionable_suggestions",
    "right_visualization",
    "clear_language",
)

RAW_SYNTAX_PATTERNS: tuple[str, ...] = (
    r"amount_total:sum",
    r"__count",
    r"__domain",
    r"partner_id\[",
    r":sum:",
    r":count:",
    r":avg:",
    r"\[\s*\d+\s*,\s*['\"]",
    r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b",
)

UNCERTAINTY_WORDS = re.compile(
    r"\b(may|might|approximately|unclear|unsure|not available|cannot confirm|"
    r"limited data|partial|estimate|likely)\b",
    re.IGNORECASE,
)

JARGON_PATTERNS: tuple[str, ...] = (
    r"\bpartner_id\b",
    r"\bread_group\b",
    r"\bxmlrpc\b",
    r"\baccount\.move\b",
    r"\bgroup_by\b",
    r"\bsql_aggregate\b",
)

SIGNIFICANT_NUMBER = re.compile(
    r"(?:AED\s*)?(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d{4,}(?:\.\d+)?)",
    re.IGNORECASE,
)

ACTIONABLE_HINT = re.compile(
    r"\b(compare|show|break down|drill|filter|export|review|analyze|check|"
    r"what|which|how|why)\b",
    re.IGNORECASE,
)

COMPARISON_VISUAL_TYPES = frozenset({"DATA_TABLE", "BAR_CHART", "PIVOT_TABLE"})
TREND_VISUAL_TYPES = frozenset({"LINE_CHART", "BAR_CHART"})


@dataclass
class CheckResult:
    """Outcome of one quality check."""

    name: str
    passed: bool
    issue: str | None = None


@dataclass
class QualityReview:
    """Aggregated quality review across all checks."""

    checks: list[CheckResult]
    pass_rate: float
    passed: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class QualityResponse:
    """User-facing payload reviewed by the quality gate."""

    text: str
    visualization: dict[str, Any] | None = None
    suggestions: list[str] = field(default_factory=list)
    tool_results: list[Any] = field(default_factory=list)


class ResponseReviser(Protocol):
    """Revise a response based on quality feedback."""

    async def __call__(
        self,
        response: QualityResponse,
        review: QualityReview,
        intent: Intent,
        context: ContextStack,
    ) -> QualityResponse:
        """Return a revised response addressing review issues."""


class RetryHandler:
    """Retry synthesis when the quality gate fails."""

    def __init__(self, reviser: ResponseReviser | None = None) -> None:
        self._reviser = reviser

    async def retry_with_feedback(
        self,
        response: QualityResponse,
        review: QualityReview,
        intent: Intent,
        context: ContextStack,
    ) -> QualityResponse:
        """Ask for a revision that addresses failed quality checks."""
        if self._reviser is not None:
            return await self._reviser(response, review, intent, context)

        revised_text = response.text.strip()
        if review.issues:
            revised_text = (
                f"{revised_text}\n\n"
                f"Note: revised to address quality issues — {'; '.join(review.issues[:3])}"
            ).strip()
        return QualityResponse(
            text=revised_text,
            visualization=response.visualization,
            suggestions=response.suggestions,
            tool_results=response.tool_results,
        )


class QualityGate:
    """Inspect responses before showing them to the user."""

    def __init__(
        self,
        *,
        min_pass_rate: float = MIN_PASS_RATE,
        retry_handler: RetryHandler | None = None,
    ) -> None:
        self.min_pass_rate = min_pass_rate
        self._retry_handler = retry_handler or RetryHandler()

    async def review(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> QualityReview:
        """Run all quality checks on a response."""
        check_results = [
            await self._run_check(name, response, intent, context)
            for name in QUALITY_CHECKS
        ]
        return self._finalize_review(check_results)

    async def ensure_quality(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> tuple[QualityResponse, QualityReview, int]:
        """Review a response and retry up to MAX_QUALITY_RETRIES when below threshold."""
        current = response
        review = await self.review(current, intent, context)
        retries = 0
        self._log_review(review, retries)

        while not review.passed and retries < MAX_QUALITY_RETRIES:
            logger.info(
                "[QualityGate] pass_rate=%.3f below threshold — retry %d/%d",
                review.pass_rate,
                retries + 1,
                MAX_QUALITY_RETRIES,
            )
            current = await self._retry_handler.retry_with_feedback(
                current,
                review,
                intent,
                context,
            )
            review = await self.review(current, intent, context)
            retries += 1
            self._log_review(review, retries)

        return current, review, retries

    @staticmethod
    def _log_review(review: QualityReview, retries: int) -> None:
        passed_count = sum(1 for check in review.checks if check.passed)
        total = len(review.checks)
        logger.info(
            "[QualityGate] Quality gate: %d/%d checks passed (pass_rate=%.3f retries=%d)",
            passed_count,
            total,
            review.pass_rate,
            retries,
        )

    @staticmethod
    def _finalize_review(check_results: list[CheckResult]) -> QualityReview:
        """Compute pass rate and aggregate issues from individual checks."""
        if not check_results:
            return QualityReview(checks=[], pass_rate=0.0, passed=False, issues=[])

        passed_count = sum(1 for check in check_results if check.passed)
        pass_rate = passed_count / len(check_results)
        issues = [check.issue for check in check_results if not check.passed and check.issue]
        return QualityReview(
            checks=check_results,
            pass_rate=pass_rate,
            passed=pass_rate >= MIN_PASS_RATE,
            issues=issues,
        )

    async def _run_check(
        self,
        check_name: str,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> CheckResult:
        """Dispatch one named quality check."""
        checks: dict[str, Callable[[QualityResponse, Intent, ContextStack], CheckResult]] = {
            "no_fabrication": self._check_no_fabrication,
            "data_consistency": self._check_data_consistency,
            "no_raw_syntax": self._check_no_raw_syntax,
            "appropriate_detail": self._check_appropriate_detail,
            "honest_about_uncertainty": self._check_honest_about_uncertainty,
            "actionable_suggestions": self._check_actionable_suggestions,
            "right_visualization": self._check_right_visualization,
            "clear_language": self._check_clear_language,
        }
        handler = checks.get(check_name)
        if handler is None:
            return CheckResult(
                name=check_name,
                passed=False,
                issue=f"Unknown quality check: {check_name}",
            )
        return handler(response, intent, context)

    @staticmethod
    def _response_blob(response: QualityResponse) -> str:
        visualization = json.dumps(response.visualization or {}, default=str)
        suggestions = json.dumps(response.suggestions, default=str)
        return f"{response.text}\n{visualization}\n{suggestions}"

    @staticmethod
    def _parse_number(raw: str) -> float | None:
        cleaned = raw.replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    @classmethod
    def _extract_significant_numbers(cls, text: str) -> set[float]:
        numbers: set[float] = set()
        for match in SIGNIFICANT_NUMBER.finditer(text or ""):
            parsed = cls._parse_number(match.group(1))
            if parsed is not None and parsed >= 1000:
                if float(parsed).is_integer() and 1900 <= parsed <= 2100:
                    continue
                numbers.add(parsed)
        return numbers

    @classmethod
    def _collect_numbers_from_payload(cls, payload: Any) -> set[float]:
        numbers: set[float] = set()
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key == "kpis" and isinstance(value, dict):
                    for kpi_entry in value.values():
                        if isinstance(kpi_entry, dict):
                            nested = kpi_entry.get("value")
                            if isinstance(nested, (int, float)) and not isinstance(nested, bool):
                                if abs(float(nested)) >= 1000:
                                    numbers.add(float(nested))
                    continue
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    if abs(float(value)) >= 1000:
                        numbers.add(float(value))
                numbers.update(cls._collect_numbers_from_payload(value))
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, (int, float)) and not isinstance(item, bool):
                    if abs(float(item)) >= 1000:
                        numbers.add(float(item))
                elif isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], int):
                    numbers.update(cls._collect_numbers_from_payload(item[1]))
                else:
                    numbers.update(cls._collect_numbers_from_payload(item))
        return numbers

    @classmethod
    def _numbers_match(cls, left: float, right: float) -> bool:
        tolerance = max(1.0, abs(left) * 0.01)
        return abs(left - right) <= tolerance

    @classmethod
    def _number_backed_by_tools(cls, value: float, tool_numbers: set[float]) -> bool:
        if not tool_numbers:
            return False
        return any(cls._numbers_match(value, tool_number) for tool_number in tool_numbers)

    def _check_no_fabrication(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> CheckResult:
        text_numbers = self._extract_significant_numbers(response.text)
        if not text_numbers:
            return CheckResult(name="no_fabrication", passed=True)

        tool_numbers = self._collect_numbers_from_payload(response.tool_results)
        tool_numbers.update(
            self._collect_numbers_from_payload(response.visualization or {}),
        )
        fabricated = sorted(
            number for number in text_numbers if not self._number_backed_by_tools(number, tool_numbers)
        )
        if fabricated:
            sample = ", ".join(f"{value:,.0f}" for value in fabricated[:3])
            return CheckResult(
                name="no_fabrication",
                passed=False,
                issue=f"Response cites numbers not present in tool results: {sample}",
            )
        return CheckResult(name="no_fabrication", passed=True)

    def _check_data_consistency(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> CheckResult:
        visualization = response.visualization or {}
        data = visualization.get("data") or {}
        headers = [str(header) for header in data.get("headers") or []]
        rows = data.get("rows") or []

        if headers and rows and any("change" in header.lower() for header in headers):
            try:
                change_index = next(
                    index for index, header in enumerate(headers) if "change" in header.lower()
                )
                period_indices = [
                    index
                    for index, header in enumerate(headers)
                    if "period" in header.lower() or "revenue" in header.lower()
                ][:2]
                if len(period_indices) == 2:
                    for row in rows:
                        if not isinstance(row, (list, tuple)) or len(row) <= change_index:
                            continue
                        left = float(row[period_indices[0]] or 0)
                        right = float(row[period_indices[1]] or 0)
                        change = float(row[change_index] or 0)
                        expected = round(right - left, 2)
                        if not self._numbers_match(change, expected):
                            return CheckResult(
                                name="data_consistency",
                                passed=False,
                                issue=(
                                    "Comparison table change column does not match period values "
                                    f"(expected {expected:,.2f}, got {change:,.2f})"
                                ),
                            )
            except (StopIteration, TypeError, ValueError):
                return CheckResult(
                    name="data_consistency",
                    passed=False,
                    issue="Comparison table rows could not be validated for internal consistency",
                )

        return CheckResult(name="data_consistency", passed=True)

    def _check_no_raw_syntax(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> CheckResult:
        blob = self._response_blob(response)
        for pattern in RAW_SYNTAX_PATTERNS:
            if re.search(pattern, blob):
                return CheckResult(
                    name="no_raw_syntax",
                    passed=False,
                    issue=f"Response exposes raw Odoo syntax matching '{pattern}'",
                )
        return CheckResult(name="no_raw_syntax", passed=True)

    def _check_appropriate_detail(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> CheckResult:
        text = (response.text or "").strip()
        if len(text) < 25:
            return CheckResult(
                name="appropriate_detail",
                passed=False,
                issue="Response is too vague — add context, period, and key figures",
            )
        if len(text) > 4000:
            return CheckResult(
                name="appropriate_detail",
                passed=False,
                issue="Response is too long for an executive summary",
            )

        rows = ((response.visualization or {}).get("data") or {}).get("rows") or []
        if len(rows) > 50:
            return CheckResult(
                name="appropriate_detail",
                passed=False,
                issue="Visualization contains too many rows for a concise summary",
            )
        return CheckResult(name="appropriate_detail", passed=True)

    def _check_honest_about_uncertainty(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> CheckResult:
        warnings: list[str] = []
        for payload in response.tool_results:
            if isinstance(payload, dict):
                for key in ("warning", "quality_warning", "note"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.strip():
                        warnings.append(value.strip())

        high_ambiguity = any(
            ambiguity.severity in {"high", "critical"}
            for ambiguity in intent.ambiguities
        )
        text = response.text or ""
        acknowledges_uncertainty = bool(UNCERTAINTY_WORDS.search(text))

        if (warnings or high_ambiguity) and not acknowledges_uncertainty:
            return CheckResult(
                name="honest_about_uncertainty",
                passed=False,
                issue="Response should acknowledge data limitations or unresolved ambiguity",
            )
        return CheckResult(name="honest_about_uncertainty", passed=True)

    def _check_actionable_suggestions(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> CheckResult:
        suggestions = [item.strip() for item in response.suggestions if str(item).strip()]
        if not suggestions:
            return CheckResult(
                name="actionable_suggestions",
                passed=False,
                issue="Provide at least one specific follow-up suggestion",
            )

        weak = [
            suggestion
            for suggestion in suggestions
            if len(suggestion) < 12 or not ACTIONABLE_HINT.search(suggestion)
        ]
        if len(weak) == len(suggestions):
            return CheckResult(
                name="actionable_suggestions",
                passed=False,
                issue="Suggestions are too generic — make them specific and actionable",
            )
        return CheckResult(name="actionable_suggestions", passed=True)

    def _check_right_visualization(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> CheckResult:
        visual_type = (response.visualization or {}).get("visual_type")
        if visual_type is None:
            if intent.expected_output in {"chart", "table"}:
                return CheckResult(
                    name="right_visualization",
                    passed=False,
                    issue="Expected a visualization for this query but none was provided",
                )
            return CheckResult(name="right_visualization", passed=True)

        if intent.primary_action == "compare" and visual_type not in COMPARISON_VISUAL_TYPES:
            return CheckResult(
                name="right_visualization",
                passed=False,
                issue=(
                    f"Comparison queries should use a comparison visual "
                    f"(DATA_TABLE/BAR_CHART/PIVOT_TABLE), not {visual_type}"
                ),
            )

        if "trend" in intent.specific_intent.lower() and visual_type not in TREND_VISUAL_TYPES:
            return CheckResult(
                name="right_visualization",
                passed=False,
                issue=f"Trend queries should use a trend visual (LINE_CHART), not {visual_type}",
            )

        return CheckResult(name="right_visualization", passed=True)

    def _check_clear_language(
        self,
        response: QualityResponse,
        intent: Intent,
        context: ContextStack,
    ) -> CheckResult:
        blob = self._response_blob(response)
        for pattern in JARGON_PATTERNS:
            if re.search(pattern, blob, re.IGNORECASE):
                return CheckResult(
                    name="clear_language",
                    passed=False,
                    issue=f"Response exposes technical jargon matching '{pattern}'",
                )
        return CheckResult(name="clear_language", passed=True)
