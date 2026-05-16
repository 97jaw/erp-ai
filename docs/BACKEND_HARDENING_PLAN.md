# BACKEND HARDENING PLAN — Technical Guidance for Cursor AI

> **Purpose:** Fix observed reliability issues in tool execution, context handling, and data retrieval. This is technical guidance only — Cursor will implement.

> **Read first:** `PROJECT_CONTEXT.md`, `TASKS_ARCHITECTURE.md`

---

## 1. Observed Problems (Real User Cases)

### Problem 1 — Wrong / Empty Tool Output
```
User Query: "top 3 profitable projects"
Response:   AED 0, total_cost 0, budget 38,411
            Random Arabic project names that don't exist
            Numbers don't match anything in Odoo

Root Cause: No tool exists for "top N projects by profitability"
            Agent hallucinated data when no proper tool was available
```

### Problem 2 — Stale Response on Follow-up
```
Turn 1: "show project NATIONAL GUARD COMMAND" → Correct response
Turn 2: "categorize the expenses by LPO, petty cash etc"
        Response: Same data as Turn 1 (wrong)

Expected: Cost distribution breakdown by category
Root Cause: Agent didn't recognize follow-up needed different tool call
            OR cache returned previous result
            OR no tool exists for cost categorization
```

### Problem 3 — Missing Tool Granularity
```
The agent has only coarse tools. Missing:
- Top N projects (by profit / revenue / cost / overrun)
- Cost categorization (LPO, Petty Cash, Labor, Staff, Materials)
- Comparison across periods
- Drill-down on specific category
- Filter by client / region / status
```

---

## 2. Root Cause Analysis

### 2.1 Tool Coverage Gaps

```
Current Tools (9):
  ✓ get_financial_report          — company-wide P&L only
  ✓ get_project_expenses           — single project dashboard
  ✓ get_project_financial_data     — single project P&L
  ✓ get_general_ledger             — all accounts
  ✓ get_trial_balance              — account summary
  ✓ get_partner_ageing             — receivables
  ✓ get_partner_ledger             — partner transactions
  ✓ get_projects_summary           — list of projects (NO financials)
  ✓ search_odoo                    — generic search

Missing Tools:
  ✗ get_top_projects_by_metric     — ranking by profit/cost/revenue
  ✗ get_project_cost_categories    — LPO/Petty Cash/Labor breakdown
  ✗ get_period_comparison          — this month vs last month
  ✗ get_project_drill_down         — drill into specific expense category
  ✗ get_projects_by_client         — filter by partner
  ✗ get_overdue_projects           — budget overrun list
```

### 2.2 Context Carry-forward Issues

```
Issue: When user says "categorize the expenses" after viewing a project,
       the agent doesn't know to:
       1. Recognize "the" refers to the just-shown project
       2. Call a different tool that returns categorized data
       3. Pass project_id from previous context

Fix Required: Better tool selection based on conversational context
```

### 2.3 Cache Invalidation

```
Currently: Cache by tool_name + tool_input hash
Problem:   Same input returns cached even if user wants fresh data
Fix:       Add cache_bust parameter on follow-up tool calls
           OR set shorter TTL for project-specific queries
```

---

## 3. Required New Tools

### 3.1 `get_top_projects_by_metric`

```python
{
    "name": "get_top_projects_by_metric",
    "description": (
        "Get top N projects ranked by a financial metric. "
        "Use for queries like 'top 3 profitable projects', "
        "'most expensive projects', 'projects with biggest overrun'. "
        "Returns actual project records with real financial numbers."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": [
                    "net_profit",        # most profitable
                    "revenue",           # highest income
                    "total_cost",        # most expensive
                    "budget_overrun",    # over budget the most
                    "margin_percent",    # best profit margin
                ],
                "description": "Which metric to rank by"
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "description": "How many projects to return"
            },
            "order": {
                "type": "string",
                "enum": ["desc", "asc"],
                "default": "desc"
            },
            "date_from": { "type": "string" },
            "date_to": { "type": "string" }
        },
        "required": ["metric"]
    }
}
```

