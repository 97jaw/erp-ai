# GROUPING & FILTERING PLAN — Technical Guidance for Cursor AI

> **Purpose:** Implement Odoo-style filtering, grouping, and aggregation as a first-class AI capability. Currently the agent hangs/stuck when asked to "group by project with clients" because it iterates manually instead of using SQL aggregation.

> **Read first:** `PROJECT_CONTEXT.md`, `BACKEND_HARDENING_PLAN.md`

---

## 1. THE PROBLEM

### Observed Behavior
```
User: "Group by project with clients"

What AI tried to do:
  1. search_odoo on project.project (got list)
  2. For each project → search_odoo on res.partner (manual iteration)
  3. Got 2 results then hung or timed out

Why it failed:
  - Claude is doing app-level iteration instead of DB-level aggregation
  - No tool exists for proper group_by operations
  - Each iteration is a round-trip to Odoo (slow)
  - Token budget exhausts before completing
```

### Root Cause
```
Missing tool: Odoo-style read_group capability
Missing pattern: SQL-level aggregation
Missing UI: Grouped data visualization
```

---

## 2. WHAT ODOO DOES NATIVELY

Odoo has a powerful built-in method called `read_group` that handles:

```python
# Odoo native syntax
self.env['account.move.line'].read_group(
    domain   = [('date', '>=', '2026-01-01'), ('state', '=', 'posted')],
    fields   = ['debit:sum', 'credit:sum', 'balance:sum'],
    groupby  = ['account_id', 'partner_id'],
    orderby  = 'balance desc',
    limit    = 50,
)

# Returns:
[
  {
    'account_id': (101, 'Cash'),
    'partner_id': (54, 'Abu Dhabi Police'),
    'debit': 50000,
    'credit': 30000,
    'balance': 20000,
    '__count': 12,
    '__domain': [...]
  },
  ...
]
```

**Key features:**
- SQL-level aggregation (fast)
- Multi-level grouping
- Multiple aggregate functions
- Returns drill-down domain for each group
- Used by Odoo UI for all pivot tables and analytics

**This is what we need to expose to the AI.**

---

## 3. THE SOLUTION — Universal Group/Aggregate Tool

### 3.1 Tool Definition

```python
{
    "name": "group_and_aggregate",
    "description": (
        "Query any Odoo model with filters, grouping, and aggregation. "
        "Equivalent to SQL: SELECT group_fields, SUM(...), COUNT(...) "
        "FROM model WHERE filters GROUP BY group_fields.\n\n"

        "USE THIS WHEN:\n"
        "- User asks 'group by X' or 'breakdown by Y'\n"
        "- User asks 'totals per project/client/month/etc.'\n"
        "- User wants pivot-table style analysis\n"
        "- User wants top N grouped results\n"
        "- Any time you'd iterate records to compute sums\n\n"

        "DO NOT USE WHEN:\n"
        "- Just listing records (use search_odoo)\n"
        "- Single record details (use search_odoo)\n"
        "- Pre-existing report tool covers it (use that)\n\n"

        "EXAMPLES:\n"
        "- 'Group projects by client' → group_by=['partner_id'], model='project.project'\n"
        "- 'Total revenue per project this month'\n"
        "- 'Invoice count by partner'\n"
        "- 'Monthly expense trend'\n"
        "- 'Top 10 customers by sales'"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "model": {
                "type": "string",
                "description": "Odoo model: 'account.move.line', 'project.project', 'sale.order', 'res.partner', etc."
            },
            "domain": {
                "type": "array",
                "description": (
                    "Odoo domain filter. Array of tuples [field, operator, value]. "
                    "Operators: =, !=, >, <, >=, <=, in, not in, like, ilike. "
                    "Logical operators: '&' (and, default), '|' (or), '!' (not).\n"
                    "Examples:\n"
                    "  [['state','=','posted'],['date','>=','2026-01-01']]\n"
                    "  ['|',['type','=','out_invoice'],['type','=','in_invoice']]"
                ),
                "items": {}
            },
            "group_by": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Fields to group by. Can be multiple for multi-level grouping. "
                    "For date fields, can append :day, :week, :month, :quarter, :year. "
                    "Examples:\n"
                    "  ['partner_id']           # group by partner\n"
                    "  ['partner_id', 'state']  # group by partner then state\n"
                    "  ['date:month']           # group by month\n"
                    "  ['analytic_account_id']  # group by project (in account.move.line)"
                )
            },
            "aggregates": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Fields to aggregate. Format: 'field:function'. "
                    "Functions: sum, avg, min, max, count, count_distinct. "
                    "Examples:\n"
                    "  ['debit:sum', 'credit:sum']\n"
                    "  ['amount_total:sum', 'id:count']\n"
                    "  ['margin:avg']"
                )
            },
            "order_by": {
                "type": "string",
                "description": (
                    "Sort the results. Format: 'field [asc|desc]'. "
                    "Examples: 'balance desc', 'partner_id asc', '__count desc'"
                )
            },
            "limit": {
                "type": "integer",
                "default": 50,
                "description": "Max groups to return. Use 5-10 for top-N, 50 for full breakdown."
            },
            "having": {
                "type": "object",
                "description": (
                    "Post-aggregation filters (optional). "
                    "Example: {'balance:sum': ['>', 1000]} = only groups with sum > 1000"
                )
            }
        },
        "required": ["model", "group_by"]
    }
}
```

