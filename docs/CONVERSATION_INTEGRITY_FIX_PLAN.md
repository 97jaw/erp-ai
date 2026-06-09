# CONVERSATION INTEGRITY FIX PLAN

> **Sprint, not architecture.** Five surgical fixes to bugs revealed by the Villa 48 incident. Each fix is small, targeted, testable. Total: 1.5 weeks. No new architecture. No new patterns. Just fix the foundation.

> **Why this comes first:** The Elrace Omni-Agent Final Plan and the Universal Odoo Access expansion are blocked until these bugs are fixed. Building on a corrupted foundation amplifies failure.

> **Read first:** Server logs from 2026-06-09 incident, `AI_CORE_INTELLIGENCE_ARCHITECTURE.md`, `ELRACE_OMNI_AGENT_FINAL_PLAN.md` (do NOT start that plan until this one is complete)

---

# PART I — THE BUGS (CONFIRMED FROM LOGS)

## 1. The Smoking Gun

```
Turn 1 (10:46:45): "Villa Maintenance No. 48 expense for this year"
  → Tool called with project_id=3288 (Villa 48)
  → Returns AED 0 / AED 0
  → Status: "On track"

Turn 5 (10:48:42): "General maintenance work - Al Mushrif need expense report"
  → Different entity, different intent
  → [TOOL] {"tool": "get_project_expense_summary",
            "cached": true,
            "duration_ms": 0}
  → Returns Villa 48 data AGAIN

The cache returned data for the WRONG entity in 0ms.
This is the root corruption.
```

## 2. The Five Bugs Stack

| # | Bug | File (suspected) | Severity |
|---|-----|------------------|----------|
| 1 | Cache key too coarse — returns wrong entity's data | `gateway/main.py` cache layer | CRITICAL |
| 2 | EntityGate bypassed when WorkingMemory has recent entity | `gateway/intelligent_handler.py` | CRITICAL |
| 3 | `primary_action="search_entity"` routed to expense tool | `gateway/core/strategy_planner.py` | HIGH |
| 4 | Quality gate accepts AED 0 / AED 0 as "On track" | `gateway/core/quality_gate.py` | HIGH |
| 5 | Format clarification ("PDF or Excel?") before entity resolved | `gateway/core/intent_analyzer.py` | MEDIUM |

---

# PART II — THE FIVE FIXES

## 3. FIX 1 — Cache Key Includes Entity Identifier

**Symptom:**
```
Query A: "Villa No. 48 expense"  → project_id=3288 → data returned
Query B: "Al Mushrif expense"    → cached=true   → project_id=3288 data returned
```

**Root Cause:**
The response cache key is likely composed of `(user_id, tool_name)` or similar, without including the actual entity identifier (project_id or project name hint).

**Fix:**
```python
# In gateway/main.py (or wherever the tool cache is keyed)

# BEFORE (buggy):
cache_key = f"{user_id}:{tool_name}"

# AFTER (correct):
def _build_tool_cache_key(user_id, tool_name, tool_input):
    """Build cache key that includes entity identity."""
    entity_id = (
        tool_input.get("project_id")
        or tool_input.get("partner_id")
        or tool_input.get("employee_id")
        or tool_input.get("id")
    )
    entity_hint = (
        tool_input.get("project_name")
        or tool_input.get("name_search")
        or tool_input.get("query")
        or ""
    )
    # Hash the entity hint to keep key length bounded
    hint_hash = hashlib.md5(entity_hint.encode()).hexdigest()[:8] if entity_hint else "noent"
    
    return f"{user_id}:{tool_name}:{entity_id or 'noid'}:{hint_hash}"


# Additional safety: short TTL for entity-resolved results
ENTITY_CACHE_TTL_SECONDS = 300  # 5 minutes max
```

**Also:** Cache MUST be invalidated when topic shifts (see Fix 2).

