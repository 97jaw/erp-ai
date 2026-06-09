# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** `docs/CONVERSATION_INTELLIGENCE_SPRINT.md` — Conversation Intelligence Sprint (6 fixes)

**Status:** Day 1 in progress — FIX 4 ✅ live verified; FIX 5 code + tests ✅, live verify pending

---

## 📍 SPRINT PROGRESS

| Fix | Description | Code | Tests | Live verify |
|-----|-------------|------|-------|-------------|
| FIX 4 | Deploy A1 breakdown unwrap | ✅ `fd4b2e6` | ✅ | ✅ Salary / AED 11,053 on project 15157 |
| FIX 5 | Number sanity (W.O=0) | ✅ | ✅ 4 tests | ⏳ |
| FIX 1 | Sticky context | — | — | — |
| FIX 2 | Follow-up routing | — | — | — |
| FIX 3 | Skip confirmed | — | — | — |
| FIX 6 | Non-financial honesty | — | — | — |
| Final | 7-turn acceptance test | — | — | — |

**FIX 4 live result (2026-06-09):** Breakdown for Villa Maintenance No. 34 (15157) returns Salary → Labor → 55002 LABER WAGES, AED 11,053.15. Chat follow-up "share the expense breakdown" shows GL breakdown (not "No data found").

**FIX 5 scope:** `spend_status` / `status_label` on summary tool; W.O=0 → no spend %; `no_contradictions` quality gate; honest narration.

**Run FIX 5 tests:**
```bash
pytest tests/core/test_project_expense_tools.py::test_zero_wo_no_percentage \
  tests/core/test_project_expense_tools.py::test_over_budget_status \
  tests/core/test_quality_gate.py::test_quality_catches_pct_of_zero \
  tests/core/test_quality_gate.py::test_quality_catches_on_track_over_budget -q
```

**Deploy:**
```bash
git push origin main
# EC2:
cd /opt/ooa && git pull && ./deploy/aws/scripts/deploy-code.sh
```

**Previous sprint (complete in code):** `docs/CONVERSATION_INTEGRITY_FIX_PLAN.md` F1–F6

---

## ⏭ NEXT

After FIX 5 live verify: **Day 2–3** FIX 1 + FIX 2 (sticky context + follow-up).

After all 6 fixes + 7-turn test: **Elrace Omni-Agent Final Plan**

---

## 🎯 NORTH STAR

> Make OOA behave like an AI colleague — not a search form. Honest numbers, sticky context, no double-confirmation.
