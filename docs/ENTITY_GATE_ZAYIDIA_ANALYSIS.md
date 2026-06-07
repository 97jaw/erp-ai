# Entity Gate — Zayidia Boys School Issue Analysis

**Date:** 2026-06-06  
**Query:** `show me Zayidia Boys School costs`  
**Odoo state (reported):** One project named **Zayidia Boys School** (id `14549`, WO `RCC-AA-MOE-2025-016`)  
**Observed response:**

> The data for show me Zayidia Boys School costs is ambiguous — multiple records match and the totals may double-count. Please narrow the client, project, or period.

**Purpose of this document:** Capture phase, expected behaviour, actual behaviour, and root-cause analysis so a follow-up plan can be written separately. No implementation is included here.

---

## 1. Current phase

| Source | What it says |
|--------|----------------|
| [`docs/CURRENT_PHASE.md`](CURRENT_PHASE.md) | **Phase 8** — Telemetry & Learning (tracker lagging) |
| **Actual engineering state** | **Phase 9 — Integration & Migration** (in progress) |

### Phase 9 work already landed (relevant to this query)

| Component | Status |
|-----------|--------|
| `/chat` and `/chat/stream` → `IntelligentQueryHandler` | Done (legacy agent loop removed from stream) |
| Generic **Entity Gate** (`gateway/core/entity_gate.py`) | Done — discover → confirm → then KPI |
| Strategy planner requires **confirmed** project before `get_project_expenses` | Done |
| Frontend entity picker + `confirmed_entities` API field | Done in code (requires gateway restart + UI rebuild) |
| `/voice` → intelligent handler | Done |

**North star (unchanged):** Senior management consultant + CFO chief of staff — never fabricate numbers; confirm before financial calls.

---

## 2. Target behaviour (Phase 9 — Generic Entity Confirmation)

Policy confirmed with product owner:

- **Always confirm** before entity-bound financial/KPI calls — even when exactly **one** match exists.
- Applies to **all users** (including super-admins).
- Company-wide tools (`get_financial_report`, `get_trial_balance`) are exempt — no entity gate.

### Intended flow for `"show me Zayidia Boys School costs"`

```
User query
    → Intent analysis + entity hints
    → Entity Gate: discovery only (project.project search_read — NO KPI)
    → 1+ matches found
    → Clarification UI: "I found Zayidia Boys School — please confirm"
    → User clicks confirm (confirmed_entities sent)
    → Strategy → get_project_expenses(project_id)
    → Cost summary
```

**Turn 1:** No expense numbers. No `get_project_expenses`.  
**Turn 2:** Financial service call only after user confirmation.

---

## 3. Observed behaviour (live)

| Aspect | What happened |
|--------|----------------|
| Response text | `DATA_AMBIGUOUS` template — "multiple records match / double-count" |
| Confirmation UI | Not described — no project confirm button |
| Financial KPI | Not called (pipeline stopped earlier) |
| User expectation | One project in Odoo → should confirm that project, then show costs |

---

## 4. Where the message comes from (code trace)

The exact user-facing text is defined in:

- **File:** `gateway/core/failure_handler.py`
- **Failure mode:** `FailureMode.DATA_AMBIGUOUS`
- **Template (lines ~145–150):** *"The data for {query_label} is ambiguous — multiple records match and the totals may double-count…"*

That mode is assigned when:

- **`HonestFailureResponder.failure_from_stage(stage="entity_resolution", …)`** runs (see `failure_handler.py` ~348–352).

So the pipeline **failed or exited during the Entity Resolution / Entity Gate stage** — not during synthesis or quality review of KPI results.

### Stages NOT reached (for this response)

```
Strategy → Execution → get_project_expenses → Synthesis → Quality
```

---

## 5. Pipeline diagram (actual path for this symptom)

```
show me Zayidia Boys School costs
    │
    ▼
[Cache] miss
    │
    ▼
[Context] + [Intent] (+ entity hints: "Zayidia Boys School")
    │
    ▼
[ENTITY_RESOLUTION] Entity Gate.evaluate()
    │
    ▼
Discovery: EntityResolver → Odoo project.project search_read
    │
    ├── (A) 0 confident matches ──► status: not_found
    │         │
    │         ▼
    │   _finalize_entity_clarification(not_found=True)
    │         │
    │         ▼
    │   failure_from_stage("entity_resolution") → DATA_AMBIGUOUS  ◄── WRONG TEMPLATE
    │         │
    │         ▼
    │   User sees "multiple records / double-count" (misleading)
    │
    ├── (B) 1+ matches ──► status: needs_confirmation
    │         │
    │         ▼
    │   Expected: "I found **Zayidia Boys School** — confirm?" + button
    │   (User did NOT report this — suggests path A or deploy gap)
    │
    └── (C) Exception in entity stage ──► PipelineStageError(ENTITY_RESOLUTION)
              │
              ▼
        Same DATA_AMBIGUOUS mapping via failure_from_stage
```

