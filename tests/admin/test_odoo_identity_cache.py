from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import xmlrpc.client

from admin.auth.odoo_identity_cache import (
    has_cached_odoo_identity,
    odoo_identity_cache_fresh,
)


def test_odoo_identity_cache_fresh_within_ttl() -> None:
    user = {
        "odoo_user_id": 4291,
        "odoo_verified_at": datetime.now(timezone.utc) - timedelta(hours=2),
    }
    assert odoo_identity_cache_fresh(user, ttl_hours=24) is True


def test_odoo_identity_cache_stale_after_ttl() -> None:
    user = {
        "odoo_user_id": 4291,
        "odoo_verified_at": datetime.now(timezone.utc) - timedelta(hours=25),
    }
    assert odoo_identity_cache_fresh(user, ttl_hours=24) is False


def test_odoo_identity_cache_ttl_zero_always_stale() -> None:
    user = {
        "odoo_user_id": 4291,
        "odoo_verified_at": datetime.now(timezone.utc),
    }
    assert odoo_identity_cache_fresh(user, ttl_hours=0) is False


def test_has_cached_odoo_identity() -> None:
    assert has_cached_odoo_identity({"odoo_user_id": 1, "odoo_verified_at": datetime.now(timezone.utc)})
    assert not has_cached_odoo_identity({"odoo_user_id": 1})
    assert not has_cached_odoo_identity({"odoo_verified_at": datetime.now(timezone.utc)})


@pytest.mark.asyncio
async def test_sync_odoo_user_link_skips_when_cache_fresh(monkeypatch) -> None:
    from admin.auth import service as service_module
    from admin.auth.service import AuthService

    monkeypatch.setattr(service_module, "ODOO_SYNC_TTL_HOURS", 24)

    verify_calls: list[str] = []

    async def fake_verify(file_id: str):
        verify_calls.append(file_id)
        return None

    monkeypatch.setattr(
        "admin.auth.odoo_verify.verify_file_id_with_odoo",
        fake_verify,
    )
    monkeypatch.setattr("admin.auth.odoo_verify._odoo_configured", lambda: True)

    users = MagicMock()
    users.set_odoo_identity = AsyncMock()

    svc = AuthService.__new__(AuthService)
    svc._users = users
    user = {
        "id": 1,
        "file_id": "2721",
        "odoo_user_id": 4291,
        "odoo_verified_at": datetime.now(timezone.utc) - timedelta(hours=1),
    }

    await svc._sync_odoo_user_link(user)

    assert verify_calls == []
    users.set_odoo_identity.assert_not_called()


@pytest.mark.asyncio
async def test_sync_odoo_user_link_refreshes_stale_cache(monkeypatch) -> None:
    from admin.auth import service as service_module
    from admin.auth.service import AuthService

    monkeypatch.setattr(service_module, "ODOO_SYNC_TTL_HOURS", 24)

    async def fake_verify(file_id: str):
        return {
            "file_id": file_id,
            "odoo_user_id": 4291,
            "employee_id": 100,
            "name": "Test User",
            "email": "test@example.com",
            "language": "en",
        }

    monkeypatch.setattr(
        "admin.auth.odoo_verify.verify_file_id_with_odoo",
        fake_verify,
    )
    monkeypatch.setattr("admin.auth.odoo_verify._odoo_configured", lambda: True)

    users = MagicMock()
    users.set_odoo_identity = AsyncMock()

    svc = AuthService.__new__(AuthService)
    svc._users = users
    user = {
        "id": 1,
        "file_id": "2721",
        "odoo_user_id": 4291,
        "odoo_verified_at": datetime.now(timezone.utc) - timedelta(hours=30),
    }

    await svc._sync_odoo_user_link(user)

    users.set_odoo_identity.assert_called_once()
    assert user["odoo_user_id"] == 4291


@pytest.mark.asyncio
async def test_sync_odoo_user_link_uses_cache_when_verify_fails(monkeypatch) -> None:
    from admin.auth import service as service_module
    from admin.auth.service import AuthService

    monkeypatch.setattr(service_module, "ODOO_SYNC_TTL_HOURS", 0)

    async def fake_verify(_file_id: str):
        return None

    monkeypatch.setattr(
        "admin.auth.odoo_verify.verify_file_id_with_odoo",
        fake_verify,
    )
    monkeypatch.setattr("admin.auth.odoo_verify._odoo_configured", lambda: True)

    users = MagicMock()
    users.set_odoo_identity = AsyncMock()

    svc = AuthService.__new__(AuthService)
    svc._users = users
    user = {
        "id": 1,
        "file_id": "2721",
        "odoo_user_id": 4291,
        "odoo_verified_at": datetime.now(timezone.utc) - timedelta(days=2),
    }

    await svc._sync_odoo_user_link(user)

    users.set_odoo_identity.assert_not_called()


def test_shared_odoo_adapter_singleton(monkeypatch) -> None:
    from gateway import odoo_adapter_pool

    odoo_adapter_pool.reset_shared_odoo_adapter()

    created: list[MagicMock] = []

    def fake_adapter_cls(config):  # noqa: ANN001
        adapter = MagicMock()
        adapter._uid = 7
        adapter.authenticate = MagicMock(return_value=7)
        created.append(adapter)
        return adapter

    monkeypatch.setenv("ODOO_V14_URL", "https://erp.example.com")
    monkeypatch.setenv("ODOO_V14_DB", "testdb")
    monkeypatch.setenv("ODOO_V14_USER", "dev")
    monkeypatch.setenv("ODOO_V14_PASSWORD", "secret")

    with patch("adapters.v14.connector.OdooV14Adapter", fake_adapter_cls):
        first = odoo_adapter_pool.get_shared_odoo_adapter()
        second = odoo_adapter_pool.get_shared_odoo_adapter()

    assert first is second
    assert len(created) == 1
    odoo_adapter_pool.reset_shared_odoo_adapter()


def test_execute_retries_once_after_protocol_error() -> None:
    from adapters.v14.connector import OdooV14Adapter
    from core.base_adapter import OdooConnectionConfig
    from core.state import OdooVersion

    config = OdooConnectionConfig(
        url="https://erp.example.com",
        database="testdb",
        username="dev",
        api_key="secret",
        version=OdooVersion.V14,
    )
    adapter = OdooV14Adapter(config)
    adapter._uid = 99
    adapter.authenticate = MagicMock(return_value=99)

    adapter._object = MagicMock()
    adapter._object.execute_kw = MagicMock(
        side_effect=[
            xmlrpc.client.ProtocolError("https://erp.example.com/xmlrpc/2/object", 502, "Bad Gateway", {}),
            {"ok": True},
        ]
    )

    result = adapter._execute("res.partner", "search_read", [[]])

    assert result == {"ok": True}
    assert adapter._object.execute_kw.call_count == 2
    adapter.authenticate.assert_not_called()
