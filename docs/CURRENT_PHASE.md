# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** HR + Payroll Rollout — Phase M6 (Payroll module certification)

**Status:** Sprint B deployed to EC2 (`ac66bda0`) — full payslip detail + drill-down routing live

| Piece | Description | Code | Tests |
|-------|-------------|------|-------|
| HR/Payroll composer | Shared slot filling: employee, period, request type, payroll subtypes | ✅ | ✅ |
| Dedicated tools | `get_payslip_detail` (full/lines/worked_days/distribution + line filters), `list_employee_requests` | ✅ | ✅ |
| Payslip drill-down | Session inherits employee/period; overtime/deductions/worked-days follow-ups | ✅ | ✅ |
| Termination routing | `employee.requests` count — not active headcount | ✅ | ✅ |
| Session context | `pending_hr_context`, filler strip, inline file ID, stale out_of_scope bypass | ✅ | ✅ |

**Key models covered:** `hr.payslip`, `hr.payslip.line`, `hr.payslip.cost.allocation`, `hr.payslip.worked_days`, `employee.requests`, `hr.employee`, `hr.attendance`, separation counts.

**Next:** UI smoke on production, then Sprint C (HR request validation/leave detail) or Sprint D (fleet driver details).

---

## 📜 PREVIOUS PLAN

**File:** Project Model — Phase 3: Project Activity lane (no Deep Think)

**Status:** Deployed — includes Phase 2.1 profile routing fixes

| Piece | Description | Code | Tests |
|-------|-------------|------|-------|
| Introspection | `scripts/introspect_project_activity.py`: ir.attachment + mail.message + progress/audit fields on project.project | ✅ | — |
| Adapter | `read_project_attachments`, `read_project_chatter_messages`, `read_project_progress_audit` | ✅ | ✅ |
| Tool | `get_project_activity` — types: attachments, chatter_summary (LLM), progress, audit | ✅ | ✅ |
| Routing | `project_activity_routing.py`; records > activity > profile precedence; Deep Think carve-out | ✅ | ✅ |
| Handler | Activity lane mirrors records: `_prepare_activity_intent`, forced tool, follow-ups | ✅ | ✅ |
| Profile fixes (2.1b) | `focus` in cache key (wo/schedule no longer serve cached engineers); profile hint override; broad project search → search_entities | ✅ | ✅ |

**Behavior contract:**
- "attachments / chatter summary / progress / last updated by of project X" → confirm → direct read (+ LLM for chatter) — NO Deep Think
- "w.o amount" → single W.O figure (not engineer table); "start date and duration" → schedule (not engineers)
- "civil amount of Villa 48" → resolves Villa 48 (not project "civil")
- "show all projects containing civil" → project search list (not Deep Think prompt)

---

## 📜 PREVIOUS PLAN (2.1)

**File:** Project Model — Phase 2.1: records lane post-deploy fixes

**Status:** Deployed `a3b68305`

| Fix | Description | Code | Tests |
|-----|-------------|------|-------|
| Per-type cache key | `tool_cache.build_tool_cache_key` now folds `record_type` / `move_type` / date window / `limit` into the key. Was `user:tool:project:hint` only, so one project's first-fetched type was served for every later type (invoices→PO→LPO→petty cash→staff→timesheets all returned the first result). Also fixes latent date-range collisions on expense tools. | ✅ | ✅ |
| out_of_scope bypass | Records (and profile) lanes are computed BEFORE the `out_of_scope` short-circuit and bypass it — "staff list" / "timesheets" were refused as unavailable HR data | ✅ | ✅ |
| Records > profile precedence | An explicit record-type keyword wins over an LLM `project_attribute`/`hr` tag — "staff list" / "supervisors" no longer fall into the profile header lane | ✅ | ✅ |
| Trailing-type follow-ups | Detection fires on active-project follow-ups even when the type trails the name ("Show <project> purchase orders" chip) | ✅ | ✅ |
| Entity hint override | `_prepare_records_intent` replaces a wrong LLM project entity with the stripped hint and clears `out_of_scope` — "petty cash of X" no longer searches project "petty cash" | ✅ | ✅ |

**Live verify (NG Al Nouf, sequential session):** PO 122 (AED 3.19M), LPO 112 (AED 2.93M), petty cash 546 (AED 143.6K), staff 27, timesheets 6,344 (61,342 hrs) — each distinct and correct.

---

## 📜 PREVIOUS PLAN (2)

