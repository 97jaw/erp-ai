"""
OOA Master State Contract
=========================
File    : core/state.py
Author  : Lead Backend Developer
Version : 1.0.0

Defines the canonical Pydantic state models for the LangGraph StateGraph.
These are the single source of truth for all node communication.

Architecture Decision (Approved — Suggestion A):
    SessionState  → persists across turns (written to Postgres at END node)
    TurnState     → reset at every turn entry (ephemeral, never persisted)
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
from datetime import datetime, UTC

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class IntentType(str, Enum):
    """The three processing tracks + guard states."""
    RAG         = "RAG"          # Track A: Retrieval
    KPI         = "KPI"          # Track B: Analytical
    WRITE       = "WRITE"        # Track C: Transactional
    AMBIGUOUS   = "AMBIGUOUS"    # Needs clarification from user
    UNKNOWN     = "UNKNOWN"      # Classification failed entirely
    ACCOUNTING = "ACCOUNTING" 
    GENERAL    = "GENERAL"


class OdooVersion(str, Enum):
    """Supported Odoo versions. Drives adapter selection."""
    V14 = "14"
    V18 = "18"


class VisualType(str, Enum):
    """Approved visualization schema types (Phase 3 contract)."""
    KPI_CARD    = "KPI_CARD"
    BAR_CHART   = "BAR_CHART"
    LINE_CHART  = "LINE_CHART"
    DATA_TABLE  = "DATA_TABLE"
    GROUPED_TABLE = "GROUPED_TABLE"
    PIVOT_TABLE = "PIVOT_TABLE"   # Added: covers region × month comparisons
    FINANCIAL_REPORT = "FINANCIAL_REPORT"   # ← P&L / Balance Sheet hierarchy
    LEDGER_TABLE     = "LEDGER_TABLE"       # ← General Ledger / Trial Balance
    AGEING_TABLE     = "AGEING_TABLE"       # ← Partner Ageing buckets


class ErrorSeverity(str, Enum):
    RECOVERABLE = "RECOVERABLE"   # e.g., field not found — can retry with discovery
    FATAL       = "FATAL"         # e.g., auth failure — must abort turn


# ---------------------------------------------------------------------------
# Sub-Models
# ---------------------------------------------------------------------------

class IntentRecord(BaseModel):
    """
    Approved — Suggestion B (deferred, now implemented within SessionState).
    Tracks not just the intent type but HOW we arrived at it.
    The `inherited` flag is critical for the sticky-domain logic.
    """
    intent_type        : IntentType
    confidence_score   : float       = Field(..., ge=0.0, le=1.0)
    classified_at_turn : int         = Field(..., ge=0)
    inherited          : bool        = Field(
        default=False,
        description=(
            "True when this intent was carried forward from a prior turn "
            "rather than freshly classified. Downstream nodes use this "
            "to decide whether to re-confirm with the user."
        ),
    )
    raw_utterance      : Optional[str] = Field(
        default=None,
        description="The original user text that produced this classification.",
    )


class OdooFilterClause(BaseModel):
    """
    A single Odoo domain clause: ('field', 'operator', 'value').
    Using a model instead of raw tuples enforces structure.
    """
    field    : str
    operator : str = Field(..., description="Odoo domain operator e.g. '=', '>=', 'ilike'")
    value    : Any


class ActiveFilters(BaseModel):
    """
    Persisted filter context. Survives across turns so follow-up questions
    like 'And what about Dubai?' only need to patch warehouse, not rebuild.
    """
    date_from    : Optional[datetime] = None
    date_to      : Optional[datetime] = None
    company_ids  : list[int]          = Field(default_factory=list)
    warehouse_id : Optional[int]      = None
    user_id      : Optional[int]      = None
    # Escape hatch: raw Odoo domain clauses for complex filters
    raw_domain   : list[OdooFilterClause] = Field(default_factory=list)

    def to_odoo_domain(self) -> list[tuple]:
        """Serialize to Odoo-compatible domain list."""
        domain: list[tuple] = []
        if self.date_from:
            domain.append(("date", ">=", self.date_from.strftime("%Y-%m-%d")))
        if self.date_to:
            domain.append(("date", "<=", self.date_to.strftime("%Y-%m-%d")))
        if self.company_ids:
            domain.append(("company_id", "in", self.company_ids))
        if self.warehouse_id:
            domain.append(("warehouse_id", "=", self.warehouse_id))
        for clause in self.raw_domain:
            domain.append((clause.field, clause.operator, clause.value))
        return domain


class ConversationTurn(BaseModel):
    """A single turn in the conversation history."""
    role      : str   # "user" | "assistant"
    content   : str
    language  : Optional[str] = None   # ISO 639-1 e.g. "ur", "ar", "en"
    timestamp : datetime = Field(default_factory=datetime.utcnow)


class PendingWritePayload(BaseModel):
    """
    Holds a WRITE intent payload at the ConfirmationNode gate.
    Cleared on either user confirmation or cancellation.
    """
    odoo_model    : str
    method        : str                # e.g. "create", "action_confirm"
    values        : dict[str, Any]
    human_summary : str                # What will be shown to user for confirmation
    created_at    : datetime = Field(default_factory=datetime.utcnow)


class ErrorState(BaseModel):
    """
    Structured error — does NOT wipe SessionState when populated.
    Recovery strategy is determined by severity.
    """
    severity    : ErrorSeverity
    source_node : str
    message     : str
    odoo_error  : Optional[str] = None   # Raw error from Odoo RPC if applicable
    timestamp   : datetime = Field(default_factory=datetime.utcnow)


class MetadataCacheEntry(BaseModel):
    """
    Local versioned file cache entry for ir.model.fields discovery.
    Approved directive: check local .json → fetch → save.
    """
    model_name   : str
    odoo_version : OdooVersion
    fields       : dict[str, Any]        # field_name → field metadata dict
    cached_at    : datetime = Field(default_factory=datetime.utcnow)
    cache_path   : str = Field(
        description="Absolute path to the .json file on disk."
    )


# ---------------------------------------------------------------------------
# CORE STATE MODELS (Suggestion A — Approved Architecture)
# ---------------------------------------------------------------------------

class SessionState(BaseModel):
    """
    PERSISTED across turns → written to Postgres checkpointer at END node.

    Represents everything the agent must remember about a user's ongoing
    conversation. A bug in TurnState can never corrupt this model.
    """

    # Identity
    session_id    : str          = Field(default_factory=lambda: str(uuid4()))
    odoo_user_id  : int          = Field(..., description="res.users ID in Odoo")
    odoo_version  : OdooVersion  = Field(..., description="Set at auth, never changes mid-session")

    # Connection (references the adapter config, not raw credentials)
    odoo_url      : str
    company_ids   : list[int]    = Field(
        default_factory=list,
        description="Multi-company: list of company IDs the user has access to."
    )

    # Conversation context (the "sticky domain" system)
    active_intent  : Optional[IntentRecord] = Field(
        default=None,
        description=(
            "Last classified intent. If next turn has no domain signal, "
            "this is inherited with inherited=True."
        ),
    )
    active_domain  : Optional[str] = Field(
        default=None,
        description="Odoo model or business domain e.g. 'sale.order', 'inventory'",
    )
    active_filters : ActiveFilters = Field(default_factory=ActiveFilters)

    # Language
    user_language  : str = Field(
        default="en",
        description="ISO 639-1 language code detected from last utterance.",
    )

    # History (last N turns for multi-turn context)
    conversation_history : list[ConversationTurn] = Field(default_factory=list)
    max_history_turns    : int = Field(
        default=10,
        description="Sliding window. Oldest turns are pruned beyond this limit.",
    )

    # Visualization
    last_visual_type : Optional[VisualType] = None

    # Timestamps
    created_at     : datetime = Field(default_factory=datetime.utcnow)
    last_active_at : datetime = Field(default_factory=datetime.utcnow)
    # Conversation context for carry-forward
    last_response_data   : Optional[Any] = Field(
        default=None,
        description="Last successful Odoo response — enables re-render without re-fetch"
    )
    last_resolved_entity : Optional[dict] = Field(
        default=None,
        description="Last resolved entity (project, employee etc) — enables 'this project' references"
    )
    last_kpi_request     : Optional[dict] = Field(
        default=None,
        description="Last KPI request params — enables date filter changes"
    )
    # -----------------------------------------------------------------------
    # Validators
    # -----------------------------------------------------------------------

    @field_validator("conversation_history")
    @classmethod
    def enforce_history_limit(
        cls, v: list[ConversationTurn]
    ) -> list[ConversationTurn]:
        """Automatically prune history to max_history_turns on assignment."""
        # Note: max_history_turns default applied here conservatively
        return v[-20:] if len(v) > 20 else v

    # -----------------------------------------------------------------------
    # Methods
    # -----------------------------------------------------------------------

    def append_turn(self, role: str, content: str, language: Optional[str] = None) -> None:
        """Add a turn and enforce the sliding window."""
        self.conversation_history.append(
            ConversationTurn(role=role, content=content, language=language)
        )
        if len(self.conversation_history) > self.max_history_turns:
            self.conversation_history = self.conversation_history[-self.max_history_turns:]
        self.last_active_at = datetime.now(UTC)

    def inherit_intent(self, current_turn: int) -> Optional[IntentRecord]:
        """
        Called by IntentClassifierNode when the new utterance has no domain signal.
        Returns the current intent marked as inherited, or None if no prior intent.
        """
        if self.active_intent is None:
            return None
        return self.active_intent.model_copy(
            update={
                "inherited": True,
                "classified_at_turn": current_turn,
            }
        )

    def patch_filters(self, **kwargs: Any) -> None:
        """
        Partially update active_filters without replacing the entire object.
        Supports the follow-up pattern: 'And what about last month?' only
        changes date fields, preserving company/warehouse context.
        """
        current = self.active_filters.model_dump()
        current.update({k: v for k, v in kwargs.items() if v is not None})
        self.active_filters = ActiveFilters(**current)


class TurnState(BaseModel):
    """
    EPHEMERAL — reset by TurnResetNode at the start of every turn.
    Never written to the persistence layer.

    Holds everything relevant only to the current request-response cycle.
    """

    # Raw input
    raw_input        : str = ""
    input_language   : Optional[str] = None   # Detected by LanguageDetectionNode

    # Classified intent for this turn (may differ from SessionState.active_intent)
    turn_intent      : Optional[IntentRecord] = None

    # Parameter extraction output (Pydantic-validated before any RPC call)
    extracted_params : dict[str, Any] = Field(default_factory=dict)

    # Write gate
    pending_confirmation : Optional[PendingWritePayload] = None
    confirmation_received: Optional[bool] = None   # True=yes, False=cancel, None=pending

    # Adapter output
    last_odoo_response   : Optional[Any] = None
    last_odoo_model      : Optional[str] = None    # e.g. "sale.order"

    # Visualization payload (sent to frontend)
    visualization_payload: Optional[dict[str, Any]] = None

    # Error (does NOT affect SessionState)
    error_state          : Optional[ErrorState] = None

    # Routing flags (set by nodes, read by conditional edges)
    requires_discovery   : bool = False   # Triggers DiscoveryTool if True
    requires_clarification: bool = False  # Routes to AmbiguityNode if True

    # Turn counter (incremented by TurnResetNode)
    turn_number          : int = 0

    def has_error(self) -> bool:
        return self.error_state is not None

    def is_write_pending(self) -> bool:
        return (
            self.pending_confirmation is not None
            and self.confirmation_received is None
        )


# ---------------------------------------------------------------------------
# Composite Graph State (what LangGraph actually carries)
# ---------------------------------------------------------------------------

class AgentState(BaseModel):
    """
    The single object passed between all LangGraph nodes.

    Nodes READ from both session and turn.
    Nodes WRITE to turn freely.
    Nodes WRITE to session only through approved mutator methods
    (append_turn, patch_filters, inherit_intent) to prevent accidental corruption.
    """
    session : SessionState
    turn    : TurnState = Field(default_factory=TurnState)

    class Config:
        # Allow mutation for LangGraph node updates
        model_config = {"frozen": False}