**Acceptance Tests:**
```python
# tests/integration/test_cache_integrity.py

async def test_different_projects_dont_share_cache():
    """Different entities must not share cache entries."""
    # First query: Villa 48
    result_a = await chat("Villa No. 48 expense for this year", user=super_admin)
    assert result_a.tool_result["project_id"] == 3288
    
    # Second query: different project entirely
    result_b = await chat("Al Mushrif expense for this year", user=super_admin)
    
    # MUST NOT return Villa 48
    assert result_b.tool_result.get("project_id") != 3288, (
        f"Cache leaked Villa 48 data into Al Mushrif query. "
        f"Got: {result_b.tool_result}"
    )


async def test_cache_key_includes_entity():
    key_a = _build_tool_cache_key(1, "get_project_expense_summary",
                                  {"project_id": 3288, "project_name": "Villa 48"})
    key_b = _build_tool_cache_key(1, "get_project_expense_summary",
                                  {"project_id": 7711, "project_name": "Al Mushrif"})
    assert key_a != key_b, "Different projects must have different cache keys"


async def test_no_entity_in_input_uses_safe_key():
    key = _build_tool_cache_key(1, "some_tool", {})
    assert "noid" in key and "noent" in key
```

**Live Test:**
Run these in sequence in the same session:
```
1. "Villa No. 48 expense this year"
2. "Al Mushrif expense this year"
3. "Hatta Hospital expense this year"
```
Each must return DIFFERENT project data. None should be cached from previous.

**Done When:** All 3 unit tests pass + live test sequence returns 3 distinct projects.

---

## 4. FIX 2 — Topic-Shift Detection + EntityGate Always Runs

**Symptom:**
```
Turn 3 query: "now General maintenance work"
Turn 3 tool: get_project_expenses({project_id: 3288, project_name: "Villa 48"})

User explicitly said "now" (topic change signal).
System ignored it and reused Villa 48 from turn 1.
```

**Root Cause:**
WorkingMemory's `recent_entities` is being treated as "use this entity" instead of "user might be referring to this." Combined with EntityGate not re-running, the previous entity sticks.

**Fix:**

```python
# In gateway/core/working_memory.py
# Add topic-shift detection

class WorkingMemory:
    def detect_topic_shift(self, current_intent: Intent) -> bool:
        """
        Returns True if current intent represents a topic shift from recent turns.
        Use to decide whether to reuse recent entities.
        """
        if not self.recent_intents:
            return False
        
        last_intent = self.recent_intents[-1]
        
        # Explicit topic-shift markers in the query
        SHIFT_MARKERS = ["now", "switch to", "change to", "instead",
                         "different", "another", "next", "actually"]
        # (Add Arabic equivalents)
        query_lower = current_intent.query.lower()
        if any(marker in query_lower for marker in SHIFT_MARKERS):
            return True
        
        # New entity that wasn't in previous intent
        current_entities = {e.value.lower() for e in current_intent.entities}
        last_entities = {e.value.lower() for e in last_intent.entities}
        if current_entities and last_entities and not (current_entities & last_entities):
            # No overlap at all → topic shift
            return True
        
        # Different subject_area
        if current_intent.subject_area != last_intent.subject_area:
            return True
        
        return False
    
    def clear_entity_context(self):
        """Wipe recent entities — call when topic shifts."""
        self.recent_entities = []


# In gateway/intelligent_handler.py
# Make EntityGate always run when intent has entities

async def handle(self, request, user):
    # ... existing context build ...
    
    # NEW: Check for topic shift BEFORE entity resolution
    if context.working_memory.detect_topic_shift(intent):
        logger.info(
            f"[TopicShift] Detected. Clearing recent entities. "
            f"Last: {context.working_memory.recent_intents[-1].query if context.working_memory.recent_intents else 'none'}, "
            f"Now: {intent.query}"
        )
        context.working_memory.clear_entity_context()
    
    # ALWAYS run EntityGate if intent has entities — never skip
    if intent.entities:
        entity_result = await self.entity_gate.evaluate(intent, context)
        # ... existing entity handling ...
```