**Implementation Pattern:**

```python
# In project.financial.service Odoo module
@api.model
def get_ai_top_projects(self, metric='net_profit', limit=5,
                        order='desc', date_from=None, date_to=None):
    """
    Returns top N projects ranked by metric.
    Uses direct SQL aggregation for performance.
    """
    # Get all active projects
    projects = self.env['project.project'].search([('active', '=', True)])

    results = []
    for project in projects:
        # Reuse existing get_project_financial_data for each
        try:
            data = self.get_project_financial_data(
                project, date_from, date_to
            )
            kpis = data.get('kpis', {})
            results.append({
                'project_id': project.id,
                'project_name': project.name,
                'wo_ref_no': project.wo_ref_no,
                'client': project.partner_id.name,
                'net_profit': float(kpis.get('net_profit', 0)),
                'revenue': float(kpis.get('total_income', 0)),
                'total_cost': float(kpis.get('total_expense', 0)),
                'budget': float(project.wo_amount or 0),
                'margin_percent': float(kpis.get('margin', 0)),
            })
        except Exception:
            continue  # Skip projects with errors

    # Calculate budget_overrun
    for r in results:
        if r['budget'] > 0:
            r['budget_overrun'] = ((r['total_cost'] - r['budget']) / r['budget']) * 100
        else:
            r['budget_overrun'] = 0

    # Sort by requested metric
    reverse = (order == 'desc')
    results.sort(key=lambda x: x[metric], reverse=reverse)

    return {
        'metric': metric,
        'limit': limit,
        'date_from': str(date_from) if date_from else None,
        'date_to': str(date_to) if date_to else None,
        'projects': results[:limit],
    }
```

**Performance Note:**
This iterates all projects which is slow. Optimization options:
- Cache result with 30 min TTL
- Run as scheduled action overnight, store in `ir.config_parameter`
- Add aggregation SQL view directly in PostgreSQL

---

### 3.2 `get_project_cost_categories`

```python
{
    "name": "get_project_cost_categories",
    "description": (
        "Get cost breakdown for a specific project, grouped by category: "
        "LPO (Local Purchase Orders), Petty Cash, Labor, Staff, Materials, "
        "Subcontractors, Equipment, Vehicles, Office. "
        "Use when user asks 'categorize expenses', 'break down by type', "
        "'what was spent on labor', etc."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer"},
            "project_name": {"type": "string"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"}
        }
    }
}
```

**Implementation:**

```python
@api.model
def get_ai_project_cost_categories(self, project_id=None, project_name=None,
                                    date_from=None, date_to=None):
    """
    Returns categorized cost breakdown for a project.
    Categories come from project.financial.service cost_distribution.
    """
    # Resolve project
    if not project_id and project_name:
        project = self._resolve_project_by_name(project_name)
        if not project:
            return {'error': 'project_not_found', 'search': project_name}
        project_id = project.id

    project = self.env['project.project'].browse(project_id)

    # Use existing expense dashboard which has cost_distribution
    dashboard = self.get_project_expense_dashboard(project_id)

    # Extract and enhance distribution
    distribution = dashboard.get('cost_distribution', [])

    # Calculate percentages and add insights
    total = sum(
        sum(item.get('amount', 0) for item in category.get('items', []))
        for category in distribution
    )

    categorized = []
    for category in distribution:
        category_total = sum(
            item.get('amount', 0) for item in category.get('items', [])
        )
        percentage = (category_total / total * 100) if total > 0 else 0

        # Sort items within category by amount
        sorted_items = sorted(
            category.get('items', []),
            key=lambda x: x.get('amount', 0),
            reverse=True
        )

        categorized.append({
            'category': category.get('name'),
            'total': category_total,
            'percentage': round(percentage, 2),
            'items_count': len(sorted_items),
            'top_items': sorted_items[:5],  # Top 5 per category
        })

    # Sort categories by total descending
    categorized.sort(key=lambda x: x['total'], reverse=True)

    return {
        'project_id': project_id,
        'project_name': project.name,
        'wo_ref_no': project.wo_ref_no,
        'total_cost': total,
        'budget': float(project.wo_amount or 0),
        'categories': categorized,
        'category_count': len(categorized),
    }
```

