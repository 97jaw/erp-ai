"""
OOA Phase 4 — CLI Chat Runner (Multi-Turn)
===========================================
File    : run_chat.py

Now supports multi-turn conversation with persistent session.

Usage:
    python run_chat.py                    ← interactive mode
    python run_chat.py "single question"  ← single question mode
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
load_dotenv()

from adapters.v14.connector import OdooV14Adapter
from core.base_adapter import OdooConnectionConfig
from core.nodes.error_node import ErrorHandlerNode
from core.nodes.intent_node import IntentClassifierNode
from core.nodes.kpi_node import KPINode
from core.nodes.language_node import LanguageDetectionNode
from core.nodes.rag_node import RAGNode
from core.nodes.response_formatter_node import ResponseFormatterNode
from core.nodes.session_nodes import SessionHydrationNode, TurnResetNode
from core.session_store import InMemorySessionStore
from core.state import AgentState, OdooVersion, SessionState, TurnState

# ---------------------------------------------------------------------------
# Persistent session file for CLI multi-turn
# ---------------------------------------------------------------------------

SESSION_FILE = Path(".cli_session.json")


def load_cli_session() -> dict:
    if SESSION_FILE.exists():
        return json.loads(SESSION_FILE.read_text())
    return {}


def save_cli_session(data: dict) -> None:
    SESSION_FILE.write_text(json.dumps(data, default=str))


def clear_cli_session() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def make_config() -> OdooConnectionConfig:
    return OdooConnectionConfig(
        url      = os.environ["ODOO_V14_URL"],
        database = os.environ["ODOO_V14_DB"],
        username = os.environ["ODOO_V14_USER"],
        api_key  = os.environ["ODOO_V14_PASSWORD"],
        version  = OdooVersion.V14,
    )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    user_input : str,
    session_id : str,
    cli_context: dict,
) -> tuple[dict, dict]:
    """
    Runs the full node pipeline.
    Returns (response_dict, updated_cli_context).
    """
    api_key = os.environ["ANTHROPIC_API_KEY"]
    config  = make_config()

    store          = InMemorySessionStore()
    session_node   = SessionHydrationNode(store=store)
    turn_reset     = TurnResetNode()
    language_node  = LanguageDetectionNode(api_key=api_key)
    intent_node    = IntentClassifierNode(
        api_key              = api_key,
        confidence_threshold = 0.75,
    )
    rag_node       = RAGNode(api_key=api_key)
    kpi_node       = KPINode(api_key=api_key)
    error_node     = ErrorHandlerNode()
    formatter_node = ResponseFormatterNode(api_key=api_key)

    adapter = OdooV14Adapter(config)
    adapter.authenticate()

    state = AgentState(
        session=SessionState(
            session_id   = session_id,
            odoo_user_id = adapter._uid,
            odoo_version = OdooVersion.V14,
            odoo_url     = config.url,
            company_ids  = [1],
        ),
        turn=TurnState(raw_input=user_input),
    )

    # --- Check if we are in clarification mode ---
    pending = cli_context.get("pending_clarification")
    if pending:
        user_input, state = _resolve_clarification(
            user_input, pending, state, adapter
        )
        if user_input is None:
            # Resolution failed — ask again
            return {
                "text"    : cli_context.get("last_question", "Please clarify."),
                "language": "en",
            }, cli_context

    print(f"\n{'═'*60}")
    print(f"  INPUT    : {state.turn.raw_input}")
    print(f"{'═'*60}")

    # Node 1
    result = session_node(state)
    if "session" in result:
        state.session = result["session"]

    # Node 2
    result = turn_reset(state)
    state.turn        = result["turn"]
    state.turn.raw_input = state.turn.raw_input or user_input

    # Node 3
    result = language_node(state)
    if "turn" in result and isinstance(result["turn"], dict):
        state.turn.input_language = result["turn"].get("input_language", "en")
    if "session" in result and isinstance(result["session"], dict):
        state.session.user_language = result["session"].get("user_language", "en")
    print(f"  LANGUAGE : {state.turn.input_language}")

    # Node 4
    result = intent_node(state)
    if "turn" in result and isinstance(result["turn"], dict):
        state.turn.turn_intent = result["turn"].get("turn_intent")
    if "session" in result and isinstance(result["session"], dict):
        state.session.active_intent = result["session"].get("active_intent")
        state.session.active_domain = result["session"].get("active_domain")

    intent = state.turn.turn_intent
    print(f"  INTENT   : {intent.intent_type if intent else 'UNKNOWN'} "
          f"({intent.confidence_score:.0%} confidence)" if intent else "")
    print(f"  DOMAIN   : {state.session.active_domain}")

    # Node 5: Route
    if state.turn.error_state:
        result = error_node(state)
        _apply(state, result)
    elif intent and intent.intent_type.value == "KPI":
        result = kpi_node(state, adapter)
        _apply(state, result)
    elif intent and intent.intent_type.value == "RAG":
        result = rag_node(state, adapter)
        _apply(state, result)

    # Error check
    if state.turn.error_state and not state.turn.visualization_payload:
        result = error_node(state)
        _apply(state, result)

    # Node 10
    result = formatter_node(state)
    if "turn" in result and isinstance(result["turn"], dict):
        state.turn.last_odoo_response = result["turn"].get(
            "last_odoo_response", {}
        )

    final = state.turn.last_odoo_response or {}

    # --- Save clarification context if needed ---
    updated_context = {}
    viz = state.turn.visualization_payload or {}
    if viz.get("visual_type") == "CLARIFICATION":
        updated_context = {
            "pending_clarification": {
                "type"          : "project_selection",
                "candidates"    : viz.get("candidates", []),
                "original_intent": (
                    intent.intent_type.value if intent else "KPI"
                ),
                "original_input": state.turn.raw_input,
                "filters"       : {},
            },
            "last_question": final.get("text", ""),
        }

    text = final.get("text", "") if isinstance(final, dict) else str(final)
    print(f"\n  RESPONSE : {text}")
    if viz.get("visual_type"):
        print(f"  VISUAL   : {viz.get('visual_type')}")
    print(f"{'═'*60}\n")

    return final, updated_context


def _resolve_clarification(
    user_input : str,
    pending    : dict,
    state      : AgentState,
    adapter    : OdooV14Adapter,
) -> tuple[str | None, AgentState]:
    """
    Resolves a pending clarification by matching user selection
    to a candidate project.
    """
    candidates = pending.get("candidates", [])

    # Try numeric selection (1, 2, 3...)
    try:
        idx = int(user_input.strip()) - 1
        if 0 <= idx < len(candidates):
            selected = candidates[idx]
            project_id = selected["id"]
            print(f"\n  SELECTED : {selected.get('name')} (id={project_id})")

            # Re-inject the original question with resolved project_id
            state.turn.raw_input = pending.get("original_input", "")
            state.session.active_domain = "project.financial.service"

            # Inject project_id directly into the KPINode via a workaround
            # Store it in session for the KPINode to pick up
            state.session.active_filters.raw_domain = []
            state.session.__dict__["_resolved_project_id"] = project_id

            return state.turn.raw_input, state
    except ValueError:
        pass

    # Try matching by WO number
    user_clean = user_input.strip().upper()
    for c in candidates:
        wo = (c.get("wo_ref_no") or "").upper()
        if wo and user_clean in wo:
            project_id = c["id"]
            print(f"\n  SELECTED : {c.get('name')} via WO (id={project_id})")
            state.turn.raw_input = pending.get("original_input", "")
            state.session.__dict__["_resolved_project_id"] = project_id
            return state.turn.raw_input, state

    return None, state


def _apply(state: AgentState, result: dict) -> None:
    if "turn" in result and isinstance(result["turn"], dict):
        for k, v in result["turn"].items():
            if hasattr(state.turn, k):
                setattr(state.turn, k, v)
    if "session" in result and isinstance(result["session"], dict):
        for k, v in result["session"].items():
            if hasattr(state.session, k):
                setattr(state.session, k, v)


# ---------------------------------------------------------------------------
# Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    session_id  = str(uuid4())

    # Single question mode
    if len(sys.argv) > 1:
        user_input  = " ".join(sys.argv[1:])
        cli_context = load_cli_session()

        response, updated_context = run_pipeline(
            user_input, session_id, cli_context
        )

        if updated_context:
            save_cli_session(updated_context)
        else:
            clear_cli_session()
        sys.exit(0)

    # Interactive mode
    print("\n  OOA — Odoo Omni-Agent")
    print("  Type your question in English, Arabic, or Urdu.")
    print("  Type 'exit' to quit | 'reset' to clear session\n")

    cli_context = load_cli_session()

    while True:
        try:
            user_input = input("  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Goodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() == "exit":
            clear_cli_session()
            print("  Goodbye!")
            break
        if user_input.lower() == "reset":
            clear_cli_session()
            cli_context = {}
            print("  Session cleared.\n")
            continue

        response, updated_context = run_pipeline(
            user_input, session_id, cli_context
        )

        cli_context = updated_context if updated_context else {}
        if not updated_context:
            clear_cli_session()
        else:
            save_cli_session(updated_context)