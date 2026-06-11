"""Odoo XML-RPC authentication error helpers."""

from __future__ import annotations

import xmlrpc.client


class OdooAuthError(ConnectionError):
    """Raised when Odoo rejects or cannot complete XML-RPC authentication."""


def format_xmlrpc_auth_fault(exc: xmlrpc.client.Fault) -> str:
    """Turn Odoo XML-RPC Fault strings into actionable messages."""
    fault = str(exc)
    lower = fault.lower()

    if "user_id" in lower and "ambiguous" in lower:
        return (
            "Odoo login failed due to a server-side SQL bug while checking API keys "
            '(column "user_id" is ambiguous). This usually comes from custom Odoo addons '
            "(for example jwt_provider) conflicting with res.users.apikeys. "
            "Your Odoo administrator must patch or upgrade those modules on the ERP server. "
            "After that, set ODOO_V14_PASSWORD to a dedicated API key from "
            "Odoo → Settings → Users → your user → API Keys (not your web login password)."
        )

    if "access denied" in lower or "accessdenied" in lower:
        return (
            "Odoo login failed: invalid database name, username, or password/API key. "
            "Check ODOO_V14_URL, ODOO_V14_DB, ODOO_V14_USER, and ODOO_V14_PASSWORD in .env."
        )

    if "2500" in fault and "users" in lower:
        return (
            "Odoo rejected login: the ERP user license limit (2500 users) is exceeded. "
            "Ask your Odoo administrator to archive unused users or clean stale sessions. "
            "As a temporary bridge workaround, set ODOO_V14_UID to the service account uid "
            "in .env.production so the gateway skips authenticate() RPC."
        )

    return (
        "Odoo XML-RPC authentication failed. "
        f"Server response: {fault[:800]}"
    )