---

### 3.2 Odoo Backend Implementation

Add to `project.financial.service` Odoo module:

```python
@api.model
def ai_group_and_aggregate(self, model, domain=None, group_by=None,
                            aggregates=None, order_by=None,
                            limit=50, having=None):
    """
    Universal AI-accessible read_group endpoint.
    Returns clean serializable aggregated data.
    """
    if not group_by:
        return {"error": "group_by is required"}

    try:
        Model = self.env[model]
    except KeyError:
        return {"error": f"Model '{model}' does not exist"}

    domain = domain or []
    aggregates = aggregates or []

    # Build fields list for read_group
    # Format: field name for groupby, field:func for aggregates
    fields = list(group_by) + list(aggregates)

    # Strip groupby modifiers (:month, etc.) for field validation
    clean_groupby = [g.split(':')[0] for g in group_by]
    clean_aggregates = [a.split(':')[0] for a in aggregates]

    # Validate fields exist
    model_fields = Model._fields
    for f in clean_groupby + clean_aggregates:
        if f not in model_fields and f != 'id':
            return {
                "error": f"Field '{f}' does not exist on model '{model}'",
                "available_fields": list(model_fields.keys())[:30]
            }

    try:
        # Determine if multi-level grouping is needed
        # Odoo's read_group only does ONE level natively
        # For multi-level, we recursively split
        if len(group_by) == 1:
            groups = Model.read_group(
                domain   = domain,
                fields   = fields,
                groupby  = group_by,
                orderby  = order_by,
                limit    = limit,
                lazy     = False,  # Important for proper grouping
            )
        else:
            # Multi-level grouping
            groups = self._recursive_group_by(
                Model, domain, group_by, aggregates, order_by, limit
            )

    except Exception as exc:
        return {
            "error": str(exc),
            "error_type": type(exc).__name__,
            "query": {
                "model": model,
                "domain": domain,
                "group_by": group_by,
                "aggregates": aggregates,
            }
        }

    # Apply HAVING filter if provided
    if having:
        groups = self._apply_having(groups, having)

    # Serialize result — convert all values to JSON-safe types
    clean_groups = []
    for g in groups:
        clean = {}
        for k, v in g.items():
            if k.startswith('__'):
                # __count, __domain — keep but rename
                clean[k.lstrip('_')] = self._serialize_value(v)
            else:
                clean[k] = self._serialize_value(v)
        clean_groups.append(clean)

    return {
        "model": model,
        "group_by": group_by,
        "aggregates": aggregates,
        "filters_applied": domain,
        "total_groups": len(clean_groups),
        "groups": clean_groups,
        "synthesized": True,
    }


def _recursive_group_by(self, Model, domain, group_by, aggregates,
                        order_by, limit):
    """
    Handle multi-level grouping by recursion.
    Example: group_by=['partner_id', 'state']
      → First group by partner_id
      → For each partner, group by state within that partner
    """
    first = group_by[0]
    rest = group_by[1:]

    fields = [first] + list(aggregates)
    top_groups = Model.read_group(
        domain   = domain,
        fields   = fields,
        groupby  = [first],
        orderby  = order_by,
        limit    = limit,
        lazy     = False,
    )

    result = []
    for g in top_groups:
        # For each top-level group, get sub-groups
        sub_domain = list(domain) + list(g.get('__domain', []))
        sub_groups = self._recursive_group_by(
            Model, sub_domain, rest, aggregates, order_by, limit
        ) if rest else []

        g['children'] = sub_groups
        result.append(g)

    return result


def _serialize_value(self, v):
    """Convert Odoo types to JSON-safe."""
    if hasattr(v, '_name'):  # Recordset
        return [v.id, v.display_name] if v else False
    if isinstance(v, (list, tuple)) and len(v) == 2 and isinstance(v[0], int):
        # (id, name) format
        return [v[0], v[1]]
    if isinstance(v, list):
        # Domain tuples
        return [self._serialize_value(x) for x in v]
    if hasattr(v, 'isoformat'):
        return v.isoformat()
    return v


def _apply_having(self, groups, having):
    """Filter groups by aggregate value conditions."""
    OPERATORS = {
        '>': lambda a, b: a > b,
        '<': lambda a, b: a < b,
        '>=': lambda a, b: a >= b,
        '<=': lambda a, b: a <= b,
        '=': lambda a, b: a == b,
        '!=': lambda a, b: a != b,
    }

    filtered = []
    for g in groups:
        passes_all = True
        for field, condition in having.items():
            if isinstance(condition, list) and len(condition) == 2:
                op, value = condition
                actual = g.get(field, 0) or 0
                if not OPERATORS[op](actual, value):
                    passes_all = False
                    break
        if passes_all:
            filtered.append(g)
    return filtered
```

