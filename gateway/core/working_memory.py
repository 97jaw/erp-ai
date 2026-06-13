"""Session and persistent working memory beyond raw conversation history.

Stores recent entities, user patterns, preferences, and strategy learnings.
In-memory for Phase 1; PostgreSQL persistence deferred to Admin Panel plan.
"""

from dataclasses import dataclass, field
from datetime import datetime
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gateway.core.intent_analyzer import Intent

logger = logging.getLogger(__name__)


@dataclass
class ActiveContext:
    """The subject the conversation is currently about."""

    project_id: int | None = None
    project_name: str | None = None
    project_wo: str | None = None
    confirmed: bool = False
    set_at_turn: int = 0
    last_referenced_turn: int = 0


@dataclass
class WorkingMemory:
    """Beyond conversation history: patterns, preferences, and recent context."""

    # Per-user persistent (in-memory for now)
    user_patterns: dict[str, Any] = field(default_factory=dict)
    user_preferences: dict[str, Any] = field(default_factory=dict)

    # Current session
    recent_entities: list[dict[str, Any]] = field(default_factory=list)
    recent_intents: list["Intent"] = field(default_factory=list)
    recent_periods: list[Any] = field(default_factory=list)
    session_facts: dict[str, Any] = field(default_factory=dict)
    active_context: ActiveContext = field(default_factory=ActiveContext)
    turn_count: int = 0

    # Strategy memory
    successful_strategies: dict[str, Any] = field(default_factory=dict)
    failed_strategies: dict[str, Any] = field(default_factory=dict)

    def set_active_project(
        self,
        project_id: int,
        name: str,
        *,
        wo: str | None = None,
        confirmed: bool = True,
    ) -> None:
        """Mark a project as the active subject of conversation."""
        self.active_context = ActiveContext(
            project_id=int(project_id),
            project_name=name,
            project_wo=wo,
            confirmed=confirmed,
            set_at_turn=self.turn_count,
            last_referenced_turn=self.turn_count,
        )
        self.session_facts["resolved_project_id"] = int(project_id)
        self.session_facts["project_name"] = name
        if confirmed:
            confirmed_entities = dict(self.session_facts.get("confirmed_entities") or {})
            confirmed_entities["project"] = {"id": int(project_id), "name": name}
            self.session_facts["confirmed_entities"] = confirmed_entities
        logger.info("[ActiveContext] Set to %s (id=%s)", name, project_id)

    def get_active_project(self) -> ActiveContext | None:
        """Return active project when conversation is still about one."""
        if self.active_context.project_id is None:
            return None
        return self.active_context

    def touch_active(self) -> None:
        """Mark active context as still relevant this turn."""
        if self.active_context.project_id is not None:
            self.active_context.last_referenced_turn = self.turn_count

    def clear_active_project(self) -> None:
        """User switched away from the current project."""
        if self.active_context.project_id is not None:
            logger.info(
                "[ActiveContext] Cleared (was %s)",
                self.active_context.project_name,
            )
        self.active_context = ActiveContext()

    def detect_topic_shift(self, message: str, intent: "Intent") -> bool:
        """Return True when this turn shifts topic away from the previous turn."""
        from gateway.core.topic_shift import detect_topic_shift

        last_turn = self.session_facts.get("last_turn")
        if last_turn is None and self.recent_intents:
            previous = self.recent_intents[-1]
            last_turn = {
                "message": previous.specific_intent,
                "entity_values": [entity.value for entity in previous.entities],
                "subject_area": previous.subject_area,
            }
        return detect_topic_shift(
            message,
            intent,
            last_turn=last_turn,
            active=self.get_active_project(),
            session_facts=dict(self.session_facts),
        )

    def clear_entity_context(self) -> None:
        """Wipe recent entities and session entity facts after a topic shift."""
        self.recent_entities = []
        self.clear_active_project()
        for key in (
            "confirmed_entities",
            "resolved_project_id",
            "last_expense_summary_project_id",
            "project_name",
            "pending_entity_clarification",
        ):
            self.session_facts.pop(key, None)

    def remember_intent(self, intent: "Intent") -> None:
        """Track recent intents for topic-shift detection within the same request cycle."""
        self.turn_count += 1
        self.recent_intents.append(intent)
        self.recent_intents = self.recent_intents[-5:]

    def remember_entity(self, entity_type: str, entity: dict[str, Any]) -> None:
        """Add to recent entities for quick reference."""
        self.recent_entities.append(
            {
                "type": entity_type,
                "data": entity,
                "timestamp": datetime.now(),
            }
        )
        self.recent_entities = self.recent_entities[-10:]

    def find_entity(
        self,
        hint: str,
        entity_type: str | None = None,
    ) -> dict[str, Any] | None:
        """Look for recently mentioned entity matching hint."""
        for entity in reversed(self.recent_entities):
            if entity_type and entity["type"] != entity_type:
                continue
            if self._matches(entity["data"], hint):
                return entity["data"]
        return None

    def summary(self) -> str:
        """Format working memory for inclusion in Claude system prompt."""
        return f"""
RECENT ENTITIES (last 10):
{self._format_entities()}

SESSION FACTS:
{self._format_session_facts()}

KNOWN USER PATTERNS:
{self._format_patterns()}

SUCCESSFUL STRATEGIES:
{self._format_strategies()}
"""

    def _matches(self, entity_data: dict[str, Any], hint: str) -> bool:
        """Return True if hint fuzzy-matches any searchable entity field."""
        normalized_hint = hint.strip().lower()
        if not normalized_hint:
            return False

        searchable_fields = ("name", "code", "display_name", "partner_name", "project_name")
        for field_name in searchable_fields:
            value = entity_data.get(field_name)
            if isinstance(value, str) and normalized_hint in value.lower():
                return True

        for value in entity_data.values():
            if isinstance(value, str) and normalized_hint in value.lower():
                return True

        return False

    def _format_entities(self) -> str:
        if not self.recent_entities:
            return "- None"
        lines: list[str] = []
        for entity in self.recent_entities:
            data = entity["data"]
            label = (
                data.get("name")
                or data.get("display_name")
                or data.get("code")
                or str(data)
            )
            lines.append(f"- {entity['type']}: {label}")
        return "\n".join(lines)

    def _format_session_facts(self) -> str:
        if not self.session_facts:
            return "- None"
        return "\n".join(f"- {key}: {value}" for key, value in self.session_facts.items())

    def _format_patterns(self) -> str:
        if not self.user_patterns:
            return "- None"
        return "\n".join(f"- {key}: {value}" for key, value in self.user_patterns.items())

    def _format_strategies(self) -> str:
        if not self.successful_strategies:
            return "- None"
        return "\n".join(
            f"- {key}: {value}" for key, value in self.successful_strategies.items()
        )
