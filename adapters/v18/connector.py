"""
Odoo 18 Connector
=================
File    : adapters/v18/connector.py
Status  : STUB — Phase 3

Implements BaseOdooAdapter for Odoo 18 using JSON-RPC / REST API.

Protocol  : httpx (async-capable) or requests
Auth      : API Key via Authorization header (Bearer token)
Endpoint  : /web/dataset/call_kw or /api/v2/ (Odoo 18 REST)

Key v18 improvements over v14:
    - Native REST API available alongside JSON-RPC
    - Field naming is more consistent
    - Better error responses (structured JSON errors)
"""

from core.base_adapter import BaseOdooAdapter, AdapterFactory
from core.state import OdooVersion


@AdapterFactory.register(OdooVersion.V18)
class OdooV18Adapter(BaseOdooAdapter):

    @property
    def version(self) -> OdooVersion:
        return OdooVersion.V18

    def authenticate(self) -> int:
        raise NotImplementedError("Phase 3.")

    def search_read(self, model, domain, fields, limit=80, offset=0, order=None):
        raise NotImplementedError("Phase 3.")

    def search_count(self, model, domain):
        raise NotImplementedError("Phase 3.")

    def get_kpi_data(self, request):
        raise NotImplementedError("Phase 3.")

    def create_record(self, model, values):
        raise NotImplementedError("Phase 3.")

    def write_record(self, model, record_ids, values):
        raise NotImplementedError("Phase 3.")

    def execute_action(self, model, method, record_ids, kwargs=None):
        raise NotImplementedError("Phase 3.")

    def _fetch_fields_from_odoo(self, model: str) -> dict:
        raise NotImplementedError("Phase 3.")