---

### 3.3 Gateway Integration

In `gateway/main.py` add to execute_tool:

```python
if tool_name == "group_and_aggregate":
    return adapter.call_method(
        "project.financial.service",
        "ai_group_and_aggregate",
        [
            tool_input.get("model"),
            tool_input.get("domain", []),
            tool_input.get("group_by", []),
            tool_input.get("aggregates", []),
            tool_input.get("order_by"),
            tool_input.get("limit", 50),
            tool_input.get("having"),
        ],
    )
```

---

## 4. EXAMPLE QUERIES AI CAN HANDLE

### 4.1 Projects Grouped by Client

```python
# User: "Show projects grouped by client"
group_and_aggregate(
    model      = "project.project",
    domain     = [["active", "=", True]],
    group_by   = ["partner_id"],
    aggregates = ["id:count", "wo_amount:sum"],
    order_by   = "wo_amount:sum desc",
    limit      = 20,
)

# Returns:
{
  "groups": [
    {
      "partner_id": [54, "Abu Dhabi Police"],
      "count": 15,
      "wo_amount": 45000000,
    },
    {
      "partner_id": [89, "Ministry of Education"],
      "count": 8,
      "wo_amount": 12000000,
    },
    ...
  ]
}
```

### 4.2 Monthly Revenue Trend

```python
# User: "Show monthly revenue trend for 2026"
group_and_aggregate(
    model      = "account.move",
    domain     = [
        ["state", "=", "posted"],
        ["type", "=", "out_invoice"],
        ["date", ">=", "2026-01-01"],
        ["date", "<=", "2026-12-31"],
    ],
    group_by   = ["date:month"],
    aggregates = ["amount_total:sum", "id:count"],
    order_by   = "date asc",
)
```

