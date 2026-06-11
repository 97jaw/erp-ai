from __future__ import annotations

import logging
import os
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from adapters.v14.connector import OdooV14Adapter

logger = logging.getLogger(__name__)

_adapter: OdooV14Adapter | None = None
_lock = threading.Lock()


def get_shared_odoo_adapter(*, authenticate: bool = True) -> OdooV14Adapter:
    """Return a process-wide Odoo adapter.

    Authentication is lazy: the first RPC calls ``_get_uid()`` which runs
    ``common.authenticate()`` at most once. Set ``ODOO_V14_UID`` to skip the
    authenticate RPC entirely (password still validated on each execute_kw).
    """
    global _adapter
    if _adapter is not None:
        return _adapter

    with _lock:
        if _adapter is not None:
            return _adapter

        from adapters.v14.auth_errors import OdooAuthError
        from adapters.v14.connector import OdooV14Adapter
        from core.base_adapter import OdooConnectionConfig
        from core.state import OdooVersion

        required = ("ODOO_V14_URL", "ODOO_V14_DB", "ODOO_V14_USER", "ODOO_V14_PASSWORD")
        missing = [key for key in required if not os.environ.get(key)]
        if missing:
            raise RuntimeError(f"Missing Odoo env vars: {', '.join(missing)}")

        config = OdooConnectionConfig(
            url=os.environ["ODOO_V14_URL"],
            database=os.environ["ODOO_V14_DB"],
            username=os.environ["ODOO_V14_USER"],
            api_key=os.environ["ODOO_V14_PASSWORD"],
            version=OdooVersion.V14,
        )
        adapter = OdooV14Adapter(config)
        if authenticate:
            eager = os.environ.get("ODOO_V14_EAGER_AUTH", "").lower() in {
                "1",
                "true",
                "yes",
            }
            if eager or os.environ.get("ODOO_V14_UID"):
                try:
                    adapter._get_uid()
                except (OdooAuthError, ConnectionError, TimeoutError, OSError) as exc:
                    logger.error("[OdooAdapterPool] Odoo connection failed: %s", exc)
                    raise
                logger.info(
                    "[OdooAdapterPool] Odoo uid ready — user: %s | uid: %s",
                    config.username,
                    adapter._uid,
                )
        _adapter = adapter
        return _adapter


def reset_shared_odoo_adapter() -> None:
    """Clear cached adapter (tests and reconnect paths)."""
    global _adapter
    with _lock:
        _adapter = None
