# PROJECT EXPENSE INTELLIGENCE PLAN

> **Goal:** Make the AI fluent in everything related to project expenses — summary, breakdown, comparison, drill-down, variance analysis. Wrap the existing Odoo backend (`project.financial.service`) as AI tools and build smart response patterns.

> **Scope:** Single project + multi-project comparison. Drill-down in chat + Visualize panel. Read-only (no Excel export inline for now).

> **Quality Bar:** When a user asks "show me project costs" — they get an executive-grade response with KPIs, top categories, and actionable insights. When they ask follow-ups, the AI never repeats the same data.

> **Read first:** `AI_CORE_INTELLIGENCE_ARCHITECTURE.md`, `FINANCIAL_INTELLIGENCE_PLAN.md`, `project-expense-backend.md`

---

# PART I — WHAT EXISTS (BACKEND READY)

## 1. The Odoo Backend We Are Wrapping

```
ALREADY BUILT in Odoo (no changes needed):

Module: x_spreadsheet
  - project.expense (base model)
  - Computed trade lines: civil, mechanical, electrical, IT, HSE, 
    general, admin, cost_control
  - Computed totals: project_count (W.O total), total_expenses
  
Module: x_spreadsheet_summary_table
  - Top 3 trade expense ranking with percentages
  - GL breakdown payload (MG → SG → Account hierarchy)
  - Breakdown wizard with summary_json
  
Module: elrace_dashboard
  - project.financial.service (AbstractModel)
  - get_project_expense_summary_mobile(project_id) → Summary data
  - get_project_expense_breakdown_mobile(project_id) → GL hierarchy
  - get_project_expense_dashboard(project_id) → Full dashboard
  - get_project_financial_data() → P&L hierarchy
  
Module: elrace_backend_apis
  - POST /api/project/expense/summary
  - POST /api/project/expense/breakdown
```

## 2. What We Build (AI Layer Only)

```
Three AI tools that wrap the existing service methods:

1. get_project_expense_summary(project_id)
   → Single-call to project.financial.service.get_project_expense_summary_mobile
   → Returns KPIs, top trade categories, expense lines

2. get_project_expense_breakdown(project_id)
   → Single-call to get_project_expense_breakdown_mobile
   → Returns full GL hierarchy (MG → SG → Account)

3. compare_project_expenses(project_ids: list[int])
   → Calls summary for each project
   → Computes variance and ranking
   → Returns comparative view

Plus smart response patterns, drill-down UI, and conversation handling.
```

---

# PART II — THE AI TOOLS

## 3. Tool 1: `get_project_expense_summary`

```python
{
    "name": "get_project_expense_summary",
    "description": (
        "Get expense summary for a SINGLE project. Returns KPIs (total expenses, "
        "W.O amount, spend %), top 3 trade categories with percentages, and "
        "categorized expense lines (LPO, petty cash, labor, materials, etc.).\n\n"
        
        "USE THIS WHEN:\n"
        "- User asks for project costs/expenses overview\n"
        "- User wants top spending categories\n"
        "- User asks 'how much did we spend on Project X'\n"
        "- User asks budget vs actual style questions\n\n"
        
        "DO NOT USE for:\n"
        "- GL account drill-down (use get_project_expense_breakdown)\n"
        "- Multiple projects (use compare_project_expenses)"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {
                "type": "integer",
                "description": "Odoo project.project ID. Must be resolved before calling."
            },
        },
        "required": ["project_id"],
    },
}
```

**Implementation:**

