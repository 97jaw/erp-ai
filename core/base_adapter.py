"""
OOA Base Adapter Contract
=========================
File    : core/base_adapter.py
Author  : Lead Backend Developer
Version : 1.0.0

Defines the abstract BaseOdooAdapter that ALL version-specific adapters
must implement. No node in the LangGraph graph imports from /adapters
directly — they only ever reference this interface.

This is the "Plugin Contract". Swapping Odoo 14 for Odoo 18 (or adding
Odoo 17 in the future) requires zero changes to /core.

Metadata Cache Strategy (Approved Directive):
    1. Check  → .cache/schema/{version}/{model}.json
    2. Miss   → Fetch from ir.model.fields via RPC
    3. Save   → Write result to .json for future calls
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from core.state import (
    AgentState,
    ErrorSeverity,
    ErrorState,
    MetadataCacheEntry,
    OdooVersion,
)

logger = logging.getLogger(__name__)

# Default local cache directory (relative to project root)
DEFAULT_CACHE_DIR = Path(".cache") / "schema"


# ---------------------------------------------------------------------------
# Connection Configuration
# ---------------------------------------------------------------------------

class OdooConnectionConfig(BaseModel):
    """
    All parameters required to establish an Odoo RPC session.
    Loaded from environment / secret vault — never hardcoded.
    """
    url          : str
    database     : str
    username     : str
    api_key      : str = Field(repr=False)   # Masked in repr for log safety
    version      : OdooVersion
    timeout_secs : int = Field(default=30)
    company_id   : Optional[int] = None      # Primary company for multi-company setups


class KPIRequest(BaseModel):
    """
    Typed parameter container for all KPI method calls.
    The LLM extracts these parameters; the adapter passes them verbatim
    to the Odoo backend method. No math is performed in middleware.
    """
    kpi_type   : str                           # e.g. "growth_rate", "net_margin"
    model      : str                           # e.g. "marketplace.stats"
    method     : str                           # e.g. "get_ai_kpi"
    filters    : dict[str, Any] = Field(default_factory=dict)
    company_id : Optional[int]  = None


class KPIResponse(BaseModel):
    """
    Standard response contract from Odoo's AI-Gateway KPI method.
    Your backend must return a dict matching this shape.
    """
    label      : str
    value      : float | int | str
    unit       : Optional[str]  = None    # "%", "PKR", "AED", etc.
    trend      : Optional[str]  = None    # "up" | "down" | "stable"
    delta      : Optional[float]= None    # Change vs prior period
    color_code : Optional[str]  = None    # Hex color for frontend rendering
    raw_data   : Optional[Any]  = None    # Full dataset if visualization needed


class WriteRequest(BaseModel):
    """
    Typed payload for all CREATE / UPDATE / ACTION calls.
    Only dispatched after user confirmation (ConfirmationNode gate).
    """
    model         : str
    method        : str           # "create" | "write" | "action_confirm" | etc.
    record_ids    : list[int] = Field(default_factory=list)  # For write/action calls
    values        : dict[str, Any] = Field(default_factory=dict)
    human_summary : str           # Must match PendingWritePayload.human_summary


# ---------------------------------------------------------------------------
# Abstract Base Adapter
# ---------------------------------------------------------------------------

class BaseOdooAdapter(ABC):
    """
    The single interface all version-specific adapters must implement.

    Responsibilities:
        - Authentication with the target Odoo instance
        - Standardized RPC method execution
        - Local versioned schema cache management
        - Structured error propagation back to AgentState

    Never instantiated directly. Use AdapterFactory to get the correct
    version implementation.
    """

    def __init__(
        self,
        config     : OdooConnectionConfig,
        cache_dir  : Path = DEFAULT_CACHE_DIR,
    ) -> None:
        self.config    = config
        self.cache_dir = cache_dir / config.version.value
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._uid: Optional[int] = None   # Odoo user UID, set after authenticate()

    # -----------------------------------------------------------------------
    # 1. Authentication
    # -----------------------------------------------------------------------

    @abstractmethod
    def authenticate(self) -> int:
        """
        Authenticate with Odoo and return the uid (res.users DB id).

        Implementations:
            v14 → xmlrpc.client common.authenticate()
            v18 → JSON-RPC /web/session/authenticate or API key header

        Raises:
            OdooAuthError if credentials are invalid.
        """
        ...

    # -----------------------------------------------------------------------
    # 2. Retrieval
    # -----------------------------------------------------------------------

    @abstractmethod
    def search_read(
        self,
        model   : str,
        domain  : list[tuple],
        fields  : list[str],
        limit   : int = 80,
        offset  : int = 0,
        order   : Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """
        Standardized data fetch. Equivalent to Odoo's search_read ORM method.

        Args:
            model   : Odoo technical model name e.g. "sale.order"
            domain  : Odoo domain list e.g. [("state","=","sale")]
            fields  : Field names to return
            limit   : Max records (default 80, matching Odoo default)
            offset  : For pagination
            order   : Sort string e.g. "date_order desc"

        Returns:
            List of record dicts.
        """
        ...

    @abstractmethod
    def search_count(
        self,
        model  : str,
        domain : list[tuple],
    ) -> int:
        """
        Returns total count matching domain without fetching records.
        Used to avoid over-fetching for KPI counts.
        """
        ...

    # -----------------------------------------------------------------------
    # 3. KPI Execution (Deterministic Analytics — core requirement)
    # -----------------------------------------------------------------------

    @abstractmethod
    def get_kpi_data(self, request: KPIRequest) -> KPIResponse:
        """
        Calls a named AI-Gateway method on your Odoo backend.

        This is the ONLY path for analytical data. The adapter never
        performs arithmetic. It calls your expert Odoo method and returns
        the response wrapped in KPIResponse.

        Canonical backend signature expected on the Odoo side:
            @api.model
            def get_ai_kpi(self, kpi_type: str, filters: dict) -> dict:
                ...

        The returned dict must conform to KPIResponse fields.

        Args:
            request : KPIRequest with kpi_type, model, method, filters

        Returns:
            KPIResponse — typed and validated by Pydantic before use.
        """
        ...

    # -----------------------------------------------------------------------
    # 4. Write Operations (gated by ConfirmationNode)
    # -----------------------------------------------------------------------

    @abstractmethod
    def create_record(
        self,
        model  : str,
        values : dict[str, Any],
    ) -> int:
        """
        Creates a single record and returns its new database ID.

        Args:
            model  : e.g. "sale.order"
            values : Field/value dict validated by Pydantic before this call

        Returns:
            Integer ID of the newly created record.
        """
        ...

    @abstractmethod
    def write_record(
        self,
        model      : str,
        record_ids : list[int],
        values     : dict[str, Any],
    ) -> bool:
        """
        Updates existing records.

        Args:
            model      : Odoo model name
            record_ids : List of IDs to update
            values     : Fields to update

        Returns:
            True on success.
        """
        ...

    @abstractmethod
    def execute_action(
        self,
        model      : str,
        method     : str,
        record_ids : list[int],
        kwargs     : Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Calls a business action method on existing records.
        e.g. action_confirm(), action_done(), action_cancel()

        Args:
            model      : Odoo model name
            method     : Method name as string
            record_ids : Records to act on
            kwargs     : Optional keyword arguments for the method

        Returns:
            Whatever Odoo returns — could be True, a dict, or an action.
        """
        ...

    # -----------------------------------------------------------------------
    # 5. Metadata Discovery + Local Cache (Approved Directive)
    # -----------------------------------------------------------------------

    def get_model_fields(
        self,
        model           : str,
        force_refresh   : bool = False,
    ) -> dict[str, Any]:
        """
        TWO-TIER FIELD DISCOVERY:

        Tier 1 (Local Cache):
            Checks .cache/schema/{version}/{model}.json
            If found and not force_refresh → return immediately (low latency)

        Tier 2 (Live Discovery):
            Fetches ir.model.fields from Odoo
            Saves result to local .json for future calls

        Args:
            model         : Odoo model name e.g. "marketplace.vendor"
            force_refresh : Bypass cache and re-fetch from Odoo

        Returns:
            Dict of {field_name: field_metadata}
        """
        cache_file = self._get_cache_path(model)

        # --- Tier 1: Local Cache Check ---
        if not force_refresh and cache_file.exists():
            logger.debug(
                "[Cache HIT] %s v%s → %s",
                model, self.config.version.value, cache_file,
            )
            return self._load_from_cache(cache_file)

        # --- Tier 2: Live Discovery ---
        logger.info(
            "[Cache MISS] Fetching ir.model.fields for %s from Odoo %s",
            model, self.config.version.value,
        )
        fields_data = self._fetch_fields_from_odoo(model)

        # Save to local cache
        self._save_to_cache(model, fields_data, cache_file)

        return fields_data

    def field_exists(self, model: str, field_name: str) -> bool:
        """
        Zero-hallucination guard. Called by nodes before any search_read
        that uses a field name extracted from user speech.

        Returns True only if the field exists in Odoo's metadata.
        """
        fields = self.get_model_fields(model)
        return field_name in fields

    def _get_cache_path(self, model: str) -> Path:
        """Converts model name to a safe filename. e.g. sale.order → sale_order.json"""
        safe_name = model.replace(".", "_")
        return self.cache_dir / f"{safe_name}.json"

    def _load_from_cache(self, cache_file: Path) -> dict[str, Any]:
        with cache_file.open("r", encoding="utf-8") as f:
            entry = MetadataCacheEntry(**json.load(f))
        return entry.fields

    def _save_to_cache(
        self,
        model      : str,
        fields_data: dict[str, Any],
        cache_file : Path,
    ) -> None:
        entry = MetadataCacheEntry(
            model_name   = model,
            odoo_version = self.config.version,
            fields       = fields_data,
            cache_path   = str(cache_file),
        )
        with cache_file.open("w", encoding="utf-8") as f:
            json.dump(entry.model_dump(mode="json"), f, indent=2, default=str)
        logger.info("[Cache SAVED] %s", cache_file)

    @abstractmethod
    def _fetch_fields_from_odoo(self, model: str) -> dict[str, Any]:
        """
        Concrete adapters implement the actual ir.model.fields RPC call here.
        v14 uses xmlrpc, v18 uses JSON-RPC — same logical result.
        """
        ...

    # -----------------------------------------------------------------------
    # 6. Error Handling (Approved Amendment)
    # -----------------------------------------------------------------------

    def build_error_state(
        self,
        source_node: str,
        message    : str,
        severity   : ErrorSeverity = ErrorSeverity.RECOVERABLE,
        odoo_error : Optional[str] = None,
    ) -> ErrorState:
        """
        Standardized error factory. All adapter exceptions should be caught
        and converted to ErrorState rather than propagating raw exceptions.
        This ensures SessionState is never corrupted by a failed turn.
        """
        return ErrorState(
            severity    = severity,
            source_node = source_node,
            message     = message,
            odoo_error  = odoo_error,
        )

    # -----------------------------------------------------------------------
    # 7. Version Identity
    # -----------------------------------------------------------------------

    @property
    @abstractmethod
    def version(self) -> OdooVersion:
        """Returns the OdooVersion enum value this adapter handles."""
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} version={self.version} url={self.config.url}>"