---

## 6. Root-cause analysis

### 6.1 Primary hypothesis (matches exact symptom)

**Discovery returned zero usable matches** (`not_found`), but the handler maps that case to **`DATA_AMBIGUOUS`**, which describes *multiple KPI records / double-counting* — not *project not found*.

Relevant code path:

- `gateway/intelligent_handler.py` → `_finalize_entity_clarification` when `entity_meta.not_found=True`
- Calls `failure_from_stage("entity_resolution", ValueError("No matching records found…"))`
- That stage maps to `FailureMode.DATA_AMBIGUOUS` → wrong user message

**Result:** User with **one** project in Odoo sees language about **multiple records** and **double-count** — confusing and incorrect.

### 6.2 Why discovery might return 0 matches (despite 1 project in Odoo UI)

| # | Possible cause | Notes |
|---|----------------|-------|
| 1 | **Name / spelling mismatch** | Query `Zayidia` vs Odoo `Zayed`, or suffix e.g. `Renovation`. `ilike` usually matches substrings; typos can still miss. |
| 2 | **Confidence cutoff** | `EntityResolver.resolve_project(..., min_confidence=0.6)` — weak scores → empty `confident_matches` → gate treats as not found. |
| 3 | **Silent adapter failure** | `EntityGate._discover` catches exceptions → returns `[]` → not found. Check gateway logs for `[EntityGate] project discovery failed`. |
| 4 | **Permissions / active flag** | Project visible in Odoo backend UI but not returned to API user used by gateway. |
| 5 | **Stale deploy** | Gateway or UI not restarted/rebuilt after Phase 9 entity gate — would show older behaviour. |
| 6 | **Frontend not sending confirm** | Second turn never happens; less likely to produce this exact `DATA_AMBIGUOUS` text on first turn. |

### 6.3 Secondary hypothesis (if discovery DID find 1 match)

If discovery worked, user should see:

> I found **Zayidia Boys School (WO-…)**. Is this the one you want financial data for?

with a clickable `confirm_entity` option — **not** the double-count message.

If that UI never appeared, check:

- `ooa-ui` rebuilt (`npm run build`) after ClarificationCard changes
- Browser cache / old static assets
- SSE `awaiting_clarification` + `clarification.options` in network tab

### 6.4 What this is NOT (for this specific message)

| Ruled out | Reason |
|-----------|--------|
| Legacy agent loop rambling ("263 school projects") | That path was replaced on `/chat/stream` |
| KPI layer `multiple_projects_found` after `get_project_expenses` | KPI stage not reached; message is from entity-resolution failure mapping |
| `AMBIGUOUS_REFERENCE` template ("I found N possible matches") | Different template; user text matches `DATA_AMBIGUOUS` exactly |

---

## 7. Expected vs actual (summary table)

| Dimension | Expected (Phase 9) | Observed |
|-----------|-------------------|----------|
| Phase | Entity Gate active on stream | Gate runs but exits at discovery |
| Turn 1 financial call | **No** | **No** ✓ |
| Turn 1 UX | Confirm single project button | Error prose, no confirm button ✗ |
| Message semantics | "Found X — please confirm" or "No project found" | "Multiple records / double-count" ✗ |
| Failure mode | `entity_confirmation` or honest `no_data` | `data_ambiguous` (misleading) ✗ |
| Odoo KPI | Only after `confirmed_entities` | Not invoked ✓ (but for wrong reason) |

---

## 8. Case matrix for follow-up plan

Use this when drafting the handling plan:

| Case | Discovery result | Expected UX | Current gap |
|------|------------------|-------------|-------------|
| **C1** | 0 matches | Honest "no project found for X" + refine hints | Wrong template (`DATA_AMBIGUOUS`) |
| **C2** | 1 match | Confirm button; no KPI until click | Should work if deploy + discovery OK |
| **C3** | 2+ matches | Candidate list; no KPI until pick | Should work if deploy OK |
| **C4** | 1 match in Odoo, 0 from API | Log domain, raw count, confidence; surface connectivity/permission | Silent empty → misleading message |
| **C5** | Confirmed entity on turn 2 | `get_project_expenses(project_id)` only | Depends on C2/C3 working first |
| **C6** | KPI returns `multiple_projects_found` | Clarification, not retry / not double-count prose | Orchestrator partially addressed; quality path TBD |

---

## 9. Key files (reference)