```python
# gateway/tools/project_expense.py

async def execute_get_project_expense_summary(
    tool_input: dict,
    adapter,
    context: ContextStack,
) -> dict:
    """
    Wraps project.financial.service.get_project_expense_summary_mobile.
    """
    project_id = tool_input["project_id"]
    
    try:
        result = await asyncio.to_thread(
            adapter.execute_kw,
            "project.financial.service",
            "get_project_expense_summary_mobile",
            [project_id],
        )
    except Exception as e:
        return {
            "status": "error",
            "error_code": "service_call_failed",
            "message": str(e),
        }
    
    if result.get("status") != "success":
        return result  # Pass through error from Odoo
    
    data = result["data"]
    
    # Normalize for AI consumption
    return {
        "status": "success",
        "project_id": project_id,
        "project_name": data["project_name"],
        "agreement_name": data.get("agreement_name"),
        "client_name": data.get("partner_name"),
        "currency": data.get("currency_name", "AED"),
        "wo_amount": data["project_count"],           # W.O total
        "total_expenses": data["total_expenses"],
        "spend_percent_of_wo": data["spend_percent_of_wo"],
        "estimation_amount": data.get("estimation_amount"),
        "top_expenses": data["top_expenses"],          # List of top 3 with %
        "expense_lines": data["expense_lines"],        # All categorized lines
        "variance_amount": data["project_count"] - data["total_expenses"],
        "is_over_budget": data["total_expenses"] > data["project_count"],
        "_source": "project_expense_summary_mobile",
    }
```

## 4. Tool 2: `get_project_expense_breakdown`

```python
{
    "name": "get_project_expense_breakdown",
    "description": (
        "Get FULL GL breakdown for a project — hierarchical view of all "
        "expense accounts grouped by Main Group → Sub Group → Account. "
        "Returns the complete expense distribution at GL level.\n\n"
        
        "USE THIS WHEN:\n"
        "- User asks 'break down by account'\n"
        "- User asks 'show GL details'\n"
        "- User wants to drill into a specific category\n"
        "- User asks 'where did the money go exactly'\n\n"
        
        "DO NOT USE for:\n"
        "- Summary view (use get_project_expense_summary instead — much smaller payload)"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_id": {"type": "integer"},
            "main_group_filter": {
                "type": "string",
                "description": "Optional: filter to specific Main Group (MG) code"
            },
        },
        "required": ["project_id"],
    },
}
```

**Implementation:**

```python
async def execute_get_project_expense_breakdown(
    tool_input: dict,
    adapter,
    context: ContextStack,
) -> dict:
    """
    Wraps project.financial.service.get_project_expense_breakdown_mobile.
    Returns hierarchical groups → subgroups → accounts.
    """
    project_id = tool_input["project_id"]
    mg_filter = tool_input.get("main_group_filter")
    
    try:
        result = await asyncio.to_thread(
            adapter.execute_kw,
            "project.financial.service",
            "get_project_expense_breakdown_mobile",
            [project_id],
        )
    except Exception as e:
        return {
            "status": "error",
            "error_code": "service_call_failed",
            "message": str(e),
        }
    
    if result.get("status") != "success":
        return result
    
    data = result["data"]
    breakdown = data.get("breakdown", {})
    groups = breakdown.get("groups", [])
    
    # Apply MG filter if requested
    if mg_filter:
        groups = [g for g in groups if g.get("code") == mg_filter or 
                  g.get("name") == mg_filter]
    
    # Calculate totals at each level for verification
    grand_total = 0
    for group in groups:
        group_total = 0
        for subgroup in group.get("subgroups", []):
            sg_total = sum(acc.get("total", 0) for acc in subgroup.get("accounts", []))
            subgroup["total"] = sg_total
            group_total += sg_total
        group["total"] = group_total
        grand_total += group_total
    
    return {
        "status": "success",
        "project_id": project_id,
        "project_name": data.get("project_name"),
        "currency": data.get("currency_name", "AED"),
        "groups": groups,
        "grand_total": grand_total,
        "group_count": len(groups),
        "wizard_id": data.get("wizard_id"),  # For future export
        "_source": "project_expense_breakdown_mobile",
        "_truncated": len(groups) > 10,  # Hint for UI
    }
```

## 5. Tool 3: `compare_project_expenses`

```python
{
    "name": "compare_project_expenses",
    "description": (
        "Compare expense data across MULTIPLE projects side-by-side. "
        "Returns each project's KPIs, ranks them by spend, and computes variance "
        "between them. Use when user wants to compare 2+ projects.\n\n"
        
        "USE THIS WHEN:\n"
        "- 'Compare Zayidia Boys School and Zayidia Girls School'\n"
        "- 'Which project is over budget'\n"
        "- 'Top 5 projects by expense'\n"
        "- 'Show me how Project A and B compare'\n\n"
        
        "DO NOT USE for:\n"
        "- Single project (use get_project_expense_summary)"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "project_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 10,
                "description": "List of 2-10 project IDs to compare"
            },
            "rank_by": {
                "type": "string",
                "enum": ["total_expenses", "spend_percent", "variance", "wo_amount"],
                "default": "total_expenses",
            },
        },
        "required": ["project_ids"],
    },
}
```