# ---------------------------------------------------------------------------
# Adapter Factory
# ---------------------------------------------------------------------------

class AdapterFactory:
    """
    The Master Controller (Phase 2 spec).
    Detects or accepts the Odoo version and returns the correct adapter.
    Nodes never instantiate adapters directly.
    """

    _registry: dict[OdooVersion, type[BaseOdooAdapter]] = {}

    @classmethod
    def register(cls, version: OdooVersion):
        """Decorator to register a concrete adapter for a version."""
        def decorator(adapter_cls: type[BaseOdooAdapter]):
            cls._registry[version] = adapter_cls
            logger.info("Registered adapter: %s for Odoo %s", adapter_cls.__name__, version)
            return adapter_cls
        return decorator

    @classmethod
    def get_adapter(
        cls,
        config: OdooConnectionConfig,
    ) -> BaseOdooAdapter:
        """
        Returns the correct adapter instance for the given config version.

        Usage:
            adapter = AdapterFactory.get_adapter(config)
            adapter.authenticate()
        """
        adapter_cls = cls._registry.get(config.version)
        if adapter_cls is None:
            raise NotImplementedError(
                f"No adapter registered for Odoo version {config.version}. "
                f"Registered: {list(cls._registry.keys())}"
            )
        return adapter_cls(config)