| File | Role |
|------|------|
| `gateway/core/entity_gate.py` | Generic discover → confirm gate |
| `gateway/intelligent_handler.py` | `_run_entity_gate`, `_finalize_entity_clarification` |
| `gateway/core/entity_resolver.py` | Multi-strategy Odoo project search |
| `gateway/core/failure_handler.py` | `DATA_AMBIGUOUS` vs `AMBIGUOUS_REFERENCE` templates |
| `gateway/core/strategy_planner.py` | Blocks KPI until `EntityGate.project_confirmed()` |
| `gateway/main.py` | `ChatRequest.confirmed_entities`, `/chat/stream` |
| `ooa-ui/src/components/chat/ClarificationCard.jsx` | Entity confirm buttons |
| `ooa-ui/src/components/chat/ChatScreen.jsx` | Sends `confirmed_entities` |

---

## 10. Suggested verification steps (before next implementation)

1. **Gateway logs** for query `show me Zayidia Boys School costs`:
   - `[EntityGate] project discovery failed`
   - `[V14Adapter] Resolving project`
   - Entity gate result status: `not_found` vs `needs_confirmation`
2. **Network tab** — `/chat/stream` done event:
   - `awaiting_clarification: true/false`
   - `clarification.reason` (`entity_confirmation` vs `entity_not_found`)
   - `clarification.options` length
3. **Direct Odoo** — `search_read` on `project.project` with `ilike` `Zayidia` as the gateway user.
4. **Deploy check** — gateway process restarted after Phase 9; UI rebuilt.

---

## 11. Resolved product decisions (2026-06-06)

These decisions close the open questions from the initial analysis and are implemented in Phase 9 follow-up.

### Q1 — Single match: mandatory confirm or skip for super-admins?

**Decision:** Keep mandatory confirm for all users, including super-admins.

**Rationale:** Financial data. One click to confirm is cheap; showing wrong project numbers to a CFO is not.

**Future:** Revisit in ~3 months once trust is established. Optional setting: "Auto-confirm single matches" for users who opt in.

### Q2 — Not-found copy and broadening?

**Decision:** Use exact structured copy with spelling / WO / client hints plus actionable buttons.

**Copy (EN):**

```
I couldn't find a project matching "{query}" in the system.

Try:
- A different spelling (e.g., "Zayed", "Zayedia")
- The Work Order number (e.g., RCC-AA-MOE-2025-016)
- The client name (e.g., Ministry of Education)

Or I can search more broadly — want me to show all projects containing "{term}"?
```

**Buttons:** `[Search broader]` → `search_broader_entity`; `[Try different name]` → `try_different_name`.

**Principles:** Honest about what happened; three concrete alternatives; actionable buttons.

### Q3 — Should `failure_from_stage("entity_resolution")` ever map to `DATA_AMBIGUOUS`?

**Decision:** **Never.**

| Entity gate outcome | Mapping |
|---------------------|---------|
| `not_found` | `FailureMode.NO_DATA_FOUND` (via dedicated clarification, not stage failure prose) |
| `needs_confirmation` / `weak_confirmation` | Not a failure — clarification turn |
| Exception | `FailureMode.TOOL_ERROR` |
| Multiple ambiguous entities | `FailureMode.AMBIGUOUS_REFERENCE` |

`DATA_AMBIGUOUS` is reserved for the KPI/synthesis layer when financial data has overlapping records (double-count risk). Entity resolution and KPI ambiguity are different problems.

### Q4 — Confidence threshold and fallback?

**Decision:** Keep `min_confidence = 0.6` for confident matches; add a weak tier:

| Score | Bucket | UX |
|-------|--------|-----|
| ≥ 0.6 | `confident_matches` | Shown as normal options |
| 0.3 – 0.6 | `weak_matches` | Shown only if no confident matches, with caveat |
| < 0.3 | Discarded | — |

When Odoo returns rows but all score below 0.6, show weak matches with:

> These are possible matches but I'm not confident. Did you mean one of these?

Never silently discard all matches and say "not found" when the resolver actually got results.

### Q5 — Telemetry fields?

**Decision:** Add to `InteractionTelemetry`:

| Field | Purpose |
|-------|---------|
| `entity_discovery_count` | Raw matches from Odoo |
| `entity_top_confidence` | Highest scored match |
| `entity_gate_status` | `not_found` / `needs_confirmation` / `weak_confirmation` / `confirmed` / `skipped` |
| `entity_confirmed_by_user` | User clicked confirm |
| `entity_auto_confirmed` | Reserved for future opt-in auto-confirm |
| `entity_strategies_used` | Which discovery strategies ran |
| `entity_strategy_that_matched` | Strategy that produced the top match |

---

*Implementation complete for Q1–Q5. Next: deploy gateway + rebuild UI; live retest Zayidia query end-to-end.*
