# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** AI Intelligence Rebuild (conversational routing + Deep Think mode)

**Status:** Code complete — pending live verification + commit

| Piece | Description | Code | Tests |
|-------|-------------|------|-------|
| Conversational branch | "Hi"/capability/off-topic → scoped responder, never Odoo/tool-error | ✅ | ✅ |
| Normal mode | Data queries without Deep Think → AI-prepared answer + narrowing, no Odoo methods | ✅ | ✅ |
| Deep Think gate | Predefined Odoo methods + synthesis only when `deep_think=true` | ✅ | ✅ |
| Eligibility | `POST /deep-think/eligibility` keyword check (no LLM) | ✅ | ✅ |
| UI button | Conditional Deep Think toggle in ChatInputBar (debounced eligibility) | ✅ | lint |
| Suggestions | Date-range + project-name interpolation; capability chips on chitchat | ✅ | ✅ |

**Key files:** `gateway/core/conversational_responder.py`, `gateway/core/deep_think.py`, `gateway/intelligent_handler.py`, `gateway/main.py`, `ooa-ui/src/main/chat/ChatInputBar.jsx`, `ooa-ui/src/components/chat/ChatScreen.jsx`

**Behavior contract:**
- Greeting / "what can you do" / off-topic → conversational reply, zero Odoo, zero tools
- Financial/data query, Deep Think OFF → AI restates + narrows (date/project) + offers Deep Think; NEVER outputs figures
- Financial/data query, Deep Think ON → entity gate → predefined Odoo methods → AI synthesis (existing pipeline)
- Follow-ups to an active project keep their forced-tool flow (continuation of Deep Think session)
- Integration tests updated: entity-gate/tool flows now pass `deep_think=True`

**Live verify (manual):** `Hi` → greeting; `what can you do?` → capabilities; `show me the P&L` (no Deep Think) → AI-prepared + button highlighted; same with Deep Think → real figures.

**Pre-existing test failures (NOT this phase):** 2x `test_quality_gate` pass-rate (10th check added, tests assume 9), 2x villa auto-confirm integration tests (expect old confirm-first flow), `test_incident_five_turn_sequence`, `test_concurrent_same_zayidia_query_all_get_confirm`, 1 live Odoo test.

---

## 📜 PREVIOUS PLAN

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
