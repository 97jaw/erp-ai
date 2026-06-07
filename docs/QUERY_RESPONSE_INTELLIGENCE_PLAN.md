# QUERY & RESPONSE INTELLIGENCE PLAN

> **Goal:** Transform every interaction from a raw data dump into a guided, intelligent experience — smart suggestions before and after responses, progressive report disclosure, proper pagination, and a clean UI with no bugs.

> **Read first:** `PROJECT_CONTEXT.md`, `PRODUCT_QUALITY_FRAMEWORK.md`, `FINANCIAL_INTELLIGENCE_PLAN.md`

---

# PART I — THE PROBLEM STATEMENT

## 1. Current State vs Target State

```
CURRENT (Broken Experience):
─────────────────────────────
User: "P&L"
AI:   [Immediately fetches ALL data for infinite date range]
      → Shows wall of text + 1000 rows
      → User overwhelmed
      → No suggestions before or after
      → No way to drill down
      → No default date protection

TARGET (Guided Intelligence):
─────────────────────────────
User: "P&L"
AI:   [BEFORE fetching — PRE suggestions appear]
      "Which period would you like?
       [This Month] [Last 3 Months] [This Year] [Custom]
       or [Skip — use last 3 months]"

User: [Selects "This Month"]
AI:   [Shows SUMMARY first]
      → 4 KPI cards + 1 chart
      → "Want a detailed breakdown? [Yes, show details] [No thanks]"

User: [Selects "Yes, show details"]
AI:   [Shows DETAIL with pagination]
      → Top 20 rows of 247 total
      → "Showing 20 of 247 accounts [Load More] [Export All]"

      [POST suggestions appear]
      → "Compare with last month"
      → "Breakdown by project"
      → "Generate PDF report"
      [Show more suggestions ▼]
```

---

# PART II — PRE-RESPONSE SUGGESTION SYSTEM

## 2. What Are Pre-Response Suggestions

```
Pre-response suggestions appear BEFORE the AI fetches data.
They are CLARIFICATION suggestions — asking the user to specify
what they actually want, avoiding guesswork.

Difference from post-response:
  Pre-response: "What do you want?" (before fetching)
  Post-response: "What do you want next?" (after showing)
```

## 3. When to Show Pre-Response Suggestions

```
TRIGGER conditions (show pre-suggestions):
  ✓ Query has no date range specified
  ✓ Query mentions multiple possible entities
  ✓ Query is ambiguous about scope (project? company?)
  ✓ Query could be summary OR detailed
  ✓ Multiple grouping options exist

DO NOT trigger (fetch directly):
  ✓ Date range clearly specified
  ✓ Specific project/partner named
  ✓ User already answered a pre-suggestion
  ✓ Query is simple greeting or general question
```

## 4. Pre-Suggestion Categories

### 4.1 Date Range Suggestions (Most Common)

```
Trigger: Any financial report without date

Suggestion set:
  [📅 This Month]      → current month
  [📅 Last 3 Months]   → default, highlighted
  [📅 This Year]       → YTD
  [📅 Custom Range]    → opens date picker
  [⏭ Skip]            → use default (last 3 months)

Arabic version:
  [📅 هذا الشهر]
  [📅 آخر 3 أشهر]
  [📅 هذا العام]
  [📅 نطاق مخصص]
  [⏭ تخطي]
```

### 4.2 Scope Suggestions

```
Trigger: "Show P&L" without specifying scope

Suggestion set:
  [🏢 Company Wide]     → all projects combined
  [🏗️ By Project]      → grouped by project
  [👤 By Client]        → grouped by client
  [📊 Compare Periods]  → show comparison

Skip option always present.
```

### 4.3 Filter Suggestions

```
Trigger: "Show top projects" — needs more context

  [💰 By Revenue]        → rank by revenue
  [📉 By Cost]           → rank by total cost
  [📈 By Profit Margin]  → rank by margin %
  [⚠️ Over Budget]       → show overruns

  [🔢 Top 5]  [🔢 Top 10]  [🔢 Top 20]
```

### 4.4 Detail Level Suggestions

```
Trigger: User asks for report

  [📋 Summary Only]      → KPIs + chart
  [📊 Standard Report]   → top 20 rows
  [📁 Full Details]      → all records paginated
```

## 5. Pre-Suggestion Implementation

### 5.1 Claude Signal — `<clarify>` Tag

```
Claude detects ambiguity in the FIRST response token.
Emits special tag before any other content:

<clarify>
{
  "reason": "date_range_missing",
  "question": "Which time period would you like for the P&L?",
  "question_ar": "أي فترة زمنية تريد للأرباح والخسائر؟",
  "options": [
    {"id": "this_month", "label": "This Month", "label_ar": "هذا الشهر",
     "query_suffix": " for this month"},
    {"id": "last_3m", "label": "Last 3 Months", "label_ar": "آخر 3 أشهر",
     "query_suffix": " for the last 3 months", "is_default": true},
    {"id": "ytd", "label": "This Year", "label_ar": "هذا العام",
     "query_suffix": " for this year"},
    {"id": "custom", "label": "Custom Range", "label_ar": "نطاق مخصص",
     "action": "open_date_picker"}
  ],
  "skip_option": {
    "label": "Skip (use last 3 months)",
    "label_ar": "تخطي (آخر 3 أشهر)",
    "query_suffix": " for the last 3 months"
  }
}
</clarify>
```