### 4.3 Expenses by Project AND Category

```python
# User: "Breakdown expenses by project and category"
group_and_aggregate(
    model      = "account.move.line",
    domain     = [
        ["account_id.user_type_id.internal_group", "=", "expense"],
        ["date", ">=", "2026-04-01"],
    ],
    group_by   = ["analytic_account_id", "account_id"],
    aggregates = ["debit:sum"],
    order_by   = "debit:sum desc",
    limit      = 100,
)
```

### 4.4 Top Customers by Revenue

```python
# User: "Top 10 customers by revenue this year"
group_and_aggregate(
    model      = "account.move",
    domain     = [
        ["state", "=", "posted"],
        ["type", "=", "out_invoice"],
        ["date", ">=", "2026-01-01"],
    ],
    group_by   = ["partner_id"],
    aggregates = ["amount_total:sum", "id:count"],
    order_by   = "amount_total:sum desc",
    limit      = 10,
)
```

### 4.5 Overdue Invoices by Client

```python
# User: "Which clients have overdue invoices?"
group_and_aggregate(
    model      = "account.move",
    domain     = [
        ["state", "=", "posted"],
        ["type", "=", "out_invoice"],
        ["payment_state", "in", ["not_paid", "partial"]],
        ["invoice_date_due", "<", today],
    ],
    group_by   = ["partner_id"],
    aggregates = ["amount_residual:sum", "id:count"],
    order_by   = "amount_residual:sum desc",
    limit      = 20,
)
```

---

## 5. AI PROMPT INTEGRATION

Add to system prompt:

```python
GROUPING_INSTRUCTIONS = """

WHEN USER ASKS FOR GROUPED DATA:

User phrases that signal grouping:
  - "group by X"
  - "breakdown by Y"
  - "totals per Z"
  - "top N by metric"
  - "X grouped by Y"
  - "show me Z categorized by W"
  - "per project", "per client", "per month"

ALWAYS use group_and_aggregate tool for these — never iterate manually.

KEY ODOO MODELS FOR COMMON GROUPINGS:

Projects:
  Model: project.project
  Common groupings: partner_id, user_id, stage_id
  Aggregates: wo_amount:sum, id:count

Invoices/Revenue:
  Model: account.move
  Common groupings: partner_id, date:month, journal_id, state
  Aggregates: amount_total:sum, amount_residual:sum, id:count
  Filter for invoices: [['type','=','out_invoice'],['state','=','posted']]

Bills/Expenses:
  Model: account.move
  Filter: [['type','=','in_invoice'],['state','=','posted']]

Journal Entries:
  Model: account.move.line
  Common groupings: account_id, partner_id, analytic_account_id, date:month
  Aggregates: debit:sum, credit:sum, balance:sum
  Filter: [['parent_state','=','posted']]

Sales Orders:
  Model: sale.order
  Common groupings: partner_id, user_id, state, date_order:month
  Aggregates: amount_total:sum, id:count

Purchase Orders:
  Model: purchase.order
  Common groupings: partner_id, state, date_order:month
  Aggregates: amount_total:sum, id:count

TIME-BASED GROUPINGS:
  - "today", "this week", "this month", "this quarter", "this year"
  - Add ":day", ":week", ":month", ":quarter", ":year" to date field
  - Example: group_by=['date:month']

ALWAYS:
  - Set a reasonable limit (10 for top-N, 50 for breakdowns)
  - Sort by the aggregate descending for "top" queries
  - Use proper filter for posted/active records only
  - Format response as appropriate visualization (table or chart)
"""
```

---

## 6. VISUALIZATION FOR GROUPED RESULTS

### 6.1 Single-Level Grouping → BAR_CHART or DATA_TABLE

