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
import re
import time
import xmlrpc.client
from typing import Any, Optional

from core.base_adapter import (
    AdapterFactory,
    BaseOdooAdapter,
    KPIRequest,
    KPIResponse,
    OdooConnectionConfig,
)
from core.entity_normalization import normalize_client_query
from core.state import OdooVersion
from adapters.v14.accounting_connector import AccountingConnector
logger = logging.getLogger(__name__)


def _xmlrpc_transport_for_url(base_url: str) -> xmlrpc.client.Transport:
    """
    Build an XML-RPC transport with a socket timeout.

    HTTPS URLs must use SafeTransport; passing plain Transport breaks TLS and
    causes connection timeouts against hosts like https://erp.elrace.com.
    """
    timeout = float(os.environ.get("ODOO_XMLRPC_TIMEOUT", "600"))
    if base_url.lower().startswith("https://"):

        class _TimeoutSafeTransport(xmlrpc.client.SafeTransport):
            def __init__(self) -> None:
                self._timeout = timeout
                super().__init__()

            def make_connection(self, host):  # noqa: ANN001
                conn = super().make_connection(host)
                conn.timeout = self._timeout
                return conn

        return _TimeoutSafeTransport()

    class _TimeoutTransport(xmlrpc.client.Transport):
        def __init__(self) -> None:
            self._timeout = timeout
            super().__init__()

        def make_connection(self, host):  # noqa: ANN001
            conn = super().make_connection(host)
            conn.timeout = self._timeout
            return conn

    return _TimeoutTransport()


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
    PROJECT_CACHE_TTL_SECONDS = 900
    TRANSLATOR_MODEL = os.environ.get(
        "ANTHROPIC_TRANSLATOR_MODEL",
        "claude-3-5-haiku-20241022",
    )
    _project_cache: dict[str, tuple[float, int | None, list | None]] = {}
    _translator_client: anthropic.Anthropic | None = None

    def __init__(self, config: OdooConnectionConfig) -> None:
        super().__init__(config)
        self._accounting: AccountingConnector | None = None
        base_url = config.url.rstrip("/")
        rpc_transport = _xmlrpc_transport_for_url(base_url)
        self._common = xmlrpc.client.ServerProxy(
            f"{base_url}/xmlrpc/2/common",
            transport=rpc_transport,
            allow_none=True,
        )
        self._object = xmlrpc.client.ServerProxy(
            f"{base_url}/xmlrpc/2/object",
            transport=rpc_transport,
            allow_none=True,
        )
        self._uid: Optional[int] = None
        self._model_fields_cache: dict[str, dict[str, Any]] = {}

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

        except (TimeoutError, OSError) as exc:
            raise ConnectionError(
                f"Cannot reach Odoo at {self.config.url!r} ({exc}). "
                "Check ODOO_V14_URL (https:// needs TLS), VPN/network, and "
                "that the server is running."
            ) from exc
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

    def read_group(
        self,
        model   : str,
        domain  : list[tuple],
        fields  : list[str],
        groupby : list[str],
        limit   : int = 80,
        offset  : int = 0,
        order   : str | None = None,
        lazy    : bool = True,
    ) -> list[dict[str, Any]]:
        kwargs: dict[str, Any] = {
            "fields" : fields,
            "groupby": groupby,
            "limit"  : limit,
            "offset" : offset,
            "lazy"   : lazy,
        }
        if order:
            kwargs["orderby"] = order

        logger.debug(
            "[V14Adapter] read_group — model: %s | domain: %s | groupby: %s",
            model, domain, groupby,
        )
        return self._execute(model, "read_group", [domain], kwargs)

    def search_count(self, model: str, domain: list[tuple]) -> int:
        """Returns total record count matching domain."""
        return self._execute(model, "search_count", [domain])

    def _get_model_fields(self, model: str) -> dict[str, dict[str, Any]]:
        cached = self._model_fields_cache.get(model)
        if cached is not None:
            return cached

        try:
            fields = self._execute(
                model,
                "fields_get",
                [],
                {"attributes": ["type", "relation", "string"]},
            )
        except Exception as exc:
            logger.warning("[V14Adapter] fields_get failed for %s: %s", model, exc)
            fields = {}

        self._model_fields_cache[model] = fields
        return fields

    def _purchase_order_client_field_names(self) -> list[str]:
        configured = os.environ.get(
            "ODOO_PO_CLIENT_FIELDS",
            "client,client_id,customer_id,x_client_id",
        )
        candidates = [name.strip() for name in configured.split(",") if name.strip()]
        available = self._get_model_fields("purchase.order")
        if not available:
            return candidates

        discovered: list[str] = []
        for name, meta in available.items():
            if meta.get("type") != "many2one":
                continue
            if meta.get("relation") not in ("res.partner", "res.partner.id"):
                continue
            if name == "partner_id":
                continue

            label = (meta.get("string") or "").lower()
            lowered = name.lower()
            if any(token in lowered for token in ("client", "customer")) or any(
                token in label for token in ("client", "customer")
            ):
                discovered.append(name)

        ordered: list[str] = []
        for name in candidates + discovered:
            if name in available and available[name].get("type") == "many2one":
                if name not in ordered:
                    ordered.append(name)
        return ordered

    def _normalize_partner_name(self, name: str) -> str:
        text = re.sub(r"\s+", " ", name or "").strip().lower()
        return re.sub(r"[.,'\"-]", "", text)

    def _score_partner_match(self, partner_name: str, query: str) -> int:
        partner = self._normalize_partner_name(partner_name)
        needle = self._normalize_partner_name(query)
        if not needle:
            return 0
        if partner == needle:
            return 100
        if needle in partner or partner in needle:
            return 90

        query_tokens = set(needle.split())
        partner_tokens = set(partner.split())
        if not query_tokens:
            return 0
        overlap = len(query_tokens & partner_tokens) / len(query_tokens)
        return int(overlap * 80)

    def _expand_partner_ids(self, partner_ids: list[int]) -> list[int]:
        if not partner_ids:
            return []

        expanded: set[int] = {int(partner_id) for partner_id in partner_ids}
        partners = self.search_read(
            model  = "res.partner",
            domain = [["id", "in", list(expanded)]],
            fields = ["commercial_partner_id", "parent_id"],
            limit  = len(expanded) + 10,
        )
        for partner in partners:
            for field_name in ("commercial_partner_id", "parent_id"):
                related = partner.get(field_name)
                if isinstance(related, (list, tuple)) and related:
                    expanded.add(int(related[0]))
        return list(expanded)

    def _resolve_client_partners(self, client_name: str) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        seen_ids: set[int] = set()

        def add_partner(partner: dict[str, Any]) -> None:
            partner_id = int(partner["id"])
            if partner_id in seen_ids:
                return
            seen_ids.add(partner_id)
            candidates.append(partner)

        for partner in self.search_read(
            model  = "res.partner",
            domain = [["name", "ilike", client_name]],
            fields = ["id", "name", "is_company"],
            limit  = 20,
            order  = "name asc",
        ):
            add_partner(partner)

        if not candidates:
            for keyword in self._extract_search_keywords(client_name)[:6]:
                for partner in self.search_read(
                    model  = "res.partner",
                    domain = [["name", "ilike", keyword]],
                    fields = ["id", "name", "is_company"],
                    limit  = 20,
                    order  = "name asc",
                ):
                    add_partner(partner)

        scored = [
            (
                self._score_partner_match(partner.get("name", ""), client_name),
                partner,
            )
            for partner in candidates
        ]
        scored.sort(key=lambda item: (-item[0], item[1].get("name", "")))
        if not scored:
            return []

        top_score = scored[0][0]
        if top_score >= 90:
            return [partner for score, partner in scored if score >= 90][:10]

        threshold = max(55, top_score - 10)
        return [partner for score, partner in scored if score >= threshold][:10]

    def _build_purchase_order_domain(
        self,
        *,
        partner_ids     : list[int],
        project_ids     : list[int],
        client_fields   : list[str],
        excluded_states : list[str],
        client_name     : str | None = None,
    ) -> list[Any]:
        clauses: list[list[Any]] = []
        for field_name in client_fields:
            if partner_ids:
                clauses.append([field_name, "in", partner_ids])
            elif client_name:
                clauses.append([field_name, "ilike", client_name])
        if project_ids:
            clauses.append(["project_id", "in", project_ids])
        if not clauses:
            return []

        if len(clauses) == 1:
            return ["&", ["state", "not in", excluded_states], clauses[0]]

        or_domain = ["|"] * (len(clauses) - 1) + clauses
        return ["&", ["state", "not in", excluded_states], *or_domain]

    def _purchase_order_read_fields(self, client_fields: list[str]) -> list[str]:
        read_fields = [
            "name",
            "partner_id",
            "date_order",
            "amount_total",
            "state",
            "project_id",
            "create_date",
        ]
        for field_name in client_fields:
            if field_name not in read_fields:
                read_fields.append(field_name)
        for field_name in ("date_approve", "confirmation_date", "write_date"):
            if field_name in self._get_model_fields("purchase.order"):
                read_fields.append(field_name)
        return read_fields

    def _purchase_order_sort_order(self) -> str:
        available = self._get_model_fields("purchase.order")
        order_parts: list[str] = []
        for field_name in ("date_approve", "date_order", "write_date", "id"):
            if field_name in available or field_name == "id":
                order_parts.append(f"{field_name} desc")
        return ", ".join(order_parts) or "id desc"

    def _present_purchase_orders(self, orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
        client_fields = self._purchase_order_client_field_names()
        rows: list[dict[str, Any]] = []

        for order in orders:
            client_name = None
            for field_name in client_fields:
                related = order.get(field_name)
                if isinstance(related, (list, tuple)) and len(related) > 1:
                    client_name = related[1]
                    break

            supplier = order.get("partner_id")
            supplier_name = (
                supplier[1]
                if isinstance(supplier, (list, tuple)) and len(supplier) > 1
                else supplier
            )
            project = order.get("project_id")
            project_name = (
                project[1]
                if isinstance(project, (list, tuple)) and len(project) > 1
                else project
            )

            rows.append({
                "id"           : order.get("id"),
                "po_number"    : order.get("name"),
                "supplier_name": supplier_name,
                "client_name"  : client_name,
                "project_name" : project_name,
                "date_order"   : order.get("date_order"),
                "amount_total" : order.get("amount_total"),
                "state"        : order.get("state"),
            })

        return rows

    def _purchase_order_excluded_states(self) -> list[str]:
        excluded = ["cancel", "cancelled"]
        extra = os.environ.get("ODOO_PO_STATE_EXCLUDE", "")
        excluded.extend(name.strip() for name in extra.split(",") if name.strip())
        return excluded

    def _dedupe_purchase_orders(
        self,
        batches: list[list[dict[str, Any]]],
        limit  : int,
    ) -> list[dict[str, Any]]:
        orders_by_id: dict[int, dict[str, Any]] = {}
        for batch in batches:
            for order in batch:
                orders_by_id[int(order["id"])] = order

        def sort_key(order: dict[str, Any]) -> tuple[Any, int]:
            return (
                order.get("date_approve")
                or order.get("date_order")
                or order.get("write_date")
                or order.get("create_date")
                or "",
                int(order.get("id") or 0),
            )

        orders = sorted(orders_by_id.values(), key=sort_key, reverse=True)
        return orders[:limit]

    def _search_purchase_orders(
        self,
        *,
        partner_ids: list[int],
        project_ids: list[int],
        client_name: str | None = None,
        limit      : int,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        client_fields = self._purchase_order_client_field_names()
        if (
            not partner_ids
            and not project_ids
            and not (client_name and client_fields)
        ):
            return [], []

        read_fields = self._purchase_order_read_fields(client_fields)
        excluded_states = self._purchase_order_excluded_states()
        strategies: list[str] = []
        sort_order = self._purchase_order_sort_order()
        domain = self._build_purchase_order_domain(
            partner_ids     = partner_ids,
            project_ids     = project_ids,
            client_fields   = client_fields,
            excluded_states = excluded_states,
            client_name     = client_name,
        )
        if not domain:
            return [], []

        try:
            orders = self.search_read(
                model  = "purchase.order",
                domain = domain,
                fields = read_fields,
                limit  = limit,
                order  = sort_order,
            )
            if partner_ids and client_fields:
                strategies.extend(
                    f"purchase.order.{field_name}" for field_name in client_fields
                )
            if client_name and client_fields:
                strategies.extend(
                    f"purchase.order.{field_name}.ilike"
                    for field_name in client_fields
                )
            if project_ids:
                strategies.append("purchase.order.project_id")
            return self._dedupe_purchase_orders([orders], limit), strategies
        except Exception as exc:
            logger.warning(
                "[V14Adapter] Combined purchase order search failed: %s",
                exc,
            )

        batches: list[list[dict[str, Any]]] = []
        for field_name in client_fields:
            field_clauses: list[list[Any]] = []
            if partner_ids:
                field_clauses.append([field_name, "in", partner_ids])
            elif client_name:
                field_clauses.append([field_name, "ilike", client_name])
            if not field_clauses:
                continue

            if len(field_clauses) == 1:
                scoped_domain = field_clauses[0]
            else:
                scoped_domain = ["|", *field_clauses]

            field_domain = ["&", ["state", "not in", excluded_states], scoped_domain]
            try:
                batches.append(
                    self.search_read(
                        model  = "purchase.order",
                        domain = field_domain,
                        fields = read_fields,
                        limit  = limit,
                        order  = sort_order,
                    )
                )
                strategies.append(f"purchase.order.{field_name}")
            except Exception as field_exc:
                logger.warning(
                    "[V14Adapter] Purchase order search via %s failed: %s",
                    field_name,
                    field_exc,
                )

        if project_ids:
            project_domain = [
                ["project_id", "in", project_ids],
                ["state", "not in", excluded_states],
            ]
            try:
                batches.append(
                    self.search_read(
                        model  = "purchase.order",
                        domain = project_domain,
                        fields = read_fields,
                        limit  = limit,
                        order  = sort_order,
                    )
                )
                strategies.append("purchase.order.project_id")
            except Exception as project_exc:
                logger.warning(
                    "[V14Adapter] Purchase order search via project_id failed: %s",
                    project_exc,
                )

        return self._dedupe_purchase_orders(batches, limit), strategies

    def get_purchase_orders(
        self,
        *,
        client_name : str | None = None,
        partner_ids : list[int] | None = None,
        project_name: str | None = None,
        project_id  : int | None = None,
        limit       : int = 10,
    ) -> dict[str, Any]:
        """Return recent purchase orders for a client or project."""
        limit = min(max(int(limit or 10), 1), 50)
        partners: list[dict[str, Any]] = []
        projects: list[dict[str, Any]] = []
        project_ids: list[int] = []
        resolved_partner_ids: list[int] = [
            int(partner_id) for partner_id in (partner_ids or [])
        ]

        if project_id:
            project_ids = [int(project_id)]
        elif project_name:
            resolved_id, candidates = self._resolve_project_id(
                {"project_name": project_name}
            )
            if resolved_id:
                project_ids = [resolved_id]
            elif candidates:
                projects = candidates
                project_ids = [int(item["id"]) for item in candidates]
        elif client_name:
            for variant in normalize_client_query(client_name):
                partners.extend(self._resolve_client_partners(variant))
            deduped: dict[int, dict[str, Any]] = {}
            for partner in partners:
                deduped[int(partner["id"])] = partner
            partners = list(deduped.values())
            resolved_partner_ids.extend(int(partner["id"]) for partner in partners)

        resolved_partner_ids = list(dict.fromkeys(resolved_partner_ids))
        if resolved_partner_ids and not partners:
            partners = self.search_read(
                model  = "res.partner",
                domain = [["id", "in", resolved_partner_ids]],
                fields = ["id", "name", "is_company"],
                limit  = len(resolved_partner_ids),
                order  = "name asc",
            )

        if resolved_partner_ids and not project_ids:
            projects = self.search_read(
                model  = "project.project",
                domain = [["partner_id", "in", resolved_partner_ids]],
                fields = ["id", "name", "partner_id", "wo_ref_no", "active"],
                limit  = 50,
                order  = "name asc",
            )
            project_ids = [int(project["id"]) for project in projects]

        if not resolved_partner_ids:
            for project in projects:
                partner = project.get("partner_id")
                if isinstance(partner, (list, tuple)) and partner:
                    resolved_partner_ids.append(int(partner[0]))

        resolved_partner_ids = self._expand_partner_ids(
            list(dict.fromkeys(resolved_partner_ids))
        )
        project_ids = list(dict.fromkeys(project_ids))
        client_fields = self._purchase_order_client_field_names()

        if not resolved_partner_ids and not project_ids and not client_name:
            return {
                "orders"         : [],
                "projects"       : projects,
                "partners"       : partners,
                "matched_clients": [],
                "count"          : 0,
                "limit"          : limit,
                "client_fields"  : client_fields,
                "note"           : "No matching client or project was found for the purchase order search.",
            }

        orders, strategies = self._search_purchase_orders(
            partner_ids = resolved_partner_ids,
            project_ids = project_ids,
            client_name = client_name if not resolved_partner_ids else None,
            limit       = limit,
        )

        note = None
        if not orders:
            note = (
                "No purchase orders matched the client field or linked project. "
                "On purchase.order, partner_id is the supplier and the client is stored "
                "separately from the vendor."
            )

        return {
            "orders"         : self._present_purchase_orders(orders),
            "projects"       : projects,
            "partners"       : partners,
            "matched_clients": [
                {"id": partner["id"], "name": partner.get("name")}
                for partner in partners
            ],
            "partner_ids"    : resolved_partner_ids,
            "project_ids"    : project_ids,
            "client_fields"  : client_fields,
            "strategies"     : strategies,
            "count"          : len(orders),
            "limit"          : limit,
            "note"           : note,
        }

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

        cache_key = project_name.strip().lower()
        cached = self._project_cache.get(cache_key)
        if cached and (time.monotonic() - cached[0]) < self.PROJECT_CACHE_TTL_SECONDS:
            return cached[1], cached[2]

        def remember(result: tuple[int | None, list | None]) -> tuple[int | None, list | None]:
            self._project_cache[cache_key] = (time.monotonic(), result[0], result[1])
            return result

        logger.info("[V14Adapter] Resolving project: '%s'", project_name)

        has_arabic = any("\u0600" <= char <= "\u06FF" for char in project_name)
        if has_arabic:
            for keyword in self._extract_search_keywords(project_name):
                candidates = self._search_projects_by_name(keyword, field="name")
                if len(candidates) == 1:
                    return remember((candidates[0]["id"], None))
                if len(candidates) > 1:
                    return remember((None, candidates))

        # --- Attempt 1: English name ilike ---
        candidates = self._search_projects_by_name(project_name, field="name")
        if len(candidates) == 1:
            return remember((candidates[0]["id"], None))
        if len(candidates) > 1:
            return remember((None, candidates))

        # --- Attempt 2: Arabic name field ilike ---
        candidates = self._search_projects_by_name(
            project_name, field="project_name_arabic"
        )
        if len(candidates) == 1:
            return remember((candidates[0]["id"], None))
        if len(candidates) > 1:
            return remember((None, candidates))

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
                return remember((candidates[0]["id"], None))
            if len(candidates) > 1:
                return remember((None, candidates))

            # Try keyword by keyword
            for keyword in translated.split():
                if len(keyword) < 3:
                    continue
                candidates = self._search_projects_by_name(keyword, field="name")
                if len(candidates) == 1:
                    return remember((candidates[0]["id"], None))
                if len(candidates) > 1:
                    return remember((None, candidates))

        # --- Zero results ---
        logger.warning(
            "[V14Adapter] Could not resolve project: '%s'", project_name
        )
        return remember((None, []))


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
            if self._translator_client is None:
                self._translator_client = anthropic.Anthropic(
                    api_key=os.environ.get("ANTHROPIC_API_KEY")
                )
            message = self._translator_client.messages.create(
                model      = self.TRANSLATOR_MODEL,
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