**Implementation:**

```python
async def execute_compare_project_expenses(
    tool_input: dict,
    adapter,
    context: ContextStack,
) -> dict:
    """
    Compare expense data across multiple projects.
    Calls summary for each in parallel.
    """
    project_ids = tool_input["project_ids"]
    rank_by = tool_input.get("rank_by", "total_expenses")
    
    # Fetch summary for each project in parallel
    tasks = [
        execute_get_project_expense_summary(
            {"project_id": pid}, adapter, context
        )
        for pid in project_ids
    ]
    summaries = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter successful results
    valid = []
    failed = []
    for pid, summary in zip(project_ids, summaries):
        if isinstance(summary, Exception):
            failed.append({"project_id": pid, "error": str(summary)})
        elif summary.get("status") != "success":
            failed.append({"project_id": pid, "error": summary.get("message")})
        else:
            valid.append(summary)
    
    if not valid:
        return {
            "status": "error",
            "error_code": "all_projects_failed",
            "message": "Could not fetch data for any project",
            "failures": failed,
        }
    
    # Rank
    rank_field = {
        "total_expenses": "total_expenses",
        "spend_percent": "spend_percent_of_wo",
        "variance": "variance_amount",
        "wo_amount": "wo_amount",
    }[rank_by]
    
    valid.sort(key=lambda p: p[rank_field], reverse=True)
    
    # Compute comparison stats
    total_wo = sum(p["wo_amount"] for p in valid)
    total_expenses = sum(p["total_expenses"] for p in valid)
    over_budget_count = sum(1 for p in valid if p["is_over_budget"])
    
    return {
        "status": "success",
        "projects": valid,
        "failed": failed,
        "ranking": [
            {
                "rank": i + 1,
                "project_id": p["project_id"],
                "project_name": p["project_name"],
                "value": p[rank_field],
            }
            for i, p in enumerate(valid)
        ],
        "totals": {
            "combined_wo": total_wo,
            "combined_expenses": total_expenses,
            "combined_variance": total_wo - total_expenses,
            "over_budget_count": over_budget_count,
            "project_count": len(valid),
        },
        "ranked_by": rank_by,
        "_source": "compare_project_expenses",
    }
```

---

# PART III — TEACHING THE AI WHEN TO USE WHAT

## 6. System Prompt Additions

Add this section to the AI's system prompt:

```
PROJECT EXPENSE QUERY HANDLING:

When user asks about project expenses, use these tools in this order:

1. ENTITY RESOLUTION FIRST
   - Resolve project name(s) using EntityResolver
   - Confirm with user if ambiguous (entity gate)
   - Get project_id(s) before any expense call

2. CHOOSE THE RIGHT TOOL
   
   User intent → Tool to call:
   
   "Show me costs/expenses for [project]"     → get_project_expense_summary
   "Show project [X] spending overview"        → get_project_expense_summary
   "How much have we spent on [X]"             → get_project_expense_summary
   "Is [X] over budget"                        → get_project_expense_summary
   
   "Break down [X] by account/GL"              → get_project_expense_breakdown
   "Show GL details for [X]"                   → get_project_expense_breakdown
   "Where exactly did money go in [X]"         → get_project_expense_breakdown
   "Show me [X] breakdown for [category]"      → get_project_expense_breakdown
                                                  with main_group_filter
   
   "Compare [A] and [B] costs"                 → compare_project_expenses
   "Which projects are over budget"            → compare_project_expenses
                                                  (need to know which projects first)
   "Top N projects by expense"                 → compare_project_expenses
   
3. NEVER call breakdown without summary first
   Unless user EXPLICITLY asks for GL/account drill-down,
   always start with summary (smaller, faster, more useful).
   
4. RESPONSE PATTERN FOR SUMMARY
   Lead with: spend status (over/under budget, %)
   Then: top 3 trade categories
   Then: notable variances or alerts
   Always offer: "Want me to break this down by account?"

5. RESPONSE PATTERN FOR BREAKDOWN
   Show: collapsible hierarchy (MG → SG → Account)
   Show top 5 MGs first, truncate rest
   Always offer drill-down into specific group

6. RESPONSE PATTERN FOR COMPARISON
   Show: ranked table (winner highlighted)
   Show: combined totals
   Surface insights: which is most efficient, which is concerning
   Always offer: "Drill into [project name]?"

KNOWN BUSINESS CONTEXT:
- W.O amount = Work Order total (the budget/agreement)
- total_expenses = operational spend (petty + labor + LPO + bills)
- spend_percent_of_wo = (total_expenses / wo_amount) * 100
- > 100% means over budget
- Top expenses are TRADE categories (civil, electrical, mech, etc.)
- GL breakdown is ACCOUNT level (different from trade)
- Some projects show negative spend_percent due to refunds
```

