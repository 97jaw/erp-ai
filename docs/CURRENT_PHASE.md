# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** `docs/CONVERSATION_INTELLIGENCE_SPRINT.md` — Conversation Intelligence Sprint (6 fixes)

**Status:** All 6 fixes complete in code — **7-turn acceptance test** is the final gate (live verify when you test)

---

## 📍 SPRINT PROGRESS

| Fix | Description | Code | Tests | Live verify |
|-----|-------------|------|-------|-------------|
| FIX 4 | Deploy A1 breakdown unwrap | ✅ `fd4b2e6` | ✅ | ✅ |
| FIX 5 | Number sanity (W.O=0) | ✅ `82669fb` | ✅ | ⏳ |
| FIX 1 | Sticky context | ✅ `8d77ad5` | ✅ | ⏳ |
| FIX 2 | Follow-up routing | ✅ `8d77ad5` | ✅ | ⏳ |
| FIX 3 | Skip confirmed projects | ✅ `58ee900` | ✅ | ⏳ |
| FIX 6 | Non-financial honesty | ✅ | ✅ 4 tests | ⏳ |
| Final | 7-turn acceptance test | — | — | ⏳ |

**FIX 6:** PM/deadline/status questions → `project_attribute` intent + honest deferral (no financial re-confirm, no tool calls).

**Run FIX 6 tests:**
```bash
pytest tests/core/test_project_attribute.py -q
```

**7-turn acceptance test** (from sprint doc — run live after deploy):
```
1. Villa 34 expense for this year
2. share the expense breakdown as well
3. breakdown of Villa Maintenance No. 34
4. (same after confirm)
5-6. General maintenance Al Mushrif
7. can you name the project manager of villa 34?
```

**Deploy:**
```bash
git push origin main
# EC2:
cd /opt/ooa && git pull && ./deploy/aws/scripts/deploy-code.sh
```

---

## ⏭ NEXT

Pass 7-turn live test → **Elrace Omni-Agent Final Plan**

---

## 🎯 NORTH STAR

> Make OOA behave like an AI colleague — not a search form. Honest numbers, sticky context, no double-confirmation.