---

### 3.3 `get_period_comparison`

```python
{
    "name": "get_period_comparison",
    "description": (
        "Compare financial metrics between two periods. "
        "Use for queries like 'compare this month vs last month', "
        "'how did we do compared to last quarter'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "report_type": {
                "type": "string",
                "enum": ["pandl", "expenses", "revenue"]
            },
            "period_1_from": {"type": "string"},
            "period_1_to": {"type": "string"},
            "period_1_label": {"type": "string"},
            "period_2_from": {"type": "string"},
            "period_2_to": {"type": "string"},
            "period_2_label": {"type": "string"}
        },
        "required": ["report_type", "period_1_from", "period_1_to",
                     "period_2_from", "period_2_to"]
    }
}
```

**Implementation pattern:**

```python
@api.model
def get_ai_period_comparison(self, report_type, period_1_from, period_1_to,
                              period_2_from, period_2_to,
                              period_1_label=None, period_2_label=None):
    """Compare two periods side-by-side."""
    p1 = self.get_ai_financial_report(report_type, period_1_from, period_1_to)
    p2 = self.get_ai_financial_report(report_type, period_2_from, period_2_to)

    p1_kpis = p1.get('kpis', {})
    p2_kpis = p2.get('kpis', {})

    # Calculate variances
    def variance(new, old):
        if old == 0:
            return None
        return round(((new - old) / old) * 100, 2)

    return {
        'period_1': {
            'label': period_1_label or f"{period_1_from} to {period_1_to}",
            'income': p1_kpis.get('total_income', 0),
            'expense': p1_kpis.get('total_expense', 0),
            'net_profit': p1_kpis.get('net_profit', 0),
            'margin': p1_kpis.get('margin', 0),
        },
        'period_2': {
            'label': period_2_label or f"{period_2_from} to {period_2_to}",
            'income': p2_kpis.get('total_income', 0),
            'expense': p2_kpis.get('total_expense', 0),
            'net_profit': p2_kpis.get('net_profit', 0),
            'margin': p2_kpis.get('margin', 0),
        },
        'variance': {
            'income_pct': variance(p1_kpis.get('total_income', 0),
                                   p2_kpis.get('total_income', 0)),
            'expense_pct': variance(p1_kpis.get('total_expense', 0),
                                    p2_kpis.get('total_expense', 0)),
            'profit_pct': variance(p1_kpis.get('net_profit', 0),
                                   p2_kpis.get('net_profit', 0)),
        }
    }
```

---

### 3.4 `get_projects_with_overrun`

```python
{
    "name": "get_projects_with_overrun",
    "description": (
        "List projects that are over budget or approaching budget limit. "
        "Use for 'which projects are over budget', 'budget warnings', "
        "'projects at risk'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "threshold_percent": {
                "type": "number",
                "default": 100,
                "description": "Show projects exceeding this % of budget"
            },
            "limit": {"type": "integer", "default": 10}
        }
    }
}
```

---

### 3.5 `get_projects_by_client`

```python
{
    "name": "get_projects_by_client",
    "description": (
        "Get all projects for a specific client/partner with financial data. "
        "Use for 'show projects for Abu Dhabi Police', "
        "'what work do we have with Ministry of Education'."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "client_name": {"type": "string"},
            "client_id": {"type": "integer"},
            "include_financials": {"type": "boolean", "default": True}
        }
    }
}
```

---

## 4. Conversation Context Improvements

### 4.1 Inject Last Resolved Entity Into Context

**Problem:** When user says "categorize the expenses" — Claude doesn't know which project.

**Solution:** Track last resolved entity in session and inject it on follow-ups.

