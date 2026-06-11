# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** Conversational fixes + Deep Think resume (post-live-test feedback round)

**Status:** Code complete + tested — deployed, pending live verification

| Fix | Description | Code | Tests |
|-----|-------------|------|-------|
| Near-miss confirm loop | `entity_gate.evaluate`: API-supplied `confirmed_entities` are authoritative — no `_matches_active` re-validation (picking "Villa 34" for query "Villa 37" now resumes) | ✅ | ✅ |
| P&L false "No data" | `has_meaningful_tool_data` recognizes financial report shape (`kpis`, `report_lines`) | ✅ | ✅ |
| Empty "for ." label | `failure_from_no_data`: label falls back to user message; financial wording drops client/project spelling hint + raw `group_and_aggregate` | ✅ | ✅ |
| Report misroute guardrail | `strategy_planner`: P&L/balance-sheet/cash-flow/trial-balance queries force `get_financial_report`/`get_trial_balance` (never entity search) | ✅ | ✅ |
| Date parsing | `resolve_report_date_range`: this/last month, last quarter, this/last year, last N months, explicit `from X to Y` — replaces hardcoded last_3_months | ✅ | ✅ |
| One-click Deep Think | Normal-mode report queries return clickable period card (`resume_deep_think`, explicit-date suffixes, detected period = default); clicking any preset/custom range resumes with `deep_think=true` and fetches real figures | ✅ | ✅ |

**Key files:** `gateway/core/entity_gate.py`, `gateway/core/quality_pipeline.py`, `gateway/core/failure_handler.py`, `gateway/core/strategy_planner.py`, `gateway/clarify.py`, `gateway/intelligent_handler.py`, `ooa-ui/src/components/chat/ChatScreen.jsx`, `ooa-ui/src/components/chat/ClarificationCard.jsx`

**Tests:** `tests/core/test_conversational_fixes.py` (14 tests). Full suite: 456 passed; 7 failures all pre-existing (verified on clean tree).

**Live verify (manual):** P&L in normal mode → period card → click preset → real figures, one click. "Villa maintainacne 37" → pick "Villa Maintenance No. 34" → expenses for 34.

---

## 📜 PREVIOUS PLAN (a)

**File:** AI Intelligence Rebuild (conversational routing + Deep Think mode)

**Status:** Deployed `78a1d32`

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
