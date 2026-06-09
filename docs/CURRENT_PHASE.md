# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** `docs/CONVERSATION_INTELLIGENCE_SPRINT.md` — Conversation Intelligence Sprint (6 fixes)

**Status:** Day 4 complete in code — FIX 3 ✅ (tests pass; live verify when you test)

---

## 📍 SPRINT PROGRESS

| Fix | Description | Code | Tests | Live verify |
|-----|-------------|------|-------|-------------|
| FIX 4 | Deploy A1 breakdown unwrap | ✅ `fd4b2e6` | ✅ | ✅ |
| FIX 5 | Number sanity (W.O=0) | ✅ `82669fb` | ✅ | ⏳ |
| FIX 1 | Sticky context (`ActiveContext`) | ✅ `8d77ad5` | ✅ | ⏳ |
| FIX 2 | Follow-up routing | ✅ `8d77ad5` | ✅ | ⏳ |
| FIX 3 | Skip confirmed projects | ✅ | ✅ 2 tests | ⏳ |
| FIX 6 | Non-financial honesty | — | — | — |
| Final | 7-turn acceptance test | — | — | — |

**FIX 3:** Entity gate skips re-confirmation when query matches an already-confirmed active project (`_matches_active` / `_extract_entity_hint`).

**Run FIX 3 tests:**
```bash
pytest tests/core/test_entity_gate.py::test_confirmed_project_not_reconfirmed \
  tests/core/test_entity_gate.py::test_new_project_still_needs_confirmation -q
```

**Deploy:**
```bash
git push origin main
# EC2:
cd /opt/ooa && git pull && ./deploy/aws/scripts/deploy-code.sh
```

---

## ⏭ NEXT

**Day 5:** FIX 6 — Non-financial honesty (project manager, attributes).

**Day 6–7:** Full 7-turn acceptance test → then **Elrace Omni-Agent Final Plan**.

---

## 🎯 NORTH STAR

> Make OOA behave like an AI colleague — not a search form. Honest numbers, sticky context, no double-confirmation.
