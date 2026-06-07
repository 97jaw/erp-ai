#!/usr/bin/env python3
"""Phase 8 acceptance — telemetry capture and learning engine."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

API_BASE = os.environ.get("OOA_API_BASE", "http://localhost:8000")


async def run_offline() -> int:
    from admin.auth.principal import CurrentUser
    from admin.auth.service import AuthService
    from admin.db.connection import close_admin_db
    from admin.db.repositories.telemetry import TelemetryRepository
    from admin.db.repositories.users import UserRepository
    from gateway.core.intent_analyzer import Intent
    from gateway.core.learning_engine import LearningEngine
    from gateway.core.strategy_fixtures import build_revenue_comparison_strategy
    from gateway.core.telemetry_capture import TelemetryCapture
    from gateway.core.working_memory import WorkingMemory
    from gateway.intelligent_handler import IntelligentQueryHandler
    from tests.core.test_execution_orchestrator import MockToolExecutor
    from tests.core.test_intelligent_handler import FixedIntentAnalyzer, _aggregate_rows, _compare_intent

    failures: list[str] = []

    if not os.environ.get("OOA_DB_URL"):
        print("SKIP DB checks: OOA_DB_URL not set")
        return 1

    service = await AuthService.create()
    repo = TelemetryRepository(service._db)
    users = UserRepository(service._db)
    user_id = None

    print("OFFLINE TEST 1: Handler writes telemetry row")
    try:
        user_id = await users.create_user(
            file_id="phase8-acceptance-user",
            name="Phase 8 Acceptance",
            email="phase8-acceptance@test.com",
        )
        handler = IntelligentQueryHandler(
            intent_analyzer=FixedIntentAnalyzer(_compare_intent()),
            telemetry_capture=TelemetryCapture.from_admin_db(service._db),
        )
        executor = MockToolExecutor(
            responses={
                ("group_and_aggregate", 1): {"rows": [_aggregate_rows("Client A", 1000)]},
                ("group_and_aggregate", 2): {"rows": [_aggregate_rows("Client A", 800)]},
            },
        )
        admin = CurrentUser(
            id=user_id,
            file_id="phase8-acceptance-user",
            name="Phase 8 Acceptance",
            language="en",
            is_super_admin=True,
            is_active=True,
            roles=("super_admin",),
            permissions=frozenset({"data.all_projects"}),
            department_ids=(1,),
        )
        response = await handler.handle(
            "Compare revenue Q1 2026 vs Q1 2025",
            admin,
            adapter=object(),
            session_id="phase8-session",
            strategy_override=build_revenue_comparison_strategy(),
            executor=executor,
        )
        row = await repo.get_by_id(response.interaction_id or "")
        if row is None:
            failures.append("Expected telemetry row after handler call")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Handler telemetry insert failed: {exc}")

    print("OFFLINE TEST 2: LearningEngine daily job")
    try:
        patterns = await LearningEngine(repo).learn_from_recent(hours=24)
        latest = await repo.latest_learning_job()
        if latest is None or latest["status"] != "success":
            failures.append("Learning job did not finish successfully")
        if not patterns.user_specific_patterns and user_id is not None:
            # Accept empty patterns when sample size is tiny, but user row should exist after job if data present
            rows = await repo.list_recent(hours=1, user_id=user_id, limit=5)
            if rows and str(user_id) not in patterns.user_specific_patterns:
                failures.append("LearningEngine did not build user-specific patterns")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Learning job failed: {exc}")

    print("OFFLINE TEST 3: Working memory loads persisted patterns")
    try:
        if user_id is not None:
            await repo.upsert_user_patterns(
                user_id,
                {"preferred_tools": ["group_and_aggregate"], "top_subject_areas": ["financial"]},
            )
            loaded = await repo.get_user_patterns(user_id)
            memory = WorkingMemory()
            LearningEngine.apply_to_working_memory(memory, loaded)
            if memory.user_patterns.get("preferred_tools") != ["group_and_aggregate"]:
                failures.append("Working memory did not load persisted patterns")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Working memory load failed: {exc}")

    print("OFFLINE TEST 4: Out-of-scope still records telemetry")
    try:
        payslip_intent = Intent(
            primary_action="fetch_data",
            subject_area="hr",
            specific_intent="what is my payslip",
            out_of_scope=True,
        )
        handler = IntelligentQueryHandler(
            intent_analyzer=FixedIntentAnalyzer(payslip_intent),
            telemetry_capture=TelemetryCapture.from_admin_db(service._db),
        )
        oos = await handler.handle(
            "what is my payslip",
            admin,
            adapter=object(),
            session_id="phase8-oos",
        )
        oos_row = await repo.get_by_id(oos.interaction_id or "")
        if oos_row is None:
            failures.append("Out-of-scope query did not create telemetry")
    except Exception as exc:  # noqa: BLE001
        failures.append(f"Out-of-scope telemetry failed: {exc}")

    if user_id:
        await users.soft_delete(user_id)
    await close_admin_db()

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1

    print("\nPhase 8 offline acceptance PASSED")
    return 0


async def run_live() -> int:
    import httpx

    failures: list[str] = []
    if not os.environ.get("OOA_DB_URL") or not os.environ.get("JWT_SECRET"):
        print("Live admin telemetry test requires OOA_DB_URL and JWT_SECRET")
        print(f"Hint: ensure {ROOT / '.env'} exists (see .env.example)")
        return 1

    async with httpx.AsyncClient(timeout=60.0) as client:
        login = await client.post(
            f"{API_BASE}/auth/login",
            json={"file_id": os.environ.get("SUPER_ADMIN_FILE_ID", "2721")},
        )
        login.raise_for_status()
        token = login.json().get("access_token")
        headers = {"Authorization": f"Bearer {token}"}

        chat = await client.post(
            f"{API_BASE}/chat/intelligent",
            headers=headers,
            json={"message": "Show revenue by client last quarter", "session_id": "phase8-live"},
        )
        chat.raise_for_status()
        interaction_id = chat.json().get("interaction_id")
        if not interaction_id:
            failures.append("Chat response missing interaction_id")

        telemetry = await client.get(f"{API_BASE}/admin/telemetry", headers=headers)
        telemetry.raise_for_status()
        body = telemetry.json()
        if "interactions" not in body or "summary" not in body:
            failures.append("Admin telemetry route missing expected payload")

        learning = await client.post(
            f"{API_BASE}/admin/telemetry/learning/run",
            headers=headers,
            params={"hours": 24},
        )
        learning.raise_for_status()
        if learning.json().get("status") != "success":
            failures.append("Admin learning run failed")

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1

    print("\nPhase 8 live acceptance PASSED")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 8 telemetry acceptance")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.live:
        return asyncio.run(run_live())
    return asyncio.run(run_offline())


if __name__ == "__main__":
    raise SystemExit(main())