```python
# In ConversationStore — add entity tracking
class ConversationStore:
    @classmethod
    def get_session_context(cls, session_id):
        """Returns enriched context including last entities."""
        messages = cls.get(session_id)

        # Extract last resolved project from recent tool calls
        last_project_id = None
        last_project_name = None

        for msg in reversed(messages[-6:]):  # Last 3 turns
            content = msg.get("content", "")
            if isinstance(content, str) and "project_id" in content:
                # Parse from previous responses
                import re
                m = re.search(r'project_id["\s:]+(\d+)', content)
                if m:
                    last_project_id = int(m.group(1))
                    break

        return {
            "last_project_id": last_project_id,
            "last_project_name": last_project_name,
        }
```

### 4.2 Enhance System Prompt with Context

```python
def build_system_prompt(today, session_context=None):
    base = SYSTEM_PROMPT.replace("{today}", today)

    if session_context and session_context.get("last_project_id"):
        base += f"""

CONVERSATION CONTEXT:
- Last project discussed: {session_context.get('last_project_name')} (ID: {session_context.get('last_project_id')})
- When user uses "this project", "the expenses", "categorize them", "drill down" etc.,
  they likely mean this project. Pass project_id={session_context.get('last_project_id')} to relevant tools.
"""
    return base
```

---

## 5. Cache Strategy Refinement

### 5.1 Smart Cache Keys

```python
# CURRENT (problematic):
def cache_key(tool, params):
    return md5(f"{tool}:{json.dumps(params)}")

# IMPROVED:
def cache_key(tool, params):
    # Exclude conversation-context params from cache key
    clean = {k: v for k, v in params.items() if k not in ['context_hint']}
    return md5(f"{tool}:{json.dumps(clean, sort_keys=True)}")
```

### 5.2 Differential TTLs

```python
CACHE_TTLS = {
    # Real-time data — short TTL
    "search_odoo": 60,                    # 1 min

    # Reports — medium TTL
    "get_project_expenses": 180,          # 3 min
    "get_project_financial_data": 180,
    "get_project_cost_categories": 180,

    # Aggregations — longer TTL
    "get_top_projects_by_metric": 600,    # 10 min
    "get_projects_with_overrun": 600,

    # Historical data — long TTL
    "get_financial_report": 300,          # 5 min
    "get_period_comparison": 600,

    # Heavy queries — longest TTL
    "get_general_ledger": 1200,           # 20 min
    "get_trial_balance": 1200,
}
```

### 5.3 Cache Bust on Explicit Re-fetch

```python
# Detect re-fetch intent in user query
REFETCH_KEYWORDS = [
    "refresh", "reload", "fresh", "latest", "now",
    "update", "current", "تحديث", "الآن", "حالياً"
]

def should_bust_cache(user_message: str) -> bool:
    msg = user_message.lower()
    return any(kw in msg for kw in REFETCH_KEYWORDS)

# In execute_tool:
if should_bust_cache(state.get('user_message', '')):
    cache.delete(cache_key(tool_name, tool_input))
```

---

## 6. Tool Selection Improvements

### 6.1 Better Tool Descriptions

```
RULE: Tool descriptions must be unambiguous about WHEN to use.

BAD:
"Get project financial data"

GOOD:
"Get detailed P&L for a SPECIFIC project with custom date range.
Use when user mentions a specific project name AND wants income/expense breakdown.
Do NOT use for company-wide P&L — use get_financial_report for that.
Do NOT use for cost categorization — use get_project_cost_categories for that."
```

Audit every tool description with this rule.

### 6.2 Explicit Tool Boundaries

Update each tool description to include:
- WHEN to use
- WHEN NOT to use
- Related tools to consider
- Example user queries

Example for `get_project_expenses`:

```python
"description": (
    "Get expense dashboard for ONE specific project. Shows total cost, "
    "budget, % of budget used, weekly trend, status (normal/warning/critical), "
    "and HIGH-LEVEL category breakdown (LPO total, Petty Cash total, etc.).\n\n"

    "USE WHEN:\n"
    "- User asks total cost of a specific project\n"
    "- User asks if a project is over budget\n"
    "- User asks high-level expense overview for one project\n\n"

    "DO NOT USE WHEN:\n"
    "- User wants DETAILED category breakdown (use get_project_cost_categories)\n"
    "- User wants multiple projects (use get_top_projects_by_metric)\n"
    "- User wants company-wide data (use get_financial_report)\n\n"

    "EXAMPLE QUERIES:\n"
    "- 'total cost for Zayidia Boys School'\n"
    "- 'is project X over budget'\n"
    "- 'expense summary for National Guard project'"
)
```

