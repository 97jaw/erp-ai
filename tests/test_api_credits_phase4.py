from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway import api_credits
from gateway.api_credits import (
    check_anthropic,
    check_elevenlabs,
    check_openai,
    publish_credit_check,
    run_all_credit_checks,
)
from gateway.metrics import REGISTRY, api_credits_remaining, api_provider_up


@pytest.fixture(autouse=True)
def _reset_last_results() -> None:
    api_credits._last_results.clear()
    yield
    api_credits._last_results.clear()


def _mock_response(status: int, json_data: dict | None = None, text: str = "") -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


@pytest.mark.asyncio
async def test_check_elevenlabs_subscription() -> None:
    client = AsyncMock()
    client.get.return_value = _mock_response(
        200,
        {
            "character_limit": 100_000,
            "character_count": 25_000,
            "tier": "starter",
        },
    )
    with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "test-key"}, clear=False):
        result = await check_elevenlabs(client)
    assert result.up is True
    assert result.credits_remaining == 75_000
    assert result.unit == "characters"


@pytest.mark.asyncio
async def test_check_anthropic_with_budget() -> None:
    client = AsyncMock()
    client.get.return_value = _mock_response(200, {})
    env = {
        "ANTHROPIC_API_KEY": "sk-test",
        "ANTHROPIC_CREDIT_BUDGET_CENTS": "10000",
    }
    with patch.dict(os.environ, env, clear=False):
        with patch(
            "gateway.api_credits._estimated_anthropic_spend_cents",
            return_value=2500.0,
        ):
            result = await check_anthropic(client)
    assert result.up is True
    assert result.credits_remaining == 7500.0


@pytest.mark.asyncio
async def test_publish_updates_prometheus_gauges() -> None:
    from gateway.api_credits import CreditCheckResult

    publish_credit_check(
        CreditCheckResult(
            provider="openai",
            up=True,
            credits_remaining=1234.0,
            unit="cents",
            checked_at=1.0,
        )
    )
    body = REGISTRY.collect()
    names = {m.name for fam in body for m in fam.samples}
    assert "ooa_api_provider_up" in names
    assert "ooa_api_credits_remaining" in names
    assert api_provider_up.labels(provider="openai")._value.get() == 1.0  # noqa: SLF001
    assert api_credits_remaining.labels(provider="openai")._value.get() == 1234.0  # noqa: SLF001


@pytest.mark.asyncio
async def test_run_all_credit_checks() -> None:
    env = {
        "ANTHROPIC_API_KEY": "sk-ant",
        "OPENAI_API_KEY": "sk-openai",
        "ELEVENLABS_API_KEY": "el-key",
        "ANTHROPIC_CREDIT_BUDGET_CENTS": "5000",
    }

    async def fake_get(url: str, **kwargs):  # type: ignore[no-untyped-def]
        if "elevenlabs.io" in url:
            return _mock_response(
                200, {"character_limit": 1000, "character_count": 100}
            )
        if "credit_grants" in url:
            return _mock_response(200, {"total_available": 12.5})
        return _mock_response(200, {})

    with patch.dict(os.environ, env, clear=False):
        with patch(
            "gateway.api_credits._estimated_anthropic_spend_cents",
            return_value=0.0,
        ):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client.get.side_effect = fake_get
                mock_client_cls.return_value = mock_client
                results = await run_all_credit_checks()

    assert len(results) == 3
    assert all(r.up for r in results)
    assert "anthropic" in api_credits.get_last_credit_checks()