**Acceptance Tests:**
```python
async def test_explicit_now_triggers_topic_shift():
    mem = WorkingMemory()
    mem.recent_intents.append(make_intent("Villa 48 expense", entities=["Villa 48"]))
    
    new_intent = make_intent("now General maintenance work", entities=["General maintenance work"])
    assert mem.detect_topic_shift(new_intent) is True


async def test_no_entity_overlap_triggers_shift():
    mem = WorkingMemory()
    mem.recent_intents.append(make_intent("Villa 48", entities=["Villa 48"]))
    
    new_intent = make_intent("Al Mushrif expense", entities=["Al Mushrif"])
    assert mem.detect_topic_shift(new_intent) is True


async def test_same_entity_no_shift():
    mem = WorkingMemory()
    mem.recent_intents.append(make_intent("Villa 48 expense", entities=["Villa 48"]))
    
    new_intent = make_intent("show me the breakdown", entities=[])  # follow-up
    assert mem.detect_topic_shift(new_intent) is False


async def test_entity_gate_runs_after_topic_shift():
    """After topic shift, EntityGate must re-resolve, not use cached."""
    # Run "Villa 48 expense" → resolves to 3288
    # Then "now Al Mushrif" → must call EntityResolver, not reuse 3288
    pass  # integration-level test
```

**Live Test:**
```
Turn 1: "Villa No. 48 expense this year"
Turn 2: "now General maintenance work"
  → Must show search results or clarification candidates for general maintenance
  → MUST NOT show Villa 48 data
Turn 3: "show me the breakdown"  (no explicit topic change)
  → Should use most recent entity (whatever was resolved in turn 2)
```

**Done When:** Unit tests pass + live test sequence behaves correctly.

---

## 5. FIX 3 — search_entity Routes To Search, Not Expense Tool

**Symptom:**
```
Turn 3 log:
  intent.primary_action: "search_entity"
  intent.specific_intent: "search_for_general_maintenance_projects"
  
  Tool called: get_project_expenses(project_id=3288)
  
  Should have called: a search/list tool to FIND general maintenance 
  projects, not fetch expenses of an unrelated project.
```

**Root Cause:**
`StrategyPlanner` defaults to expense tools when subject_area is "project" regardless of `primary_action`. The "search_entity" action is being ignored.

**Fix:**

```python
# In gateway/core/strategy_planner.py

class StrategyPlanner:
    async def plan(self, intent: Intent, context: ContextStack) -> Strategy:
        # NEW: Route by primary_action FIRST, not subject_area
        
        if intent.primary_action == "search_entity":
            return self._plan_entity_search(intent, context)
        
        if intent.out_of_scope:
            return self._plan_out_of_scope(intent, context)
        
        # ... existing logic for fetch_data, analyze, etc ...
    
    def _plan_entity_search(self, intent: Intent, context: ContextStack) -> Strategy:
        """When user wants to SEARCH for entities, not get specific data."""
        entity_type = intent.entities[0].type if intent.entities else "project"
        entity_hint = intent.entities[0].value if intent.entities else ""
        
        return Strategy(
            steps=[ExecutionStep(
                step_number=1,
                description=f"Search for {entity_type} matching '{entity_hint}'",
                tool="search_entities",  # or use EntityResolver directly
                tool_input={
                    "entity_type": entity_type,
                    "query": entity_hint,
                    "limit": 10,
                },
                expected_output="entity_list",
            )],
            synthesis_approach="present_candidates",
            quality_checks=["no_fabrication", "not_all_zero"],
            estimated_duration_ms=2000,
        )
```

If a dedicated `search_entities` tool does not exist, use the existing `EntityResolver.resolve_project` directly:

```python
# In gateway/intelligent_handler.py — handle search_entity action

if intent.primary_action == "search_entity":
    entity_hint = intent.entities[0].value if intent.entities else ""
    entity_type = intent.entities[0].type if intent.entities else "project"
    
    if entity_type == "project":
        result = await self.entity_resolver.resolve_project(
            query=entity_hint,
            context=context,
            min_confidence=0.3,  # Show even weak matches as candidates
        )
        
        # Return as candidates for user to pick
        return self._build_search_response(result, intent, context)
    
    # ... handle other entity types ...
```

**Acceptance Tests:**
```python
async def test_search_entity_action_routes_to_search():
    intent = Intent(
        primary_action="search_entity",
        subject_area="project",
        entities=[EntityReference(type="project", value="General maintenance")],
    )
    strategy = await planner.plan(intent, context)
    
    # Must NOT be get_project_expense_summary
    assert strategy.steps[0].tool != "get_project_expense_summary"
    assert strategy.steps[0].tool in ("search_entities", "list_projects")


async def test_general_maintenance_returns_candidates():
    """User searching general term gets list, not specific project data."""
    result = await chat("show me general maintenance projects", user=super_admin)
    
    # Should be a list/candidates, not a single project's expense data
    assert result.visual_type in ("PROJECT_LIST", "CANDIDATE_LIST", "ENTITY_OPTIONS")
    assert result.visual_type != "PROJECT_EXPENSE_SUMMARY"
```

**Live Test:**
```
"General maintenance work expense report"
```
Expected: List of projects containing "general maintenance" with clickable options.
NOT expected: Random project's expense data shown directly.

**Done When:** Unit tests pass + live test returns a candidate list.

---

## 6. FIX 4 — Quality Gate Catches Zero-Data Fabrication

**Symptom:**
```
Quality gate: 7/8 checks passed (pass_rate=0.875)
Response shown to user:
  "Villa No. 48 ... total spend is AED 0 (0.0% of W.O AED 0). 
   Status: on track."

AED 0 on AED 0 budget is not "on track" — it is "no data."
```

**Root Cause:**
The 8 quality checks (from AI Core Architecture Phase 5) do not include a sanity check for "all numeric values returned are 0 AND the response claims success."

**Fix:**

```python
# In gateway/core/quality_gate.py

class QualityGate:
    QUALITY_CHECKS = [
        "no_fabrication",
        "data_consistency",
        "appropriate_detail",
        "no_raw_syntax",
        "actionable_suggestions",
        "honest_about_uncertainty",
        "right_visualization",
        "clear_language",
        "not_all_zero",  # NEW
    ]
    
    async def _check_not_all_zero(self, response, intent, context):
        """
        If response shows all zero numeric values AND claims success/positive 
        status, this is suspicious — likely missing data or wrong entity.
        """
        viz = response.visualization or {}
        
        # Extract all numeric values from viz
        kpis = viz.get("kpis", {}) or {}
        numeric_values = []
        for kpi in kpis.values():
            if isinstance(kpi, dict):
                v = kpi.get("value")
                if isinstance(v, (int, float)):
                    numeric_values.append(v)
        
        # Also check direct fields
        for k in ("wo_amount", "total_expenses", "total", "amount", "balance"):
            v = viz.get(k)
            if isinstance(v, (int, float)):
                numeric_values.append(v)
        
        if not numeric_values:
            return CheckResult(name="not_all_zero", passed=True)
        
        all_zero = all(v == 0 for v in numeric_values)
        
        # Check if response claims success despite all zeros
        text_lower = (response.narrative or "").lower()
        SUCCESS_LANGUAGE = ["on track", "healthy", "good shape", "no concerns"]
        claims_success = any(s in text_lower for s in SUCCESS_LANGUAGE)
        
        if all_zero and claims_success:
            return CheckResult(
                name="not_all_zero",
                passed=False,
                issue=(
                    "Response shows all-zero values but claims success status. "
                    "This is likely a missing-data scenario, not a real result. "
                    "Should say 'no data found' or verify entity is correct."
                ),
            )
        
        # Also flag if W.O is 0 AND spent is 0 even without success language
        wo = viz.get("wo_amount") or viz.get("kpis", {}).get("wo_amount", {}).get("value")
        spent = viz.get("total_expenses") or viz.get("kpis", {}).get("total_expenses", {}).get("value")
        if wo == 0 and spent == 0:
            return CheckResult(
                name="not_all_zero",
                passed=False,
                issue=(
                    "Both W.O Amount and Total Spent are zero. "
                    "Project may have no W.O assigned, no expenses logged, "
                    "or wrong entity was matched. Verify before presenting as result."
                ),
            )
        
        return CheckResult(name="not_all_zero", passed=True)
```