## 7. Smart Response Examples

```
QUERY: "show me Zayidia Boys School costs"

LAYER 1 INTELLIGENCE:
  Intent: fetch_data, subject: project, entities: [Zayidia Boys School]
  Entity resolved → project_id = 14549

TOOLS CALLED:
  get_project_expense_summary(14549)

RESPONSE NARRATIVE (good):
  "Zayidia Boys School is at 78% of W.O — spent AED 1.74M of 
   AED 2.24M agreement value.
   
   Top 3 cost categories:
   • Civil Engineering — AED 580K (33%)
   • Mechanical — AED 420K (24%)
   • Electrical — AED 280K (16%)
   
   ⚠ Watch: Civil at 33% is higher than typical (industry avg ~22% 
   for similar projects)
   
   Want me to break this down by GL account?"

  [Visualization: KPI Card + Pie of top 3]
  [Suggestions: 
    - "Drill into Civil Engineering costs"
    - "Compare with Zayidia Girls School"
    - "Show full GL breakdown"]

RESPONSE NARRATIVE (bad — what we are avoiding):
  "Here are the expenses for Zayidia Boys School:
   Total: AED 1,745,234.56
   civil_expense: 580000
   mechnical_expense: 420000
   ..."
   (raw fields exposed, no insight, no follow-up)
```

```
QUERY: "compare Zayidia Boys School and Zayidia Girls School"

LAYER 1 INTELLIGENCE:
  Intent: compare, entities: [2 projects]
  Both resolved → [14549, 14610]

TOOLS CALLED:
  compare_project_expenses([14549, 14610])

RESPONSE NARRATIVE:
  "Comparing the two Zayidia school projects:

                              Boys School    Girls School
   W.O Amount:                 AED 2.24M      AED 2.85M
   Spent:                      AED 1.74M      AED 2.91M
   Spend %:                    78%            102% ⚠
   Status:                     On track       Over budget by AED 60K
   
   Girls School is currently over budget. Main driver looks like 
   higher Mechanical spend (35% vs 24% for Boys School).
   
   Want me to drill into Girls School to identify what pushed 
   the budget?"

  [Visualization: Comparative bar chart]
  [Suggestions:
    - "Drill into Girls School mechanical costs"
    - "Show GL breakdown for both"
    - "What changed in last 30 days for Girls School"]
```

```
QUERY: "what specifically caused Girls School to go over budget"

LAYER 1 INTELLIGENCE:
  Intent: explain, has session memory of Girls School (id 14610)

TOOLS CALLED:
  get_project_expense_breakdown(14610)
  (Uses session memory — does not re-resolve project)

RESPONSE:
  "Looking at the GL breakdown for Zayidia Girls School:

   Top expense groups:
   • Direct Project Costs — AED 1.85M (63%)
     - Materials Subgroup — AED 1.12M
     - Labor Subgroup — AED 730K
   • Subcontractors — AED 670K (23%)
     - Civil contractors — AED 410K
     - MEP contractors — AED 260K
   • Overhead — AED 390K (13%)
   
   The variance vs Boys School is concentrated in:
   - Materials (AED 1.12M vs 580K — likely due to project scope)
   - Subcontractor MEP (AED 260K higher than Boys School)
   
   Want to see the transactions in the Materials subgroup?"
```

