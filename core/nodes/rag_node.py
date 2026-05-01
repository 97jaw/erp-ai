"""
OOA Phase 2 — Node 5
=====================
File    : core/nodes/rag_node.py
Author  : Lead Backend Developer
Version : 1.0.0

RAGNode:
    - Extracts search parameters from user input using Claude
    - Validates every field name via adapter.field_exists()
    - Executes search_read through the version adapter
    - Triggers discovery if any field fails validation
    - Never invents data — zero hallucination policy enforced
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

from core.base_adapter import BaseOdooAdapter
from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
)

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """You are a search parameter extractor for an Odoo ERP system.

The user wants to RETRIEVE records from Odoo.
Active Odoo model : {odoo_domain}
User language     : {user_language}
User input        : "{raw_input}"

Extract the search parameters and respond with ONLY this JSON:
{{
  "model"  : "technical.model.name",
  "domain" : [["field", "operator", "value"]],
  "fields" : ["field1", "field2", "field3"],
  "limit"  : 10,
  "order"  : "field_name desc"
}}

Rules:
1. model must be the Odoo technical name (e.g. account.move, sale.order)
2. domain must use Odoo domain syntax with technical field names
3. fields must be real Odoo technical field names
4. limit default is 10, max is 80
5. order is optional — omit if not specified
6. Use ONLY lowercase technical names — never human labels
7. For name searches use 'ilike' operator
8. No explanation, no markdown — JSON only"""


# ---------------------------------------------------------------------------
# Pydantic model for Claude's structured response
# ---------------------------------------------------------------------------

class SearchParams(BaseModel):
    """Validated search parameters extracted by Claude."""
    model  : str
    domain : list[list[Any]] = Field(default_factory=list)
    fields : list[str]
    limit  : int = Field(default=10, ge=1, le=80)
    order  : str | None = None

    @field_validator("model")
    @classmethod
    def model_must_be_technical(cls, v: str) -> str:
        if " " in v:
            raise ValueError(f"model '{v}' must be a technical name.")
        return v.lower().strip()

    @field_validator("fields")
    @classmethod
    def fields_must_be_lowercase(cls, v: list[str]) -> list[str]:
        return [f.lower().strip() for f in v]

    def to_odoo_domain(self) -> list[tuple]:
        """Convert nested lists to Odoo domain tuples."""
        return [tuple(clause) for clause in self.domain]


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class RAGNode:
    """
    Retrieval node. Extracts → Validates → Fetches via Adapter.

    Approved behaviors:
        - Field validation before every search_read call
        - requires_discovery=True if any field fails validation
        - search_read always goes through BaseOdooAdapter
        - API or RPC failure → RECOVERABLE error in TurnState
        - Returns partial dict only
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for RAGNode.")
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def __call__(
        self,
        state  : AgentState,
        adapter: BaseOdooAdapter,
    ) -> dict[str, Any]:

        raw_input   = state.turn.raw_input
        odoo_domain = state.session.active_domain or "sale.order"

        # --- Step 1: Extract search parameters via Claude ---
        try:
            params = self._extract_params(raw_input, odoo_domain, state)
        except Exception as exc:
            logger.error("[RAG] Extraction failed: %s", exc)
            return self._error_result(
                state, f"Parameter extraction failed: {exc}"
            )

        logger.info(
            "[RAG] Extracted params — model: %s | fields: %s | domain: %s",
            params.model, params.fields, params.domain,
        )

        # --- Step 2: Validate fields against adapter cache ---
        invalid_fields = self._validate_fields(params, adapter)

        if invalid_fields:
            logger.warning(
                "[RAG] Invalid fields detected: %s — triggering discovery.",
                invalid_fields,
            )
            # Signal the graph to route through DiscoveryTool before retrying
            return {
                "turn": {
                    "extracted_params"  : params.model_dump(),
                    "requires_discovery": True,
                    "last_odoo_model"   : params.model,
                },
            }

        # --- Step 3: Execute search_read via adapter ---
        try:
            records = adapter.search_read(
                model  = params.model,
                domain = params.to_odoo_domain(),
                fields = params.fields,
                limit  = params.limit,
                order  = params.order,
            )
        except Exception as exc:
            logger.error("[RAG] search_read failed: %s", exc)
            return self._error_result(
                state, f"Odoo search failed: {exc}"
            )

        logger.info(
            "[RAG] search_read returned %d records from %s.",
            len(records), params.model,
        )

        # --- Step 4: Return results as partial dict ---
        return {
            "turn": {
                "extracted_params"   : params.model_dump(),
                "last_odoo_response" : records,
                "last_odoo_model"    : params.model,
                "requires_discovery" : False,
            },
        }

    # -----------------------------------------------------------------------
    # Internal Helpers
    # -----------------------------------------------------------------------

    def _extract_params(
        self,
        raw_input  : str,
        odoo_domain: str,
        state      : AgentState,
    ) -> SearchParams:
        """Calls Claude to extract structured search parameters."""
        prompt = EXTRACTION_PROMPT.format(
            odoo_domain   = odoo_domain,
            user_language = state.session.user_language,
            raw_input     = raw_input,
        )

        message = self.client.messages.create(
            model      = "claude-sonnet-4-20250514",
            max_tokens = 300,
            messages   = [{"role": "user", "content": prompt}],
        )

        raw_json = message.content[0].text.strip()

        # Strip markdown fences defensively
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]

        parsed = json.loads(raw_json)
        return SearchParams(**parsed)

    def _validate_fields(
        self,
        params : SearchParams,
        adapter: BaseOdooAdapter,
    ) -> list[str]:
        """
        Validates every extracted field against adapter cache.
        Returns list of invalid field names (empty = all valid).
        """
        invalid = []
        for field in params.fields:
            if not adapter.field_exists(params.model, field):
                invalid.append(field)
                logger.warning(
                    "[RAG] Field '%s' not found in %s metadata.",
                    field, params.model,
                )
        return invalid

    def _error_result(
        self, state: AgentState, message: str
    ) -> dict[str, Any]:
        """Builds a RECOVERABLE error result."""
        return {
            "turn": {
                "error_state": ErrorState(
                    severity    = ErrorSeverity.RECOVERABLE,
                    source_node = "RAGNode",
                    message     = message,
                ),
            },
        }