When this check fails, the retry handler should:

```python
# In gateway/core/quality_gate.py — RetryHandler

async def retry_with_feedback(self, response, review, context):
    failed_issues = [c.issue for c in review.checks if not c.passed]
    
    feedback_prompt = f"""
Your previous response had these issues:
{chr(10).join(failed_issues)}

If the issue is "all zero values":
- This usually means the project/entity has no data OR you matched the wrong entity
- Instead of saying "on track" with zero values, be honest:
  "I found [entity] but there is no expense data recorded for it. 
   This could mean the project has not started, data is in a 
   different system, or I matched the wrong project. Want me to verify?"
- Or surface the issue for user to confirm

Revise the response.
"""
    # ... existing retry logic ...
```

**Acceptance Tests:**
```python
async def test_zero_values_with_success_fails_quality():
    response = SynthesizedResult(
        narrative="Villa 48: total spend AED 0 of W.O AED 0. Status: on track.",
        visualization={
            "kpis": {
                "wo_amount": {"value": 0},
                "total_expenses": {"value": 0},
            },
        },
    )
    review = await gate.review(response, intent, context)
    
    assert not review.passed
    assert any("not_all_zero" in c.name for c in review.checks if not c.passed)


async def test_zero_values_without_success_still_fails():
    """Even without 'on track', zero W.O + zero spent is suspicious."""
    response = SynthesizedResult(
        narrative="Villa 48 expenses: AED 0 spent of AED 0 budget.",
        visualization={"wo_amount": 0, "total_expenses": 0},
    )
    review = await gate.review(response, intent, context)
    assert not review.passed


async def test_real_zero_spent_with_real_budget_passes():
    """Project with budget but no spend yet should pass."""
    response = SynthesizedResult(
        narrative="Villa 48: spent AED 0 of AED 100,000 W.O budget. Project not yet started.",
        visualization={
            "kpis": {
                "wo_amount": {"value": 100000},
                "total_expenses": {"value": 0},
            },
        },
    )
    review = await gate.review(response, intent, context)
    assert review.passed
```

**Live Test:**
```
"Show me [project that has 0 W.O and 0 spent]"
```
Expected: "I found this project but there's no expense data — possibly not started, or you may want to verify. Want me to check related projects?"
NOT expected: "AED 0 of AED 0 — on track."

**Done When:** Tests pass + live test shows honest "no data" response.

---

## 7. FIX 5 — Suppress Premature Format Clarifications

**Symptom:**
```
Turn 5 log:
  query: "General maintenance work - Al Mushrif need expense report"
  clarification_question: "I found your request for Al Mushrif maintenance 
                          project expenses. Could you please confirm the 
                          exact project name or provide the project ID? 
                          Also, would you prefer the report in PDF or 
                          Excel format?"

User has not yet seen any data. System has not yet resolved the entity.
Asking about PDF vs Excel is premature and confusing.
```

**Root Cause:**
IntentAnalyzer treats `output_format` ambiguity as a blocking clarification. Format choice should come AFTER data is shown (as a suggestion), not before resolution.

**Fix:**