---

# PART IV — UI PATTERNS

## 8. The Visualization Schema

```python
# Visualization types for expense responses

PROJECT_EXPENSE_SUMMARY_VIZ = {
    "visual_type": "PROJECT_EXPENSE_SUMMARY",
    "label": "Zayidia Boys School Expenses",
    "level": "summary",
    "project_id": 14549,
    "kpis": {
        "wo_amount": {"value": 2240000, "label": "W.O Amount", "unit": "AED"},
        "total_expenses": {"value": 1745000, "label": "Total Spent", "unit": "AED"},
        "spend_pct": {"value": 78, "label": "Spend %", "unit": "%",
                     "trend": {"direction": "neutral", "context": "On track"}},
        "variance": {"value": 495000, "label": "Remaining", "unit": "AED",
                    "trend": {"direction": "up", "context": "AED 495K available"}},
    },
    "top_expenses": [
        {"label": "Civil Engineering", "value": 580000, "pct": 33.2},
        {"label": "Mechanical", "value": 420000, "pct": 24.0},
        {"label": "Electrical", "value": 280000, "pct": 16.0},
    ],
    "expense_lines": [...],  # All categorized lines
    "actions": [
        {"label": "Drill GL Breakdown", "action": "get_breakdown"},
        {"label": "Compare with...", "action": "compare"},
    ],
}


PROJECT_EXPENSE_BREAKDOWN_VIZ = {
    "visual_type": "PROJECT_EXPENSE_BREAKDOWN",
    "label": "GL Breakdown: Zayidia Boys School",
    "project_id": 14549,
    "groups": [
        {
            "code": "DC",
            "name": "Direct Costs",
            "total": 1120000,
            "pct": 64.2,
            "expanded": True,  # First group expanded by default
            "subgroups": [
                {
                    "code": "MAT",
                    "name": "Materials",
                    "total": 720000,
                    "expanded": False,
                    "accounts": [
                        {"code": "5101", "name": "Cement & Concrete", 
                         "total": 320000},
                        {"code": "5102", "name": "Steel Reinforcement", 
                         "total": 280000},
                    ],
                },
            ],
        },
    ],
    "grand_total": 1745000,
}


PROJECT_EXPENSE_COMPARISON_VIZ = {
    "visual_type": "PROJECT_EXPENSE_COMPARISON",
    "label": "Project Comparison",
    "projects": [
        {
            "id": 14549,
            "name": "Zayidia Boys School",
            "wo_amount": 2240000,
            "total_expenses": 1745000,
            "spend_pct": 78,
            "is_over_budget": False,
            "rank": 1,
        },
        {
            "id": 14610,
            "name": "Zayidia Girls School",
            "wo_amount": 2850000,
            "total_expenses": 2910000,
            "spend_pct": 102,
            "is_over_budget": True,
            "rank": 2,
        },
    ],
    "totals": {
        "combined_wo": 5090000,
        "combined_expenses": 4655000,
        "over_budget_count": 1,
    },
    "chart_type": "side_by_side_bar",
}
```

## 9. React Components Needed

```
ooa-ui/src/visualizations/project_expense/

├── ProjectExpenseSummary.jsx       # Main summary view
│   ├── KPIGrid                      # 4 KPI boxes
│   ├── TopExpensesChart             # Bar chart top 3
│   ├── ExpenseLinesTable            # Categorized lines
│   └── ActionBar                    # "Drill", "Compare"
│
├── ProjectExpenseBreakdown.jsx     # GL hierarchy view
│   ├── BreakdownHierarchy           # Tree view
│   ├── GroupRow                     # MG row (clickable)
│   ├── SubgroupRow                  # SG row (clickable)
│   └── AccountRow                   # Leaf with amount
│
├── ProjectExpenseComparison.jsx    # Multi-project compare
│   ├── ComparisonTable              # Side-by-side table
│   ├── ComparativeBarChart          # Visual comparison
│   └── VarianceCallouts             # Highlight differences
│
└── shared/
    ├── ExpenseBudgetBar.jsx         # Visual budget bar
    ├── OverBudgetBadge.jsx          # Warning indicator
    └── ExpenseTrendIndicator.jsx    # Trend arrow + context
```