```
For numeric aggregates → BAR_CHART:
  X-axis: group field
  Y-axis: aggregate value
  Color: theme accent
  Hover: shows all aggregates

For non-numeric → DATA_TABLE:
  Columns: group fields + aggregates
  Rows: each group
```

### 6.2 Multi-Level Grouping → NESTED_TABLE (New Viz Type)

Add new visualization type for hierarchical groups:

```javascript
// New visual_type: GROUPED_TABLE
{
  "visual_type": "GROUPED_TABLE",
  "label": "Projects by Client and Status",
  "groups": [
    {
      "name": "Abu Dhabi Police",
      "aggregates": { "count": 15, "wo_amount": 45000000 },
      "children": [
        {
          "name": "In Progress",
          "aggregates": { "count": 8, "wo_amount": 25000000 }
        },
        {
          "name": "Completed",
          "aggregates": { "count": 7, "wo_amount": 20000000 }
        }
      ]
    },
    ...
  ]
}
```

### 6.3 Frontend Component: GroupedTable.jsx

```jsx
function GroupedTable({ groups, level = 0 }) {
  return (
    <div style={{ marginLeft: level * 20 }}>
      {groups.map((g, i) => (
        <div key={i}>
          <div className="group-header">
            <span>{g.name}</span>
            <span>{formatAggregates(g.aggregates)}</span>
            {g.children && <ExpandIcon />}
          </div>
          {g.children && (
            <GroupedTable groups={g.children} level={level + 1} />
          )}
        </div>
      ))}
    </div>
  );
}

// Features:
// - Collapsible/expandable groups
// - Indented hierarchy
// - Summary row at top
// - Click group → drill down via __domain
```

### 6.4 PIVOT_TABLE for Cross-Tabulation

For queries like "Revenue by Client by Month":

```
                Jan'26  Feb'26  Mar'26  Apr'26  Total
  ─────────────────────────────────────────────────────
  Abu Dhabi PD   2.1M    3.4M    2.8M    4.2M    12.5M
  Min Education  0.8M    1.2M    1.5M    1.0M     4.5M
  Civil Defense  0.5M    0.7M    0.9M    1.1M     3.2M
  ─────────────────────────────────────────────────────
  Total          3.4M    5.3M    5.2M    6.3M    20.2M
```

---

## 7. PERFORMANCE CONSIDERATIONS

### 7.1 Query Limits

```python
DEFAULT_LIMITS = {
    "simple_groupby": 50,       # Single level
    "multi_groupby": 20,        # Multi-level (more expensive)
    "time_series": 36,          # Months for 3 years max
    "top_n": 10,                # Top queries
}

# Enforce in backend
def ai_group_and_aggregate(self, ..., limit=50):
    # Cap at reasonable maximum
    limit = min(limit, 200)
```

### 7.2 Caching Strategy

```python
CACHE_TTLS = {
    "group_and_aggregate": 300,  # 5 minutes
}

# Cache key includes all parameters
# Same query within 5 min → cached
```

### 7.3 Indexing Recommendations

For the Odoo PostgreSQL database, ensure these indexes exist:

```sql
-- Critical for grouping performance:
CREATE INDEX IF NOT EXISTS idx_account_move_line_account_partner
  ON account_move_line (account_id, partner_id);

CREATE INDEX IF NOT EXISTS idx_account_move_line_date_state
  ON account_move_line (date, parent_state);

CREATE INDEX IF NOT EXISTS idx_account_move_partner_type
  ON account_move (partner_id, type, state);

CREATE INDEX IF NOT EXISTS idx_project_partner
  ON project_project (partner_id);

CREATE INDEX IF NOT EXISTS idx_account_move_line_analytic
  ON account_move_line (analytic_account_id, date);
```

### 7.4 Timeout Protection