```python
# In gateway/core/intent_analyzer.py — update the prompt

INTENT_ANALYZER_PROMPT_ADDITIONS = """
CLARIFICATION RULES:

1. ENTITY ambiguity → requires_clarification=true ONLY IF user role 
   demands confirmation (non-super-admin). Super admin: try to resolve.

2. PERIOD ambiguity → DO NOT clarify. Use sensible default (last 3 months).
   Mention the default in response, offer to change.

3. OUTPUT FORMAT ambiguity → NEVER clarify upfront. 
   Format choice comes AFTER data is shown, as a suggestion:
   "Want this as PDF or Excel?"
   NOT as a blocking question before showing anything.

4. SCOPE ambiguity (summary vs detailed) → use sensible default 
   (summary first, offer drill-down as suggestion).

5. Multiple ambiguities → clarify the highest-severity one only.
   Never ask 2+ questions in one clarification.

WHEN IN DOUBT: 
  - Resolve and show data
  - Mention assumptions inline ("Using last 3 months by default")
  - Offer changes as suggestions
"""
```

Also explicit in intent schema:

```python
# Type hint: format clarifications should never appear in
# clarification_question field

def _validate_clarification(intent: Intent) -> Intent:
    """Strip premature format clarifications."""
    if not intent.clarification_question:
        return intent
    
    q_lower = intent.clarification_question.lower()
    FORMAT_KEYWORDS = ["pdf", "excel", "format", "csv", "xlsx", "download"]
    
    # If clarification is ONLY about format, remove it
    if any(kw in q_lower for kw in FORMAT_KEYWORDS):
        # Check if it's ONLY about format (not also about entity)
        ENTITY_KEYWORDS = ["which", "what project", "what client", "specify"]
        is_entity_clarification = any(kw in q_lower for kw in ENTITY_KEYWORDS)
        
        if not is_entity_clarification:
            # Pure format question — defer to suggestions
            intent.clarification_question = None
            intent.requires_clarification = False
        else:
            # Mixed: keep entity part, strip format part
            # (Simple heuristic — could split sentences)
            sentences = intent.clarification_question.split(".")
            kept = [
                s for s in sentences 
                if not any(kw in s.lower() for kw in FORMAT_KEYWORDS)
            ]
            intent.clarification_question = ".".join(kept).strip()
    
    return intent


# Call this after IntentAnalyzer returns
intent = await self.intent_analyzer.analyze(query, context)
intent = _validate_clarification(intent)
```

**Acceptance Tests:**
```python
def test_pure_format_clarification_stripped():
    intent = Intent(
        requires_clarification=True,
        clarification_question="Would you prefer PDF or Excel format?",
        # ... other fields ...
    )
    cleaned = _validate_clarification(intent)
    assert not cleaned.requires_clarification
    assert cleaned.clarification_question is None


def test_entity_clarification_kept():
    intent = Intent(
        requires_clarification=True,
        clarification_question="Which Al Mushrif project did you mean?",
    )
    cleaned = _validate_clarification(intent)
    assert cleaned.requires_clarification
    assert "Al Mushrif" in cleaned.clarification_question


def test_mixed_clarification_keeps_entity_strips_format():
    intent = Intent(
        requires_clarification=True,
        clarification_question=(
            "Could you confirm which Al Mushrif project. "
            "Also, would you prefer PDF or Excel format?"
        ),
    )
    cleaned = _validate_clarification(intent)
    assert "Al Mushrif" in cleaned.clarification_question
    assert "PDF" not in cleaned.clarification_question
    assert "Excel" not in cleaned.clarification_question
```

**Live Test:**
```
"expense report for Zayidia Boys School"
```
Expected: Direct response with expense data. Suggestions include "Download as PDF" / "Download as Excel" if relevant.
NOT expected: "Would you prefer PDF or Excel?" as a blocking question.

**Done When:** Tests pass + live test shows data before any format question.

---

# PART III — IMPLEMENTATION PHASES

## 8. Build Order (1.5 Weeks)

### Phase F1 — Cache Integrity (Days 1-2)