## 10. Breakdown Drill-Down UI

```
The hierarchy collapses/expands inline in the chat.

INITIAL VIEW (collapsed):
  ┌────────────────────────────────────────┐
  │ Zayidia Boys School — GL Breakdown    │
  │ Total: AED 1,745,000                   │
  ├────────────────────────────────────────┤
  │ ▶ Direct Costs              AED 1.12M  │
  │ ▶ Subcontractors            AED 670K   │
  │ ▶ Overhead                  AED 390K   │
  │ ▶ Equipment                 AED 95K    │
  └────────────────────────────────────────┘

USER CLICKS "Direct Costs":
  ┌────────────────────────────────────────┐
  │ Zayidia Boys School — GL Breakdown    │
  │ Total: AED 1,745,000                   │
  ├────────────────────────────────────────┤
  │ ▼ Direct Costs              AED 1.12M  │
  │   ▶ Materials               AED 720K   │
  │   ▶ Labor                   AED 400K   │
  │ ▶ Subcontractors            AED 670K   │
  │ ▶ Overhead                  AED 390K   │
  └────────────────────────────────────────┘

USER CLICKS "Materials":
  ┌────────────────────────────────────────┐
  │ ▼ Direct Costs              AED 1.12M  │
  │   ▼ Materials               AED 720K   │
  │     • 5101 Cement & Concrete  AED 320K │
  │     • 5102 Steel Reinforcement AED 280K│
  │     • 5103 Other Materials    AED 120K │
  │   ▶ Labor                   AED 400K   │
  └────────────────────────────────────────┘

Implementation:
  - Pure CSS/React state, no new API calls
  - Data already in viz payload
  - Smooth expand (height transition only — no bounce)
  - Click any account → opens transactions modal (Phase 2)
```

---

# PART V — INSIGHT GENERATION

## 11. Business Rules for Insights

The AI should automatically surface these insights:

```python
# Insight rules for project expense responses

EXPENSE_INSIGHT_RULES = [
    {
        "condition": "spend_pct > 95",
        "severity": "warning",
        "message": "Approaching budget limit (>95% spent)",
    },
    {
        "condition": "spend_pct > 100",
        "severity": "critical",
        "message": "OVER BUDGET — review urgently",
    },
    {
        "condition": "spend_pct < 30 and project_age_months > 6",
        "severity": "info",
        "message": "Low spend rate for project age — possible delays",
    },
    {
        "condition": "top_expense_1_pct > 40",
        "severity": "info",
        "message": "Concentrated spending — {category} alone is {pct}% of total",
    },
    {
        "condition": "variance_vs_estimation > 15",
        "severity": "warning",
        "message": "Actual spend significantly above original estimation",
    },
]


def generate_insights(summary_data: dict, context: dict) -> list[dict]:
    """Apply insight rules to expense data."""
    insights = []
    
    spend_pct = summary_data["spend_percent_of_wo"]
    top_expense = summary_data["top_expenses"][0] if summary_data["top_expenses"] else None
    
    # Over/under budget
    if spend_pct > 100:
        over_amount = summary_data["total_expenses"] - summary_data["wo_amount"]
        insights.append({
            "severity": "critical",
            "icon": "⚠",
            "title": "Over Budget",
            "message": f"Over W.O by AED {over_amount:,.0f} ({spend_pct:.1f}%)",
        })
    elif spend_pct > 95:
        insights.append({
            "severity": "warning", 
            "icon": "⚠",
            "title": "Near Budget Limit",
            "message": f"Spent {spend_pct:.1f}% of W.O",
        })
    
    # Concentration
    if top_expense and top_expense.get("percentage", 0) > 40:
        insights.append({
            "severity": "info",
            "icon": "ⓘ",
            "title": "Concentrated Spending",
            "message": f"{top_expense['label']} alone is "
                      f"{top_expense['percentage']:.1f}% of total expenses",
        })
    
    return insights
```

## 12. Comparison Insights

