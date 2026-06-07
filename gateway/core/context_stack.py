"""Context Stack assembly for a single query turn.

Defines the top-level container that combines user, conversation, capability,
memory, business, temporal, and quality context into one prompt-ready structure.
"""

from dataclasses import dataclass

from gateway.core.business_context import BusinessContext
from gateway.core.capability_manifest import CapabilityManifest
from gateway.core.temporal_context import TemporalContext
from gateway.core.user_context import UserContext
from gateway.core.working_memory import WorkingMemory


@dataclass
class ConversationContext:
    """Current conversation turn context."""

    session_id: str | None
    message: str
    turn_number: int = 1

    def summary(self) -> str:
        """Format conversation context for Claude prompt injection."""
        return f"""
Session: {self.session_id or "new"}
Current message: {self.message}
Turn: {self.turn_number}
"""


@dataclass
class QualityTargets:
    """Quality expectations applied to every response."""

    minimum_quality_score: float = 0.85
    max_retries: int = 2
    bar: str = "Senior management consultant + CFO's chief of staff"

    def summary(self) -> str:
        """Format quality targets for Claude prompt injection."""
        return f"""
Quality bar: {self.bar}
Minimum score before user sees response: {self.minimum_quality_score}
Max internal retries: {self.max_retries}
"""


@dataclass
class ContextStack:
    """Complete context for a single query, built fresh for every turn."""

    user: UserContext
    conversation: ConversationContext
    capability_manifest: CapabilityManifest
    working_memory: WorkingMemory
    business_context: BusinessContext
    temporal_context: TemporalContext
    quality_targets: QualityTargets

    def to_prompt_section(self) -> str:
        """Format the full context stack for inclusion in Claude system prompt."""
        return f"""
=== USER CONTEXT ===
{self.user.summary()}

=== CONVERSATION CONTEXT ===
{self.conversation.summary()}

=== CAPABILITIES ===
{self.capability_manifest.summary()}

=== WORKING MEMORY ===
{self.working_memory.summary()}

=== BUSINESS CONTEXT ===
{self.business_context.summary()}

=== TEMPORAL CONTEXT ===
{self.temporal_context.summary()}

=== QUALITY TARGETS ===
{self.quality_targets.summary()}
"""
