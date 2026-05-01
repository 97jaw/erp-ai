"""
OOA Phase 3 — Odoo 14 Adapter
===============================
File    : adapters/v14/connector.py
Author  : Lead Backend Developer
Version : 1.0.0

Implements BaseOdooAdapter for Odoo 14 using XML-RPC.

Authentication : username + password via common.authenticate()
Execution      : object.execute_kw()
Custom Engine  : call_method() for project.financial.service
"""

from __future__ import annotations
import anthropic
import os
import logging
import xmlrpc.client
from typing import Any, Optional

from core.base_adapter import (
    AdapterFactory,
    BaseOdooAdapter,
    KPIRequest,
    KPIResponse,
    OdooConnectionConfig,
)
from core.state import ErrorSeverity, OdooVersion
from adapters.v14.accounting_connector import AccountingConnector
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Custom Exceptions for Conversational Fallback
# ---------------------------------------------------------------------------

class ProjectNotFoundError(Exception):
    """
    Raised when no project matches the user's search term.
    The agent uses this to ask for WO reference or agreement ID.
    """
    def __init__(self, search_term: str) -> None:
        self.search_term = search_term
        super().__init__(f"No project found matching: '{search_term}'")


class ProjectAmbiguousError(Exception):
    """
    Raised when multiple projects match the user's search term.
    The agent uses this to show a selection list to the user.
    """
    def __init__(self, candidates: list[dict]) -> None:
        self.candidates = candidates
        super().__init__(
            f"Multiple projects found: {len(candidates)} matches"
        )

