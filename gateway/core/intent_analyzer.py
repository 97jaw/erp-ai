"""Intent analysis models and Claude-backed analyzer for the reasoning engine."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Protocol

from gateway.core.clarification_validation import CLARIFICATION_PROMPT_RULES, validate_clarification
from gateway.core.project_attribute_utils import is_project_attribute_query
from gateway.session_entities import build_session_context_prompt

logger = logging.getLogger(__name__)

INTENT_ANALYZER_MODEL = "claude-sonnet-4-20250514"


class AnalyzerException(Exception):
    """Raised when intent analysis cannot complete due to Claude/API failure."""


class JsonCompletionClient(Protocol):
    """Minimal Claude JSON completion interface for testing and production."""

    async def complete_json(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int = 800,
    ) -> str:
        """Return raw text expected to contain JSON for intent parsing."""


@dataclass
class EntityReference:
    """An entity mentioned or implied in the user's query."""

    type: str
    value: str
    confidence: float

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logging."""
        return asdict(self)


@dataclass
class Ambiguity:
    """An ambiguous aspect of the query that may need resolution or clarification."""

    type: str
    description: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logging."""
        return asdict(self)


@dataclass
class Intent:
    """Structured classification of what the user actually wants."""

    primary_action: str
    subject_area: str
    specific_intent: str
    entities: list[EntityReference] = field(default_factory=list)
    implicit_requirements: list[str] = field(default_factory=list)
    ambiguities: list[Ambiguity] = field(default_factory=list)
    expected_output: str = "summary"
    urgency: str = "normal"
    estimated_complexity: str = "simple"
    requires_clarification: bool = False
    clarification_question: str | None = None
    out_of_scope: bool = False
    out_of_scope_reason: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Intent:
        """Build an Intent from Claude JSON output."""
        entities = [
            EntityReference(
                type=str(item["type"]),
                value=str(item["value"]),
                confidence=float(item.get("confidence", 0.0)),
            )
            for item in data.get("entities") or []
            if isinstance(item, dict) and "type" in item and "value" in item
        ]
        ambiguities = [
            Ambiguity(
                type=str(item["type"]),
                description=str(item["description"]),
                severity=str(item.get("severity", "low")),
            )
            for item in data.get("ambiguities") or []
            if isinstance(item, dict) and "type" in item and "description" in item
        ]
        clarification_question = data.get("clarification_question")
        out_of_scope_reason = data.get("out_of_scope_reason")
        return cls(
            primary_action=str(data["primary_action"]),
            subject_area=str(data["subject_area"]),
            specific_intent=str(data["specific_intent"]),
            entities=entities,
            implicit_requirements=[
                str(item) for item in data.get("implicit_requirements") or []
            ],
            ambiguities=ambiguities,
            expected_output=str(data.get("expected_output", "summary")),
            urgency=str(data.get("urgency", "normal")),
            estimated_complexity=str(data.get("estimated_complexity", "simple")),
            requires_clarification=bool(data.get("requires_clarification", False)),
            clarification_question=(
                str(clarification_question) if clarification_question is not None else None
            ),
            out_of_scope=bool(data.get("out_of_scope", False)),
            out_of_scope_reason=(
                str(out_of_scope_reason) if out_of_scope_reason is not None else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation for logging."""
        return {
            "primary_action": self.primary_action,
            "subject_area": self.subject_area,
            "specific_intent": self.specific_intent,
            "entities": [entity.to_dict() for entity in self.entities],
            "implicit_requirements": list(self.implicit_requirements),
            "ambiguities": [ambiguity.to_dict() for ambiguity in self.ambiguities],
            "expected_output": self.expected_output,
            "urgency": self.urgency,
            "estimated_complexity": self.estimated_complexity,
            "requires_clarification": self.requires_clarification,
            "clarification_question": self.clarification_question,
            "out_of_scope": self.out_of_scope,
            "out_of_scope_reason": self.out_of_scope_reason,
        }


class AnthropicJsonClient:
    """Production Claude client for structured JSON intent analysis."""

    async def complete_json(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int = 800,
    ) -> str:
        """Call Claude and return the raw text response."""
        import anthropic

        def _call() -> str:
            client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            block = response.content[0]
            return getattr(block, "text", str(block))

        try:
            return await asyncio.to_thread(_call)
        except Exception as exc:
            raise AnalyzerException(f"Claude intent analysis failed: {exc}") from exc


class IntentAnalyzer:
    """Extract structured intent from a user query using Claude."""

    def __init__(
        self,
        client: JsonCompletionClient | None = None,
        model: str = INTENT_ANALYZER_MODEL,
    ) -> None:
        self._client = client or AnthropicJsonClient()
        self._model = model

    async def analyze(self, query: str, context: ContextStack) -> Intent:
        """Analyze the query and return a structured Intent."""
        prompt = self._build_prompt(query, context)
        try:
            raw_response = await self._client.complete_json(model=self._model, prompt=prompt)
        except AnalyzerException:
            raise
        except Exception as exc:
            raise AnalyzerException(f"Claude intent analysis failed: {exc}") from exc

        intent = self._parse_response(raw_response, query, context)
        intent = self._apply_manifest_guardrails(query, intent, context)
        intent = self._apply_project_attribute_detection(query, intent)
        intent = validate_clarification(intent)
        logger.info(
            "[IntentAnalyzer] query=%r intent=%s",
            query,
            json.dumps(intent.to_dict(), ensure_ascii=True),
        )
        return intent

    def _build_prompt(self, query: str, context: ContextStack) -> str:
        """Build a lean focused prompt for Claude intent extraction."""
        available = ", ".join(
            capability.code for capability in context.capability_manifest.available
        )
        unavailable = ", ".join(
            capability.code for capability in context.capability_manifest.unavailable
        )
        user = context.user
        session_context = build_session_context_prompt(context.conversation.session_id)
        facts = context.working_memory.session_facts
        if not session_context and facts.get("resolved_project_id"):
            project_name = facts.get("project_name") or "the last project"
            session_context = (
                "\n\nCONVERSATION CONTEXT:\n"
                f"- Last project discussed: {project_name} "
                f"(ID: {facts['resolved_project_id']})\n"
            )
        return (
            "You are an intent analyzer for an ERP assistant.\n"
            f"User: {user.name} ({user.primary_role}, assumption={user.assumption_level()})\n"
            f"Available capabilities: {available}\n"
            f"Unavailable capabilities: {unavailable}\n"
            f"{session_context}"
            f'Query: "{query}"\n'
            "Return ONLY valid JSON with this schema:\n"
            "{"
            '"primary_action":"fetch_data|analyze|compare|generate_report|'
            'search_entity|explain|ask_question|other",'
            '"subject_area":"financial|project|project_attribute|hr|sales|inventory|general|other",'
            '"specific_intent":"...",'
            '"entities":[{"type":"project|partner|account|period|amount",'
            '"value":"...","confidence":0.0}],'
            '"implicit_requirements":["..."],'
            '"ambiguities":[{"type":"...","description":"...",'
            '"severity":"low|medium|high"}],'
            '"expected_output":"summary|table|chart|number|narrative|file",'
            '"urgency":"low|normal|high",'
            '"estimated_complexity":"simple|moderate|complex",'
            '"requires_clarification":false,'
            '"clarification_question":null,'
            '"out_of_scope":false,'
            '"out_of_scope_reason":null'
            "}\n"
            "Rules: mark out_of_scope when unavailable capability is required; "
            "minimize requires_clarification for super_admin/top_mgmt; "
            "use fetch_data for report/data requests; "
            "when CONVERSATION CONTEXT lists a last project and the user asks for "
            "cost/expense breakdown or drill-down without naming a new project, set "
            "requires_clarification=false, subject_area=project, primary_action=analyze.\n"
            "ATTRIBUTE vs FINANCIAL queries:\n"
            "If the user asks about a project ATTRIBUTE (project manager, client, "
            "deadline, status, location, team) rather than financial data "
            "(expenses, costs, revenue, budget), set subject_area=project_attribute, "
            "primary_action=ask_question, requires_clarification=false.\n"
            "Examples: 'who is the PM of Villa 34' → project_attribute; "
            "'Villa 34 expense' → financial/project.\n"
            f"{CLARIFICATION_PROMPT_RULES}"
        )

    def _parse_response(
        self,
        raw_response: str,
        query: str,
        context: ContextStack,
    ) -> Intent:
        """Parse Claude JSON into Intent, falling back safely on parse errors."""
        try:
            payload = json.loads(self._extract_json(raw_response))
            if not isinstance(payload, dict):
                raise ValueError("Intent JSON must be an object")
            return Intent.from_dict(payload)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning(
                "[IntentAnalyzer] Invalid intent JSON for query=%r: %s",
                query,
                exc,
            )
            return self._fallback_intent(query, context)

    def _apply_manifest_guardrails(
        self,
        query: str,
        intent: Intent,
        context: ContextStack,
    ) -> Intent:
        """Override intent when the query clearly requires an unavailable capability."""
        lowered = query.lower()
        trigger_map = {
            "payslip": "hr.payslips",
            "pay slip": "hr.payslips",
            "salary slip": "hr.payslips",
            "leave balance": "hr.leave_balance",
            "attendance record": "hr.attendance",
            "attendance": "hr.attendance",
        }
        for phrase, capability_code in trigger_map.items():
            if phrase not in lowered:
                continue
            if context.capability_manifest.status_of(capability_code) != "unavailable":
                continue
            unavailable = next(
                (
                    capability
                    for capability in context.capability_manifest.unavailable
                    if capability.code == capability_code
                ),
                None,
            )
            alternative = unavailable.alternative if unavailable else "Use the HR portal."
            return Intent(
                primary_action=intent.primary_action,
                subject_area="hr",
                specific_intent=intent.specific_intent or query,
                entities=intent.entities,
                implicit_requirements=intent.implicit_requirements,
                ambiguities=intent.ambiguities,
                expected_output=intent.expected_output,
                urgency=intent.urgency,
                estimated_complexity="simple",
                requires_clarification=False,
                clarification_question=None,
                out_of_scope=True,
                out_of_scope_reason=(
                    f"{capability_code} is unavailable. {alternative}"
                ),
            )
        return intent

    def _apply_project_attribute_detection(self, query: str, intent: Intent) -> Intent:
        if not is_project_attribute_query(query):
            return intent
        return replace(
            intent,
            subject_area="project_attribute",
            primary_action="ask_question",
            requires_clarification=False,
            clarification_question=None,
        )

    def _fallback_intent(self, query: str, context: ContextStack) -> Intent:
        """Return a conservative fallback when Claude JSON cannot be parsed."""
        return Intent(
            primary_action="other",
            subject_area="general",
            specific_intent=query,
            requires_clarification=True,
            clarification_question=(
                "Could you clarify what you would like me to look up or analyze?"
            ),
            ambiguities=[
                Ambiguity(
                    type="parse_error",
                    description="Intent analyzer could not parse Claude JSON response",
                    severity="high",
                )
            ],
        )

    @staticmethod
    def _extract_json(raw_response: str) -> str:
        """Strip optional markdown fences from Claude output."""
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        return cleaned.strip()