```
[ ] Find current cache implementation in gateway/main.py
[ ] Implement _build_tool_cache_key with entity inclusion
[ ] Add ENTITY_CACHE_TTL_SECONDS limit
[ ] Wire cache invalidation on topic shift (depends on Fix 2)
[ ] Write 3 unit tests
[ ] Tests pass
[ ] Live verification: Villa 48 → Al Mushrif → Hatta Hospital all return distinct data

TESTS:
1. test_different_projects_dont_share_cache (integration)
2. test_cache_key_includes_entity (unit)
3. test_no_entity_in_input_uses_safe_key (unit)

LIVE TEST:
Sequence of 3 distinct project queries in same session.
All 3 return different project data.

DONE WHEN: All pass.
```

### Phase F2 — Topic-Shift Detection (Days 3-4)

```
[ ] Add WorkingMemory.detect_topic_shift() method
[ ] Add WorkingMemory.clear_entity_context() method
[ ] Wire into IntelligentQueryHandler before entity resolution
[ ] Add SHIFT_MARKERS list (English + Arabic)
[ ] Ensure EntityGate always runs when intent has entities
[ ] Write 4 unit tests
[ ] Tests pass
[ ] Live verification: "Villa 48 ... now General maintenance" doesn't reuse Villa 48

TESTS:
1. test_explicit_now_triggers_topic_shift
2. test_no_entity_overlap_triggers_shift
3. test_same_entity_no_shift
4. test_entity_gate_runs_after_topic_shift (integration)

LIVE TEST:
Turn 1: Villa 48 expense → returns Villa 48 data
Turn 2: now General maintenance → returns search/candidates, NOT Villa 48
Turn 3: show the breakdown → uses turn 2's resolved entity

DONE WHEN: All pass.
```

### Phase F3 — search_entity Routing (Day 5)

```
[ ] Update StrategyPlanner.plan() to route by primary_action first
[ ] Add _plan_entity_search method
[ ] Either: create search_entities tool wrapping EntityResolver
   OR: handle directly in IntelligentQueryHandler
[ ] Add visualization type ENTITY_CANDIDATES for results
[ ] Write 2 unit tests + 1 integration test
[ ] Tests pass
[ ] Live verification: "general maintenance projects" returns list, not random data

TESTS:
1. test_search_entity_action_routes_to_search
2. test_general_maintenance_returns_candidates (integration)

LIVE TEST:
"General maintenance work expense report"
Expected: Candidate list of matching projects.

DONE WHEN: All pass.
```

### Phase F4 — Zero-Data Quality Check (Days 6-7)

```
[ ] Add not_all_zero check to QualityGate.QUALITY_CHECKS
[ ] Implement _check_not_all_zero method
[ ] Update RetryHandler.retry_with_feedback for zero-data scenario
[ ] Add honesty message template for zero-data case
[ ] Write 3 unit tests + 1 integration test
[ ] Tests pass
[ ] Live verification: project with AED 0 / AED 0 returns honest message

TESTS:
1. test_zero_values_with_success_fails_quality
2. test_zero_values_without_success_still_fails
3. test_real_zero_spent_with_real_budget_passes
4. test_quality_gate_retries_on_zero_data (integration)

LIVE TEST:
Query a project known to have zero W.O and zero spend.
Response must say "no expense data" or similar honesty,
NOT "AED 0 of AED 0 — on track."

DONE WHEN: All pass.
```

### Phase F5 — Suppress Premature Format Clarifications (Day 8)

```
[ ] Add _validate_clarification post-processor
[ ] Wire after IntentAnalyzer.analyze call
[ ] Update INTENT_ANALYZER_PROMPT with new clarification rules
[ ] Write 3 unit tests
[ ] Tests pass
[ ] Live verification: "expense report" doesn't ask PDF/Excel upfront

TESTS:
1. test_pure_format_clarification_stripped
2. test_entity_clarification_kept
3. test_mixed_clarification_keeps_entity_strips_format

LIVE TEST:
"expense report for Zayidia Boys School"
Expected: Data first, format option as suggestion.
NOT expected: "PDF or Excel?" as upfront question.

DONE WHEN: All pass.
```