**File:** Project Model — Phase 2: Project Records lanes (no Deep Think)

**Status:** Deployed `74714b91`

| Piece | Description | Code | Tests |
|-------|-------------|------|-------|
| Live model map | `scripts/introspect_project_records.py`: petty cash = `hr.expense` (lines, 53,958 project-linked) + `hr.expense.sheet` (headers); staff = `staff.list` (42k), supervisors = `project.supervisor` (3.9k); invoices/POs link via the project's ANALYTIC account (`account.move.project_id` / `purchase.order.project_id` → `account.analytic.account`); timesheets = `account.analytic.line` → project.project | ✅ | — |
| Adapter | `connector.read_project_records(record_type, project_id, dates, limit)` — `PROJECT_RECORD_SPECS` for 9 types, analytic resolution, `safe_search_read` + `search_count` + `read_group` totals; curated fields (full reads crash on `hr.expense.sheet._compute_owner_expense_line`) | ✅ | ✅ |
| Tool | `gateway/tools/project_records.py` `get_project_records` — types: invoices, client_invoices, lpo_invoices, purchase_orders, timesheets, petty_cash, petty_cash_sheets, staff, supervisors; default last-3-months for dated types; normalized rows | ✅ | ✅ |
| Routing | `project_records_routing.py` detection + record_type; analysis disqualifier (breakdown/P&L/compare stays Deep Think); Deep Think carve-out; `extract_records_project_hint` strips record keyword | ✅ | ✅ |
| Handler | Records lane mirrors profile lane: `_prepare_records_intent`, neutral confirm wording, forced `get_project_records` post-confirm + follow-ups; entity gate requires project | ✅ | ✅ |
| Synthesis | `narrate_project_records` (count + AED/hours total + period + honest zero-state); per-type DATA_TABLE columns; records suggestion chips (sibling types, date widen, expenses handoff); meaningful-data | ✅ | ✅ |

**Behavior contract:**
- "invoices / LPO invoices / client invoices / purchase orders / timesheets / petty cash / staff list / supervisors of project X" → confirm → direct ORM list, latest 20, true total in narration — NO Deep Think
- Client = out_invoice, LPO = in_invoice; generic "invoices" = both with Kind column
- "expenses / breakdown / P&L / compare" still Deep Think
- Deviation (documented): records cards are `disclosure_exempt` — the tool already pages (latest N) and narration carries the true total; the disclosure layer would replace the table with a summary chart and offer a misleading "See all N"

**Live smoke (NG Al Nouf, project 14458):** client invoices 2 (AED 3.45M), LPO invoices 112 (AED 2.93M), POs 122 (AED 3.19M), timesheets 6,291 (60,795 hrs), petty cash 546 (AED 143.6K), staff 27, supervisors 9 — all via direct reads.

**Tests:** `tests/core/test_project_records.py` (19). Full suite: 840 passed; 6 failures pre-existing (+3 transient live Odoo auth race, pass on retry).

---

## 📜 PREVIOUS PLAN (1.2)

**File:** Project Model — Phase 1.2: W.O-only focus + trade-word entity hint fix

**Status:** Deployed `d06d0520`

| Fix | Description | Code | Tests |
|-----|-------------|------|-------|
| W.O-only focus | "w.o amount of X" → `wo_amount` focus = single W.O Amount line/row (not the whole distribution). "estimation amount" → `estimation`. "...distribution" still → full `amounts` | ✅ | ✅ |
| Trade-word hint | `extract_project_name_hint` strips leading "<trade/engineers/w.o> amount of" qualifier → "civil amount of Villa Maintenance 48" resolves project "Villa Maintenance 48" (was searching "civil") | ✅ | ✅ |

**Behavior contract additions:**
- "w.o amount of project X" → just the W.O Amount value
- "civil amount of Villa 48" → resolves Villa 48, returns Civil only (no more "couldn't find project civil")

---

## 📜 PREVIOUS PLAN (1.1)

**File:** Project Model — Phase 1.1: engineer focus, clean suggestions, correct wording

**Status:** Deployed `3d53dc7`

