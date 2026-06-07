"""Session and persistent working memory beyond raw conversation history.

Stores recent entities, user patterns, preferences, and strategy learnings.
In-memory for Phase 1; PostgreSQL persistence deferred to Admin Panel plan.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class WorkingMemory:
    """Beyond conversation history: patterns, preferences, and recent context."""

    # Per-user persistent (in-memory for now)
    user_patterns: dict[str, Any] = field(default_factory=dict)
    user_preferences: dict[str, Any] = field(default_factory=dict)

    # Current session
    recent_entities: list[dict[str, Any]] = field(default_factory=list)
    recent_periods: list[Any] = field(default_factory=list)
    session_facts: dict[str, Any] = field(default_factory=dict)

    # Strategy memory
    successful_strategies: dict[str, Any] = field(default_factory=dict)
    failed_strategies: dict[str, Any] = field(default_factory=dict)

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