```python
def generate_comparison_insights(comparison_data: dict) -> list[dict]:
    """Insights for multi-project comparison."""
    insights = []
    projects = comparison_data["projects"]
    
    if len(projects) < 2:
        return insights
    
    over_budget = [p for p in projects if p["is_over_budget"]]
    
    if over_budget:
        names = [p["project_name"] for p in over_budget]
        insights.append({
            "severity": "warning",
            "icon": "⚠",
            "title": "Projects Over Budget",
            "message": f"{len(over_budget)} of {len(projects)} are over W.O: "
                      f"{', '.join(names)}",
        })
    
    # Identify outliers
    spend_pcts = [p["spend_percent_of_wo"] for p in projects]
    if max(spend_pcts) - min(spend_pcts) > 30:
        insights.append({
            "severity": "info",
            "icon": "ⓘ",
            "title": "Wide Spend Variation",
            "message": f"Spend % ranges from {min(spend_pcts):.0f}% to "
                      f"{max(spend_pcts):.0f}% across projects",
        })
    
    return insights
```

---

# PART VI — IMPLEMENTATION PHASES

## 13. Build Order (4 Weeks)

### Phase E1 — Tool Implementation (Week 1)

```
[ ] Create gateway/tools/project_expense.py
[ ] Implement get_project_expense_summary tool
[ ] Implement get_project_expense_breakdown tool
[ ] Implement compare_project_expenses tool
[ ] Add all three to TOOLS array in gateway/main.py
[ ] Add to CAPABILITY_MANIFEST as "available"
[ ] Unit tests for each tool (mock adapter, verify normalization)

TESTS (minimum):
1. summary tool returns normalized fields
2. summary tool handles Odoo error gracefully
3. breakdown tool parses hierarchy correctly
4. breakdown tool computes totals at each level
5. compare tool fetches projects in parallel
6. compare tool ranks correctly by total_expenses
7. compare tool ranks correctly by spend_percent
8. compare tool handles partial failures (one project errors)
9. All tools include proper _source field for telemetry

LIVE TEST:
- Call summary for Zayidia Boys School (14549)
- Verify numbers match Odoo mobile API exactly
- Tell me when ready for verification

DONE WHEN: All tests pass AND I confirm live numbers match Odoo.
```

### Phase E2 — System Prompt Integration (Week 2)

```
[ ] Add PROJECT EXPENSE QUERY HANDLING section to system prompt
[ ] Add tool selection guidance
[ ] Add response pattern examples
[ ] Add business context (W.O, trade vs GL, etc.)
[ ] Test 15 different query phrasings

TESTS — AI must call correct tool for each:
1. "show me Zayidia Boys School costs" → summary
2. "Zayidia Boys School expense overview" → summary  
3. "how much did we spend on Zayidia" → summary (after resolution)
4. "is Zayidia over budget" → summary
5. "break down Zayidia by account" → breakdown
6. "show GL details for Zayidia" → breakdown
7. "where exactly did money go" → breakdown (after summary in context)
8. "compare Boys and Girls Zayidia" → compare
9. "which Zayidia project is over budget" → compare
10. "drill into materials for Boys School" → breakdown with filter
11. (after summary) "show full breakdown" → breakdown using session memory
12. "expenses for project 14549" → summary direct
13. Arabic: "تكاليف مشروع زايديا" → summary
14. "what's the spend status of Zayidia Boys" → summary
15. "tell me about Zayidia Boys School money" → summary

LIVE TEST:
- Run all 15 queries
- Verify correct tool is called each time
- Tell me when ready for verification

DONE WHEN: 14/15 tool selections correct (one edge case OK).
```

### Phase E3 — Visualization Components (Week 3)

```
[ ] Build ProjectExpenseSummary.jsx
[ ] Build ProjectExpenseBreakdown.jsx with expand/collapse
[ ] Build ProjectExpenseComparison.jsx
[ ] Build shared components (BudgetBar, OverBudgetBadge)
[ ] Register all viz types in Visualization router
[ ] Apply theme (sky blue / dark / abstract)
[ ] Mobile responsive

TESTS (visual + functional):
1. Summary card renders with all 4 KPIs
2. Top expenses bar chart shows correctly
3. Breakdown hierarchy expands and collapses smoothly
4. Breakdown shows correct totals at each level
5. Comparison side-by-side table renders
6. Over budget badge appears when spend > 100%
7. Insight callouts appear with correct severity colors
8. Click on expense line → triggers follow-up action
9. Mobile layout works (responsive grid)
10. RTL Arabic renders correctly

FRONTEND TEST (I verify visually):
- Query "show me Zayidia Boys School costs"
- Take screenshot
- Verify it looks production-quality
- Repeat for breakdown and comparison

DONE WHEN: All 3 viz types look professional + I approve screenshots.
```