### 5.2 System Prompt Addition

```python
PRE_SUGGESTION_INSTRUCTIONS = """

PRE-RESPONSE CLARIFICATION PROTOCOL:

Before fetching ANY financial data, check:

1. DATE RANGE SPECIFIED?
   If NO date range in user query → emit <clarify> with date options
   Then STOP and wait for user selection.

2. SCOPE CLEAR?
   If "P&L" without scope → emit <clarify> with scope options
   "project X" clearly scoped → proceed directly

3. SKIP/DEFAULT handling:
   If user selects "Skip" or presses Enter without selecting →
   use LAST 3 MONTHS as default ALWAYS.
   Never query without a date range. NEVER.

DEFAULT DATE RANGE RULE (ABSOLUTE):
  ⚠ ALWAYS use last 3 months when no date specified.
  NEVER fetch all-time data.
  NEVER fetch without a date range.
  Code the default: date_from = today - 90 days

AFTER user answers clarification OR if query is clear:
  → Proceed with data fetch
  → Show SUMMARY first (see progressive disclosure rules)

DO NOT emit <clarify> when:
  - User already answered a clarification
  - Date range is explicitly stated
  - User says "skip" or "default"
  - Query is a follow-up to existing conversation
"""
```

### 5.3 Frontend Handler

```javascript
// Parse <clarify> from stream
function parseStreamChunk(chunk, botId) {
  if (chunk.includes('<clarify>')) {
    // Extract clarify JSON
    const clarifyStart = chunk.indexOf('<clarify>') + 9;
    const clarifyEnd = chunk.indexOf('</clarify>');
    const clarifyJson = chunk.slice(clarifyStart, clarifyEnd);
    const clarify = JSON.parse(clarifyJson);

    // Show pre-suggestion UI
    setMessages(prev => prev.map(msg =>
      msg.id === botId
        ? {
            ...msg,
            clarification: clarify,
            state: 'awaiting_clarification',
          }
        : msg
    ));

    setLoading(false);  // Stop loading — waiting for user
    return;  // Don't process rest of stream
  }
  // Normal text processing
}

// When user selects a clarification option
const handleClarificationSelect = (option, originalQuery) => {
  const enrichedQuery = originalQuery + option.query_suffix;
  sendMessage(enrichedQuery, { skipClarification: true });
};

// When user skips
const handleClarificationSkip = (originalQuery, skipOption) => {
  const enrichedQuery = originalQuery + skipOption.query_suffix;
  sendMessage(enrichedQuery, { skipClarification: true });
};
```

### 5.4 Clarification UI Component

```jsx
// ClarificationCard.jsx
function ClarificationCard({ clarification, originalQuery, onSelect }) {
  const [showDatePicker, setShowDatePicker] = useState(false);
  const isRtl = isArabic(clarification.question);

  return (
    <div style={styles.clarifyCard}>
      <div style={styles.clarifyQuestion}>
        {isRtl ? clarification.question_ar : clarification.question}
      </div>

      <div style={styles.clarifyOptions}>
        {clarification.options.map(opt => (
          <button
            key={opt.id}
            style={{
              ...styles.clarifyBtn,
              ...(opt.is_default ? styles.clarifyBtnDefault : {}),
            }}
            onClick={() => {
              if (opt.action === 'open_date_picker') {
                setShowDatePicker(true);
              } else {
                onSelect(opt, originalQuery);
              }
            }}
          >
            {isRtl ? opt.label_ar : opt.label}
            {opt.is_default && <span style={styles.defaultBadge}>Default</span>}
          </button>
        ))}
      </div>

      {showDatePicker && (
        <DateRangePicker
          onSelect={(from, to) => {
            onSelect({
              query_suffix: ` from ${from} to ${to}`
            }, originalQuery);
          }}
          onCancel={() => setShowDatePicker(false)}
        />
      )}

      <button
        style={styles.skipBtn}
        onClick={() => onSelect(clarification.skip_option, originalQuery)}
      >
        {isRtl ? clarification.skip_option.label_ar : clarification.skip_option.label}
      </button>
    </div>
  );
}
```

---

# PART III — POST-RESPONSE SUGGESTION ENGINE

## 6. Smart Post-Suggestions

```
After EVERY substantive response, show exactly 3 suggestions.
Each suggestion is actionable and specific to what was just shown.

Rules:
  ✓ Exactly 3 at a time
  ✓ [Show More] rotates to next 3 from pool
  ✓ Never repeat the exact same suggestion twice in session
  ✓ Context-aware (know what report was just shown)
  ✓ Include filters/groupby in suggestions
  ✓ Skippable — user can ignore them completely
  ✓ Language matches user's language
```

## 7. Suggestion Pools by Report Type

### 7.1 P&L Suggestions

