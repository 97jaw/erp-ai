"""
External API credit / health checks (MONITORING_PLAN Phase 4).
Periodically updates ooa_api_credits_remaining and ooa_api_provider_up gauges.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx

from gateway.metrics import ai_cost_cents, api_credits_remaining, api_provider_up

logger = logging.getLogger(__name__)

ANTHROPIC_VERSION = "2023-06-01"
UNKNOWN_CREDITS = -1.0

_last_results: dict[str, dict[str, Any]] = {}
_scheduler_task: asyncio.Task[None] | None = None


@dataclass
class CreditCheckResult:
    provider: str
    up: bool
    credits_remaining: float
    unit: str
    detail: str = ""
    checked_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def get_last_credit_checks() -> dict[str, dict[str, Any]]:
    return dict(_last_results)


def _estimated_anthropic_spend_cents() -> float:
    try:
        metric = ai_cost_cents.labels(provider="anthropic", service="claude")
        return float(metric._value.get())  # noqa: SLF001
    except Exception:
        return 0.0


async def check_anthropic(client: httpx.AsyncClient) -> CreditCheckResult:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return CreditCheckResult(
            provider="anthropic",
            up=False,
            credits_remaining=UNKNOWN_CREDITS,
            unit="cents",
            detail="ANTHROPIC_API_KEY not set",
            checked_at=time.time(),
        )

    up = False
    detail = ""
    credits = UNKNOWN_CREDITS

    try:
        resp = await client.get(
            "https://api.anthropic.com/v1/models",
            headers={
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
        )
        up = resp.status_code == 200
        if not up:
            detail = f"models HTTP {resp.status_code}"
    except Exception as exc:
        detail = str(exc)[:200]

    budget_cents = float(os.environ.get("ANTHROPIC_CREDIT_BUDGET_CENTS", "0") or 0)
    if budget_cents > 0:
        spent = _estimated_anthropic_spend_cents()
        credits = max(0.0, budget_cents - spent)
        detail = f"estimated from budget ({budget_cents:.0f}c) minus gateway spend ({spent:.0f}c)"
    elif up:
        detail = detail or "API reachable; set ANTHROPIC_CREDIT_BUDGET_CENTS for balance alerts"

    return CreditCheckResult(
        provider="anthropic",
        up=up,
        credits_remaining=credits,
        unit="cents",
        detail=detail,
        checked_at=time.time(),
    )


async def check_openai(client: httpx.AsyncClient) -> CreditCheckResult:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        return CreditCheckResult(
            provider="openai",
            up=False,
            credits_remaining=UNKNOWN_CREDITS,
            unit="cents",
            detail="OPENAI_API_KEY not set",
            checked_at=time.time(),
        )

    up = False
    credits = UNKNOWN_CREDITS
    detail = ""

    try:
        resp = await client.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        up = resp.status_code == 200
        if not up:
            detail = f"models HTTP {resp.status_code}"
    except Exception as exc:
        detail = str(exc)[:200]

    try:
        resp = await client.get(
            "https://api.openai.com/dashboard/billing/credit_grants",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        if resp.status_code == 200:
            data = resp.json()
            available = data.get("total_available")
            if available is not None:
                credits = float(available) * 100.0
                detail = "billing credit_grants"
        elif not detail:
            detail = f"billing HTTP {resp.status_code}"
    except Exception as exc:
        if not detail:
            detail = f"billing: {exc}"[:200]

    return CreditCheckResult(
        provider="openai",
        up=up,
        credits_remaining=credits,
        unit="cents",
        detail=detail,
        checked_at=time.time(),
    )


async def check_elevenlabs(client: httpx.AsyncClient) -> CreditCheckResult:
    api_key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not api_key:
        return CreditCheckResult(
            provider="elevenlabs",
            up=False,
            credits_remaining=UNKNOWN_CREDITS,
            unit="characters",
            detail="ELEVENLABS_API_KEY not set",
            checked_at=time.time(),
        )

    up = False
    credits = UNKNOWN_CREDITS
    detail = ""

    try:
        resp = await client.get(
            "https://api.elevenlabs.io/v1/user/subscription",
            headers={"xi-api-key": api_key},
        )
        up = resp.status_code == 200
        if resp.status_code == 200:
            data = resp.json()
            limit = int(data.get("character_limit") or 0)
            used = int(data.get("character_count") or 0)
            credits = float(max(0, limit - used))
            detail = f"subscription tier={data.get('tier', '?')}"
        else:
            detail = f"subscription HTTP {resp.status_code}"
    except Exception as exc:
        detail = str(exc)[:200]

    return CreditCheckResult(
        provider="elevenlabs",
        up=up,
        credits_remaining=credits,
        unit="characters",
        detail=detail,
        checked_at=time.time(),
    )


def publish_credit_check(result: CreditCheckResult) -> None:
    api_provider_up.labels(provider=result.provider).set(1 if result.up else 0)
    if result.credits_remaining >= 0:
        api_credits_remaining.labels(provider=result.provider).set(result.credits_remaining)
    _last_results[result.provider] = result.to_dict()


async def run_all_credit_checks() -> list[CreditCheckResult]:
    timeout = float(os.environ.get("OOA_CREDIT_CHECK_TIMEOUT", "15"))
    results: list[CreditCheckResult] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        for checker in (check_anthropic, check_openai, check_elevenlabs):
            try:
                result = await checker(client)
            except Exception as exc:
                provider = checker.__name__.replace("check_", "")
                result = CreditCheckResult(
                    provider=provider,
                    up=False,
                    credits_remaining=UNKNOWN_CREDITS,
                    unit="unknown",
                    detail=str(exc)[:200],
                    checked_at=time.time(),
                )
            publish_credit_check(result)
            results.append(result)
            logger.info(
                "API credit check",
                extra={
                    "event": "api_credit_check",
                    "category": "infra",
                    "provider": result.provider,
                    "up": result.up,
                    "credits_remaining": result.credits_remaining,
                    "unit": result.unit,
                    "detail": result.detail,
                },
            )

    return results


async def _credit_check_loop() -> None:
    interval_min = max(1, int(os.environ.get("OOA_CREDIT_CHECK_MINUTES", "15")))
    initial_delay = float(os.environ.get("OOA_CREDIT_CHECK_INITIAL_DELAY", "10"))
    await asyncio.sleep(initial_delay)

    while True:
        try:
            await run_all_credit_checks()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Credit check loop failed")
        await asyncio.sleep(interval_min * 60)


def start_credit_check_scheduler() -> asyncio.Task[None] | None:
    """Start background credit checks if enabled (default on)."""
    global _scheduler_task

    enabled = os.environ.get("OOA_CREDIT_CHECKS_ENABLED", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    if not enabled:
        logger.info("API credit checks disabled (OOA_CREDIT_CHECKS_ENABLED=false)")
        return None

    if _scheduler_task and not _scheduler_task.done():
        return _scheduler_task

    _scheduler_task = asyncio.create_task(
        _credit_check_loop(),
        name="ooa-credit-checks",
    )
    return _scheduler_task


def stop_credit_check_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
    _scheduler_task = None
