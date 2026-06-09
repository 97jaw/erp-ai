#!/usr/bin/env python3
"""Run Conversation Integrity Sprint (F1–F6) automated checks + print live verify steps."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SPRINT_TEST_PATHS = [
    "tests/test_tool_cache_integrity.py",
    "tests/core/test_topic_shift.py",
    "tests/core/test_search_entity_routing.py",
    "tests/core/test_quality_gate.py",
    "tests/core/test_clarification_validation.py",
    "tests/integration/test_conversation_integrity_sprint.py",
    "tests/integration/test_intelligent_handler.py::test_villa_cost_breakdown_follow_up_reuses_session_project",
    "tests/integration/test_intelligent_handler.py::test_general_maintenance_returns_candidates",
]

LIVE_VERIFY_SEQUENCE = """
Live verification (same session on EC2 after deploy):

1. Villa Maintenance No. 48 expense for this year
   → Villa 48 expense data (or honest no-data if W.O/spend are zero)

2. General maintenance work need expense report
   → ONE entity clarification only (no PDF/Excel question)

3. now General maintenance work
   → Topic shift: search/candidates, NOT Villa 48 data

4. give General maintenance work need expense report
   → Candidates or resolved general-maintenance project — NOT Villa 48

5. General maintenance work - Al Mushrif need expense report
   → Al Mushrif project data — NOT Villa 48

Cache spot-check (same session):
   Villa 48 → Al Mushrif → Hatta Hospital — three distinct project_id values

Deploy:
   git push origin main
   ssh ubuntu@<host> 'cd /opt/ooa && git pull && ./deploy/aws/scripts/deploy-code.sh'
"""


def main() -> int:
    cmd = [sys.executable, "-m", "pytest", *SPRINT_TEST_PATHS, "-q"]
    print("Running Conversation Integrity Sprint test suite...")
    print(" ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    print()
    if result.returncode == 0:
        print("Automated sprint tests: PASSED")
    else:
        print("Automated sprint tests: FAILED")
        return result.returncode

    print(LIVE_VERIFY_SEQUENCE)
    print("Mark F6 live verify complete in docs/CURRENT_PHASE.md after manual checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