```python
PANDL_SUGGESTIONS = {
    "drill_down": [
        "Break down expenses by account",
        "Show which projects contributed most to revenue",
        "What are the top 5 cost categories?",
        "Show income breakdown by client",
    ],
    "comparison": [
        "Compare with last month",
        "Compare with same period last year",
        "Show P&L trend for last 6 months",
        "How does this compare to our budget?",
    ],
    "filter": [
        "Filter by Abu Dhabi Police projects only",
        "Show only direct project costs",
        "Exclude administrative expenses",
        "Group by operating unit",
    ],
    "export": [
        "Generate executive PDF report",
        "Export to Excel for analysis",
        "Create management summary",
    ],
    "analysis": [
        "Why is the margin lower than last month?",
        "Which expense categories can be reduced?",
        "What is our largest fixed cost?",
        "Identify any unusual transactions",
    ],
}
```

### 7.2 Balance Sheet Suggestions

```python
BALANCE_SHEET_SUGGESTIONS = {
    "analysis": [
        "What is our current ratio?",
        "Calculate quick ratio",
        "How has working capital changed?",
        "Compare assets vs liabilities trend",
    ],
    "detail": [
        "Show breakdown of current assets",
        "List all outstanding receivables",
        "Show fixed assets by category",
        "What are our long-term liabilities?",
    ],
}
```

### 7.3 Project Report Suggestions

```python
PROJECT_SUGGESTIONS = {
    "costs": [
        "Break down costs by LPO, petty cash, labor",
        "Show cost trend over project timeline",
        "Compare planned vs actual costs",
        "Which cost category is highest?",
    ],
    "comparison": [
        "Compare all active projects side by side",
        "Which projects are over budget?",
        "Show top 5 most profitable projects",
        "Compare this project to similar ones",
    ],
    "client": [
        "Show all projects for this client",
        "What is total revenue from this client?",
        "View client payment history",
    ],
}
```

### 7.4 Receivables Suggestions

```python
RECEIVABLES_SUGGESTIONS = {
    "priority": [
        "Which client is most overdue?",
        "Show invoices overdue by more than 60 days",
        "What is the total risk amount?",
        "Show collection priority list",
    ],
    "client": [
        "Send reminder for top overdue client",
        "Show full ledger for this client",
        "View payment history by client",
    ],
}
```

## 8. Suggestion Pool Manager

```python
# gateway/suggestions.py

from enum import Enum
import random

class SuggestionContext(Enum):
    PANDL = "pandl"
    BALANCE_SHEET = "balance_sheet"
    TRIAL_BALANCE = "trial_balance"
    GENERAL_LEDGER = "general_ledger"
    PARTNER_AGEING = "partner_ageing"
    PROJECT = "project"
    RECEIVABLES = "receivables"
    COMPARISON = "comparison"
    GENERAL = "general"


def build_suggestions(
    context: SuggestionContext,
    data_context: dict,         # What was just shown
    session_history: list,      # Suggestions already shown this session
    language: str = "en",
    count: int = 3,
) -> list[str]:
    """
    Build 3 contextual suggestions based on what was just shown.
    Never repeats suggestions already shown in this session.
    """
    pool = get_suggestion_pool(context, data_context)

    # Filter out already-shown suggestions
    fresh = [s for s in pool if s not in session_history]

    # If we've exhausted the pool, reset
    if len(fresh) < count:
        fresh = pool  # Reset rotation

    # Pick count suggestions intelligently (not fully random)
    selected = pick_diverse_suggestions(fresh, count)

    # Translate if needed
    if language == "ar":
        selected = [translate_suggestion_ar(s) for s in selected]

    return selected


def get_suggestion_pool(context: SuggestionContext, data: dict) -> list[str]:
    """Build suggestion pool based on context and data."""
    pool = []

    if context == SuggestionContext.PANDL:
        pool.extend(PANDL_SUGGESTIONS["drill_down"])
        pool.extend(PANDL_SUGGESTIONS["comparison"])
        pool.extend(PANDL_SUGGESTIONS["filter"])

        # Context-aware additions based on data
        if data.get("net_profit", 0) < 0:
            pool.insert(0, "Why is this period showing a loss?")
        if data.get("margin", 100) < 15:
            pool.insert(0, "How can we improve the profit margin?")

    elif context == SuggestionContext.PROJECT:
        pool.extend(PROJECT_SUGGESTIONS["costs"])
        pool.extend(PROJECT_SUGGESTIONS["comparison"])

        # Context-aware
        if data.get("over_budget"):
            pool.insert(0, "Show which cost category caused the overrun")

    return pool


def pick_diverse_suggestions(pool: list, count: int) -> list:
    """
    Pick diverse suggestions — ensure mix of drill/compare/action types.
    """
    categories = {
        "drill": [],
        "compare": [],
        "filter": [],
        "export": [],
        "analysis": [],
    }

    for s in pool:
        if any(w in s.lower() for w in ["break", "show", "list", "what"]):
            categories["drill"].append(s)
        elif any(w in s.lower() for w in ["compare", "vs", "trend", "change"]):
            categories["compare"].append(s)
        elif any(w in s.lower() for w in ["filter", "only", "exclude", "group"]):
            categories["filter"].append(s)
        elif any(w in s.lower() for w in ["pdf", "excel", "export", "generate"]):
            categories["export"].append(s)
        else:
            categories["analysis"].append(s)

    # Pick one from 3 different categories for variety
    selected = []
    for cat in ["drill", "compare", "analysis", "filter", "export"]:
        if categories[cat] and len(selected) < count:
            selected.append(random.choice(categories[cat]))

    return selected[:count]
```

