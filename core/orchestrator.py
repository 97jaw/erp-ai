"""
OOA Phase 2 — Orchestrator
===========================
File    : core/orchestrator.py
Author  : Lead Backend Developer
Version : 1.0.0

Builds and compiles the LangGraph StateGraph.
Wires all nodes and conditional edges into a single runnable graph.

Flow:
    START
      │
      ▼
    SessionHydrationNode
      │
      ▼
    TurnResetNode
      │
      ▼
    LanguageDetectionNode
      │
      ▼
    IntentClassifierNode
      │
      ├── RAG       → RAGNode       → ResponseFormatterNode
      ├── KPI       → KPINode       → ResponseFormatterNode
      ├── AMBIGUOUS → ResponseFormatterNode
      └── error     → ErrorHandlerNode → ResponseFormatterNode
                                          │
                                          ▼
                                        END
                                   (session persisted)
"""

from __future__ import annotations

import logging
import os
from typing import Any, Literal

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from core.base_adapter import AdapterFactory, OdooConnectionConfig
from core.nodes.error_node import ErrorHandlerNode
from core.nodes.intent_node import IntentClassifierNode
from core.nodes.kpi_node import KPINode
from core.nodes.language_node import LanguageDetectionNode
from core.nodes.rag_node import RAGNode
from core.nodes.response_formatter_node import ResponseFormatterNode
from core.nodes.session_nodes import SessionHydrationNode, TurnResetNode
from core.session_store import InMemorySessionStore, SessionStore
from core.state import AgentState, IntentType, OdooVersion, SessionState, TurnState

load_dotenv()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Routing Functions (Conditional Edges)
# ---------------------------------------------------------------------------

def route_by_intent(
    state: AgentState,
) -> Literal["rag", "kpi", "accounting", "ambiguous", "error"]:

    if state.turn.error_state is not None:
        return "error"

    intent = state.turn.turn_intent
    if intent is None:
        return "ambiguous"

    if intent.intent_type == IntentType.RAG:
        return "rag"
    if intent.intent_type == IntentType.KPI:
        return "kpi"
    if intent.intent_type == IntentType.ACCOUNTING:
        return "accounting"

    return "ambiguous"

def route_after_execution(
    state: AgentState,
) -> Literal["error", "format"]:
    """
    After RAGNode or KPINode — check if an error occurred.
    Discovery flag is also treated as a recoverable error for now.
    """
    if state.turn.error_state is not None:
        return "error"

    if state.turn.requires_discovery:
        logger.info(
            "[Router] Discovery required for model '%s' — routing to error.",
            state.turn.last_odoo_model,
        )
        return "error"

    return "format"


# ---------------------------------------------------------------------------
# Adapter-Aware Node Wrappers
# ---------------------------------------------------------------------------

def make_rag_node_fn(
    rag_node: RAGNode,
    adapter_config: OdooConnectionConfig,
):
    """
    Wraps RAGNode.__call__ with adapter injection.
    LangGraph nodes receive only state — adapter is injected via closure.
    """
    adapter = AdapterFactory.get_adapter(adapter_config)
    adapter.authenticate()

    def _call(state: AgentState) -> dict[str, Any]:
        return rag_node(state, adapter)

    return _call


def make_kpi_node_fn(
    kpi_node: KPINode,
    adapter_config: OdooConnectionConfig,
):
    """Wraps KPINode.__call__ with adapter injection."""
    adapter = AdapterFactory.get_adapter(adapter_config)
    adapter.authenticate()

    def _call(state: AgentState) -> dict[str, Any]:
        return kpi_node(state, adapter)

    return _call


# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_graph(
    store         : SessionStore,
    adapter_config: OdooConnectionConfig,
    api_key       : str | None = None,
    confidence_threshold: float = 0.75,
) -> StateGraph:
    """
    Builds and compiles the full LangGraph StateGraph.

    Args:
        store              : Session persistence backend
        adapter_config     : Odoo connection config (version detected here)
        api_key            : Anthropic API key
        confidence_threshold: Intent classifier threshold (default 0.75)

    Returns:
        Compiled StateGraph ready for invocation.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    # --- Instantiate all nodes ---
    session_node    = SessionHydrationNode(store=store)
    turn_reset_node = TurnResetNode()
    language_node   = LanguageDetectionNode(api_key=key)
    intent_node     = IntentClassifierNode(
        api_key              = key,
        confidence_threshold = confidence_threshold,
    )
    rag_node        = RAGNode(api_key=key)
    kpi_node        = KPINode(api_key=key)
    error_node      = ErrorHandlerNode()
    formatter_node  = ResponseFormatterNode(api_key=key)

    # Wrap adapter-dependent nodes
    rag_fn = make_rag_node_fn(rag_node, adapter_config)
    kpi_fn = make_kpi_node_fn(kpi_node, adapter_config)

    # --- Build graph ---
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("session_hydration", session_node)
    graph.add_node("turn_reset",        turn_reset_node)
    graph.add_node("language_detection",language_node)
    graph.add_node("intent_classifier", intent_node)
    graph.add_node("rag",               rag_fn)
    graph.add_node("kpi",               kpi_fn)
    graph.add_node("error_handler",     error_node)
    graph.add_node("response_formatter",formatter_node)

    # --- Wire edges ---

    # Linear entry pipeline
    graph.add_edge(START,                "session_hydration")
    graph.add_edge("session_hydration",  "turn_reset")
    graph.add_edge("turn_reset",         "language_detection")
    graph.add_edge("language_detection", "intent_classifier")

    # Conditional routing after intent classification
    graph.add_conditional_edges(
        "intent_classifier",
        route_by_intent,
        {
            "rag"      : "rag",
            "kpi"      : "kpi",
            "ambiguous": "response_formatter",
            "error"    : "error_handler",
        },
    )

    # Conditional routing after RAG/KPI execution
    graph.add_conditional_edges(
        "rag",
        route_after_execution,
        {
            "error" : "error_handler",
            "format": "response_formatter",
        },
    )
    graph.add_conditional_edges(
        "kpi",
        route_after_execution,
        {
            "error" : "error_handler",
            "format": "response_formatter",
        },
    )

    # Error handler always routes to formatter
    graph.add_edge("error_handler",      "response_formatter")

    # Formatter is always the final node
    graph.add_edge("response_formatter", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Convenience Runner (for local testing)
# ---------------------------------------------------------------------------

def run_agent(
    user_input    : str,
    session_id    : str,
    odoo_user_id  : int,
    odoo_url      : str,
    odoo_version  : OdooVersion,
    odoo_db       : str,
    odoo_username : str,
    odoo_api_key  : str,
    company_ids   : list[int] | None = None,
) -> dict[str, Any]:
    """
    Convenience function for local testing.
    Creates a fresh graph run with the given input.

    Returns the final response dict from ResponseFormatterNode.
    """
    store = InMemorySessionStore()

    config = OdooConnectionConfig(
        url      = odoo_url,
        database = odoo_db,
        username = odoo_username,
        api_key  = odoo_api_key,
        version  = odoo_version,
    )

    graph = build_graph(store=store, adapter_config=config)

    initial_state = AgentState(
        session=SessionState(
            session_id   = session_id,
            odoo_user_id = odoo_user_id,
            odoo_version = odoo_version,
            odoo_url     = odoo_url,
            company_ids  = company_ids or [1],
        ),
        turn=TurnState(raw_input=user_input),
    )

    result = graph.invoke(initial_state)
    return result["turn"]["last_odoo_response"]