| Piece | Description | Code | Tests |
|-------|-------------|------|-------|
| Focus routing | `project_profile_routing.derive_profile_focus`: single named trade ("civil amount") → `civil`/`electrical`/`mechanical`/`ict`; generic "engineer(s) amount" → `engineers` (4 disciplines only); W.O/estimation/distribution stays `amounts`. Tool enum extended | ✅ | ✅ |
| Narration | `narrate_project_profile`: `engineers` focus = the 4 discipline amounts only (no W.O/Estimation/Plumbing/role rows); single-trade focus = just that trade; all-unset → "not set in Odoo" | ✅ | ✅ |
| Visual card | `_project_profile_visual`: engineers → 4 rows; single trade → 1 row; profile cards carry `disclosure_exempt` | ✅ | ✅ |
| Disclosure exempt | `apply_progressive_disclosure` skips `disclosure_exempt` cards — no more summary-chart stripping / "Would you like the detailed breakdown?" / "See all 9 records" on profile answers | ✅ | ✅ |
| Suggestions | `SmartSuggestionsGenerator`: `get_project_profile` in tool_names → profile chips only (schedule, PM, engineer amounts, expenses-as-Deep-Think-handoff); never export/compare/filter chips | ✅ | ✅ |
| Confirm wording | `profile_query` threaded into `_finalize_entity_clarification` → "Please confirm which project you mean." (no "financial data" promise) | ✅ | ✅ |

**Behavior contract:**
- "engineers amount of project X" → confirm project → Civil/Electrical/Mechanical/ICT amounts ONLY
- "civil amount of project X" → that one trade only
- Profile confirm card never says "financial data"
- Profile answers never show expense/export/compare chips or disclosure prompts

**Tests:** `tests/core/test_project_profile.py` (27) + `test_project_attribute.py` (5). Full suite: 819 passed; 6 failures pre-existing (2x quality_gate, 2x villa auto-confirm, conversation integrity, phase10 concurrent).

**Live verify (manual):** "tell me engineers amount of project national guard" → confirm → 4-row engineer table, profile chips; "civil amount of Villa Maintenance 48" → single row; confirm wording check.

---

## 📜 PREVIOUS PLAN (-1)

**File:** Project Model — Phase 1: Project Profile lane (no Deep Think)

**Status:** Deployed `f5dd4f8`

| Piece | Description | Code | Tests |
|-------|-------------|------|-------|
| Live field map | `scripts/introspect_project_profile.py` ran against live Odoo; exact value match with UI: Civil=`project_eng_amount`, Electrical=`electrical_eng_amount`, Mechanical=`mechanical_eng_amount`, ICT=`it_eng_amount`; W.O=`wo_amount` | ✅ | — |
| Adapter read | `connector.read_project_profile(project_id)` — 66 curated fields, single-record read (multi-record full reads crash on Elrace `pending_days` compute bug); m2o names come free as `[id, name]` | ✅ | ✅ |
| Tool | `gateway/tools/project_profile.py` `get_project_profile(project_id, focus)` → sections: identity, client_contract, location, schedule, amounts (distribution/rollups), team, status, progress, audit; registered in TOOLS + execute_tool | ✅ | ✅ |
| Routing | `project_profile_routing.py` (detection + focus); Deep Think carve-out in `is_deep_think_eligible`; handler: project_attribute deferral replaced by profile lane (falls back when no project ref); profile bypasses normal-mode gate; follow-up + post-entity-gate forced `get_project_profile` | ✅ | ✅ |
| Synthesis | `narrate_project_profile` (focused section only, exact decimals, honest "not set in Odoo"); `result_synthesizer` dispatch; DATA_TABLE profile card | ✅ | ✅ |

**Behavior contract:**
- "engineers amount of project national guard" → entity confirm → header read → Civil/Electrical/Mechanical/ICT amounts (NOT the expense report)
- "who is the PM of Villa 48" → answered from header (old deferral only when no project reference)
- Profile queries never light up the Deep Think button; expenses/P&L/breakdown still do
- Unset amounts → "not set in Odoo", never fabricated zeros

**Tests:** `tests/core/test_project_profile.py` (18) + reworked `test_project_attribute.py` (5). Full suite: 805+ passed; 9 failures all verified pre-existing on clean worktree (2x quality_gate, 2x villa auto-confirm, conversation integrity, phase10 concurrent, 3x live Odoo auth — server-side `could not serialize access` race in `base_user_role_company`).

**Live verify (manual):** "tell me engineers amount of project national guard" → select project → distribution amounts table; "who is the project manager of Villa Maintenance 48"; "show me expenses for Villa 48" still routes to Deep Think expense flow.

---

## 📜 PREVIOUS PLAN (0)

**File:** Conversational fixes + Deep Think resume (post-live-test feedback round)

**Status:** Deployed `97a3693` — live verified

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
