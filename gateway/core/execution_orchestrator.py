"""Execution orchestration for the reasoning engine."""

from __future__ import annotations

import asyncio
import ast
import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Protocol

from gateway.core.context_stack import ContextStack
from gateway.core.entity_gate import EntityGate
from gateway.core.entity_resolver import StepFailure
from gateway.core.strategy_planner import ExecutionStep, Strategy

logger = logging.getLogger(__name__)

VARIABLE_REFERENCE_PATTERN = re.compile(r"^\{\{step_(\d+)\.([^}]+)\}\}$")
FALLBACK_SPEC_PATTERN = re.compile(r"^use_tool:([^:]+):(.+)$")
MAX_STEP_RETRIES = 2
DEFAULT_RETRY_DELAY_SECONDS = 0.5

OrchestrationStepStatus = Literal[
    "pending",
    "running",
    "success",
    "failed",
    "fallback",
]

ORCHESTRATION_STEP_STATUSES: tuple[OrchestrationStepStatus, ...] = (
    "pending",
    "running",
    "success",
    "failed",
    "fallback",
)


class VariableResolutionError(Exception):
    """Raised when a {{step_N.field_name}} reference cannot be resolved."""


@dataclass
class OrchestrationLogEntry:
    """One orchestration event for UI display and telemetry."""

    step_number: int
    tool: str
    status: OrchestrationStepStatus
    duration_ms: int
    input_summary: str
    output_summary: str
    error: str | None
    timestamp: datetime

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logging."""
        payload = asdict(self)
        payload["timestamp"] = self.timestamp.isoformat()
        return payload


@dataclass
class VerificationCheck:
    """Outcome of a single strategy quality check."""

    check: str
    passed: bool
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logging."""
        return asdict(self)