```python
# In gateway/main.py
import asyncio

async def execute_tool_with_timeout(tool_name, tool_input, adapter, timeout=30):
    """Wrap tool execution with timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(execute_tool, tool_name, tool_input, adapter),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        return {
            "error": "query_timeout",
            "message": "Query took too long. Try narrowing the date range or adding filters.",
            "suggestion": "Reduce limit or add specific filter criteria"
        }
```

---

## 8. EDGE CASES

### 8.1 Empty Groups
```python
# If group has no records:
{
  "partner_id": [54, "Abu Dhabi Police"],
  "amount_total": 0,
  "count": 0
}
# Filter these out unless user wants to see "zero" groups
```

### 8.2 Many2many Fields
```python
# Cannot directly group_by m2m fields
# Solution: Use the through-relation model
# Example: Group by tag_ids → use account.move.line.tag_ids
```

### 8.3 Date Granularity Errors
```python
# User says "last 5 years grouped by month" = 60 groups
# Default limit 50 cuts off
# Solution: AI should calculate expected groups and adjust limit
```

### 8.4 Multi-Company
```python
# Always inject company filter:
if not any(d[0] == 'company_id' for d in domain if isinstance(d, list)):
    domain.append(['company_id', '=', 1])  # Default to Elrace
```

---

## 9. ERROR HANDLING

### 9.1 Common Errors

```python
ERROR_PATTERNS = {
    "field_not_exists": {
        "user_message": "I don't recognize that field. Available fields include: ...",
        "ai_recovery": "Try a different field name"
    },
    "invalid_model": {
        "user_message": "That model doesn't exist. Did you mean...?",
        "ai_recovery": "Suggest similar valid models"
    },
    "timeout": {
        "user_message": "Query is taking too long. Adding more specific filters will help.",
        "ai_recovery": "Reduce date range or add filters"
    },
    "too_many_groups": {
        "user_message": "Too many groups to display. Showing top N.",
        "ai_recovery": "Truncate to limit"
    },
}
```

### 9.2 AI Self-Recovery

```
If tool returns error:
  1. Read error_type and available_fields
  2. Try alternative field names
  3. If still failing, ask user to clarify
  4. Never hang — always return something
```

---

## 10. IMPLEMENTATION PHASES

### Phase 1 — Core Tool (Week 1)
```
[ ] Add ai_group_and_aggregate method to project.financial.service
[ ] Test single-level grouping with all common models
[ ] Add tool definition in gateway/main.py
[ ] Update SYSTEM_PROMPT with grouping instructions
[ ] Live test with: projects by client, invoices by month
```

### Phase 2 — Multi-Level + Visualization (Week 2)
```
[ ] Implement recursive multi-level grouping
[ ] Add GROUPED_TABLE visualization type
[ ] Build GroupedTable.jsx component
[ ] Add expand/collapse interactions
[ ] Test 2-level and 3-level groupings
```

### Phase 3 — Pivot Tables (Week 3)
```
[ ] Add PIVOT_TABLE visualization type
[ ] Cross-tabulation logic (rows + columns)
[ ] Build PivotTable.jsx component
[ ] Add subtotals and totals
[ ] Click-to-drilldown via __domain
```

### Phase 4 — Performance + Polish (Week 4)
```
[ ] Add database indexes (with Odoo admin)
[ ] Implement query timeout handling
[ ] Add caching layer
[ ] Skeleton loading state for grouped queries
[ ] Performance testing with large datasets
```

---

## 11. TESTING STRATEGY

### 11.1 Required Tests