## 9. "Show More Suggestions" Pattern

```jsx
// SuggestionBar.jsx
function SuggestionBar({ suggestions, onSelect, onShowMore, language }) {
  const [visible, setVisible] = useState(suggestions.slice(0, 3));
  const isRtl = language === 'ar';

  return (
    <div style={{
      ...styles.suggestionBar,
      flexDirection: isRtl ? 'row-reverse' : 'row',
    }}>
      {visible.map((s, i) => (
        <button
          key={i}
          style={styles.suggBtn}
          onClick={() => onSelect(s)}
        >
          {s}
        </button>
      ))}

      <button
        style={styles.moreBtn}
        onClick={() => {
          onShowMore();  // Backend rotates to next 3
        }}
      >
        {isRtl ? 'المزيد ▾' : 'More ▾'}
      </button>
    </div>
  );
}
```

---

# PART IV — PROGRESSIVE REPORT DISCLOSURE

## 10. The 3-Level System

```
Every report follows this pattern:

LEVEL 1 — SUMMARY (Always shown first)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
  │ Income │ │Expense │ │ Profit │ │ Margin │
  │ 17.4M  │ │ 13.3M  │ │  4.1M  │ │ 23.4%  │
  └────────┘ └────────┘ └────────┘ └────────┘

  [Bar chart of top 5 items]

  AI narrative: 2-3 sentence insight

  "Want the detailed breakdown?"
  [Yes, show accounts] [No thanks]


LEVEL 2 — STANDARD (Top 20 rows)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ┌────────────────────────────────────┐
  │ Account    Debit    Credit  Balance │ ← sortable
  │ Revenue    0        17.4M   17.4M  │
  │ Direct     11.6M    0       11.6M  │
  │ Admin      1.6M     0       1.6M   │
  │ ...                                │
  │ Showing 20 of 247 accounts         │
  │ [Load 20 more] [Load all] [Export] │
  └────────────────────────────────────┘

  "Want all 247 accounts?"
  [Load Full Report] [Export to Excel] [Generate PDF]


LEVEL 3 — FULL (All records, paginated)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Paginated table: 50 per page
  Page 1 / 5 | [← Prev] [Next →]
  Sort: clickable headers
  Export: always available
```

## 11. How AI Controls Progressive Disclosure

```python
PROGRESSIVE_DISCLOSURE_PROMPT = """

PROGRESSIVE REPORT DISCLOSURE — MANDATORY:

RULE 1: ALWAYS show summary first.
  Every financial report response must start with:
  → Summary KPIs (4 key numbers)
  → One visualization (chart or KPI grid)
  → 2-3 sentence narrative
  → Offer to expand

RULE 2: Ask before showing details.
  After summary, append:
  "Would you like the detailed breakdown?"
  Options: [See Account Details] [No Thanks]

RULE 3: Limit rows by default.
  When showing table data:
  → Default: top 20 rows only
  → Always show: "Displaying 20 of X total records"
  → Always offer: [Load More] [Export All]
  → NEVER dump all records without pagination notice

RULE 4: Signal report levels in visualization block.
  Add "level" field to visualization:
  {
    "visual_type": "FINANCIAL_REPORT",
    "level": "summary",             ← "summary", "standard", "full"
    "total_records": 247,
    "shown_records": 20,
    "can_expand": true,
    "expand_label": "See all 247 accounts",
    ...
  }

RULE 5: User asked for details → skip level 1.
  If user says "detailed", "full", "all accounts", "show everything"
  → Skip level 1 summary
  → Go directly to level 2 (still paginated)
"""
```

## 12. Visualization Level Schema Update

```python
# Updated visualization contract
VISUALIZATION_SCHEMA = {
    "visual_type": "FINANCIAL_REPORT | BAR_CHART | DATA_TABLE | ...",
    "label": "Report title",
    "level": "summary | standard | full",   # NEW
    "date_from": "2026-01-01",              # NEW - always show dates
    "date_to": "2026-03-31",               # NEW
    "total_records": 247,                  # NEW - total available
    "shown_records": 20,                   # NEW - currently shown
    "can_expand": True,                    # NEW - has more data?
    "expand_label": "See all 247 accounts",# NEW
    "kpis": {...},
    "data": {...},
    "suggestions": [...],
}
```

---

# PART V — LARGE DATA HANDLING

## 13. The Pagination System

### 13.1 Backend — Pagination Support