@dataclass
class VerificationResult:
    """Aggregated verification against strategy quality checks."""

    passed: bool
    checks: list[VerificationCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logging."""
        return {
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
        }


@dataclass
class ExecutionResult:
    """Outcome of executing a strategy through the orchestrator."""

    results: dict[int, Any]
    failures: list[StepFailure]
    verification: VerificationResult
    strategy_used: Strategy
    orchestration_log: list[OrchestrationLogEntry] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logging."""
        return {
            "results": self.results,
            "failures": [
                {
                    "step_number": failure.step.step_number,
                    "tool": failure.step.tool,
                    "error": str(failure.error),
                }
                for failure in self.failures
            ],
            "verification": self.verification.to_dict(),
            "strategy_used": self.strategy_used.to_dict(),
            "orchestration_log": [entry.to_dict() for entry in self.orchestration_log],
        }


class OrchestrationException(Exception):
    """Raised when a strategy cannot be executed."""


class ToolExecutor(Protocol):
    """Minimal tool execution interface for orchestrator tests and production."""

    async def execute(
        self,
        tool: str,
        tool_input: dict[str, Any],
        context: ContextStack,
    ) -> Any:
        """Run one gateway tool and return its payload."""


class ExecutionOrchestrator:
    """Execute strategies with sequential and parallel step scheduling."""

    def __init__(
        self,
        executor: ToolExecutor,
        *,
        retry_delay_seconds: float = DEFAULT_RETRY_DELAY_SECONDS,
    ) -> None:
        self._executor = executor
        self._retry_delay_seconds = retry_delay_seconds

    async def execute(self, strategy: Strategy, context: ContextStack) -> ExecutionResult:
        """Run all strategy steps and return aggregated results."""
        results: dict[int, Any] = {}
        failures: list[StepFailure] = []
        orchestration_log: list[OrchestrationLogEntry] = []

        for group in self._group_parallel_steps(strategy.steps):
            if len(group) == 1:
                step = group[0]
                step_result = await self._run_step_with_fallback(
                    step,
                    results,
                    context,
                    orchestration_log,
                    failures,
                )
                if step_result is not None:
                    results[step.step_number] = step_result
            else:
                tasks = [
                    self._run_step_with_fallback(
                        step,
                        results,
                        context,
                        orchestration_log,
                        failures,
                    )
                    for step in group
                ]
                step_results = await asyncio.gather(*tasks)
                for step, step_result in zip(group, step_results):
                    if step_result is not None:
                        results[step.step_number] = step_result

        verification = self._verify_results(results, strategy.quality_checks)
        return ExecutionResult(
            results=results,
            failures=failures,
            verification=verification,
            strategy_used=strategy,
            orchestration_log=orchestration_log,
        )

    async def _run_step_with_fallback(
        self,
        step: ExecutionStep,
        prior_results: dict[int, Any],
        context: ContextStack,
        orchestration_log: list[OrchestrationLogEntry],
        failures: list[StepFailure],
    ) -> Any | None:
        """Execute a step, applying deterministic fallback when the primary path fails."""
        try:
            return await self._execute_step(step, prior_results, context, orchestration_log)
        except Exception as exc:
            if not step.fallback_if_fails:
                failures.append(StepFailure(step=step, error=exc))
                logger.warning(
                    "[Orchestrator] step=%d tool=%s status=failed error=%s",
                    step.step_number,
                    step.tool,
                    exc,
                )
                return None

            try:
                fallback_result = await self._execute_fallback(
                    step,
                    prior_results,
                    context,
                    orchestration_log,
                )
            except Exception as fallback_exc:
                failures.append(StepFailure(step=step, error=fallback_exc))
                logger.warning(
                    "[Orchestrator] step=%d tool=%s status=failed fallback_error=%s",
                    step.step_number,
                    step.tool,
                    fallback_exc,
                )
                return None

            logger.info(
                "[Orchestrator] step=%d tool=%s status=fallback applied",
                step.step_number,
                step.tool,
            )
            return fallback_result

    async def _execute_step(
        self,
        step: ExecutionStep,
        prior_results: dict[int, Any],
        context: ContextStack,
        orchestration_log: list[OrchestrationLogEntry],
    ) -> Any:
        """Execute one step with retry logic and append a log entry."""
        started = time.perf_counter()
        tool_input = self._resolve_variables(step.tool_input, prior_results)
        input_summary = self._summarize_payload(tool_input)
        last_error: Exception | None = None

        for attempt in range(MAX_STEP_RETRIES):
            try:
                result = await self._executor.execute(step.tool, tool_input, context)
            except Exception as exc:
                last_error = exc
                if attempt < MAX_STEP_RETRIES - 1:
                    await asyncio.sleep(self._retry_delay_seconds)
                    continue
                duration_ms = int((time.perf_counter() - started) * 1000)
                entry = self._build_log_entry(
                    step=step,
                    status="failed",
                    duration_ms=duration_ms,
                    input_summary=input_summary,
                    output_summary="",
                    error=str(exc),
                )
                orchestration_log.append(entry)
                logger.info("[Orchestrator] %s", json.dumps(entry.to_dict(), ensure_ascii=True))
                raise

            if self._is_ambiguous_entity_error(result):
                duration_ms = int((time.perf_counter() - started) * 1000)
                entry = self._build_log_entry(
                    step=step,
                    status="failed",
                    duration_ms=duration_ms,
                    input_summary=input_summary,
                    output_summary=self._summarize_payload(result),
                    error=str(result.get("error")),
                )
                orchestration_log.append(entry)
                logger.info("[Orchestrator] %s", json.dumps(entry.to_dict(), ensure_ascii=True))
                raise OrchestrationException(
                    f"Step {step.step_number} returned ambiguous entity reference",
                )

            if self._is_permission_denied(result):
                duration_ms = int((time.perf_counter() - started) * 1000)
                message = self._permission_denied_message(result)
                entry = self._build_log_entry(
                    step=step,
                    status="failed",
                    duration_ms=duration_ms,
                    input_summary=input_summary,
                    output_summary=self._summarize_payload(result),
                    error=message,
                )
                orchestration_log.append(entry)
                logger.info("[Orchestrator] %s", json.dumps(entry.to_dict(), ensure_ascii=True))
                raise OrchestrationException(message)

            if self._is_empty_or_invalid(result):
                if attempt < MAX_STEP_RETRIES - 1 and not self._is_non_retryable_empty(result):
                    tool_input = self._broaden_search(step.tool, tool_input)
                    input_summary = self._summarize_payload(tool_input)
                    continue
                duration_ms = int((time.perf_counter() - started) * 1000)
                entry = self._build_log_entry(
                    step=step,
                    status="failed",
                    duration_ms=duration_ms,
                    input_summary=input_summary,
                    output_summary=self._summarize_payload(result),
                    error="Empty or invalid tool result",
                )
                orchestration_log.append(entry)
                logger.info("[Orchestrator] %s", json.dumps(entry.to_dict(), ensure_ascii=True))
                raise OrchestrationException(
                    f"Step {step.step_number} returned empty or invalid data",
                )

            duration_ms = int((time.perf_counter() - started) * 1000)
            output_summary = self._summarize_payload(result)
            entry = self._build_log_entry(
                step=step,
                status="success",
                duration_ms=duration_ms,
                input_summary=input_summary,
                output_summary=output_summary,
                error=None,
            )
            orchestration_log.append(entry)
            logger.info("[Orchestrator] %s", json.dumps(entry.to_dict(), ensure_ascii=True))
            return result

        if last_error is not None:
            raise last_error
        raise OrchestrationException(f"Step {step.step_number} failed without a result")

    async def _execute_fallback(
        self,
        step: ExecutionStep,
        prior_results: dict[int, Any],
        context: ContextStack,
        orchestration_log: list[OrchestrationLogEntry],
    ) -> Any:
        """Execute a deterministic fallback tool for a failed step."""
        fallback_tool, fallback_input = self._parse_fallback_spec(step.fallback_if_fails)
        started = time.perf_counter()
        tool_input = self._resolve_variables(fallback_input, prior_results)
        input_summary = self._summarize_payload(tool_input)
        try:
            result = await self._executor.execute(fallback_tool, tool_input, context)
        except Exception as exc:
            duration_ms = int((time.perf_counter() - started) * 1000)
            entry = self._build_log_entry(
                step=step,
                status="failed",
                duration_ms=duration_ms,
                input_summary=f"fallback {fallback_tool}: {input_summary}",
                output_summary="",
                error=str(exc),
            )
            orchestration_log.append(entry)
            logger.info("[Orchestrator] %s", json.dumps(entry.to_dict(), ensure_ascii=True))
            raise

        if self._is_empty_or_invalid(result):
            duration_ms = int((time.perf_counter() - started) * 1000)
            entry = self._build_log_entry(
                step=step,
                status="failed",
                duration_ms=duration_ms,
                input_summary=f"fallback {fallback_tool}: {input_summary}",
                output_summary=self._summarize_payload(result),
                error="Empty or invalid fallback result",
            )
            orchestration_log.append(entry)
            logger.info("[Orchestrator] %s", json.dumps(entry.to_dict(), ensure_ascii=True))
            raise OrchestrationException(
                f"Fallback for step {step.step_number} returned empty or invalid data",
            )

        duration_ms = int((time.perf_counter() - started) * 1000)
        entry = self._build_log_entry(
            step=step,
            status="fallback",
            duration_ms=duration_ms,
            input_summary=f"fallback {fallback_tool}: {input_summary}",
            output_summary=self._summarize_payload(result),
            error=None,
        )
        orchestration_log.append(entry)
        logger.info("[Orchestrator] %s", json.dumps(entry.to_dict(), ensure_ascii=True))
        return result

    def _parse_fallback_spec(self, fallback_spec: str) -> tuple[str, dict[str, Any]]:
        """Parse use_tool:tool_name:{json} fallback instructions."""
        match = FALLBACK_SPEC_PATTERN.match(fallback_spec.strip())
        if not match:
            raise OrchestrationException(f"Invalid fallback spec: {fallback_spec!r}")
        tool_name = match.group(1).strip()
        try:
            tool_input = ast.literal_eval(match.group(2).strip())
        except (SyntaxError, ValueError) as exc:
            raise OrchestrationException(
                f"Invalid fallback JSON in spec: {fallback_spec!r}",
            ) from exc
        if not isinstance(tool_input, dict):
            raise OrchestrationException("Fallback tool input must be a JSON object")
        return tool_name, tool_input

    @staticmethod
    def _is_permission_denied(result: Any) -> bool:
        """Return True when RBAC or universal-tool access blocked the call."""
        if not isinstance(result, dict):
            return False
        if result.get("permission_denied"):
            return True
        if result.get("error_code") == "permission_denied":
            return True
        return False

    @staticmethod
    def _permission_denied_message(result: Any) -> str:
        if isinstance(result, dict):
            if result.get("error"):
                return str(result["error"])
            if result.get("message"):
                return str(result["message"])
        return "Missing permission for this data"

    @staticmethod
    def _is_non_retryable_empty(result: Any) -> bool:
        """Empty payloads that broadening filters cannot fix."""
        if not isinstance(result, dict):
            return False
        if result.get("error"):
            return True
        if result.get("status") == "error":
            return True
        return False

    @staticmethod
    def _is_empty_or_invalid(result: Any) -> bool:
        """Return True when a tool payload is not usable."""
        if result is None:
            return True
        if isinstance(result, dict):
            if result.get("error"):
                return True
            if result.get("status") == "error":
                return True
            if "rows" in result and isinstance(result["rows"], list) and not result["rows"]:
                return True
            if "groups" in result and isinstance(result["groups"], list) and not result["groups"]:
                return True
            if not result:
                return True
        if isinstance(result, list) and not result:
            return True
        return False

    @staticmethod
    def _is_ambiguous_entity_error(result: Any) -> bool:
        """Return True when a tool result indicates entity ambiguity (non-retryable)."""
        if not isinstance(result, dict):
            return False
        return result.get("error") in {
            "multiple_projects_found",
            "project_ambiguous",
            "project_not_found",
        }

    @staticmethod
    def _broaden_search(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Relax tool input for a broader retry attempt."""
        broadened = dict(tool_input)
        if "limit" in broadened and isinstance(broadened["limit"], int):
            broadened["limit"] = max(broadened["limit"] * 2, 50)
        else:
            broadened["limit"] = 50
        broadened["broadened"] = True
        model = str(broadened.get("model") or "").lower()
        payroll_scoped = model.startswith("hr.payslip") or model.startswith("hr.")
        if EntityGate.is_entity_bound_financial_tool(tool_name):
            for key in ("date_from", "date_to"):
                broadened.pop(key, None)
        elif payroll_scoped:
            broadened.pop("partner_id", None)
        else:
            for key in ("partner_id", "project_id", "date_from", "date_to"):
                broadened.pop(key, None)
        return broadened

    def _group_parallel_steps(self, steps: list[ExecutionStep]) -> list[list[ExecutionStep]]:
        """Split steps into sequential groups of parallelizable steps."""
        if not steps:
            return []

        steps_by_number = {step.step_number: step for step in steps}
        pending = set(steps_by_number)
        completed: set[int] = set()
        groups: list[list[ExecutionStep]] = []

        while pending:
            runnable = sorted(
                (
                    steps_by_number[step_number]
                    for step_number in pending
                    if all(dep in completed for dep in steps_by_number[step_number].depends_on)
                ),
                key=lambda step: step.step_number,
            )
            if not runnable:
                raise OrchestrationException("Strategy has unsatisfiable step dependencies")

            unscheduled = {step.step_number for step in runnable}
            while unscheduled:
                seed_number = min(unscheduled)
                seed = steps_by_number[seed_number]
                cluster = [seed]
                unscheduled.remove(seed_number)
                for candidate_number in list(unscheduled):
                    candidate = steps_by_number[candidate_number]
                    if self._are_parallel(seed, candidate):
                        cluster.append(candidate)
                        unscheduled.remove(candidate_number)
                groups.append(sorted(cluster, key=lambda step: step.step_number))

            for step in runnable:
                completed.add(step.step_number)
                pending.remove(step.step_number)

        return groups

    @staticmethod
    def _are_parallel(left: ExecutionStep, right: ExecutionStep) -> bool:
        """Return True when two steps are marked to run in parallel."""
        return (
            right.step_number in left.parallel_with
            or left.step_number in right.parallel_with
        )

    def _resolve_variables(
        self,
        tool_input: dict[str, Any],
        prior_results: dict[int, Any],
    ) -> dict[str, Any]:
        """Resolve {{step_N.field_name}} references in tool input."""
        return self._resolve_value(tool_input, prior_results)

    def _resolve_value(self, value: Any, prior_results: dict[int, Any]) -> Any:
        """Resolve variable references in nested tool input values."""
        if isinstance(value, dict):
            return {
                key: self._resolve_value(item, prior_results)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._resolve_value(item, prior_results) for item in value]
        if isinstance(value, str):
            match = VARIABLE_REFERENCE_PATTERN.match(value.strip())
            if not match:
                return value
            step_number = int(match.group(1))
            field_name = match.group(2).strip()
            if step_number not in prior_results:
                raise VariableResolutionError(
                    f"Cannot resolve {value}: step_{step_number} has no result yet",
                )
            step_result = prior_results[step_number]
            if not isinstance(step_result, dict):
                raise VariableResolutionError(
                    f"Cannot resolve {value}: step_{step_number} result is not an object",
                )
            if field_name not in step_result:
                raise VariableResolutionError(
                    f"Cannot resolve {value}: missing field {field_name!r} on step_{step_number}",
                )
            return step_result[field_name]
        return value

    @staticmethod
    def _verify_results(
        results: dict[int, Any],
        quality_checks: list[str],
    ) -> VerificationResult:
        """Apply basic post-execution verification for Step 4.2."""
        checks = [
            VerificationCheck(
                check=check,
                passed=bool(results),
                message=None if results else "No step results were produced",
            )
            for check in quality_checks
        ]
        return VerificationResult(
            passed=all(check.passed for check in checks),
            checks=checks,
        )

    @staticmethod
    def _summarize_payload(payload: Any) -> str:
        """Return a compact summary string for orchestration logs."""
        if payload is None:
            return "null"
        if isinstance(payload, dict):
            if "rows" in payload and isinstance(payload["rows"], list):
                return f"{len(payload['rows'])} rows"
            if "total" in payload:
                return f"total={payload['total']}"
            return f"{len(payload)} keys"
        if isinstance(payload, list):
            return f"{len(payload)} items"
        text = str(payload)
        return text if len(text) <= 80 else f"{text[:77]}..."

    @staticmethod
    def _build_log_entry(
        *,
        step: ExecutionStep,
        status: OrchestrationStepStatus,
        duration_ms: int,
        input_summary: str,
        output_summary: str,
        error: str | None,
    ) -> OrchestrationLogEntry:
        """Build one orchestration log entry."""
        return OrchestrationLogEntry(
            step_number=step.step_number,
            tool=step.tool,
            status=status,
            duration_ms=duration_ms,
            input_summary=input_summary,
            output_summary=output_summary,
            error=error,
            timestamp=datetime.now(timezone.utc),
        )