---

## 7. Data Validation & Sanity Checks

### 7.1 Tool Result Validation

```python
def validate_tool_result(tool_name: str, result: dict) -> dict:
    """Adds sanity checks to prevent hallucination-friendly responses."""

    if tool_name == "get_top_projects_by_metric":
        projects = result.get('projects', [])
        # Filter out projects with all zero metrics
        valid = [p for p in projects
                 if p.get('revenue', 0) > 0 or p.get('total_cost', 0) > 0]
        if not valid:
            return {
                "warning": "No projects with financial activity found in this period",
                "projects": [],
                "suggestion": "Try a wider date range or check if data exists"
            }
        result['projects'] = valid

    if tool_name in ["get_project_expenses", "get_project_financial_data"]:
        # Verify project actually exists and has data
        if result.get('kpis', {}).get('total_income', 0) == 0 and \
           result.get('kpis', {}).get('total_expense', 0) == 0:
            result['warning'] = (
                "This project has no financial activity in the specified period. "
                "Numbers may not be representative."
            )

    return result
```

### 7.2 Reject Hallucinated Data

```python
# Add to system prompt:
DATA_INTEGRITY = """

DATA INTEGRITY RULES (NEVER VIOLATE):
1. Never report numbers that did not come from a tool call
2. If a tool returns empty/zero data, say so explicitly — do not fabricate
3. If you don't know, call the tool again or ask the user
4. Never combine numbers from multiple unrelated tool calls into a summary
5. If a tool returns an error, surface it to the user — do not guess
6. Project names must come from actual Odoo records — never invent
"""
```

---

## 8. Error Surfacing

### 8.1 Better Error Returns from Tools

```python
# CURRENT (bad):
except Exception as exc:
    return {"error": str(exc)}

# IMPROVED:
except Exception as exc:
    return {
        "error": True,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "user_message": _humanize_error(exc),
        "suggested_action": _suggest_recovery(exc),
        "retry_safe": _is_retry_safe(exc),
    }

def _humanize_error(exc) -> str:
    """Convert technical errors to user-friendly messages."""
    if "ProjectAmbiguousError" in type(exc).__name__:
        return "Multiple projects match. Please pick one."
    if "ProjectNotFoundError" in type(exc).__name__:
        return "No project found with that name. Try the WO reference number."
    if "Timeout" in type(exc).__name__:
        return "Odoo server is responding slowly. Try again in a moment."
    return "Could not fetch data. Please try a different query."
```

---

## 9. Logging & Observability

### 9.1 Structured Tool Call Logs

```python
# Add to execute_tool:
import time

def execute_tool(tool_name, tool_input, adapter):
    start = time.time()

    log_entry = {
        "tool": tool_name,
        "input_keys": list(tool_input.keys()),
        "input_summary": {
            k: v for k, v in tool_input.items()
            if k in ['date_from', 'date_to', 'project_name', 'metric']
        },
        "cached": False,
    }

    # ... existing execution ...

    log_entry.update({
        "duration_ms": int((time.time() - start) * 1000),
        "result_size": len(json.dumps(result, default=str)),
        "result_has_error": "error" in result if isinstance(result, dict) else False,
    })
    logger.info("[TOOL] %s", json.dumps(log_entry))
    return result
```

### 9.2 Session Quality Metrics

```python
# Track per session:
- Total tool calls made
- Tools used (which ones)
- Total tokens consumed (Anthropic API)
- Average response time
- User satisfaction signals (clicked suggestion = positive)

# Output as Prometheus metrics or simple JSON logs
```

---

## 10. Testing Strategy

### 10.1 Required Test Cases