@AdapterFactory.register(OdooVersion.V14)
class OdooV14Adapter(BaseOdooAdapter):
    """
    Odoo 14 XML-RPC Adapter.

    All Odoo communication goes through two xmlrpc endpoints:
        /xmlrpc/2/common  → authentication
        /xmlrpc/2/object  → all model operations
    """

    def __init__(self, config: OdooConnectionConfig) -> None:
        super().__init__(config)
        self._accounting: AccountingConnector | None = None
        self._common = xmlrpc.client.ServerProxy(
            f"{config.url.rstrip('/')}/xmlrpc/2/common"
        )
        self._object = xmlrpc.client.ServerProxy(
            f"{config.url.rstrip('/')}/xmlrpc/2/object"
        )
        self._uid: Optional[int] = None

    # -----------------------------------------------------------------------
    # Version Identity
    # -----------------------------------------------------------------------

    @property
    def version(self) -> OdooVersion:
        return OdooVersion.V14
    @property
    def accounting(self) -> AccountingConnector:
        """Lazy-loaded AccountingConnector."""
        if self._accounting is None:
            self._accounting = AccountingConnector(self)
        return self._accounting
    # -----------------------------------------------------------------------
    # 1. Authentication
    # -----------------------------------------------------------------------

    def authenticate(self) -> int:
        """
        Authenticates via XML-RPC common.authenticate().
        Stores uid for all subsequent calls.
        """
        try:
            uid = self._common.authenticate(
                self.config.database,
                self.config.username,
                self.config.api_key,  # password stored in api_key field
                {},
            )
            if not uid:
                raise ConnectionError(
                    f"Authentication failed for user '{self.config.username}' "
                    f"on database '{self.config.database}'. "
                    f"Check credentials in .env file."
                )
            self._uid = uid
            logger.info(
                "[V14Adapter] Authenticated — user: %s | uid: %d | db: %s",
                self.config.username,
                self._uid,
                self.config.database,
            )
            return self._uid

        except xmlrpc.client.Fault as exc:
            logger.error("[V14Adapter] XML-RPC auth fault: %s", exc)
            raise

    def _ensure_authenticated(self) -> None:
        """Auto-authenticates if uid is not set."""
        if self._uid is None:
            self.authenticate()

    # -----------------------------------------------------------------------
    # 2. Core execute_kw wrapper
    # -----------------------------------------------------------------------

    def _execute(
        self,
        model  : str,
        method : str,
        args   : list,
        kwargs : dict | None = None,
    ) -> Any:
        """
        Central XML-RPC execute_kw call.
        All adapter methods route through here.
        """
        self._ensure_authenticated()
        return self._object.execute_kw(
            self.config.database,
            self._uid,
            self.config.api_key,
            model,
            method,
            args,
            kwargs or {},
        )

    # -----------------------------------------------------------------------
    # 3. Retrieval
    # -----------------------------------------------------------------------

    def search_read(
        self,
        model  : str,
        domain : list[tuple],
        fields : list[str],
        limit  : int = 80,
        offset : int = 0,
        order  : Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Standard search_read via XML-RPC."""
        kwargs: dict[str, Any] = {
            "fields": fields,
            "limit" : limit,
            "offset": offset,
        }
        if order:
            kwargs["order"] = order

        logger.debug(
            "[V14Adapter] search_read — model: %s | domain: %s | fields: %s",
            model, domain, fields,
        )

        return self._execute(model, "search_read", [domain], kwargs)

    def search_count(self, model: str, domain: list[tuple]) -> int:
        """Returns total record count matching domain."""
        return self._execute(model, "search_count", [domain])

    # -----------------------------------------------------------------------
    # 4. Custom Method Caller (Suggestion 2 — Approved)
    # -----------------------------------------------------------------------

    def call_method(
        self,
        model  : str,
        method : str,
        args   : list,
        kwargs : dict | None = None,
    ) -> Any:
        """
        Calls any named method on any Odoo model via execute_kw.

        Used for your custom financial engine:
            call_method(
                "project.financial.service",
                "get_project_expense_dashboard",
                [project_id]
            )

        Args:
            model  : Odoo technical model name
            method : Method name as string
            args   : Positional arguments as list
            kwargs : Keyword arguments as dict

        Returns:
            Whatever Odoo returns — could be dict, list, bool.
        """
        logger.info(
            "[V14Adapter] call_method — model: %s | method: %s | args: %s",
            model, method, args,
        )
        return self._execute(model, method, args, kwargs)

    # -----------------------------------------------------------------------
    # 5. KPI Execution
    # -----------------------------------------------------------------------

    def get_kpi_data(self, request: KPIRequest) -> KPIResponse:
        """
        Calls your Odoo AI-Gateway KPI method via execute_kw.

        For project.financial.service methods, the response is a rich
        dict — we normalize it into KPIResponse with raw_data attached.
        """
        logger.info(
            "[V14Adapter] get_kpi_data — model: %s | method: %s | filters: %s",
            request.model, request.method, request.filters,
        )

        # Build args from filters
        args = self._build_kpi_args(request)

        raw = self._execute(request.model, request.method, args)

        return self._normalize_kpi_response(raw, request)

    def _build_kpi_args(self, request: KPIRequest) -> list:
        """
        Builds positional args list from KPIRequest filters.
        Resolves project name to ID — raises descriptive errors for
        zero or multiple matches so the agent can interact with user.
        """
        filters = request.filters

        if request.method == "get_project_expense_dashboard":
            project_id, candidates = self._resolve_project_id(filters)

            if project_id:
                return [project_id]

            if candidates:
                # Multiple matches — raise with candidate list for agent
                raise ProjectAmbiguousError(candidates)

            # Zero matches — raise for agent to ask clarifying question
            raise ProjectNotFoundError(filters.get("project_name", ""))

        if request.method == "get_project_financial_data":
            project_id, candidates = self._resolve_project_id(filters)

            if project_id:
                return [
                    project_id,
                    filters.get("date_from"),
                    filters.get("date_to"),
                ]

            if candidates:
                raise ProjectAmbiguousError(candidates)

            raise ProjectNotFoundError(filters.get("project_name", ""))

        return [filters]


    def _resolve_project_id(
        self,
        filters: dict,
    ) -> tuple[int | None, list | None]:
        """
        Resolves a project ID from filters.

        Returns:
            (project_id, None)          → single match found
            (None, candidates_list)     → multiple matches found
            (None, [])                  → zero matches found
        """
        # Direct ID provided — no resolution needed
        project_id = filters.get("project_id")
        if project_id:
            return int(project_id), None

        project_name = filters.get("project_name")
        if not project_name:
            return None, []

        logger.info("[V14Adapter] Resolving project: '%s'", project_name)

        # --- Attempt 1: English name ilike ---
        candidates = self._search_projects_by_name(project_name, field="name")
        if len(candidates) == 1:
            return candidates[0]["id"], None
        if len(candidates) > 1:
            return None, candidates

        # --- Attempt 2: Arabic name field ilike ---
        candidates = self._search_projects_by_name(
            project_name, field="project_name_arabic"
        )
        if len(candidates) == 1:
            return candidates[0]["id"], None
        if len(candidates) > 1:
            return None, candidates

        # --- Attempt 3: Claude translation → English ilike ---
        logger.info(
            "[V14Adapter] No match — translating '%s' to English", project_name
        )
        translated = self._translate_to_english(project_name)
        if translated and translated.lower() != project_name.lower():
            logger.info("[V14Adapter] Translated: '%s'", translated)

            # Try full translated name
            candidates = self._search_projects_by_name(translated, field="name")
            if len(candidates) == 1:
                return candidates[0]["id"], None
            if len(candidates) > 1:
                return None, candidates

            # Try keyword by keyword
            for keyword in translated.split():
                if len(keyword) < 3:
                    continue
                candidates = self._search_projects_by_name(keyword, field="name")
                if len(candidates) == 1:
                    return candidates[0]["id"], None
                if len(candidates) > 1:
                    return None, candidates

        # --- Zero results ---
        logger.warning(
            "[V14Adapter] Could not resolve project: '%s'", project_name
        )
        return None, []


    def _search_projects_by_name(
        self,
        name : str,
        field: str = "name",
        limit: int = 5,
    ) -> list[dict]:
        """
        Searches project.project by any name field.
        Returns list of candidates with WO, agreement, and client info.
        """
        try:
            results = self.search_read(
                model  = "project.project",
                domain = [[field, "ilike", name]],
                fields = [
                    "id",
                    "name",
                    "project_name_arabic",
                    "wo_ref_no",
                    "agreement_id",
                    "partner_id",
                ],
                limit  = limit,
            )
            return results
        except Exception as exc:
            logger.error(
                "[V14Adapter] Search failed on field '%s': %s", field, exc
            )
            return []


    def _translate_to_english(self, text: str) -> str:
        """
        Translates Arabic/Urdu text to English using Claude.
        Optimized for UAE place names, project names, and proper nouns.
        """
        try:
            import anthropic
            client = anthropic.Anthropic(
                api_key=os.environ.get("ANTHROPIC_API_KEY")
            )
            message = client.messages.create(
                model      = "claude-sonnet-4-20250514",
                max_tokens = 100,
                messages   = [{
                    "role"   : "user",
                    "content": (
                        f"You are translating a UAE construction/facilities "
                        f"project name from Arabic to English.\n\n"
                        f"Rules:\n"
                        f"1. This is a PROPER NOUN — a place name or project name "
                        f"in the UAE (Abu Dhabi, Al Ain, Dubai area)\n"
                        f"2. Transliterate place names phonetically — do NOT "
                        f"translate their meaning\n"
                        f"3. For example: زايدية = Zayidia (NOT Zaidism)\n"
                        f"4. For example: مدرسة = School\n"
                        f"5. For example: بنين = Boys\n"
                        f"6. Reply with ONLY the English result, nothing else\n\n"
                        f"Translate: {text}"
                    ),
                }],
            )
            return message.content[0].text.strip()
        except Exception as exc:
            logger.error("[V14Adapter] Translation failed: %s", exc)
            return text

    def _extract_search_keywords(self, name: str) -> list[str]:
        """
        Extracts searchable keywords from Arabic/Urdu/English project names.
        Filters out generic words that would match too many projects.
        """
        # Generic words to skip in Arabic
        arabic_stop = {
            "ما", "هو", "هي", "في", "من", "إلى", "على", "مشروع",
            "التكاليف", "تكاليف", "إجمالي", "المشروع", "عن", "هل",
            "كم", "متى", "أين", "لماذا", "كيف", "الذي", "التي"
        }
        # Generic words to skip in English
        english_stop = {
            "the", "a", "an", "of", "for", "in", "at", "to",
            "project", "total", "cost", "what", "is", "show"
        }

        words = name.replace("؟", "").replace("?", "").split()
        keywords = []

        for word in words:
            clean = word.strip(".,؟?!")
            if len(clean) < 3:
                continue
            if clean in arabic_stop or clean.lower() in english_stop:
                continue
            keywords.append(clean)

        logger.debug("[V14Adapter] Extracted keywords: %s", keywords)
        return keywords
        
    def _normalize_kpi_response(
        self,
        raw    : Any,
        request: KPIRequest,
    ) -> KPIResponse:

        if not isinstance(raw, dict):
            return KPIResponse(label=request.kpi_type, value=raw)

        # --- Check hierarchy FIRST (get_project_financial_data) ---
        if "hierarchy" in raw:
            kpis = raw.get("kpis", {})
            return KPIResponse(
                label      = raw.get("project", request.kpi_type),
                value      = kpis.get("net_profit", 0),
                unit       = "AED",
                trend      = "up" if kpis.get("net_profit", 0) >= 0 else "down",
                delta      = kpis.get("margin", 0),
                raw_data   = raw,
            )

        # --- Then check kpis (get_project_expense_dashboard) ---
        if "kpis" in raw:
            kpis = raw.get("kpis", {})
            return KPIResponse(
                label      = raw.get("project_name", request.kpi_type),
                value      = kpis.get("total_cost", 0),
                unit       = "AED",
                trend      = kpis.get("status", "normal"),
                delta      = kpis.get("exceed_percent", 0),
                color_code = self._status_to_color(kpis.get("status", "normal")),
                raw_data   = raw,
            )

        # Generic dict response
        return KPIResponse(
            label    = request.kpi_type,
            value    = raw.get("value", raw.get("total", 0)),
            raw_data = raw,
        )

    def _status_to_color(self, status: str) -> str:
        """Maps Odoo status strings to hex color codes for frontend."""
        return {
            "normal"  : "#22c55e",  # green
            "warning" : "#f59e0b",  # amber
            "critical": "#ef4444",  # red
        }.get(status, "#6b7280")    # gray default

    # -----------------------------------------------------------------------
    # 6. Write Operations
    # -----------------------------------------------------------------------

    def create_record(self, model: str, values: dict[str, Any]) -> int:
        """Creates a record and returns its new ID."""
        return self._execute(model, "create", [values])

    def write_record(
        self,
        model      : str,
        record_ids : list[int],
        values     : dict[str, Any],
    ) -> bool:
        return self._execute(model, "write", [record_ids, values])

    def execute_action(
        self,
        model      : str,
        method     : str,
        record_ids : list[int],
        kwargs     : Optional[dict[str, Any]] = None,
    ) -> Any:
        return self._execute(model, method, [record_ids], kwargs)

    # -----------------------------------------------------------------------
    # 7. Metadata Discovery
    # -----------------------------------------------------------------------

    def _fetch_fields_from_odoo(self, model: str) -> dict[str, Any]:
        """
        Fetches field metadata from ir.model.fields.
        Called by BaseOdooAdapter.get_model_fields() on cache miss.
        """
        logger.info(
            "[V14Adapter] Fetching ir.model.fields for model: %s", model
        )
        fields_data = self._execute(
            model,
            "fields_get",
            [],
            {"attributes": ["string", "type", "required", "relation"]},
        )
        return fields_data