### Phase F6 — Full Integration Verification (Day 9-10)

```
[ ] Re-run the EXACT 5-query sequence from the bug report:
    1. "Villa Maintenance No. 48 expense for this year"
    2. "General maintenance work need expense report"
    3. "now General maintenance work"
    4. "give General maintenance work need expense report"
    5. "General maintenance work - Al Mushrif need expense report"

[ ] Each must behave correctly per acceptance criteria:
    Query 1: Returns Villa 48 expense data (or honest "no data" if zero)
    Query 2: Asks ONE entity clarification (NOT format)
    Query 3: Recognizes topic shift, returns search candidates
    Query 4: Either shows candidates or shows resolved project — NOT Villa 48
    Query 5: Resolves Al Mushrif specifically, shows data — NOT Villa 48

[ ] Update CURRENT_PHASE.md
[ ] Commit final state
[ ] Document any remaining edge cases in PARKING_LOT.md

DONE WHEN: All 5 queries behave correctly back-to-back.
```

---

# PART IV — WHAT TO DO RIGHT NOW

## 9. Tell Cursor

```
Read CONVERSATION_INTEGRITY_FIX_PLAN.md.

This is a 1.5-week bug-fix sprint. NOT new architecture.

It must be completed BEFORE the Elrace Omni-Agent Final Plan.

CRITICAL: All 5 fixes target bugs revealed by the Villa 48 incident
logs from 2026-06-09. Each bug is documented with file location, 
symptom, and fix.

Start Phase F1: Cache Integrity (Days 1-2).

Steps:
1. Find the current tool response cache implementation in 
   gateway/main.py (or wherever caching lives)
2. Show me the current cache code BEFORE changing anything
3. Propose the new cache key implementation
4. Wait for my approval before changing
5. Implement with tests
6. Tests must pass
7. Live verify: 3 distinct project queries return 3 distinct results
8. Then move to Phase F2

Rules:
- One phase at a time
- Tests must pass before live test
- Live test must pass before next phase
- Update CURRENT_PHASE.md after each phase
- No new features, no architectural changes, just these 5 fixes

After all 6 phases done (~10 working days), report back. Then we
move to the Elrace Omni-Agent Final Plan with a solid foundation.
```

---

# PART V — AFTER THIS PLAN

```
Once these 5 fixes ship:

Foundation is solid:
  ✓ Cache integrity (no cross-entity contamination)
  ✓ Topic-shift handling (user can change subjects naturally)
  ✓ Search routing (search queries get search results)
  ✓ Zero-data honesty (no fake "on track" on empty data)
  ✓ Format-question timing (data first, format later)

THEN proceed in this order:

1. ELRACE_OMNI_AGENT_FINAL_PLAN.md (3 weeks)
   Build the 4 universal tools on a solid foundation.
   
2. Continue Phase 9 / Phase 10 from AI_CORE plan if not done.

3. PROJECT_EXPENSE_INTELLIGENCE_PLAN refinements based on 
   real usage.

4. UI improvements based on live feedback.

Sequencing matters. Foundation → universal access → polish.
We do not extend a broken foundation.
```

---

# PART VI — WHY THESE FIVE FIXES, NOT MORE

```
What I deliberately did NOT include in this plan:

✗ Refactoring WorkingMemory entirely
  → Too big, current structure works once topic-shift is wired

✗ Rebuilding the cache layer
  → Just fix the key. Don't redesign.

✗ Rewriting EntityResolver
  → Already working. Just ensure it always runs.

✗ New visualization types
  → ENTITY_CANDIDATES might exist; if not, simple list works

✗ Touching the Visualize agent
  → Unrelated to these bugs

✗ Major changes to IntelligentQueryHandler
  → Just add topic-shift check before entity gate

Discipline: smallest possible change for each bug.
1.5 weeks total. Then move on.
```

This sprint is the floor. After it, every other plan stands on solid ground.