```python
# tests/test_group_aggregate.py

def test_simple_grouping():
    """Group projects by client"""
    result = adapter.call_method(
        "project.financial.service",
        "ai_group_and_aggregate",
        ["project.project", [["active","=",True]], ["partner_id"], ["id:count"]]
    )
    assert "groups" in result
    assert len(result["groups"]) > 0
    assert "partner_id" in result["groups"][0]
    assert "count" in result["groups"][0]

def test_multi_level_grouping():
    """Group projects by client AND state"""
    result = adapter.call_method(
        "project.financial.service",
        "ai_group_and_aggregate",
        ["project.project", [], ["partner_id", "stage_id"], ["id:count"]]
    )
    assert "groups" in result
    # Each top-level group has children
    assert "children" in result["groups"][0]

def test_time_grouping():
    """Group invoices by month"""
    result = adapter.call_method(
        "project.financial.service",
        "ai_group_and_aggregate",
        ["account.move",
         [["type","=","out_invoice"],["state","=","posted"]],
         ["date:month"],
         ["amount_total:sum"]]
    )
    assert "groups" in result

def test_top_n():
    """Top 5 customers"""
    result = adapter.call_method(...)
    assert len(result["groups"]) <= 5

def test_error_invalid_model():
    result = adapter.call_method(
        "project.financial.service",
        "ai_group_and_aggregate",
        ["non.existent.model", [], ["field"], []]
    )
    assert "error" in result

def test_error_invalid_field():
    result = adapter.call_method(
        "project.financial.service",
        "ai_group_and_aggregate",
        ["project.project", [], ["nonexistent_field"], []]
    )
    assert "error" in result
    assert "available_fields" in result
```

### 11.2 Live Conversation Tests

After implementation, test these queries end-to-end:

```
✓ "Show projects grouped by client"
✓ "Top 10 customers by sales this year"
✓ "Monthly revenue trend for 2026"
✓ "Expense breakdown by project and category"
✓ "Which clients have overdue invoices?"
✓ "Group invoices by status"
✓ "Sales orders by salesperson this month"
✓ "Group employees by department"
✓ "Purchase orders by vendor and state"
✓ "Stock movements by warehouse and product"
```

All should complete in < 5 seconds without hanging.

---

## 12. SUCCESS CRITERIA

```
✓ "Group projects by client" completes in < 3s
✓ No hanging or timeouts on common queries
✓ Multi-level grouping works (up to 3 levels)
✓ Time-based grouping works (day/week/month/quarter/year)
✓ Aggregates compute correctly (sum/count/avg/min/max)
✓ Results render as proper visualization
✓ Click on group drills down to records
✓ Errors are user-friendly with recovery suggestions
✓ Cache reduces repeat query latency to < 200ms
✓ AI uses this tool naturally for any "group by" phrasing
```

---

## 13. ANTI-PATTERNS TO AVOID

```
✗ Don't iterate records in Python for aggregation (use read_group)
✗ Don't fetch full records when you only need aggregates
✗ Don't call search_odoo in a loop (N+1 problem)
✗ Don't return raw recordsets (serialize properly)
✗ Don't allow unlimited limits (cap at 200)
✗ Don't skip the domain filter for "active" records
✗ Don't forget company_id filter for multi-company setups
✗ Don't render >100 groups in UI without pagination
```

---

## 14. QUICK REFERENCE FOR CURSOR

When implementing:

```
1. Read PROJECT_CONTEXT.md → Pattern 1 (Adding Tools)
2. Add ai_group_and_aggregate to Odoo module first
3. Test directly: adapter.call_method(...)
4. Verify multi-level works (recursive)
5. Add tool definition in gateway/main.py
6. Update SYSTEM_PROMPT with examples
7. Build GroupedTable.jsx component
8. Add PIVOT_TABLE visual type
9. Test all 10 example queries above
10. Profile performance — must be < 5s
```

---

## 15. RELATED FILES

```
Modify:
  - project.financial.service Odoo module (add ai_group_and_aggregate)
  - gateway/main.py (add tool definition + executor)
  - core/state.py (add GROUPED_TABLE, PIVOT_TABLE to VisualType enum)
  - ooa-ui/src/App.jsx (add GroupedTable component)

Reference:
  - PROJECT_CONTEXT.md (architecture patterns)
  - BACKEND_HARDENING_PLAN.md (other tool patterns)
  - V1.2_VISION.md (PDF generation may use grouped data)
```
