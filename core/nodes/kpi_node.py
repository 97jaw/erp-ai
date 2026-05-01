"""
OOA Phase 2 — Node 6
=====================
File    : core/nodes/kpi_node.py
Author  : Lead Backend Developer
Version : 1.0.0

KPINode:
    - Extracts kpi_type and filters from user input using Claude
    - Calls adapter.get_kpi_data() — ALL math stays in Odoo backend
    - Automatically selects VisualType based on data shape
    - Never performs arithmetic — pure parameter orchestrator
    - Returns partial dict only
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import anthropic
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from core.base_adapter import BaseOdooAdapter, KPIRequest, KPIResponse
from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
    VisualType,
)

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

KPI_EXTRACTION_PROMPT = """You are a KPI parameter extractor for an Odoo ERP system.

The user wants ANALYTICS or a KPI calculation.
Active Odoo model : {odoo_domain}
User language     : {user_language}
User input        : "{raw_input}"

Session filters already active:
- Date from  : {date_from}
- Date to    : {date_to}
- Company IDs: {company_ids}

IMPORTANT ROUTING RULES:
- If the user asks about project costs, expenses, budget, profit, margin,
  LPO, petty cash, labor, staff, cost distribution, or financial data
  for a specific project → use model: project.financial.service
  and method: get_project_expense_dashboard
- If the user asks for financial data with a date range → use
  model: project.financial.service
  and method: get_project_financial_data
- For all other KPIs use the active model

Extract the KPI parameters and respond with ONLY this JSON:
{{
  "kpi_type" : "snake_case_kpi_name",
  "model"    : "technical.model.name",
  "method"   : "get_ai_kpi",
  "filters"  : {{
    "project_id"  : null,
    "project_name": null,
    "date_from"   : null,
    "date_to"     : null,
    "company_ids" : [],
    "warehouse_id": null,
    "group_by"    : null,
    "location"    : null
  }}
}}


