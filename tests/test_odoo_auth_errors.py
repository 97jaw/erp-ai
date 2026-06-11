import xmlrpc.client
from unittest.mock import patch

from adapters.v14.auth_errors import OdooAuthError, format_xmlrpc_auth_fault
from adapters.v14.connector import OdooV14Adapter
from tests.test_v14_adapter import make_config


def test_format_ambiguous_user_id_fault():
    fault = xmlrpc.client.Fault(
        1,
        'psycopg2.ProgrammingError: column reference "user_id" is ambiguous',
    )
    message = format_xmlrpc_auth_fault(fault)
    assert "ambiguous" in message.lower()
    assert "jwt_provider" in message or "api keys" in message.lower()


def test_user_limit_fault_message():
    exc = xmlrpc.client.Fault(
        2,
        "Maximimum allowed records in table \"Users\" is 2500, "
        "while after this update you would have 2547",
    )
    message = format_xmlrpc_auth_fault(exc)
    assert "2500" in message
    assert "ODOO_V14_UID" in message


def test_authenticate_fault_raises_odoo_auth_error():
    with patch("xmlrpc.client.ServerProxy") as mock_proxy:
        mock_proxy.return_value.authenticate.side_effect = xmlrpc.client.Fault(
            1,
            'column reference "user_id" is ambiguous',
        )
        adapter = OdooV14Adapter(make_config())
        adapter._common = mock_proxy.return_value
        try:
            adapter.authenticate()
            assert False, "expected OdooAuthError"
        except OdooAuthError as exc:
            assert "ambiguous" in str(exc).lower()