```python
def execute_query_with_pagination(
    params: dict,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """
    All data queries support pagination.
    Returns current page + metadata.
    """
    offset = (page - 1) * page_size

    # First get total count (fast)
    count_result = execute_count_query(params)
    total = count_result["total"]

    # Then get page data
    params["limit"] = page_size
    params["offset"] = offset
    data = execute_data_query(params)

    return {
        "data": data,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_records": total,
            "total_pages": math.ceil(total / page_size),
            "has_next": (page * page_size) < total,
            "has_prev": page > 1,
        }
    }


# Pagination endpoint
@app.post("/query/page")
async def get_next_page(
    query_id: str,           # Cache key for the original query
    page: int,
    page_size: int = 20,
    sort_by: str = None,
    sort_dir: str = "desc",
    user: User = Depends(get_current_user),
):
    """
    Get next page of results for an existing query.
    Query is cached by query_id.
    """
    cached_params = redis.get(f"query:{query_id}")
    if not cached_params:
        raise HTTPException(400, "Query expired. Please run again.")

    params = json.loads(cached_params)
    if sort_by:
        params["order_by"] = f"{sort_by} {sort_dir}"

    return execute_query_with_pagination(params, page, page_size)
```

### 13.2 Frontend — Pagination Component

```jsx
// DataTableWithPagination.jsx
function DataTableWithPagination({ data, pagination, queryId, onPageChange }) {
  const [sortColumn, setSortColumn] = useState(null);
  const [sortDir, setSortDir] = useState('desc');

  const handleSort = (column) => {
    const dir = column === sortColumn && sortDir === 'desc' ? 'asc' : 'desc';
    setSortColumn(column);
    setSortDir(dir);
    onPageChange(1, column, dir);  // Reset to page 1 with new sort
  };

  return (
    <div style={styles.tableContainer}>

      {/* Row count badge */}
      <div style={styles.tableHeader}>
        <span style={styles.rowCount}>
          Showing {pagination.page_size * (pagination.page - 1) + 1}–
          {Math.min(pagination.page * pagination.page_size, pagination.total_records)} of{' '}
          <strong>{pagination.total_records.toLocaleString()}</strong> records
        </span>
        <div style={styles.tableActions}>
          <button onClick={() => exportAll(queryId)}>
            📥 Export All
          </button>
          <button onClick={() => generatePDF(queryId)}>
            📄 PDF
          </button>
        </div>
      </div>

      {/* Table */}
      <div style={styles.tableScroll}>
        <table style={styles.table}>
          <thead>
            <tr>
              {columns.map(col => (
                <th
                  key={col.key}
                  onClick={() => handleSort(col.key)}
                  style={{
                    ...styles.th,
                    cursor: 'pointer',
                  }}
                >
                  {col.label}
                  {sortColumn === col.key && (
                    <span>{sortDir === 'desc' ? ' ↓' : ' ↑'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr
                key={i}
                style={{
                  background: i % 2 === 0
                    ? 'rgba(255,255,255,0.02)'
                    : 'transparent',
                  cursor: 'pointer',
                }}
                onClick={() => onRowDrillDown(row)}
              >
                {Object.values(row).map((cell, j) => (
                  <td key={j} style={styles.td}>
                    {formatCell(cell, columns[j])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination controls */}
      <div style={styles.pagination}>
        <button
          disabled={!pagination.has_prev}
          onClick={() => onPageChange(pagination.page - 1, sortColumn, sortDir)}
          style={styles.pageBtn}
        >
          ← Previous
        </button>

        <span style={styles.pageInfo}>
          Page {pagination.page} of {pagination.total_pages}
        </span>

        <button
          disabled={!pagination.has_next}
          onClick={() => onPageChange(pagination.page + 1, sortColumn, sortDir)}
          style={styles.pageBtn}
        >
          Next →
        </button>
      </div>

      {/* Quick load options */}
      {pagination.has_next && (
        <div style={styles.loadOptions}>
          <button onClick={() => onPageChange(pagination.page + 1)}>
            Load next 20
          </button>
          <button onClick={() => exportAll(queryId)}>
            Export all {pagination.total_records} to Excel
          </button>
        </div>
      )}
    </div>
  );
}
```

---

# PART VI — DEFAULT DATE RANGE

## 14. The Golden Rule

```
⚠ ABSOLUTE RULE: NEVER query financial data without a date range.

Default when not specified: LAST 3 MONTHS
  date_from = today - 90 days
  date_to   = today

This must be enforced at 3 levels:
  1. System prompt (Claude instruction)
  2. Tool execution (validate before calling)
  3. Backend gateway (inject default if missing)
```

## 15. Date Range Enforcement

