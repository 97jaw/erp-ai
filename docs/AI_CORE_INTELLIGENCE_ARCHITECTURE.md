# AI CORE INTELLIGENCE ARCHITECTURE

> **The Mission:** Rebuild the intelligence layer from single-shot tool calling to a true reasoning system. After this rebuild, the AI thinks before responding, verifies before asserting, learns from each interaction, knows its own limits, and responds like a senior management consultant working alongside a CFO's chief of staff.

> **Quality Bar:** "Senior management consultant + CFO's chief of staff" — proactive, precise, honest, anticipatory. Never fabricates. Always verifies. Maximally useful within capability bounds.

> **Failure Modes Authorized:** B (always help with what's possible) + C (ask if ambiguous, honest if impossible). Never A alone (just saying "I don't know" without trying).

> **Scope:** 8-10 week rebuild. Significant code changes. Existing tests rewritten. This is the most important plan in the project.

> **Read first:** `PROJECT_CONTEXT.md`, `PRODUCT_QUALITY_FRAMEWORK.md`, `QUERY_RESPONSE_INTELLIGENCE_PLAN.md`

---

# PART I — STRATEGIC PRINCIPLES

## 1. The Ten Commandments of This Architecture

```
1. THINK BEFORE ACTING
   Every non-trivial query gets a plan before execution.
   Plans are explicit, verifiable, and revisable.

2. VERIFY BEFORE ASSERTING
   Numbers are checked. Periods are confirmed. 
   Names are resolved. Then we speak.

3. NEVER FABRICATE
   When something is unavailable, say so honestly.
   No fake errors. No imaginary capabilities.
   No "try again later" excuses.

4. USE MULTIPLE TOOLS NATURALLY
   Real analysts use 5 tools to answer 1 question.
   We orchestrate, not single-shot.

5. KNOW WHO YOU ARE TALKING TO
   Super admin vs junior user vs guest get different responses.
   Same query → different depth, defaults, and assumptions.

6. KNOW WHAT YOU CAN DO
   Capability manifest is explicit and current.
   Unavailable features acknowledged honestly with roadmap.

7. SELF-CRITIQUE BEFORE SHOWING
   Bad responses caught internally and revised.
   User sees the final, not the draft.

8. LEARN FROM PATTERNS
   What worked for this user? What strategy succeeded?
   Apply learnings to next interactions.

9. ANTICIPATE THE NEXT QUESTION
   The best assistant prepares the next move proactively.
   Surface follow-ups as suggestions before asked.

10. HONESTY IS INTELLIGENCE
    "I don't know" is intelligent.
    "Let me verify" is intelligent.
    "I cannot do this but here's what I can do" is intelligent.
    Faking confidence is the worst behavior.
```

## 2. The Architectural Shift

```
OLD ARCHITECTURE (what we have):
┌─────────────────────────────────────┐
│ User query                          │
│   ↓                                 │
│ Claude.messages.create()            │
│   ↓                                 │
│ Tool call (single, sometimes 2-3)   │
│   ↓                                 │
│ Tool result                         │
│   ↓                                 │
│ Claude formats response             │
│   ↓                                 │
│ Return to user                      │
└─────────────────────────────────────┘

Problems:
  - No reasoning checkpoint
  - No verification
  - No quality gate
  - No context awareness
  - No self-correction
  - No learning

NEW ARCHITECTURE (target):
┌─────────────────────────────────────────────────────┐
│ User query                                          │
│   ↓                                                 │
│ Context Stack Builder                               │
│   (user, permissions, history, preferences, tools)  │
│   ↓                                                 │
│ Intent Analyzer                                     │
│   (what does user actually want?)                   │
│   ↓                                                 │
│ Strategy Planner                                    │
│   (single-shot or multi-step?)                      │
│   ↓                                                 │
│ Execution Orchestrator                              │
│   (run tools, handle failures, verify outputs)      │
│   ↓                                                 │
│ Result Synthesizer                                  │
│   (combine multiple tool outputs intelligently)     │
│   ↓                                                 │
│ Quality Gate                                        │
│   (self-critique, retry if below bar)               │
│   ↓                                                 │
│ Response Composer                                   │
│   (narrative + visualization + suggestions)         │
│   ↓                                                 │
│ Proactive Layer                                     │
│   (anticipate next, prepare follow-ups)             │
│   ↓                                                 │
│ Telemetry Capture                                   │
│   (track for learning)                              │
│   ↓                                                 │
│ Return to user                                      │
└─────────────────────────────────────────────────────┘
```

---

# PART II — THE CONTEXT STACK

## 3. What Context Means

Every query the AI processes must include a rich context block. Not just "previous messages" — but a full structured view of who, what, when, and how.

```python
# core/context_stack.py

@dataclass
class ContextStack:
    """
    Complete context for a single query.
    Built fresh for every turn.
    """
    # Identity
    user: UserContext
    
    # Conversation
    conversation: ConversationContext
    
    # Capabilities
    capability_manifest: CapabilityManifest
    
    # Memory
    working_memory: WorkingMemory
    
    # Business
    business_context: BusinessContext
    
    # Time
    temporal_context: TemporalContext
    
    # Quality
    quality_targets: QualityTargets
    
    def to_prompt_section(self) -> str:
        """Format for inclusion in Claude system prompt."""
        return f"""
=== USER CONTEXT ===
{self.user.summary()}

=== CONVERSATION CONTEXT ===
{self.conversation.summary()}

=== CAPABILITIES ===
{self.capability_manifest.summary()}

=== WORKING MEMORY ===
{self.working_memory.summary()}

=== BUSINESS CONTEXT ===
{self.business_context.summary()}

=== TEMPORAL CONTEXT ===
{self.temporal_context.summary()}

=== QUALITY TARGETS ===
{self.quality_targets.summary()}
"""
```

## 4. UserContext — Who Is Asking

```python
@dataclass
class UserContext:
    user_id: int
    name: str
    file_id: str
    
    # Role hierarchy
    primary_role: str           # "super_admin", "top_management", etc.
    level: int                   # 100, 70, 50, etc.
    permissions: set[str]        # All effective permissions
    
    # Department
    primary_department: str      # "Finance", "PM", etc.
    departments: list[str]
    
    # Preferences (from memory)
    preferred_language: str      # "en" or "ar"
    preferred_currency: str      # "AED"
    default_date_range: str      # "last_3_months"
    response_style: str          # "brief" or "detailed"
    
    # History
    last_login: datetime
    typical_queries: list[str]   # What this user usually asks
    
    def assumption_level(self) -> str:
        """How aggressively should AI make assumptions?"""
        if self.level >= 70:  # Top mgmt + super admin
            return "aggressive"  # Make assumptions, act fast
        if self.level >= 50:  # Managers
            return "moderate"    # Verify when ambiguous
        return "conservative"    # Always confirm
    
    def access_breadth(self) -> str:
        """What scope of data can they see?"""
        if "data.all_projects" in self.permissions:
            return "all"
        if "data.own_department_only" in self.permissions:
            return "department"
        return "limited"
    
    def summary(self) -> str:
        return f"""
User: {self.name} (File ID: {self.file_id})
Role: {self.primary_role} (level {self.level})
Department: {self.primary_department}
Assumption Level: {self.assumption_level()}
Data Access: {self.access_breadth()}
Language: {self.preferred_language}
Style: {self.response_style}

CRITICAL: 
- This user is a {self.primary_role}. 
- Apply {self.assumption_level()} assumption level.
- {self.behavior_rules()}
"""
    
    def behavior_rules(self) -> str:
        if self.level >= 70:
            return """
- Resolve ambiguous queries by SEARCHING, not asking
- Show top match + alternatives, do NOT ask for exact name
- Default to all-data view unless specified
- Skip basic clarifications they obviously don't need
- Provide insights, not just data
"""
        if self.level >= 50:
            return """
- Try to resolve, but confirm when ambiguous
- Show top 3 matches if uncertain
- Department-scoped data by default
"""
        return """
- Be explicit about scope and data shown
- Confirm interpretation before fetching
- Educate about available features
"""
```

## 5. CapabilityManifest — What I Can Do

```python
@dataclass
class CapabilityManifest:
    """
    Explicit inventory of what's available and what isn't.
    Updated as features ship.
    """
    available: list[Capability]
    unavailable: list[Capability]
    coming_soon: list[Capability]
    
    def can_do(self, capability_code: str) -> bool:
        return capability_code in {c.code for c in self.available}
    
    def status_of(self, capability_code: str) -> str:
        for c in self.available:
            if c.code == capability_code:
                return "available"
        for c in self.coming_soon:
            if c.code == capability_code:
                return "coming_soon"
        for c in self.unavailable:
            if c.code == capability_code:
                return "unavailable"
        return "unknown"
    
    def summary(self) -> str:
        """For inclusion in Claude system prompt."""
        return f"""
WHAT YOU CAN DO:
{self._format_list(self.available)}

WHAT YOU CANNOT DO (be honest if asked):
{self._format_list(self.unavailable)}

WHAT'S COMING SOON (mention when relevant):
{self._format_list(self.coming_soon)}

CRITICAL RULES:
- If asked about an "unavailable" capability:
  → State honestly it's not available
  → Suggest alternative if any
  → Offer to track when ready
  → DO NOT FABRICATE FAKE ERRORS like "database issue"

- If asked about "coming_soon" capability:
  → Acknowledge it's in development
  → Provide ETA if known
  → Suggest workaround
"""


# Initial manifest
CAPABILITY_MANIFEST = CapabilityManifest(
    available=[
        Capability("financial.pandl", "Profit & Loss reports"),
        Capability("financial.balance_sheet", "Balance Sheet"),
        Capability("financial.cash_flow", "Cash Flow Statement"),
        Capability("financial.trial_balance", "Trial Balance"),
        Capability("financial.general_ledger", "General Ledger"),
        Capability("project.financials", "Project financial data"),
        Capability("project.search", "Project search by name/code"),
        Capability("partner.search", "Customer/Vendor search"),
        Capability("partner.ageing", "Receivables/Payables ageing"),
        Capability("partner.ledger", "Partner transaction history"),
        Capability("reports.generate_pdf", "PDF report generation"),
        Capability("reports.generate_excel", "Excel export"),
        Capability("voice.input", "Voice query input"),
        Capability("voice.output", "Voice response output"),
        Capability("language.arabic", "Arabic language support"),
        Capability("language.english", "English language support"),
    ],
    unavailable=[
        Capability("hr.payslips", "Payslip access",
            alternative="Use the HR portal directly at hr.elrace.com",
            roadmap="Q3 2026"),
        Capability("hr.attendance", "Attendance records",
            alternative="Use HR portal",
            roadmap="Q3 2026"),
        Capability("hr.leave_balance", "Leave balance",
            alternative="Use HR portal",
            roadmap="Q3 2026"),
        Capability("inventory.stock", "Inventory levels",
            alternative="Use Odoo Inventory module directly",
            roadmap="Q4 2026"),
        Capability("crm.opportunities", "Sales opportunities",
            alternative="Use CRM module",
            roadmap="Q4 2026"),
        Capability("write.create_invoice", "Create invoices",
            alternative="Use Odoo directly",
            roadmap="Q4 2026"),
        Capability("write.approve_payments", "Approve payments",
            alternative="Use Odoo approval flow",
            roadmap="2027"),
    ],
    coming_soon=[
        Capability("integrations.outlook_email", "Outlook email sync",
            eta="Q2 2026"),
        Capability("integrations.whatsapp", "WhatsApp delivery",
            eta="Q3 2026"),
        Capability("dashboards.custom", "Custom dashboards",
            eta="Q3 2026"),
        Capability("forecasting.cash_flow", "Cash flow forecasting",
            eta="Q4 2026"),
    ],
)
```

## 6. WorkingMemory — What I've Learned

```python
@dataclass
class WorkingMemory:
    """
    Beyond conversation history.
    Patterns, preferences, recent context.
    """
    # Per-user persistent
    user_patterns: dict          # "always asks about Zayidia project"
    user_preferences: dict       # "wants Excel for >50 rows"
    
    # Current session
    recent_entities: list        # Recently referenced projects, partners
    recent_periods: list         # Date ranges used this session
    session_facts: dict          # Things established this session
    
    # Strategy memory
    successful_strategies: dict  # What worked: {query_type: strategy}
    failed_strategies: dict      # What didn't: avoid repeating
    
    def remember_entity(self, entity_type: str, entity: dict):
        """Add to recent entities for quick reference."""
        self.recent_entities.append({
            "type": entity_type,
            "data": entity,
            "timestamp": datetime.now(),
        })
        # Keep last 10
        self.recent_entities = self.recent_entities[-10:]
    
    def find_entity(self, hint: str, entity_type: str = None):
        """Look for recently mentioned entity matching hint."""
        for entity in reversed(self.recent_entities):
            if entity_type and entity["type"] != entity_type:
                continue
            if self._matches(entity["data"], hint):
                return entity["data"]
        return None
    
    def summary(self) -> str:
        return f"""
RECENT ENTITIES (last 10):
{self._format_entities()}

SESSION FACTS:
{self._format_session_facts()}

KNOWN USER PATTERNS:
{self._format_patterns()}

SUCCESSFUL STRATEGIES:
{self._format_strategies()}
"""
```

## 7. BusinessContext — Where We Are

```python
@dataclass
class BusinessContext:
    """
    Information about the business that shapes responses.
    """
    company_name: str = "Elrace Cos. & Gen. Cont. CO."
    company_id: int = 1
    currency: str = "AED"
    fiscal_year_start: int = 1  # January
    fiscal_year_end: int = 12   # December
    
    # Industry knowledge
    industry: str = "Construction & Facilities Management"
    geography: str = "UAE"
    
    # Key business rules
    business_norms: dict = field(default_factory=lambda: {
        "healthy_gross_margin": (15, 30),  # 15-30% normal for construction
        "concerning_dso": 90,                # >90 days is concerning
        "vat_rate": 5,                      # UAE VAT 5%
        "weekend": ["Friday", "Saturday"],
    })
    
    # Top entities (for quick reference)
    top_clients: list = field(default_factory=lambda: [
        "Abu Dhabi Police",
        "National Guard",
        "Civil Defense",
        "Ministry of Interior",
    ])
    
    def summary(self) -> str:
        return f"""
Company: {self.company_name}
Currency: {self.currency}
Fiscal Year: Jan-Dec
Industry: {self.industry}
Geography: {self.geography}

Healthy gross margin: {self.business_norms['healthy_gross_margin'][0]}-{self.business_norms['healthy_gross_margin'][1]}%
Concerning DSO threshold: {self.business_norms['concerning_dso']} days
"""
```

## 8. TemporalContext — When We Are

```python
@dataclass
class TemporalContext:
    """Time-aware context."""
    now: datetime
    today: date
    timezone: str = "Asia/Dubai"
    
    # Derived
    current_fiscal_year: int
    current_quarter: int
    current_month: int
    is_month_end: bool          # Last 3 days of month?
    is_quarter_end: bool
    is_year_end: bool
    business_day: bool
    
    # Default ranges
    last_3_months: tuple
    last_quarter: tuple
    last_year: tuple
    ytd: tuple
    
    def summary(self) -> str:
        return f"""
Current time: {self.now.strftime('%Y-%m-%d %H:%M')} {self.timezone}
Current fiscal year: {self.current_fiscal_year}
Current quarter: Q{self.current_quarter}
Period markers: month-end={self.is_month_end}, quarter-end={self.is_quarter_end}

When user says relative period, use:
  "last month" → {self.last_month}
  "last quarter" → {self.last_quarter}
  "last year" → {self.last_year}
  "this year" / "YTD" → {self.ytd}
  Without specification → last 3 months: {self.last_3_months}
"""
```

---

# PART III — THE REASONING ENGINE

## 9. Intent Analysis

Before executing, the AI must deeply understand the intent. Not just keywords.

```python
# core/intent_analyzer.py

class IntentAnalyzer:
    """
    Analyzes user query to extract structured intent.
    """
    
    def analyze(self, query: str, context: ContextStack) -> Intent:
        """
        Returns rich intent classification.
        """
        # Use Claude with focused prompt for intent analysis
        prompt = f"""
You are an intent analyzer. Extract structured intent from this query.

USER: {context.user.name} ({context.user.primary_role})
QUERY: {query}

Return JSON with:
{{
  "primary_action": "<one of: fetch_data, analyze, compare, generate_report, search_entity, explain, ask_question, other>",
  "subject_area": "<financial, project, hr, sales, inventory, etc.>",
  "specific_intent": "<concise description>",
  "entities": [
    {{"type": "project|partner|account|period|amount", "value": "...", "confidence": 0.0-1.0}}
  ],
  "implicit_requirements": [
    "<what user expects implicitly>"
  ],
  "ambiguities": [
    {{"type": "...", "description": "...", "severity": "low|medium|high"}}
  ],
  "expected_output": "<table|chart|summary|number|narrative|file>",
  "urgency": "low|normal|high",
  "estimated_complexity": "simple|moderate|complex",
  "requires_clarification": true/false,
  "clarification_question": "..." (if needed),
  "out_of_scope": true/false,
  "out_of_scope_reason": "..." (if applicable)
}}

CRITICAL ANALYSIS RULES:
1. Check capability manifest — is this within scope?
2. Identify ambiguities — what could be interpreted multiple ways?
3. Note implicit requirements — what does user expect without saying?
4. For super_admin/top_mgmt users: minimize required clarification
"""
        
        result = await claude.complete(prompt, response_format="json")
        return Intent.from_dict(result)


@dataclass
class Intent:
    primary_action: str
    subject_area: str
    specific_intent: str
    entities: list[EntityReference]
    implicit_requirements: list[str]
    ambiguities: list[Ambiguity]
    expected_output: str
    urgency: str
    estimated_complexity: str
    requires_clarification: bool
    clarification_question: str | None
    out_of_scope: bool
    out_of_scope_reason: str | None
```

## 10. Strategy Planning

For non-trivial queries, plan the approach before executing.

```python
# core/strategy_planner.py

class StrategyPlanner:
    """
    Plans how to fulfill the intent.
    """
    
    def plan(self, intent: Intent, context: ContextStack) -> Strategy:
        """
        Returns execution strategy.
        """
        # Simple queries: single tool
        if intent.estimated_complexity == "simple":
            return self.plan_simple(intent, context)
        
        # Complex queries: multi-step plan
        return self.plan_complex(intent, context)
    
    def plan_complex(self, intent: Intent, context: ContextStack) -> Strategy:
        prompt = f"""
You are a strategy planner. Given this intent, create a step-by-step plan.

INTENT: {intent.specific_intent}
ENTITIES: {intent.entities}
AVAILABLE TOOLS: {context.capability_manifest.tools_summary()}

Return JSON:
{{
  "steps": [
    {{
      "step_number": 1,
      "description": "What this step does",
      "tool": "tool_name",
      "tool_input": {{...}},
      "depends_on": [],  // step numbers
      "parallel_with": [],  // can run in parallel
      "expected_output": "...",
      "fallback_if_fails": "..."
    }}
  ],
  "synthesis_approach": "How to combine results",
  "quality_checks": [
    "Things to verify in the result"
  ],
  "estimated_duration_ms": 3000
}}

PLANNING RULES:
- Decompose complex queries into atomic steps
- Identify steps that can run in parallel
- Plan fallbacks for likely failures
- Include verification steps
- Keep total steps under 10
"""
        
        result = await claude.complete(prompt, response_format="json")
        return Strategy.from_dict(result)


@dataclass
class Strategy:
    steps: list[ExecutionStep]
    synthesis_approach: str
    quality_checks: list[str]
    estimated_duration_ms: int
```

## 11. Execution Orchestration

```python
# core/orchestrator.py

class ExecutionOrchestrator:
    """
    Executes the strategy with verification and error handling.
    """
    
    async def execute(self, strategy: Strategy, context: ContextStack) -> ExecutionResult:
        """
        Run the strategy, return results.
        """
        results = {}
        failures = []
        
        # Group steps by parallel-ability
        execution_groups = self._group_parallel_steps(strategy.steps)
        
        for group in execution_groups:
            if len(group) == 1:
                # Sequential
                step = group[0]
                result = await self._execute_step(step, results, context)
                results[step.step_number] = result
            else:
                # Parallel execution
                tasks = [self._execute_step(s, results, context) for s in group]
                step_results = await asyncio.gather(*tasks, return_exceptions=True)
                for step, result in zip(group, step_results):
                    if isinstance(result, Exception):
                        failures.append(StepFailure(step, result))
                        # Apply fallback
                        if step.fallback_if_fails:
                            fallback_result = await self._execute_fallback(
                                step.fallback_if_fails, results, context
                            )
                            results[step.step_number] = fallback_result
                    else:
                        results[step.step_number] = result
        
        # Verify quality
        verification = await self._verify_results(
            results, strategy.quality_checks, context
        )
        
        return ExecutionResult(
            results=results,
            failures=failures,
            verification=verification,
            strategy_used=strategy,
        )
    
    async def _execute_step(self, step, prior_results, context) -> dict:
        """
        Execute one step with retry logic.
        """
        # Resolve tool_input variables from prior results
        tool_input = self._resolve_variables(step.tool_input, prior_results)
        
        max_retries = 2
        for attempt in range(max_retries):
            try:
                result = await call_tool(step.tool, tool_input, context)
                
                # Validate result structure
                if self._is_empty_or_invalid(result):
                    if attempt < max_retries - 1:
                        # Try with broader parameters
                        tool_input = self._broaden_search(tool_input)
                        continue
                
                return result
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(0.5)  # Brief retry delay
```

---

# PART IV — ENTITY RESOLUTION

## 12. The Multi-Strategy Resolver

This solves the "national guard" problem.

```python
# core/entity_resolver.py

class EntityResolver:
    """
    Robust entity resolution with multiple strategies.
    Never gives up after one try.
    """
    
    async def resolve_project(
        self,
        query: str,
        context: ContextStack,
        min_confidence: float = 0.6
    ) -> ResolutionResult:
        """
        Find project(s) matching the query.
        Uses 5+ strategies in parallel.
        """
        strategies = [
            self._exact_phrase_match,
            self._all_words_match,
            self._any_word_match,
            self._fuzzy_match,
            self._acronym_match,
            self._arabic_english_equivalent,
            self._semantic_similarity,
            self._description_match,  # Match in project description, not just name
        ]
        
        # Run all strategies in parallel
        all_results = await asyncio.gather(
            *[strategy(query, context) for strategy in strategies]
        )
        
        # Merge and deduplicate
        merged = self._merge_results(all_results)
        
        # Score by confidence
        scored = self._score_matches(merged, query)
        
        # Filter by confidence
        confident = [m for m in scored if m.confidence >= min_confidence]
        
        # Apply user-level filtering
        accessible = self._filter_by_permissions(confident, context.user)
        
        return ResolutionResult(
            query=query,
            total_matches=len(merged),
            confident_matches=accessible,
            top_match=accessible[0] if accessible else None,
            confidence=accessible[0].confidence if accessible else 0,
            ambiguity_level=self._calculate_ambiguity(accessible),
            strategies_used=[s.__name__ for s in strategies],
        )
    
    async def _exact_phrase_match(self, query, context):
        """Try exact phrase first."""
        return await search_projects(domain=[
            ["name", "ilike", query]
        ])
    
    async def _all_words_match(self, query, context):
        """All words must be present, any order."""
        words = query.split()
        domain = [
            ["name", "ilike", word] for word in words
        ]
        # Build AND condition
        if len(words) > 1:
            domain = ["&"] * (len(words) - 1) + domain
        return await search_projects(domain=domain)
    
    async def _any_word_match(self, query, context):
        """Any word match (broader)."""
        words = query.split()
        domain = [
            ["name", "ilike", word] for word in words
        ]
        if len(words) > 1:
            domain = ["|"] * (len(words) - 1) + domain
        return await search_projects(domain=domain)
    
    async def _fuzzy_match(self, query, context):
        """Levenshtein/similarity matching."""
        all_projects = await search_projects(domain=[])
        from difflib import SequenceMatcher
        
        scored = []
        for project in all_projects:
            ratio = SequenceMatcher(None, query.lower(), project["name"].lower()).ratio()
            if ratio > 0.5:
                scored.append((project, ratio))
        
        return [p[0] for p in sorted(scored, key=lambda x: -x[1])[:20]]
    
    async def _acronym_match(self, query, context):
        """Check for acronyms like NGC, ADP, etc."""
        ACRONYM_MAP = {
            "ngc": "National Guard",
            "adp": "Abu Dhabi Police",
            "ngn": "National Guard Network",
            "moe": "Ministry of Education",
            "moi": "Ministry of Interior",
            "moh": "Ministry of Health",
            "cd": "Civil Defense",
        }
        
        query_lower = query.lower()
        # Check if query IS an acronym
        if query_lower in ACRONYM_MAP:
            expanded = ACRONYM_MAP[query_lower]
            return await self._all_words_match(expanded, context)
        
        # Check if query CONTAINS an acronym
        for acronym, expansion in ACRONYM_MAP.items():
            if acronym in query_lower.split():
                expanded = query_lower.replace(acronym, expansion)
                return await self._all_words_match(expanded, context)
        
        return []
    
    async def _arabic_english_equivalent(self, query, context):
        """Try Arabic equivalents."""
        ARABIC_EQUIVALENTS = {
            "national guard": ["الحرس الوطني"],
            "abu dhabi police": ["شرطة أبوظبي"],
            "civil defense": ["الدفاع المدني"],
            "ministry of education": ["وزارة التربية"],
        }
        
        results = []
        for english, arabics in ARABIC_EQUIVALENTS.items():
            if english in query.lower():
                for arabic in arabics:
                    arabic_results = await search_projects(
                        domain=[["name", "ilike", arabic]]
                    )
                    results.extend(arabic_results)
        return results
    
    async def _semantic_similarity(self, query, context):
        """
        For now, use Claude to assess relevance.
        Future: embedding-based similarity.
        """
        all_projects = await search_projects(domain=[], limit=200)
        
        prompt = f"""
Query: "{query}"
Projects: {json.dumps([{"id": p["id"], "name": p["name"]} for p in all_projects[:50]])}

Return the project IDs that are semantically relevant to the query.
Return JSON: {{"matches": [project_id, ...]}}
"""
        result = await claude.complete(prompt, response_format="json")
        ids = result.get("matches", [])
        return [p for p in all_projects if p["id"] in ids]
    
    async def _description_match(self, query, context):
        """Match in project description, agreement name, partner name."""
        return await search_projects(domain=[
            "|", "|",
            ["description", "ilike", query],
            ["agreement_name", "ilike", query],
            ["partner_id.name", "ilike", query],
        ])
    
    def _score_matches(self, matches, query):
        """Score each match by relevance."""
        scored = []
        query_lower = query.lower()
        query_words = set(query_lower.split())
        
        for match in matches:
            name_lower = match["name"].lower()
            
            # Exact match
            if name_lower == query_lower:
                confidence = 1.0
            # Starts with
            elif name_lower.startswith(query_lower):
                confidence = 0.9
            # Contains exact phrase
            elif query_lower in name_lower:
                confidence = 0.85
            # All words present
            elif all(word in name_lower for word in query_words):
                confidence = 0.75
            # Word overlap
            else:
                name_words = set(name_lower.split())
                overlap = len(query_words & name_words) / max(len(query_words), 1)
                confidence = overlap * 0.6
            
            scored.append(Match(
                entity=match,
                confidence=confidence,
                strategy=match.get("_strategy", "unknown")
            ))
        
        return sorted(scored, key=lambda m: -m.confidence)
    
    def _calculate_ambiguity(self, matches):
        """How ambiguous is the result set?"""
        if not matches:
            return "no_match"
        if len(matches) == 1:
            return "unambiguous"
        if matches[0].confidence > 0.9 and matches[1].confidence < 0.7:
            return "clear_winner"
        if all(m.confidence > 0.7 for m in matches[:3]):
            return "multiple_strong"
        return "weak_matches"
```

## 13. The Resolution Decision Tree

```python
class ResolutionStrategy:
    """
    Decides how to handle resolution results based on user role.
    """
    
    def decide(self, result: ResolutionResult, context: ContextStack) -> Decision:
        user_level = context.user.assumption_level()
        
        # No matches
        if not result.confident_matches:
            return Decision(
                action="search_broader",
                followup="If still nothing: be honest, ask for help",
            )
        
        # One unambiguous match
        if result.ambiguity_level == "unambiguous":
            return Decision(
                action="use_match",
                match=result.top_match,
                note=f"Resolved unambiguously to {result.top_match.entity['name']}",
            )
        
        # Clear winner
        if result.ambiguity_level == "clear_winner":
            if user_level == "aggressive":
                return Decision(
                    action="use_top_with_mention",
                    match=result.top_match,
                    note=f"Using top match (used {result.top_match.entity['name']}). "
                         f"Other candidates available if needed.",
                )
            else:
                return Decision(
                    action="confirm_top",
                    match=result.top_match,
                    alternatives=result.confident_matches[1:4],
                )
        
        # Multiple strong candidates
        if result.ambiguity_level == "multiple_strong":
            if user_level == "aggressive":
                # Show top 3, ask for pick
                return Decision(
                    action="quick_pick",
                    match=None,
                    alternatives=result.confident_matches[:3],
                    note="Multiple matches — pick one",
                )
            return Decision(
                action="show_candidates",
                alternatives=result.confident_matches[:5],
            )
        
        # Weak matches
        if result.ambiguity_level == "weak_matches":
            return Decision(
                action="broaden_or_clarify",
                alternatives=result.confident_matches[:3],
                note="No strong matches — try broader search or clarify",
            )
```

---

# PART V — RESULT SYNTHESIS

## 14. Combining Multiple Tool Outputs

```python
# core/synthesizer.py

class ResultSynthesizer:
    """
    Combines outputs from multiple tools into coherent response.
    """
    
    async def synthesize(
        self,
        execution_result: ExecutionResult,
        intent: Intent,
        context: ContextStack,
    ) -> SynthesizedResult:
        """
        Take raw tool outputs and create unified response.
        """
        # Build synthesis context
        synthesis_input = {
            "user_query": intent.specific_intent,
            "tool_results": execution_result.results,
            "failures": execution_result.failures,
            "verification": execution_result.verification,
        }
        
        # Use Claude to synthesize
        prompt = self._build_synthesis_prompt(synthesis_input, context)
        
        synthesized = await claude.complete(prompt)
        
        return SynthesizedResult(
            narrative=synthesized.text,
            visualization=synthesized.visualization,
            data_quality=self._assess_quality(execution_result),
            confidence=self._calculate_confidence(execution_result),
        )
    
    def _build_synthesis_prompt(self, input, context):
        return f"""
You are synthesizing results from multiple tool calls into a unified response.

USER QUERY: {input['user_query']}
USER ROLE: {context.user.primary_role}

TOOL RESULTS:
{json.dumps(input['tool_results'], indent=2)}

FAILURES (if any):
{input['failures']}

SYNTHESIS RULES:
1. Lead with the most important number/finding
2. Use specific, accurate numbers (no rounding errors)
3. If data has issues, mention them honestly
4. Apply business context (industry knowledge)
5. Choose right visualization for the data
6. Be concise — every sentence must earn its place
7. End with 3 actionable suggestions

OUTPUT FORMAT:
<narrative>
Your 2-4 sentence summary with key findings
</narrative>

<visualization>
{{visualization JSON object}}
</visualization>

<suggestions>
- Suggestion 1
- Suggestion 2
- Suggestion 3
</suggestions>
"""
```

---

# PART VI — THE QUALITY GATE

## 15. Self-Critique Before Showing User

This is critical. The user never sees the draft. They see the final.

```python
# core/quality_gate.py

class QualityGate:
    """
    Inspects responses BEFORE showing user.
    Retries if quality below threshold.
    """
    
    QUALITY_CHECKS = [
        "no_fabrication",
        "data_consistency",
        "appropriate_detail",
        "no_raw_syntax",
        "actionable_suggestions",
        "honest_about_uncertainty",
        "right_visualization",
        "clear_language",
    ]
    
    MIN_PASS_RATE = 0.85  # 85% of checks must pass
    
    async def review(
        self,
        synthesized: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
    ) -> QualityReview:
        """
        Run all quality checks. If below threshold, request revision.
        """
        check_results = []
        for check in self.QUALITY_CHECKS:
            result = await self._run_check(check, synthesized, intent, context)
            check_results.append(result)
        
        pass_rate = sum(1 for c in check_results if c.passed) / len(check_results)
        
        return QualityReview(
            checks=check_results,
            pass_rate=pass_rate,
            passed=pass_rate >= self.MIN_PASS_RATE,
            issues=[c.issue for c in check_results if not c.passed],
        )
    
    async def _run_check(self, check_name, response, intent, context):
        if check_name == "no_fabrication":
            return await self._check_no_fabrication(response)
        elif check_name == "data_consistency":
            return await self._check_data_consistency(response)
        # ... etc
    
    async def _check_no_fabrication(self, response):
        """
        Verify the AI didn't make up data.
        """
        prompt = f"""
Review this AI response for fabrication:

{response.narrative}

VISUALIZATION DATA:
{response.visualization}

Check for:
1. Numbers that weren't in tool results
2. Entity names that weren't in tool results
3. Made-up references or sources
4. Fictional error messages like "database issue"

Return JSON:
{{"passed": true/false, "issue": "..." (if failed)}}
"""
        result = await claude.complete(prompt, response_format="json")
        return CheckResult(
            name="no_fabrication",
            passed=result["passed"],
            issue=result.get("issue"),
        )


class RetryHandler:
    """
    If quality gate fails, retry with feedback.
    """
    
    async def retry_with_feedback(
        self,
        original_response: SynthesizedResult,
        review: QualityReview,
        context: ContextStack,
    ) -> SynthesizedResult:
        """
        Ask Claude to revise based on quality issues.
        """
        prompt = f"""
Your previous response had quality issues:

ORIGINAL RESPONSE:
{original_response.narrative}

ISSUES IDENTIFIED:
{json.dumps(review.issues, indent=2)}

REVISE THE RESPONSE to fix these issues.
- Address each issue specifically
- Keep good parts unchanged
- Don't introduce new errors
- Same format as before (narrative + visualization + suggestions)
"""
        
        revised = await claude.complete(prompt)
        return SynthesizedResult.from_claude(revised)
```

---

# PART VII — HONEST FAILURE HANDLING

## 16. The Failure Taxonomy

```python
# core/failure_handler.py

class FailureMode(Enum):
    """All ways the AI can fail to fulfill a request."""
    
    # Capability gaps
    TOOL_NOT_AVAILABLE = "tool_not_available"
    FEATURE_COMING_SOON = "feature_coming_soon"
    OUT_OF_SCOPE = "out_of_scope"
    
    # Data issues
    NO_DATA_FOUND = "no_data_found"
    DATA_INCOMPLETE = "data_incomplete"
    DATA_AMBIGUOUS = "data_ambiguous"
    
    # Permission issues
    PERMISSION_DENIED = "permission_denied"
    DEPARTMENT_RESTRICTED = "department_restricted"
    
    # System issues
    TOOL_ERROR = "tool_error"
    TIMEOUT = "timeout"
    SERVICE_UNAVAILABLE = "service_unavailable"
    
    # Query issues
    AMBIGUOUS_REFERENCE = "ambiguous_reference"
    INVALID_PERIOD = "invalid_period"
    UNCLEAR_INTENT = "unclear_intent"


class HonestFailureResponder:
    """
    Generates honest, helpful responses for each failure mode.
    NEVER fabricates excuses.
    """
    
    RESPONSE_TEMPLATES = {
        FailureMode.TOOL_NOT_AVAILABLE: {
            "tone": "honest, helpful",
            "structure": """
Acknowledge: "{capability} is not available in this assistant yet."
Alternative: "{alternative_method}"
Roadmap: "{roadmap_info}"
Offer: "Want me to track this and notify you when ready?"
""",
            "never": "Don't say 'database issue', 'temporary error', 'try again'"
        },
        
        FailureMode.NO_DATA_FOUND: {
            "tone": "honest, exploratory",
            "structure": """
Direct: "I couldn't find {entity} matching '{query}'"
Show effort: "I searched: {strategies_tried}"
Suggest: "Did you mean: {fuzzy_matches}?"
Offer: "Or try: {broader_search_options}"
""",
            "never": "Don't pretend to have searched if you didn't"
        },
        
        FailureMode.AMBIGUOUS_REFERENCE: {
            "tone": "helpful, decisive",
            "structure": """
Acknowledge: "I found {n} possible matches for '{query}'"
Show: [List top 3 with key distinguishing info]
For super_admin: "I'll use {top_match} unless you say otherwise"
For others: "Which one did you mean?"
""",
        },
        
        FailureMode.PERMISSION_DENIED: {
            "tone": "respectful, clear",
            "structure": """
Direct: "Your current role doesn't have access to {data_type}"
Why: "This requires {required_permission}"
Action: "Contact {admin_role} to request access"
""",
            "never": "Don't share what you saw before refusing"
        },
        
        FailureMode.TOOL_ERROR: {
            "tone": "honest, technical when helpful",
            "structure": """
Acknowledge: "Something went wrong calling {tool}"
Honest: "Error: {error_summary}" (only if user is technical role)
Action: "Try: {retry_or_alternative}"
""",
        },
    }
    
    def respond(self, failure: Failure, context: ContextStack) -> Response:
        template = self.RESPONSE_TEMPLATES[failure.mode]
        
        # Use Claude to craft the specific response
        prompt = f"""
The AI cannot fulfill this request due to: {failure.mode.value}

DETAILS:
{failure.details}

USER:
{context.user.summary()}

RESPONSE TEMPLATE:
{template['structure']}

CRITICAL RULES:
- {template['tone']}
- {template.get('never', '')}
- NEVER fabricate explanations
- NEVER suggest the user retry if the actual issue is missing capability
- Be specific and actionable

Generate the response.
"""
        return await claude.complete(prompt)
```

## 17. Examples of Honest Responses

```
SCENARIO 1: User asks about payslip
─────────────────────────────────────
Bad (current):
  "I'm currently unable to access the payroll system due to a 
  temporary database issue. Please try again."

Good (after this plan):
  "Payslip access isn't built into this assistant yet — payroll is 
  on the roadmap for Q3 2026. For now, please use the HR portal 
  at hr.elrace.com to view your latest payslip.
  
  Want me to notify you when it's ready here?"


SCENARIO 2: Super admin asks about National Guard project
─────────────────────────────────────────────────────────
Bad (current):
  "I need to identify which specific project you're referring to. 
  Could you clarify which 'National Guard' project..."

Good (after this plan):
  "I see two main National Guard projects:
  
  • Airport NGC — Buildings + infrastructure (Budget: AED 24.1M)
  • National Ambulance Command Buildings (Budget: AED 26.0M)
  
  I'll prepare the May 2026 expense report for both — use the 
  one you need:
  
  AIRPORT NGC — May 2026 Expenses
  Total: AED [calculating...]
  ...
  
  NATIONAL AMBULANCE COMMAND — May 2026 Expenses
  Total: AED [calculating...]
  ..."

(Super admin gets BOTH because resolution decided to be aggressive)


SCENARIO 3: User asks about future feature
──────────────────────────────────────────
Bad: "I'll process that for you" (then fails)

Good:
  "Forecasting isn't available yet — that's planned for Q4 2026. 
  
  In the meantime, I can show you:
  • Historical cash flow trends (which forecasting will build on)
  • Last 12 months actual vs prior periods
  
  Want either of those?"
```

---

# PART VIII — PROACTIVE INTELLIGENCE

## 18. Anticipating Next Questions

```python
# core/proactive_layer.py

class ProactiveIntelligence:
    """
    Predicts what user will need next and prepares it.
    """
    
    async def anticipate(
        self,
        current_response: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
    ) -> ProactiveActions:
        """
        Predict next likely needs.
        """
        # Use Claude to predict
        prompt = f"""
User just asked: {intent.specific_intent}
Response given: {current_response.narrative[:500]}

User profile:
- Role: {context.user.primary_role}
- Typical patterns: {context.working_memory.user_patterns}

Predict the 3 most likely next actions this user will take.

Consider:
1. Drill-downs they might want
2. Comparisons they might want
3. Exports they might want
4. Related questions they might ask
5. Actions based on what was just shown

Return JSON:
{{
  "predicted_actions": [
    {{
      "action": "...",
      "likelihood": 0.0-1.0,
      "pre_computable": true/false,
      "suggestion_text": "What to show as suggestion"
    }}
  ],
  "pre_compute_recommendations": [
    "Things to fetch in background"
  ]
}}
"""
        result = await claude.complete(prompt, response_format="json")
        
        # Pre-compute high-likelihood actions
        for action in result["predicted_actions"]:
            if action["likelihood"] > 0.7 and action["pre_computable"]:
                asyncio.create_task(self._pre_compute(action, context))
        
        return ProactiveActions.from_dict(result)
    
    async def _pre_compute(self, action, context):
        """Fetch likely needs in background, cache results."""
        # Run the predicted action, cache result
        # User clicks suggestion → instant response
        pass
```

## 19. Smart Suggestions Generation

```python
class SmartSuggestionsGenerator:
    """
    Generates contextual, diverse, useful suggestions.
    Not generic — specific to what was just shown.
    """
    
    def generate(
        self,
        synthesized: SynthesizedResult,
        intent: Intent,
        context: ContextStack,
    ) -> list[Suggestion]:
        """
        Return 3 high-quality suggestions.
        """
        # Build candidate pool
        candidates = []
        
        # Drill-down candidates
        candidates.extend(self._drill_down_suggestions(synthesized, intent))
        
        # Comparison candidates
        candidates.extend(self._comparison_suggestions(synthesized, intent))
        
        # Action candidates
        candidates.extend(self._action_suggestions(synthesized, intent))
        
        # Insight-based candidates
        candidates.extend(self._insight_suggestions(synthesized, intent))
        
        # Filter by:
        # 1. Not already shown this session
        # 2. Permission-appropriate
        # 3. Actually useful
        eligible = self._filter_eligible(candidates, context)
        
        # Diversify (different categories)
        diverse = self._diversify(eligible, target_count=3)
        
        return diverse
```

---

# PART IX — TELEMETRY AND LEARNING

## 20. Capturing Every Interaction

```python
# core/telemetry.py

@dataclass
class InteractionTelemetry:
    """Full record of every AI interaction."""
    
    # Identification
    interaction_id: str
    user_id: int
    session_id: str
    timestamp: datetime
    
    # Input
    user_query: str
    user_query_language: str
    
    # Processing
    intent_extracted: Intent
    strategy_used: Strategy
    tools_called: list[str]
    tool_durations_ms: dict
    
    # Quality
    quality_review: QualityReview
    retries_needed: int
    confidence: float
    
    # Output
    response_text: str
    response_length: int
    visualization_type: str
    suggestions_offered: list[str]
    
    # User behavior
    user_satisfaction_signal: str | None  # thumbs up/down
    next_query_within_60s: str | None     # Indicator of incompleteness
    suggestion_clicked: str | None         # Which suggestion was useful
    chat_continued: bool                   # User engaged further
    
    # Costs
    tokens_input: int
    tokens_output: int
    cost_cents: int
    total_duration_ms: int


class LearningEngine:
    """
    Analyzes telemetry to improve over time.
    """
    
    async def learn_from_recent(self, hours: int = 24):
        """Analyze recent interactions for patterns."""
        recent = await self.fetch_recent_telemetry(hours)
        
        patterns = {
            "common_failures": self._find_common_failures(recent),
            "successful_strategies": self._find_successful_strategies(recent),
            "user_specific_patterns": self._find_user_patterns(recent),
            "tool_performance": self._analyze_tool_performance(recent),
            "quality_drift": self._detect_quality_drift(recent),
        }
        
        # Update working memory with learnings
        await self._apply_learnings(patterns)
        
        # Surface insights for admin
        return patterns
```

---

# PART X — THE NEW MAIN LOOP

## 21. Putting It All Together

```python
# gateway/intelligent_handler.py

class IntelligentQueryHandler:
    """
    The new main loop. Replaces gateway/main.py's chat handler.
    """
    
    def __init__(self):
        self.context_builder = ContextStackBuilder()
        self.intent_analyzer = IntentAnalyzer()
        self.strategy_planner = StrategyPlanner()
        self.orchestrator = ExecutionOrchestrator()
        self.entity_resolver = EntityResolver()
        self.synthesizer = ResultSynthesizer()
        self.quality_gate = QualityGate()
        self.proactive_layer = ProactiveIntelligence()
        self.suggestion_generator = SmartSuggestionsGenerator()
        self.telemetry = TelemetryCapture()
        self.failure_handler = HonestFailureResponder()
    
    async def handle(self, request: ChatRequest, user: User) -> ChatResponse:
        """
        Main handler. Routes query through entire intelligence pipeline.
        """
        start_time = time.time()
        interaction = InteractionTelemetry(
            interaction_id=str(uuid.uuid4()),
            user_id=user.id,
            user_query=request.message,
            timestamp=datetime.utcnow(),
        )
        
        try:
            # 1. Build context stack
            context = await self.context_builder.build(user, request)
            
            # 2. Analyze intent
            intent = await self.intent_analyzer.analyze(request.message, context)
            interaction.intent_extracted = intent
            
            # 3. Handle out-of-scope upfront
            if intent.out_of_scope:
                response = await self.failure_handler.respond(
                    Failure(
                        mode=self._classify_out_of_scope(intent),
                        details=intent.out_of_scope_reason,
                    ),
                    context,
                )
                return self._finalize(response, interaction)
            
            # 4. Resolve ambiguities (entity resolution)
            if intent.entities:
                resolution_results = {}
                for entity_ref in intent.entities:
                    if entity_ref.type == "project":
                        result = await self.entity_resolver.resolve_project(
                            entity_ref.value, context
                        )
                        resolution_results[entity_ref.value] = result
                
                # Apply resolution decisions
                intent = self._apply_resolutions(intent, resolution_results, context)
            
            # 5. Check if clarification needed
            if intent.requires_clarification and context.user.assumption_level() != "aggressive":
                return self._ask_clarification(intent.clarification_question)
            
            # 6. Plan strategy
            strategy = await self.strategy_planner.plan(intent, context)
            interaction.strategy_used = strategy
            
            # 7. Execute
            execution_result = await self.orchestrator.execute(strategy, context)
            interaction.tools_called = [s.tool for s in strategy.steps]
            
            # 8. Synthesize results
            synthesized = await self.synthesizer.synthesize(
                execution_result, intent, context
            )
            
            # 9. Quality gate
            review = await self.quality_gate.review(synthesized, intent, context)
            interaction.quality_review = review
            
            retries = 0
            while not review.passed and retries < 2:
                synthesized = await self.quality_gate.retry_with_feedback(
                    synthesized, review, context
                )
                review = await self.quality_gate.review(synthesized, intent, context)
                retries += 1
            interaction.retries_needed = retries
            
            # 10. Generate suggestions
            suggestions = self.suggestion_generator.generate(
                synthesized, intent, context
            )
            
            # 11. Proactive layer
            proactive = await self.proactive_layer.anticipate(
                synthesized, intent, context
            )
            
            # 12. Compose response
            response = ChatResponse(
                text=synthesized.narrative,
                visualization=synthesized.visualization,
                suggestions=[s.text for s in suggestions],
                confidence=synthesized.confidence,
                proactive_data=proactive.pre_computed_data,
            )
            
            return self._finalize(response, interaction)
            
        except Exception as e:
            # Honest error handling
            failure = Failure(
                mode=FailureMode.TOOL_ERROR,
                details=str(e),
            )
            response = await self.failure_handler.respond(failure, context)
            return self._finalize(response, interaction)
        
        finally:
            interaction.total_duration_ms = int((time.time() - start_time) * 1000)
            await self.telemetry.record(interaction)
```

---

# PART XI — IMPLEMENTATION PHASES

## 22. Build Order (10 Weeks)

### Phase 1 — Context Stack (Week 1-2)
```
[ ] Build UserContext with role-aware behavior rules
[ ] Build CapabilityManifest with full inventory
[ ] Build WorkingMemory with PostgreSQL persistence
[ ] Build BusinessContext, TemporalContext
[ ] Build ContextStackBuilder
[ ] Integration tests
[ ] Verify context is injected into Claude prompts
```

### Phase 2 — Intent & Strategy (Week 3)
```
[ ] Build IntentAnalyzer with Claude
[ ] Build Intent dataclass with full schema
[ ] Build StrategyPlanner
[ ] Build Strategy execution model
[ ] Test intent extraction on 50 example queries
[ ] Test strategy planning on complex queries
```

### Phase 3 — Entity Resolution (Week 4)
```
[ ] Build EntityResolver with 8 strategies
[ ] Implement project resolver
[ ] Implement partner resolver
[ ] Implement account resolver
[ ] Build ResolutionStrategy decision tree
[ ] Test "national guard" scenario passes
[ ] Test Arabic equivalents
[ ] Test acronym matching
```

### Phase 4 — Orchestration (Week 5)
```
[ ] Build ExecutionOrchestrator
[ ] Implement parallel step execution
[ ] Implement retry logic
[ ] Implement fallback handling
[ ] Tool input variable resolution
[ ] Verification between steps
```

### Phase 5 — Synthesis & Quality (Week 6)
```
[ ] Build ResultSynthesizer
[ ] Build QualityGate with all 8 checks
[ ] Build RetryHandler
[ ] Test quality gate catches fabrication
[ ] Test quality gate catches raw syntax
[ ] Test quality gate enforces no-error-fabrication
```

### Phase 6 — Failure Handling (Week 7)
```
[ ] Build FailureMode enum
[ ] Build HonestFailureResponder
[ ] Implement all response templates
[ ] Test payslip scenario gives honest response
[ ] Test out-of-scope queries handled correctly
[ ] Test ambiguous entity gives smart response
```

### Phase 7 — Proactive Layer (Week 8)
```
[ ] Build ProactiveIntelligence
[ ] Build SmartSuggestionsGenerator
[ ] Pre-computation system
[ ] Cache predicted needs
[ ] Test suggestions feel relevant
```

### Phase 8 — Telemetry & Learning (Week 9)
```
[ ] Build TelemetryCapture
[ ] PostgreSQL telemetry table
[ ] Build LearningEngine
[ ] Daily pattern analysis job
[ ] Memory update from learnings
[ ] Admin dashboard for telemetry
```

### Phase 9 — Integration & Migration (Week 10)
```
[ ] Build IntelligentQueryHandler
[ ] Wire all components together
[ ] Replace gateway/main.py chat handler
[ ] Migration tests
[ ] A/B test old vs new on 100 queries
[ ] Performance verification (< 5s typical)
[ ] Cost verification (< $0.10 per query)
```

### Phase 10 — Hardening (Week 10)
```
[ ] Load testing
[ ] Edge case testing
[ ] Multi-user concurrent testing
[ ] Document for team
[ ] Train Cursor on new patterns
[ ] Ship!
```

---

# PART XII — TEST SCENARIOS

## 23. The Canonical Test Suite

```
These exact scenarios MUST pass after rebuild:

SCENARIO A: Payslip Query
─────────────────────────
Input:  "what is my last payslip"
PASS:   Honest response acknowledging payroll not available
PASS:   Suggests HR portal as alternative
PASS:   Mentions roadmap
FAIL:   Says "database issue" or "try again"


SCENARIO B: Super Admin Project Search
──────────────────────────────────────
Input:  "give me national guard project expense report for last month"
PASS:   Finds National Guard projects on first try
PASS:   Shows top match + alternatives
PASS:   Does not ask for exact project name
PASS:   For super_admin: proceeds with top match aggressively
FAIL:   Asks user to provide project name first


SCENARIO C: Ambiguous Reference
───────────────────────────────
Input:  "Show me the Zayidia project costs"
PASS:   Recognizes 2 Zayidia projects exist
PASS:   Shows both with key distinguishing info
PASS:   Asks which one for clarity (or shows both for super admin)


SCENARIO D: Out of Scope
────────────────────────
Input:  "Forecast next month's cash position"
PASS:   Honest about forecasting not built
PASS:   Suggests historical trends as alternative
PASS:   Offers to track when available


SCENARIO E: Multi-step Query
────────────────────────────
Input:  "Compare top 5 projects revenue this year vs last year"
PASS:   Decomposes into: get top 5, get current revenue, 
        get last year revenue, compute variance, synthesize
PASS:   Returns coherent comparison
PASS:   Uses comparative visualization


SCENARIO F: Permission-Restricted
─────────────────────────────────
Input:  (Regular user) "Show me all department budgets"
PASS:   Acknowledges permission limit
PASS:   Shows only their department's data
PASS:   Mentions who to ask for broader access


SCENARIO G: Vague Date
──────────────────────
Input:  "How are we doing?"
PASS:   Asks brief clarification or uses sensible default (this month)
PASS:   States clearly what period was used
PASS:   Offers to switch period


SCENARIO H: Arabic Query
────────────────────────
Input:  "أرني تقرير الأرباح والخسائر لهذا الشهر"
PASS:   Responds in Arabic
PASS:   Visualizations have Arabic labels
PASS:   Numbers formatted correctly for Arabic


SCENARIO I: Complex Analytical
──────────────────────────────
Input:  "Why is our margin lower this month?"
PASS:   Fetches current margin
PASS:   Fetches prior month margin
PASS:   Decomposes variance into income vs cost changes
PASS:   Identifies specific drivers
PASS:   Provides explanation, not just data


SCENARIO J: Follow-up Continuity
────────────────────────────────
Previous: "Show me Zayidia Boys School costs"
Now:      "And the income?"
PASS:    Knows "Zayidia Boys School" is the subject
PASS:    Returns income for that project
PASS:    Maintains context naturally
```

---

# PART XIII — UI FOR THE NEW INTELLIGENCE

## 24. What User Sees Differently

```
1. SHORTER ROUND TRIPS
   Most queries answered in one turn
   Multi-step queries done internally
   User doesn't see the orchestration

2. HONEST DISCLAIMERS WHEN NEEDED
   "I assumed Airport NGC since you said National Guard"
   "Using last 3 months by default"
   "Note: payroll isn't built yet"

3. CONFIDENCE INDICATORS
   High confidence: regular response
   Medium: "I'm fairly confident this is..."
   Low: "I'm not certain — here's what I found..."

4. PROACTIVE PREVIEW LOADING
   While showing P&L, pre-load breakdown
   User clicks "Break down by project" → instant

5. THINKING INDICATORS (during processing)
   "Searching projects..."
   "Calculating variance..."
   "Verifying numbers..."
   Subtle, transparent

6. SMARTER SUGGESTIONS
   Based on what was actually shown
   Predictive of next likely need
   Never repeated in same session

7. NO FAKE ERRORS
   Real failures shown honestly
   With actionable alternatives
```

## 25. New UI Components Needed

```
ooa-ui/src/intelligence/
├── ConfidenceIndicator.jsx     # Shows AI's confidence level
├── ThinkingIndicator.jsx       # Multi-step process visibility
├── AssumptionNote.jsx          # "I assumed X" callouts
├── EntityResolutionCard.jsx    # When multiple matches found
├── HonestErrorCard.jsx         # Replaces fake errors
├── ProactivePreloadBadge.jsx   # "Already loaded" indicators
└── ContextChip.jsx             # Shows what context AI used
```

## 26. UI Patterns

### Confidence Indicator

```
For each response, show subtle confidence:

HIGH CONFIDENCE (0.85+):
  Just the response, no indicator

MEDIUM CONFIDENCE (0.65-0.85):
  Small "verified ●" badge

LOW CONFIDENCE (<0.65):
  "I'm not fully certain — please verify"
  Shows what was uncertain
```

### Thinking Indicator (Multi-step queries)

```
While orchestrator runs multi-step:

  ┌──────────────────────────────┐
  │  ⊙ Thinking...               │
  │                              │
  │  ● Resolving project name    │
  │  ● Fetching current revenue  │
  │  ◐ Fetching prior period     │ ← in progress
  │  ◯ Computing variance         │
  │  ◯ Identifying drivers       │
  └──────────────────────────────┘

Sub-status lines update as steps complete.
User sees the AI is genuinely working.
```

### Assumption Note

```
When AI made an assumption:

  ╭──────────────────────────────╮
  │ ⓘ I used "Airport NGC" since │
  │   you said "National Guard". │
  │   [Change project] [Continue]│
  ╰──────────────────────────────╯

Inline, dismissible.
User can correct if wrong.
```

### Honest Error Card

```
Replaces fake "database error" messages:

  ╭──────────────────────────────╮
  │ ⚠ Can't do this yet          │
  │                              │
  │  Payslip access isn't built  │
  │  into this assistant.        │
  │                              │
  │  In the meantime:            │
  │  • Use HR portal (hr.elrace) │
  │  • Coming Q3 2026            │
  │                              │
  │  [Notify me] [HR Portal]     │
  ╰──────────────────────────────╯
```

---

# PART XIV — METRICS FOR SUCCESS

## 27. How We'll Know This Works

```
QUANTITATIVE METRICS:

Quality:
  - Quality gate pass rate: target 95%
  - Retry rate: target <15% of queries
  - Fabrication incidents: target 0
  - User correction rate: target <5%

Efficiency:
  - Average turns per task: target 1.5 (was 3.2)
  - Resolution-first success: target 80%
  - Pre-computed cache hits: target 30%

Performance:
  - p50 response time: target <3s
  - p95 response time: target <8s
  - Concurrent users: support 50+

Cost:
  - Per query: target <$0.10
  - Per session: target <$2.00

QUALITATIVE METRICS:

User feedback:
  - "Feels like a senior analyst" — target >80% agree
  - "Honest when can't help" — target >90% agree
  - "Anticipates what I need" — target >70% agree
  - "Trust the numbers" — target >95% agree

User behavior:
  - Suggestion click-through: target >40%
  - Follow-up questions: target decrease (means complete answers)
  - Sessions per week per user: target increase
  - Time to value: target <30 seconds
```

---

# PART XV — TELL CURSOR

```
"Read AI_CORE_INTELLIGENCE_ARCHITECTURE.md.

This is a complete rebuild of the intelligence layer.
10 weeks across 10 phases.

This REPLACES the current handler in gateway/main.py.
Existing tests will need rewriting.

Start Phase 1: Context Stack.

1. Create core/ folder structure
2. Build UserContext with full role-aware behavior
3. Build CapabilityManifest with the full inventory from PART II
4. Build WorkingMemory backed by PostgreSQL
5. Build BusinessContext and TemporalContext
6. Build ContextStackBuilder
7. Integration tests verifying context injection

After Phase 1 confirmed working, proceed to Phase 2.

CRITICAL RULES:
1. Quality bar: 'senior management consultant + CFO's chief of staff'
2. Failure handling: Option B (always help with what's possible) + 
   Option C (ask if ambiguous, honest if impossible)
3. Never fabricate errors — be honest about limitations
4. Multi-tool orchestration over single-shot
5. Quality gate before user sees any response
6. Each phase must be production-quality before next

Reference:
- PROJECT_CONTEXT.md for current architecture
- PRODUCT_QUALITY_FRAMEWORK.md for quality standards
- All scenarios in PART XII must pass after Phase 10

This is the most important plan in the project.
The brain of everything we're building.
Get it right."
```

---

# PART XVI — WHAT THIS DOESN'T REPLACE

```
This rebuild affects:
  ✓ How queries are understood
  ✓ How tools are orchestrated
  ✓ How responses are quality-checked
  ✓ How errors are handled
  ✓ How learning happens

This rebuild DOES NOT affect:
  ✗ The financial tools themselves (query_accounting, etc.)
  ✗ The Visualize agent
  ✗ The PDF/Excel generators
  ✗ The Admin panel
  ✗ The integrations (Outlook, Slack, etc.)
  ✗ The UI design language

Those layers stay. This rebuilds the BRAIN that uses them.
```

---

This is the architecture that takes us from "uses Claude" to "is intelligent."

Every interaction passes through reasoning, verification, quality control, and learning. Every response is honest, accurate, and proactive. Every failure handled gracefully.

After this is built, the product is no longer a chatbot. It's an assistant.
