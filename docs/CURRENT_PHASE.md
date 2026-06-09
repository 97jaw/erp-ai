# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** `docs/CONVERSATION_INTELLIGENCE_SPRINT.md` — Conversation Intelligence Sprint (6 fixes)

**Status:** Day 1 complete — FIX 4 ✅ + FIX 5 ✅ (code/tests/deploy; chat E2E pending Odoo recovery)

---

## 📍 SPRINT PROGRESS

| Fix | Description | Code | Tests | Live verify |
|-----|-------------|------|-------|-------------|
| FIX 4 | Deploy A1 breakdown unwrap | ✅ `fd4b2e6` | ✅ | ✅ Salary / AED 11,053 on project 15157 |
| FIX 5 | Number sanity (W.O=0) | ✅ `82669fb` | ✅ 4 tests | ✅ narrative on EC2 (Odoo 502 blocked full chat E2E) |
| FIX 1 | Sticky context | — | — | — |
| FIX 2 | Follow-up routing | — | — | — |
| FIX 3 | Skip confirmed | — | — | — |
| FIX 6 | Non-financial honesty | — | — | — |
| Final | 7-turn acceptance test | — | — | — |

**FIX 4 live result (2026-06-09):** Breakdown for Villa Maintenance No. 34 (15157) returns Salary → Labor → 55002 LABER WAGES, AED 11,053.15. Chat follow-up "share the expense breakdown" shows GL breakdown (not "No data found").

**FIX 5 live result (2026-06-09):** Deployed `82669fb`. EC2 container with Villa 34 payload (wo=0, spent=12120) now narrates: *"AED 12,120 in recorded expenses, but no W.O budget is assigned…"* — not *"2% on track"*. Full `/chat/stream` E2E blocked briefly by Odoo `502 Bad Gateway` on `erp.elrace.com`; retry when Odoo is back.

**Next:** Day 2–3 FIX 1 + FIX 2 (sticky context + follow-up).

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