Rules:
1. kpi_type must be snake_case
2. If user mentions a project by NAME, set project_name to that name
3. If user mentions a project by ID, set project_id to that integer
4. method must match the routing rules above exactly
5. Inherit active session filters if user does not override them
6. If the input contains [project_id=NUMBER], extract that exact number as project_id in filters — do not search by name
7. No explanation, no markdown — JSON only"""
# ---------------------------------------------------------------------------
# Pydantic model for Claude's structured response
# ---------------------------------------------------------------------------

class KPIExtractionResult(BaseModel):
    """Validated KPI parameters extracted by Claude."""
    kpi_type : str
    model    : str
    method   : str = "get_ai_kpi"
    filters  : dict[str, Any] = Field(default_factory=dict)

    class Config:
        extra = "allow"


# ---------------------------------------------------------------------------
# Visualization Rule Engine (Suggestion 2 — Approved)
# ---------------------------------------------------------------------------

class VisualizationSelector:
    """
    Selects the correct VisualType based on KPIResponse data shape.
    Pure rule engine — no Claude call needed.

    Rules:
        Single scalar value          → KPI_CARD
        List with time field         → LINE_CHART
        List with category field     → BAR_CHART
        List of records (no metrics) → DATA_TABLE
        Two-dimensional data         → PIVOT_TABLE
    """

    TIME_KEYWORDS     = {"month", "week", "day", "date", "year", "period", "quarter"}
    CATEGORY_KEYWORDS = {"region", "warehouse", "company", "product", "category", "vendor"}

    def select(self, response: KPIResponse) -> VisualType:
        """Returns the most appropriate VisualType for the given response."""

        # Single scalar — always KPI_CARD
        if not isinstance(response.raw_data, list):
            logger.debug("[VisSelector] Single value → KPI_CARD")
            return VisualType.KPI_CARD

        data = response.raw_data

        # Empty list — default to KPI_CARD
        if not data:
            return VisualType.KPI_CARD

        # Inspect keys of first record
        if isinstance(data[0], dict):
            keys = {k.lower() for k in data[0].keys()}

            # Two dimensions present → PIVOT_TABLE
            has_time     = bool(keys & self.TIME_KEYWORDS)
            has_category = bool(keys & self.CATEGORY_KEYWORDS)
            if has_time and has_category:
                logger.debug("[VisSelector] Two dimensions → PIVOT_TABLE")
                return VisualType.PIVOT_TABLE

            # Time dimension → LINE_CHART
            if has_time:
                logger.debug("[VisSelector] Time dimension → LINE_CHART")
                return VisualType.LINE_CHART

            # Category dimension → BAR_CHART
            if has_category:
                logger.debug("[VisSelector] Category dimension → BAR_CHART")
                return VisualType.BAR_CHART

        # Default for lists → DATA_TABLE
        logger.debug("[VisSelector] List data → DATA_TABLE")
        return VisualType.DATA_TABLE


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class KPINode:
    """
    Analytics node. Extracts parameters → Calls Odoo KPI method → Selects viz.

    Zero arithmetic policy:
        This node NEVER performs math. It extracts parameters from speech,
        passes them to your Odoo backend via adapter.get_kpi_data(), and
        wraps the result in a visualization payload.

    Approved behaviors:
        - Pure parameter extraction via Claude
        - All calculations delegated to Odoo backend
        - Automatic VisualType selection via rule engine
        - RECOVERABLE error on any failure
        - Returns partial dict only
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for KPINode.")
        self.client   = anthropic.Anthropic(api_key=self.api_key)
        self.vis_selector = VisualizationSelector()

    def __call__(
        self,
        state  : AgentState,
        adapter: BaseOdooAdapter,
    ) -> dict[str, Any]:

        raw_input   = state.turn.raw_input
        odoo_domain = state.session.active_domain or "sale.order"

        # --- Use parameters from IntentClassifier if already extracted ---
        pre_extracted = state.turn.extracted_params or {}
        if pre_extracted.get("model") and pre_extracted.get("method"):
            logger.info(
                "[KPI] Using pre-extracted params: model=%s method=%s",
                pre_extracted.get("model"),
                pre_extracted.get("method"),
            )
            try:
                kpi_request = KPIRequest(
                    kpi_type   = pre_extracted.get("kpi_type", "project_kpi"),
                    model      = pre_extracted.get("model"),
                    method     = pre_extracted.get("method"),
                    filters    = {
                        "project_id"  : pre_extracted.get("project_id"),
                        "project_name": pre_extracted.get("project_name"),
                        "date_from"   : pre_extracted.get("date_from"),
                        "date_to"     : pre_extracted.get("date_to"),
                    },
                    company_id = (
                        state.session.company_ids[0]
                        if state.session.company_ids else None
                    ),
                )
                try:
                    kpi_response = adapter.get_kpi_data(kpi_request)
                except Exception as exc:
                    exc_name = type(exc).__name__
                    if exc_name == "ProjectAmbiguousError":
                        return self._ambiguous_project_result(exc.candidates, state)
                    if exc_name == "ProjectNotFoundError":
                        return self._not_found_project_result(exc.search_term, state)
                    return self._error_result(f"Odoo KPI method failed: {exc}")

                visual_type           = self.vis_selector.select(kpi_response)
                visualization_payload = self._build_payload(kpi_response, visual_type)

                return {
                    "turn": {
                        "extracted_params"      : kpi_request.model_dump(),
                        "last_odoo_response"    : kpi_response.model_dump(),
                        "last_odoo_model"       : kpi_request.model,
                        "visualization_payload" : visualization_payload,
                    },
                    "session": {
                        "last_visual_type": visual_type,
                    },
                }
            except Exception as exc:
                logger.warning(
                    "[KPI] Pre-extracted params failed (%s), falling through to extraction",
                    exc,
                )

        # --- Step 1: Extract KPI parameters via Claude ---
        try:
            extraction = self._extract_params(raw_input, odoo_domain, state)
        except Exception as exc:
            logger.error("[KPI] Extraction failed: %s", exc)
            return self._error_result(f"KPI parameter extraction failed: {exc}")

        logger.info(
            "[KPI] Extracted — kpi_type: %s | model: %s | filters: %s",
            extraction.kpi_type,
            extraction.model,
            extraction.filters,
        )

        # --- Step 2: Build KPIRequest and call Odoo backend ---
        kpi_request = KPIRequest(
            kpi_type   = extraction.kpi_type,
            model      = extraction.model,
            method     = extraction.method,
            filters    = extraction.filters,
            company_id = (
                state.session.company_ids[0]
                if state.session.company_ids else None
            ),
        )

        try:
            kpi_response = adapter.get_kpi_data(kpi_request)
        except Exception as exc:
            exc_name = type(exc).__name__
            if exc_name == "ProjectAmbiguousError":
                return self._ambiguous_project_result(exc.candidates, state)
            if exc_name == "ProjectNotFoundError":
                return self._not_found_project_result(exc.search_term, state)
            logger.error("[KPI] Odoo KPI call failed: %s", exc)
            return self._error_result(f"Odoo KPI method failed: {exc}")

        # --- Step 3: Select visualization ---
        visual_type           = self.vis_selector.select(kpi_response)
        visualization_payload = self._build_payload(kpi_response, visual_type)

        logger.info("[KPI] Selected visualization: %s", visual_type)

        return {
            "turn": {
                "extracted_params"      : kpi_request.model_dump(),
                "last_odoo_response"    : kpi_response.model_dump(),
                "last_odoo_model"       : extraction.model,
                "visualization_payload" : visualization_payload,
            },
            "session": {
                "last_visual_type": visual_type,
            },
        }
        
    def _ambiguous_project_result(
        self,
        candidates: list[dict],
        state     : AgentState,
    ) -> dict[str, Any]:
        """
        Returns a structured response when multiple projects match.
        Formats a selection list with WO, agreement, and client info.
        """
        language = state.turn.input_language or "en"

        # Build human-readable candidate list
        lines = []
        for i, p in enumerate(candidates, 1):
            wo        = p.get("wo_ref_no")    or "N/A"
            agreement = p.get("agreement_id")
            # Extract name from [id, name] tuple if needed
            if isinstance(agreement, list) and len(agreement) > 1:
                agreement = agreement[1]
            else:
                agreement = agreement or "N/A"

            client = p.get("partner_id")
            if isinstance(client, list) and len(client) > 1:
                client = client[1]
            else:
                client = client or "N/A"

            # Only show Arabic name if it looks real (more than 2 chars, not garbage)
            ar_name = p.get("project_name_arabic") or ""
            ar_name = ar_name if len(ar_name) > 3 else ""

            line = f"{i}. {p.get('name', 'Unknown')}"
            if ar_name:
                line += f" ({ar_name})"
            line += f"\n   WO: {wo}"
            line += f"\n   Agreement: {agreement}"
            line += f"\n   Client: {client}"
            lines.append(line)

        # Language-aware prompt
        prompts = {
            "en": (
                f"I found {len(candidates)} projects matching your search. "
                f"Please specify which one:\n" + "\n".join(lines)
            ),
            "ar": (
                f"وجدت {len(candidates)} مشاريع مطابقة لبحثك. "
                f"يرجى تحديد المشروع المقصود:\n" + "\n".join(lines)
            ),
            "ur": (
                f"آپ کی تلاش سے {len(candidates)} پروجیکٹس ملے۔ "
                f"براہ کرم مطلوبہ پروجیکٹ بتائیں:\n" + "\n".join(lines)
            ),
        }

        message = prompts.get(language, prompts["en"])

        logger.info(
            "[KPI] Ambiguous project — %d candidates found.", len(candidates)
        )

        return {
            "turn": {
                "last_odoo_response"    : message,
                "requires_clarification": True,
                "visualization_payload" : {
                    "visual_type": "CLARIFICATION",
                    "message"    : message,
                    "candidates" : candidates,
                },
            },
        }


    def _not_found_project_result(
        self,
        search_term: str,
        state      : AgentState,
    ) -> dict[str, Any]:
        """
        Returns a conversational response when zero projects match.
        Asks user for WO reference number or agreement ID.
        """
        language = state.turn.input_language or "en"

        prompts = {
            "en": (
                f"I could not find a project matching '{search_term}'. "
                f"Could you please provide the WO reference number "
                f"or agreement ID to help me find the right project?"
            ),
            "ar": (
                f"لم أتمكن من العثور على مشروع يطابق '{search_term}'. "
                f"هل يمكنك تزويدي برقم أمر العمل أو معرّف الاتفاقية "
                f"للعثور على المشروع الصحيح؟"
            ),
            "ur": (
                f"'{search_term}' سے ملتا جلتا کوئی پروجیکٹ نہیں ملا۔ "
                f"براہ کرم WO ریفرنس نمبر یا ایگریمنٹ ID فراہم کریں "
                f"تاکہ میں صحیح پروجیکٹ تلاش کر سکوں۔"
            ),
        }

        message = prompts.get(language, prompts["en"])

        logger.info(
            "[KPI] Project not found — search term: '%s'", search_term
        )

        return {
            "turn": {
                "last_odoo_response"    : message,
                "requires_clarification": True,
                "visualization_payload" : {
                    "visual_type": "CLARIFICATION",
                    "message"    : message,
                    "search_term": search_term,
                },
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
    ) -> KPIExtractionResult:
        """Calls Claude to extract KPI parameters."""
        filters = state.session.active_filters

        prompt = KPI_EXTRACTION_PROMPT.format(
            odoo_domain   = odoo_domain,
            user_language = state.session.user_language,
            raw_input     = raw_input,
            date_from     = filters.date_from or "null",
            date_to       = filters.date_to   or "null",
            company_ids   = state.session.company_ids or [],
        )

        message = self.client.messages.create(
            model      = "claude-sonnet-4-20250514",
            max_tokens = 300,
            messages   = [{"role": "user", "content": prompt}],
        )

        raw_json = message.content[0].text.strip()

        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]

        parsed = json.loads(raw_json)
        return KPIExtractionResult(**parsed)

    def _build_payload(
        self,
        response   : KPIResponse,
        visual_type: VisualType,
    ) -> dict[str, Any]:
        """
        Wraps KPIResponse into the Standard Visualization JSON contract
        defined in Phase 3. Frontend renders directly from this structure.
        """
        base = {
            "visual_type" : visual_type.value,
            "label"       : response.label,
            "unit"        : response.unit,
            "color_code"  : response.color_code,
        }

        if visual_type == VisualType.KPI_CARD:
            return {
                **base,
                "value"      : response.value,
                "delta"      : response.delta,
                "trend"      : response.trend,
            }

        if visual_type in (VisualType.LINE_CHART, VisualType.BAR_CHART):
            raw = response.raw_data or []
            return {
                **base,
                "labels"    : [r.get("label", str(i)) for i, r in enumerate(raw)],
                "datasets"  : [{"data": [r.get("value", 0) for r in raw]}],
                "axis_title": response.label,
            }

        if visual_type == VisualType.PIVOT_TABLE:
            return {
                **base,
                "raw_data"        : response.raw_data,
                "row_dimension"   : None,
                "col_dimension"   : None,
                "value_field"     : "value",
                "aggregation"     : "sum",
            }

        # DATA_TABLE default
        return {
            **base,
            "rows"   : response.raw_data or [],
            "sort_by": None,
        }

    def _error_result(self, message: str) -> dict[str, Any]:
        return {
            "turn": {
                "error_state": ErrorState(
                    severity    = ErrorSeverity.RECOVERABLE,
                    source_node = "KPINode",
                    message     = message,
                ),
            },
        }