```python
# gateway/date_utils.py

from datetime import date, timedelta

DEFAULT_RANGE_DAYS = 90  # Last 3 months

def get_default_date_range() -> tuple[str, str]:
    """Returns last 3 months date range."""
    today = date.today()
    date_from = (today - timedelta(days=DEFAULT_RANGE_DAYS)).strftime("%Y-%m-%d")
    date_to = today.strftime("%Y-%m-%d")
    return date_from, date_to


def enforce_date_range(tool_input: dict) -> dict:
    """
    Validate and enforce date range on all financial queries.
    Injects default if missing.
    """
    financial_tools = {
        "query_accounting", "get_financial_report",
        "get_general_ledger", "get_trial_balance",
        "group_and_aggregate", "compare_periods",
    }

    tool_name = tool_input.get("_tool_name", "")
    if tool_name not in financial_tools:
        return tool_input

    date_from = tool_input.get("date_from")
    date_to = tool_input.get("date_to")

    # Both missing → inject defaults
    if not date_from and not date_to:
        default_from, default_to = get_default_date_range()
        tool_input["date_from"] = default_from
        tool_input["date_to"] = default_to
        tool_input["_date_was_defaulted"] = True
        logger.info(
            "[DateRange] Defaulted to last 3 months: %s → %s",
            default_from, default_to
        )

    # Only from missing
    elif not date_from:
        tool_input["date_from"] = (
            date.fromisoformat(date_to) - timedelta(days=DEFAULT_RANGE_DAYS)
        ).strftime("%Y-%m-%d")

    # Only to missing
    elif not date_to:
        tool_input["date_to"] = date.today().strftime("%Y-%m-%d")

    # Validate: from before to
    if tool_input["date_from"] > tool_input["date_to"]:
        tool_input["date_from"], tool_input["date_to"] = (
            tool_input["date_to"], tool_input["date_from"]
        )

    # Validate: not future
    if tool_input["date_to"] > date.today().strftime("%Y-%m-%d"):
        tool_input["date_to"] = date.today().strftime("%Y-%m-%d")

    return tool_input


# Apply in execute_tool
def execute_tool(tool_name, tool_input, adapter):
    tool_input["_tool_name"] = tool_name
    tool_input = enforce_date_range(tool_input)
    # ... rest of execution
```

## 16. Date Range Display Badge

```
Every report visualization must show date range:

┌──────────────────────────────────────┐
│ P&L Summary                          │
│ 📅 Feb 14 – May 14, 2026 (90 days)  │ ← Always visible
│                                      │
│ [Change Period ▼]                    │
└──────────────────────────────────────┘

If date was defaulted, show subtle notice:
  📅 Last 3 months (default) [Change]
```

---

# PART VII — CURRENT UI BUG FIXES

## 17. Bug Catalog (All Known Issues)

### Bug 1 — Visualization Block Showing as Raw Text

```
Issue: <visualization>{...}</visualization> sometimes appears in chat text
Affected: App.jsx streaming parser

Root cause: When AI starts a new tool call after text,
            the clean-up regex doesn't catch the block

Fix:
  // In the 'done' handler — more aggressive cleanup
  let cleanText = msg.text;

  // Remove visualization block (any position)
  cleanText = cleanText.replace(
    /<visualization>[\s\S]*?<\/visualization>/g, ''
  );

  // Remove viz-hint tags
  cleanText = cleanText.replace(
    /<viz-hint>[\s\S]*?<\/viz-hint>/g, ''
  );

  // Remove clarify tags
  cleanText = cleanText.replace(
    /<clarify>[\s\S]*?<\/clarify>/g, ''
  );

  // Remove tool fetching artifacts
  cleanText = cleanText.replace(
    /\n_Fetching [^_]+\.\.\._\n/g, ''
  );
  cleanText = cleanText.replace(
    /Let me (try|get|fetch|search|look|check)[^\n]*/g, ''
  );

  cleanText = cleanText.trim();
```

### Bug 2 — Raw Field Names Visible

```
Issue: "amount_total:sum: 0" or "partner_id[54, 'Abu Dhabi Police']"
       showing in text or visualization

Fix:
  Add post-processing to humanize_output():

  def humanize_output(text: str) -> str:
      # Remove aggregate suffixes
      text = re.sub(r'\b(\w+):sum\b', r'\1', text)
      text = re.sub(r'\b(\w+):count\b', r'\1', text)
      text = re.sub(r'\b(\w+):avg\b', r'\1', text)

      # Fix Odoo tuples in text
      text = re.sub(r'\[(\d+),\s*[\'"]([^\'"]+)[\'"]\]', r'\2', text)

      return text
```

### Bug 3 — Suggestions Not Rewiring After Refresh

```
Issue: After page refresh, loaded suggestions from localStorage
       don't trigger new queries

Root cause: onSuggestion handlers are functions, not serializable

Fix (correct approach):
  // In sendMessage — store suggestion handler in component, not message
  // Don't attach handlers to individual messages
  // Use a single global handler in ChatScreen

  const handleSuggestionClick = useCallback((suggestion) => {
    sendMessage(suggestion, { isFromSuggestion: true });
  }, [sendMessage]);

  // In message rendering, pass the global handler
  <Suggestions
    items={msg.suggestions}
    onSelect={handleSuggestionClick}  // Always current, not stale
  />
```

### Bug 4 — Loading Spinner Doesn't Stop on Error

```
Issue: If AI fails, loading spinner stays on indefinitely

Fix:
  // In sendMessage catch block:
  } catch (err) {
    setLoading(false);           // ← Make sure this runs
    setError(err.message);
    setMessages(prev => prev.map(msg =>
      msg.id === botId
        ? { ...msg, text: "Sorry, something went wrong. Please try again." }
        : msg
    ));
  } finally {
    setLoading(false);           // ← Also in finally for safety
  }
```

### Bug 5 — Bar Chart Not Rendering