```
For each new tool, add tests covering:

1. Happy path with valid params
2. Empty result handling
3. Invalid project name
4. Date range edge cases (future dates, year boundaries)
5. Tool timeout handling
6. Concurrent calls (cache contention)
7. Large result truncation
8. Multi-turn conversation continuity
```

### 10.2 Live Validation Tests

```python
# tests/test_live_tools.py
def test_top_projects_real_data():
    """Validate against known Elrace data."""
    result = adapter.call_method(
        "project.financial.service",
        "get_ai_top_projects",
        ["net_profit", 3, "desc", "2026-04-01", "2026-04-30"]
    )

    assert "projects" in result
    assert len(result["projects"]) <= 3
    assert all("net_profit" in p for p in result["projects"])
    # Each project should have non-zero financial activity
    assert all(
        p["revenue"] > 0 or p["total_cost"] > 0
        for p in result["projects"]
    )
```

---

## 11. Implementation Order

### Phase 1 — Critical Tools (Week 1)
```
[ ] Add get_ai_top_projects to Odoo module
[ ] Add get_ai_project_cost_categories to Odoo module
[ ] Add corresponding tools in gateway/main.py
[ ] Update tool descriptions with clear boundaries
[ ] Test against live Elrace data
```

### Phase 2 — Context Awareness (Week 2)
```
[ ] Implement session context tracking
[ ] Inject last_project_id into system prompt
[ ] Add cache bust on refresh keywords
[ ] Improve tool descriptions for follow-up queries
```

### Phase 3 — Comparison & Analytics (Week 3)
```
[ ] Add get_ai_period_comparison
[ ] Add get_ai_projects_with_overrun
[ ] Add get_ai_projects_by_client
[ ] Add data validation layer
```

### Phase 4 — Polish (Week 4)
```
[ ] Better error handling per tool
[ ] Structured logging
[ ] Test suite for all tools
[ ] Cache TTL tuning based on usage patterns
```

---

## 12. Acceptance Criteria

A tool is "production ready" when:

```
✓ Has clear, unambiguous description with WHEN/WHEN NOT to use
✓ Returns clean serializable Python dict (no ORM objects)
✓ Validates inputs (date format, IDs exist, etc.)
✓ Handles errors gracefully with user-friendly messages
✓ Includes data validation (no zero/empty hallucinations)
✓ Logs structured info for debugging
✓ Has appropriate cache TTL
✓ Has live test against Elrace data
✓ Numbers match Odoo UI exactly (for financial tools)
✓ Works in both English and Arabic queries
```

---

## 13. Quick Reference for Cursor

When implementing any tool:

```
1. Read PROJECT_CONTEXT.md → Pattern 1 (Adding a New Odoo Report)
2. Add get_ai_<name>() method in project.financial.service
3. Test directly via adapter.call_method() before integration
4. Add TOOLS entry in gateway/main.py with detailed description
5. Add executor branch in execute_tool() with caching
6. Add validation in validate_tool_result()
7. Test in chat UI with real queries
8. Compare output to Odoo UI numbers
9. Move task from TODO to DONE in TASKS_FEATURES.md
```

---

## 14. Anti-Patterns to Avoid

```
✗ Don't add a tool that overlaps with existing tools
✗ Don't return random/hallucinated project names
✗ Don't use TransientModel methods directly via XML-RPC
✗ Don't trust cache when user explicitly asks for fresh data
✗ Don't return error strings — return structured error dicts
✗ Don't iterate all records when SQL aggregation is possible
✗ Don't hardcode date ranges — always make them parameters
✗ Don't skip the validation layer
✗ Don't add a tool without updating the system prompt context
✗ Don't deploy without testing against live data
```

---

## 15. Success Metrics (Track These)

```
Before hardening:
  - Tool call success rate: ~75%
  - Hallucinated data incidents: occasional
  - Context-aware follow-ups: often broken
  - User correction rate: high

After hardening (targets):
  - Tool call success rate: > 95%
  - Hallucinated data incidents: zero
  - Context-aware follow-ups: > 90% accurate
  - User correction rate: low
  - Query categorization accuracy: > 95%
```