### Phase E4 — Insights & Polish (Week 4)

```
[ ] Implement EXPENSE_INSIGHT_RULES
[ ] Wire insights into response synthesis
[ ] Add comparison insights
[ ] Test all rules with real Elrace data
[ ] Add suggestions appropriate to each viz type
[ ] Performance check: all responses < 3 seconds
[ ] Update CURRENT_PHASE.md

QUALITY CHECKS:
1. Over-budget project triggers critical insight
2. Concentrated spending triggers info insight
3. Wide variance in comparison triggers callout
4. Insights are specific (mention actual numbers)
5. No insights for normal-state projects (avoid noise)
6. Suggestions vary by viz type
7. Suggestions never repeat in same session

LIVE TEST (final):
Run these exact queries in chat:
A. "show me Zayidia Boys School costs"
B. (follow-up) "break it down"
C. (new) "compare with Zayidia Girls School"
D. (follow-up) "drill into materials for Girls School"
E. "which schools are over budget"

Show me all 5 screenshots.
ALL must be production-quality (CFO would accept them).

DONE WHEN: All 5 live tests look senior-consultant-grade.
```

---

# PART VII — QUALITY ACCEPTANCE TESTS

## 14. The Canonical Test Suite

```
Every one of these must produce executive-grade output:

QUERIES TO PASS:

A. Single project summary
   "show me Zayidia Boys School costs"
   → Summary with KPIs, top 3, insights, suggestions

B. Variation on summary
   "how is Zayidia Boys School doing financially"
   → Same tool, different framing

C. Budget-focused
   "is Zayidia Boys School over budget"
   → Lead with status, then numbers

D. Drill-down request
   "break down Zayidia Boys School by account"
   → Hierarchy view with first group expanded

E. Comparison
   "compare Zayidia Boys School and Zayidia Girls School"
   → Side-by-side with variance highlighted

F. Top-N
   "show me top 5 most expensive projects"
   → Compare tool with ranking

G. Filtered drill
   "show materials breakdown for Zayidia Girls School"
   → Breakdown with main_group_filter

H. Follow-up context
   After (A): "now show me the breakdown"
   → Uses session memory, no re-resolution

I. Arabic variation
   "تكاليف مشروع زايديا للبنين"
   → Same response in Arabic

J. Vague query handled
   "project costs"
   → Asks which project (clarification)

K. Multiple projects same query
   "school projects expenses"
   → Lists schools + asks to pick or compares
```

## 15. Numbers Must Match

```
For Phase E1, the numbers returned MUST match Odoo exactly:

Reference: Odoo mobile API /api/project/expense/summary
For project 14549 (Zayidia Boys School)

Expected fields to verify:
  project_count (W.O)         — must match
  total_expenses              — must match  
  estimation_amount           — must match
  Top 3 trade categories      — must match (same items, same %)
  All expense_lines totals    — must match

If ANY number differs → STOP and investigate before proceeding.
```

---

# PART VIII — TELL CURSOR

```
"Read PROJECT_EXPENSE_INTELLIGENCE_PLAN.md.

This is a 4-week plan in 4 phases.
We wrap existing Odoo backend — no Odoo changes needed.

Start Phase E1: Tool Implementation.

1. Create gateway/tools/project_expense.py
2. Implement the 3 tools (summary, breakdown, compare)
3. Add to TOOLS array in gateway/main.py
4. Add to CAPABILITY_MANIFEST
5. Write all 9 unit tests
6. Tests must pass

Critical:
- Wrap project.financial.service methods only
- Do NOT add to Odoo — backend already exists
- Numbers must match Odoo mobile API exactly
- Use asyncio.to_thread for XML-RPC calls
- Tell me when ready for live verification

After Phase E1 confirmed, move to Phase E2."
```