```
Issue: BAR_CHART visualization type exists in data but no component renders it

Root cause: Missing BAR_CHART case in Visualization component

Fix:
  // In Visualization.jsx
  function Visualization({ viz }) {
    if (!viz) return null;
    const { visual_type } = viz;

    if (visual_type === "KPI_CARD")         return <KPICard data={viz} />;
    if (visual_type === "DATA_TABLE")        return <DataTable data={viz} />;
    if (visual_type === "FINANCIAL_REPORT")  return <FinancialReport data={viz} />;
    if (visual_type === "BAR_CHART")         return <BarChart data={viz} />;  // ← ADD
    if (visual_type === "LINE_CHART")        return <LineChart data={viz} />;  // ← ADD
    if (visual_type === "GROUPED_TABLE")     return <GroupedTable data={viz} />;  // ← ADD
    if (visual_type === "PIVOT_TABLE")       return <PivotTable data={viz} />;  // ← ADD

    return null;
  }

  // Add BarChart component using Recharts:
  import { BarChart as RechartsBar, Bar, XAxis, YAxis,
           CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

  function BarChart({ data }) {
    const chartData = (data.data?.labels || []).map((label, i) => ({
      name: label.length > 20 ? label.slice(0, 20) + '...' : label,
      value: data.data?.values?.[i] || 0,
    }));

    return (
      <div style={styles.chartCard}>
        <div style={styles.chartTitle}>{data.label}</div>
        <ResponsiveContainer width="100%" height={300}>
          <RechartsBar data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={v => `AED ${(v/1e6).toFixed(1)}M`} />
            <Tooltip
              formatter={(v) => [`AED ${v.toLocaleString()}`, 'Amount']}
              contentStyle={{ background: '#1a2744', border: 'none' }}
            />
            <Bar dataKey="value" fill="#c9a84c" radius={[4, 4, 0, 0]} />
          </RechartsBar>
        </ResponsiveContainer>
      </div>
    );
  }
```

### Bug 6 — Textarea Not Auto-Resizing

```
Issue: Input box stays single line even for long messages

Fix:
  // In App.jsx input handler
  const handleInputChange = (e) => {
    const el = e.target;
    setInput(el.value);

    // Auto-resize
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 120) + 'px';
  };

  // Update textarea
  <textarea
    onChange={handleInputChange}  // ← Use this instead of direct setInput
    style={{
      ...styles.input,
      height: 'auto',              // ← Remove fixed height
      minHeight: '24px',
      maxHeight: '120px',
    }}
  />
```

### Bug 7 — Arabic Text Not Detected Mid-Sentence

```
Issue: Messages with mixed Arabic/English show wrong direction

Fix:
  const detectDirection = (text = "") => {
    const arabicChars = (text.match(/[\u0600-\u06FF]/g) || []).length;
    const latinChars = (text.match(/[a-zA-Z]/g) || []).length;

    // Use majority language
    if (arabicChars === 0 && latinChars === 0) return 'ltr';
    return arabicChars > latinChars ? 'rtl' : 'ltr';
  };

  // Apply per paragraph, not per message:
  text.split('\n').map((para, i) => (
    <p key={i} style={{ direction: detectDirection(para) }}>
      {para}
    </p>
  ))
```

### Bug 8 — Mobile Layout Overflows

```
Issue: Visualization cards and tables overflow on small screens

Fix in styles:
  tableScroll: {
    overflowX: 'auto',      // ← Already there
    WebkitOverflowScrolling: 'touch', // ← ADD for smooth iOS scrolling
    maxWidth: '100%',       // ← ADD
  },

  kpiGrid: {
    gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', // ← Responsive
  },

  messages: {
    padding: '24px 12px', // ← Reduce padding on mobile
  }

  // Add media query:
  @media (max-width: 768px) {
    .bubble { maxWidth: '90%'; }
    .kpi-value { fontSize: '20px'; }
    .reportKpis { gridTemplateColumns: '1fr 1fr'; }
  }
```

### Bug 9 — Duplicate Messages on Stream Reconnect

```
Issue: Sometimes messages appear twice when stream reconnects

Fix:
  // Track processed message IDs
  const processedIds = useRef(new Set());

  const addMessage = (msg) => {
    if (processedIds.current.has(msg.id)) return;
    processedIds.current.add(msg.id);
    setMessages(prev => [...prev, msg]);
  };
```

### Bug 10 — Clear Chat Not Resetting Session

```
Issue: After clear chat, old session_id persists
       AI has memory of previous conversation

Fix:
  const clearChat = () => {
    localStorage.removeItem("ooa_messages");
    localStorage.removeItem("ooa_session_id");
    localStorage.removeItem("ooa_suggestions_shown"); // ← Also clear suggestions cache

    // Force new session
    SESSION_ID = sessionId();
    localStorage.setItem("ooa_session_id", SESSION_ID);

    // Also notify backend to clear session
    fetch(`${API_BASE}/session/${SESSION_ID}`, { method: 'DELETE' });

    window.location.reload();
  };
```

---

# PART VIII — IMPLEMENTATION PHASES

## 18. Build Order (8 Weeks)

