# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** `docs/CONVERSATION_INTELLIGENCE_SPRINT.md` — Conversation Intelligence Sprint (6 fixes)

**Status:** Day 2–3 complete in code — FIX 1 + FIX 2 ✅ (tests pass; live verify when you test)

---

## 📍 SPRINT PROGRESS

| Fix | Description | Code | Tests | Live verify |
|-----|-------------|------|-------|-------------|
| FIX 4 | Deploy A1 breakdown unwrap | ✅ `fd4b2e6` | ✅ | ✅ |
| FIX 5 | Number sanity (W.O=0) | ✅ `82669fb` | ✅ 4 tests | ⏳ Odoo E2E when back |
| FIX 1 | Sticky context (`ActiveContext`) | ✅ | ✅ 2 tests | ⏳ |
| FIX 2 | Follow-up routing | ✅ | ✅ 3 tests | ⏳ |
| FIX 3 | Skip confirmed | — | — | — |
| FIX 6 | Non-financial honesty | — | — | — |
| Final | 7-turn acceptance test | — | — | — |

**FIX 1:** `WorkingMemory.active_context` — set after successful project expense tools; hydrated from session scope; cleared on topic shift.

**FIX 2:** `is_followup_to_active()` — follow-ups like "share the breakdown" reuse active project and skip entity gate (no re-search on `15157`, no re-confirm).

**Run FIX 1+2 tests:**
```bash
pytest tests/core/test_active_context.py -q
```

**Deploy:**
```bash
git push origin main
# EC2:
cd /opt/ooa && git pull && ./deploy/aws/scripts/deploy-code.sh
```

---

## ⏭ NEXT

**Day 4:** FIX 3 — Entity gate skips already-confirmed projects.

After all 6 fixes + 7-turn test: **Elrace Omni-Agent Final Plan**

---

## 🎯 NORTH STAR

> Make OOA behave like an AI colleague — not a search form. Honest numbers, sticky context, no double-confirmation.
