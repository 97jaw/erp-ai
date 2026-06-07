#!/usr/bin/env python3
"""Run the daily learning job (Phase 8)."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

async def main() -> int:
    parser = argparse.ArgumentParser(description="Run LearningEngine daily job")
    parser.add_argument("--hours", type=int, default=24, help="Lookback window in hours")
    args = parser.parse_args()

    from admin.db.connection import close_admin_db, init_admin_db
    from gateway.core.learning_engine import run_daily_learning_job

    db = await init_admin_db()
    try:
        patterns = await run_daily_learning_job(hours=args.hours)
        print("Learning job completed.")
        print("Users updated:", len(patterns.user_specific_patterns))
        print("Common failures:", patterns.common_failures)
        print("Quality drift:", patterns.quality_drift)
        return 0
    finally:
        await close_admin_db()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