### Phase 1 — Bug Fixes (Week 1, HIGHEST PRIORITY)
```
[ ] Fix Bug 1: Visualization block showing as text
[ ] Fix Bug 2: Raw field names visible
[ ] Fix Bug 3: Suggestion handler rewiring
[ ] Fix Bug 4: Loading spinner stuck
[ ] Fix Bug 5: BAR_CHART not rendering (add Recharts)
[ ] Fix Bug 6: Textarea auto-resize
[ ] Fix Bug 7: Arabic detection
[ ] Fix Bug 8: Mobile overflow
[ ] Fix Bug 9: Duplicate messages
[ ] Fix Bug 10: Clear chat reset
[ ] Test all 10 fixes with real queries
```

### Phase 2 — Default Date Range (Week 2)
```
[ ] Implement enforce_date_range utility
[ ] Inject default in execute_tool
[ ] Update system prompt with date rules
[ ] Add date range badge to visualization schema
[ ] Show badge in report header component
[ ] Test: all queries get dates, no infinite range
```

### Phase 3 — Progressive Disclosure (Week 3)
```
[ ] Update visualization schema with level/pagination fields
[ ] Update system prompt with progressive disclosure rules
[ ] Build summary-level rendering
[ ] Add "Want detailed breakdown?" component
[ ] Build level switching in frontend
[ ] Test P&L: summary → detail flow
```

### Phase 4 — Pagination System (Week 4)
```
[ ] Implement execute_query_with_pagination backend
[ ] Add /query/page endpoint
[ ] Build DataTableWithPagination component
[ ] Add sort-by-column to tables
[ ] Add "Load more" / page controls
[ ] Test with 1000+ row datasets
```

### Phase 5 — Pre-Response Suggestions (Week 5)
```
[ ] Add <clarify> tag parser in system prompt
[ ] Build ClarificationCard component
[ ] Handle date picker option
[ ] Handle skip option
[ ] Test: P&L without date shows clarification
[ ] Test: P&L with date skips clarification
```

### Phase 6 — Post-Response Suggestion Engine (Week 6)
```
[ ] Build suggestion pool per report type
[ ] Build SuggestionPoolManager
[ ] Implement diversity picker
[ ] Add session-level dedup
[ ] Build "Show More" rotation
[ ] Test: every report type gets useful suggestions
```

### Phase 7 — Integration Testing (Week 7)
```
[ ] Test complete flow: vague query → clarify → summary → details → suggestions
[ ] Test Arabic language throughout
[ ] Test on mobile devices
[ ] Test all 50 canonical queries from FINANCIAL_INTELLIGENCE_PLAN
[ ] Performance: ensure no regressions
```

### Phase 8 — Polish (Week 8)
```
[ ] Visual polish on all new components
[ ] Animation for clarification card appearance
[ ] Smooth transitions level 1 → 2 → 3
[ ] Loading skeletons for pagination
[ ] Edge cases: empty results, errors, timeouts
```

---

# PART IX — TESTING CHECKLIST

## 19. What "Done" Looks Like

```
Pre-Response Suggestions:
  ✓ "P&L" → shows date clarification
  ✓ "P&L for April" → goes directly (no clarification)
  ✓ Skip button works → uses last 3 months
  ✓ Arabic queries → Arabic clarification options
  ✓ Custom date picker → correct dates used

Progressive Disclosure:
  ✓ Every report shows summary first (KPIs + chart)
  ✓ "Want details?" prompt appears
  ✓ Yes → shows table with 20 rows
  ✓ "Load more" → gets next 20
  ✓ Total count always visible
  ✓ Export works for full dataset

Post Suggestions:
  ✓ Every response has exactly 3 suggestions
  ✓ "Show more" rotates to next 3
  ✓ No repeated suggestions in same session
  ✓ Suggestions are useful and specific
  ✓ Arabic suggestions for Arabic queries
  ✓ Clicking suggestion sends correct query

Date Range:
  ✓ No query ever runs without date range
  ✓ Default = last 3 months
  ✓ Date badge shows on all reports
  ✓ Defaulted date shows "(default)" label

Bug Fixes:
  ✓ No raw visualization blocks in text
  ✓ No raw field names visible
  ✓ Suggestions work after page refresh
  ✓ Loading spinner stops on error
  ✓ Bar charts render correctly
  ✓ Textarea grows with content
  ✓ Arabic/English direction correct per paragraph
  ✓ Mobile: no horizontal overflow
  ✓ No duplicate messages
  ✓ Clear chat resets session completely
```

---

# PART X — TELL CURSOR

```
"Read QUERY_RESPONSE_INTELLIGENCE_PLAN.md.

Start with Phase 1: Bug Fixes (all 10 bugs listed in Part VII).
These are blocking production quality and must be fixed first.

Fix each bug in the order listed:
1. Fix Bug 1 in App.jsx (cleanup regex)
2. Fix Bug 5 (add BarChart using Recharts — install recharts if needed)
3. Fix Bug 3 (suggestion rewiring)
4. Fix Bug 6 (textarea auto-resize)
5. Then remaining bugs in order

After Phase 1 confirmed working:
Move to Phase 2: Default Date Range enforcement.

Reference:
- PRODUCT_QUALITY_FRAMEWORK.md for quality standards
- FINANCIAL_INTELLIGENCE_PLAN.md for query patterns
- PROJECT_CONTEXT.md for architecture"
```
