# PRODUCT QUALITY FRAMEWORK — Production AI Standards

> **The Bar:** This is a production AI product using Claude — Anthropic's flagship model. The output quality must reflect that. Raw debug data, zero values, ugly field names, and broken visualizations are unacceptable.

> **Critical Reading:** Cursor must read this before ANY code change. Quality is non-negotiable.

---

## 1. THE WAKE-UP CALL — Analysis of Recent Failure

### What User Saw (Real Screenshot)
```
Query: "Revenue comparison by client"

Output (UNACCEPTABLE):
  ▸ AD PORTS GROUPamount_total:sum: 0
  ▸ Abu Dhabi Civil Defense Authority (ADCDA)amount_total:sum: 0
  ▸ Abu Dhabi Health Services Co. (SEHA)amount_total:sum: 0
  ▸ Abu Dhabi Policeamount_total:sum: 0
  ...
    ▸ Undefinedamount_total:sum: 0
    ▸ Undefinedamount_total:sum: 0
  ...
```

### Why This Is Embarrassing

```
1. ALL VALUES ARE ZERO
   - Wrong filter applied (missing 'state=posted' or wrong type)
   - AI should have detected and retried
   - Should never present zero-data as result

2. RAW DEVELOPER SYNTAX VISIBLE
   - "amount_total:sum: 0" is internal API field syntax
   - User-facing should be "Revenue: AED 0"
   - This breaks the magic completely

3. NO ACTUAL COMPARISON
   - "Comparison" means showing differences
   - User got a list, not a comparison
   - Should be a bar chart or ranked visualization

4. "UNDEFINED" SUB-GROUPS
   - Means recursive grouping broke
   - These should be filtered out or labeled meaningfully

5. NO ERROR HANDLING
   - AI presented broken data as if it were correct
   - No "Hmm, all zeros — let me try a different approach"

6. NO BEAUTIFUL OUTPUT
   - It's a long ugly list
   - Not visualized
   - Not actionable
```

**This output makes the product feel like a beta tech demo, not an enterprise AI product.**

---

## 2. THE QUALITY MANIFESTO

### What Production AI Looks Like

```
✦ EVERY response must be USEFUL — never just data
✦ EVERY number must be FORMATTED — never raw
✦ EVERY visualization must MATCH the intent — comparison → chart, list → table
✦ EVERY zero-result must be QUESTIONED — retry or explain
✦ EVERY field name must be HUMAN — "amount_total" → "Revenue"
✦ EVERY response must be COMPLETE — no half-finished outputs
✦ EVERY query must FEEL like asking a brilliant analyst — not a database
```

### The Production Test

Before showing ANY response to user, ask:

```
1. Would I show this to a CFO?
2. Does it answer the actual question?
3. Are numbers properly formatted?
4. Is the visualization appropriate?
5. Is there any internal jargon visible?
6. Would a human analyst be embarrassed by this output?

If ANY answer is "no" → don't show it. Fix it first.
```

---

## 3. THE QUALITY PIPELINE (Every Response Goes Through This)

```
┌──────────────────────────────────────────────────────────────┐
│  USER QUERY                                                  │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 1: INTENT ANALYSIS                                     │
│ - What is the user actually asking?                          │
│ - What visualization type is appropriate?                    │
│ - Comparison? Trend? List? Single number?                    │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 2: DATA RETRIEVAL                                      │
│ - Choose correct tool/method                                 │
│ - Apply correct filters                                      │
│ - Multi-company aware                                        │
│ - Posted-only by default for financial data                  │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 3: VALIDATION (CRITICAL)                               │
│ - Is the result meaningful?                                  │
│ - Are all values zero? → Retry with corrected filter         │
│ - Does it match expected magnitude?                          │
│ - Sanity check: total revenue > 0 if real business           │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 4: TRANSFORMATION                                      │
│ - Map field names to human labels                            │
│ - Format numbers (AED 1,234,567)                             │
│ - Sort meaningfully                                          │
│ - Filter out noise (null, undefined, zero rows)              │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 5: VISUALIZATION SELECTION                             │
│ - Match viz type to intent                                   │
│ - Comparison → BAR_CHART (sorted descending)                 │
│ - Trend → LINE_CHART                                         │
│ - Breakdown → PIE_CHART or stacked bar                       │
│ - List → DATA_TABLE                                          │
│ - Single metric → KPI_CARD                                   │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 6: NARRATIVE GENERATION                                │
│ - Write 2-3 sentence summary                                 │
│ - Highlight key insight (largest, smallest, trend)           │
│ - Provide actionable observation                             │
│ - Match user's language (English/Arabic)                     │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 7: FINAL QUALITY CHECK                                 │
│ - No raw field names visible                                 │
│ - All numbers formatted                                      │
│ - Visualization renders correctly                            │
│ - Narrative makes sense                                      │
│ - Would pass "CFO test"                                      │
└────────────────────────┬─────────────────────────────────────┘
                         │
                         ▼
                  USER SEES RESULT
```

If ANY layer fails → don't proceed. Retry, recover, or explain.

---

## 4. CURSOR'S REQUIRED SKILLS

For this project, Cursor must operate with these expert-level skills:

### Skill 1 — Odoo Domain Expertise
```
Cursor must know:
  ✓ Odoo data model (account.move, account.move.line, project.project, etc.)
  ✓ Common field meanings (state, type, posted, draft, residual)
  ✓ Required filters for accurate financial data
  ✓ Multi-company implications
  ✓ Analytic accounts and how they link to projects
  ✓ Currency handling (always AED for Elrace)

Test of competence:
  "Get total revenue for April" → must know:
    Model: account.move
    Domain: type=out_invoice, state=posted, date range, company_id=1
    Aggregate: amount_total:sum
```

### Skill 2 — Data Quality Detection
```
Cursor must build code that:
  ✓ Detects when all results are zero
  ✓ Detects suspicious data (revenue but no expenses, etc.)
  ✓ Detects missing critical filters
  ✓ Auto-retries with corrected parameters
  ✓ Explains gracefully when data truly doesn't exist

Code pattern:
  result = execute_query(...)
  if is_suspicious(result):
      result = retry_with_corrections(...)
  if still_suspicious(result):
      explain_to_user(result, suggestions)
```

### Skill 3 — Visualization Intelligence
```
Cursor must map user intent to viz type:

  "comparison" → BAR_CHART (sorted by value)
  "trend" / "over time" → LINE_CHART
  "breakdown" → STACKED_BAR or PIE_CHART
  "top N" → BAR_CHART (limit N)
  "total" / "how much" → KPI_CARD
  "list" / "show me" → DATA_TABLE
  "compare X vs Y" → COMPARISON_CARD (side-by-side)
  "grouped by" → GROUPED_TABLE
```

### Skill 4 — Number & Text Formatting
```
Cursor must format ALL outputs:

Numbers:
  Raw: 17364135.58
  Display: "AED 17,364,136" (rounded, comma-separated, currency prefix)

  Raw: 0.2344
  Display: "23.44%" (percentage with proper symbol)

  Raw: -463318
  Display: "AED -463,318" or "AED 463,318 (Loss)"

Field names:
  amount_total → "Revenue" or "Invoice Amount"
  amount_residual → "Outstanding"
  debit / credit → context-dependent label
  partner_id → "Client" / "Customer" / "Vendor"
  date:month → "Month"
  __count → "Number of records"

NEVER show raw syntax like "amount_total:sum" to user.
```

### Skill 5 — Narrative Writing
```
Every visualization must include 2-3 sentence narrative:

Bad:
  "Here are the results: [table]"

Good:
  "Revenue is concentrated with your top 3 clients (60% of total).
   Abu Dhabi Police leads with AED 10.5M, followed by National Guard
   at AED 4.3M. Consider diversification — top client concentration
   may be a business risk."

Pattern:
  1. Lead with the key finding
  2. Provide one or two supporting facts
  3. Offer an actionable insight
```

### Skill 6 — Error Recovery
```
Cursor must build robust error handling:

  Tool returns error → analyze error → try alternative approach
  All zeros → likely wrong filter → try without filter, then add filter
  Empty result → maybe wrong model → suggest alternatives
  Timeout → reduce scope → retry with narrower query
  Field not found → check available fields → use similar one

Never surface raw errors. Always translate to user language.
```

---

## 5. SPECIFIC FIXES FOR THE FAILED QUERY

### "Revenue comparison by client" — The CORRECT Implementation

```python
# What should happen step-by-step:

# STEP 1: Intent Analysis
intent = {
    "type": "comparison",
    "subject": "revenue",
    "grouping": "client",
    "expected_viz": "BAR_CHART_RANKED",  # Sorted descending
    "time_range": None,  # Need to clarify or use default
}

# STEP 2: Clarification (if needed)
# Since no date range, AI should ask:
# "For what period? This month / This year / Last quarter?"
# OR: Default to "this year" with disclosure

# STEP 3: Build correct query
query = {
    "model": "account.move",
    "domain": [
        ["type", "=", "out_invoice"],      # Customer invoices only
        ["state", "=", "posted"],           # POSTED only (this was missing!)
        ["company_id", "=", 1],             # Elrace company
        ["date", ">=", "2026-01-01"],       # This year
    ],
    "group_by": ["partner_id"],
    "aggregates": ["amount_total:sum"],
    "order_by": "amount_total:sum desc",
    "limit": 20,
}

# STEP 4: Execute and validate
result = group_and_aggregate(**query)

# STEP 5: Quality check
total = sum(g["amount_total"] for g in result["groups"])
if total == 0:
    # SUSPICIOUS — retry without state filter to see what's there
    result = retry_without_filter(query, "state")
    if total still 0:
        return user_message(
            "No customer invoices found in this period. "
            "Would you like me to check draft invoices instead?"
        )

# STEP 6: Transform
formatted_data = []
for g in result["groups"]:
    if g["amount_total"] > 0:  # Skip zero-value clients
        formatted_data.append({
            "client": g["partner_id"][1],  # Get display name
            "revenue": g["amount_total"],
            "formatted_revenue": format_currency(g["amount_total"]),
            "percentage": (g["amount_total"] / total) * 100,
        })

# STEP 7: Build visualization
visualization = {
    "visual_type": "BAR_CHART",
    "label": "Revenue by Client — 2026",
    "data": {
        "labels": [d["client"] for d in formatted_data],
        "values": [d["revenue"] for d in formatted_data],
        "formatted_values": [d["formatted_revenue"] for d in formatted_data],
    },
    "total": total,
    "total_formatted": format_currency(total),
}

# STEP 8: Generate narrative
top_3 = formatted_data[:3]
top_3_pct = sum(d["percentage"] for d in top_3)

narrative = f"""Your revenue is led by {top_3[0]['client']} at {top_3[0]['formatted_revenue']} ({top_3[0]['percentage']:.0f}% of total). The top 3 clients account for {top_3_pct:.0f}% of total revenue — {format_currency(total)} year-to-date.
"""

# RESULT TO USER:
{
    "text": narrative,
    "visualization": visualization,
    "suggestions": [
        "Show this comparison for last quarter",
        "Which client has grown most this year?",
        "Compare revenue vs costs by client",
    ]
}
```

---

## 6. THE TEST SUITE (Required Before Production)

Every query type must have an automated test that validates output quality.

### 6.1 Quality Test Structure

```python
# tests/quality/test_query_quality.py

QUALITY_TESTS = [
    {
        "query": "Revenue comparison by client",
        "language": "en",
        "expectations": {
            "visualization_type": "BAR_CHART",
            "min_groups": 5,           # Real data has at least 5 clients
            "all_values_positive": True,  # No zeros allowed
            "has_narrative": True,
            "narrative_mentions_top": True,
            "currency_formatted": True,    # Must contain "AED"
            "no_raw_syntax": True,         # No ":sum:" visible
            "response_time_ms": 5000,      # Max 5 seconds
        }
    },
    {
        "query": "Top 5 most expensive projects",
        "expectations": {
            "visualization_type": "BAR_CHART",
            "groups_count": 5,
            "sorted_descending": True,
        }
    },
    # ... 50+ more queries
]

def test_all_quality_cases():
    for test in QUALITY_TESTS:
        response = send_query(test["query"], test.get("language", "en"))
        assert_quality(response, test["expectations"])

def assert_quality(response, expected):
    if expected.get("visualization_type"):
        assert response["visualization"]["visual_type"] == expected["visualization_type"]

    if expected.get("all_values_positive"):
        for g in response["visualization"]["data"]["values"]:
            assert g > 0, f"Found zero value: {g}"

    if expected.get("currency_formatted"):
        assert "AED" in response["text"]

    if expected.get("no_raw_syntax"):
        forbidden = [":sum:", ":count:", "amount_total:", "__count", "partner_id["]
        for f in forbidden:
            assert f not in response["text"]
            assert f not in str(response["visualization"])
```

### 6.2 The 50 Canonical Test Queries

```
FINANCIAL REPORTS:
01. "Profit and loss this month"
02. "P&L last quarter"
03. "Balance sheet as of today"
04. "Cash flow this year"
05. "Trial balance"

REVENUE & SALES:
06. "Revenue this month"
07. "Revenue comparison by client"
08. "Top 10 customers by revenue"
09. "Monthly revenue trend 2026"
10. "Revenue by region"

EXPENSES:
11. "Total expenses this month"
12. "Expense breakdown by category"
13. "Top expense categories"
14. "Expense trend over last 6 months"
15. "Salary costs this year"

PROJECTS:
16. "List active projects"
17. "Top 5 most profitable projects"
18. "Projects over budget"
19. "Project costs for Zayidia Boys School"
20. "Projects grouped by client"
21. "Project budget vs actual"

RECEIVABLES & PAYABLES:
22. "Who owes us money"
23. "Outstanding invoices by client"
24. "Customer ageing report"
25. "Overdue invoices"
26. "Vendor payments due"

GROUPINGS:
27. "Invoices grouped by partner"
28. "Sales by salesperson this month"
29. "Purchases by vendor"
30. "Group invoices by status"

COMPARISONS:
31. "This month vs last month"
32. "Compare Q1 vs Q2"
33. "Revenue this year vs last year"
34. "Profit margin trend"

ARABIC QUERIES:
35. "الأرباح والخسائر لهذا الشهر"
36. "إجمالي المصروفات هذا الشهر"
37. "أعلى 5 عملاء"
38. "المشاريع النشطة"

EDGE CASES:
39. "Show me something" (vague)
40. "Profit" (incomplete)
41. "Project XYZ" (doesn't exist)
42. "Sales for 2050" (future date)
43. "Empty database scenario"

PDF GENERATION:
44. "Generate PDF of this month's performance"
45. "Create executive summary report"

VOICE:
46. (audio) "what is my profit margin"
47. (audio Arabic) "اعرض الأرباح"

CONVERSATION:
48. "Show me top projects" → "now categorize them"
49. "P&L April" → "compare with March"
50. "Sales by client" → "drill into top one"
```

Every single one must pass quality assertions before deployment.

---

## 7. ANTI-PATTERNS CATALOG (What Cursor MUST Avoid)

### Anti-Pattern 1: Raw API Output
```
❌ DON'T:
  Display: "amount_total:sum: 17364135.58"

✅ DO:
  Display: "Revenue: AED 17,364,136"
```

### Anti-Pattern 2: All Zeros Passed Through
```
❌ DON'T:
  Tool returns all zeros → display all zeros → ship to user

✅ DO:
  Tool returns all zeros → detect → retry with corrected filter → 
  or explain "No data found, possibly because [reason]"
```

### Anti-Pattern 3: Wrong Visualization
```
❌ DON'T:
  "Revenue comparison by client" → render as nested expandable list

✅ DO:
  "Revenue comparison by client" → render as horizontal bar chart, 
  sorted descending, with values labeled
```

### Anti-Pattern 4: Missing Context
```
❌ DON'T:
  Just show data without explanation

✅ DO:
  Lead with insight: "Revenue is concentrated with 3 clients (60%)..."
  Then show data
  Suggest follow-ups
```

### Anti-Pattern 5: Forgetting Filters
```
❌ DON'T:
  account.move query without state=posted
  → Get draft + cancelled + posted all mixed

✅ DO:
  ALWAYS include:
  - state = "posted" for completed transactions
  - company_id = 1 for Elrace
  - type filter for revenue (out_invoice) or expenses (in_invoice)
```

### Anti-Pattern 6: Surface-Level Errors
```
❌ DON'T:
  Show: "KeyError: 'partner_id'"

✅ DO:
  Show: "I had trouble grouping by client. Let me try a different approach..."
  Then attempt retry
```

### Anti-Pattern 7: Token Waste
```
❌ DON'T:
  Iterate 1000 records and pass all to Claude
  → 100K tokens, costs $$$

✅ DO:
  Aggregate first via SQL/read_group
  → Pass summary (50 rows) to Claude
  → 5K tokens, costs cents
```

### Anti-Pattern 8: Ignoring Conversation Context
```
❌ DON'T:
  User: "Top projects" → response
  User: "categorize them" → AI fetches everything again, doesn't know "them"

✅ DO:
  Track last entity in conversation
  "them" = the projects from previous turn
  Pass project IDs to next tool call
```

---

## 8. CURSOR'S DEVELOPMENT WORKFLOW

For every change Cursor makes, follow this workflow:

### Step 1: Understand
```
- Read relevant context files (PROJECT_CONTEXT.md, etc.)
- Understand the user-facing goal
- Identify which quality layers are affected
```

### Step 2: Design
```
- Sketch the data flow
- Identify required tool calls
- Choose visualization type
- Plan the narrative
```

### Step 3: Implement
```
- Write code following established patterns
- Add validation at each step
- Format outputs at the boundary
- Handle errors gracefully
```

### Step 4: Test Live
```
- Run query against real Elrace data
- Verify output is production-quality
- Check against the "CFO test"
- Run automated quality assertions
```

### Step 5: Validate
```
- Before declaring "done":
  □ No raw field names visible to user?
  □ All numbers properly formatted?
  □ Right visualization for query intent?
  □ Narrative is insightful?
  □ Zero/null cases handled?
  □ Errors handled gracefully?
  □ Suggestions provided?
  □ Works in both Arabic and English?
```

### Step 6: Document
```
- Update PROJECT_CONTEXT.md if new pattern
- Add test case to quality suite
- Move task in TASKS_FEATURES.md to DONE
```

---

## 9. FIELD NAME → HUMAN LABEL DICTIONARY

Cursor must maintain a comprehensive mapping. Add to `gateway/main.py`:

```python
FIELD_LABELS = {
    # Money fields
    "amount_total": "Revenue",
    "amount_residual": "Outstanding Balance",
    "amount_untaxed": "Subtotal",
    "amount_tax": "Tax",
    "debit": "Debit",
    "credit": "Credit",
    "balance": "Balance",

    # Project fields
    "wo_amount": "Contract Amount",
    "wo_ref_no": "WO Reference",
    "x_studio_total_cost": "Total Cost",

    # Relations
    "partner_id": "Client",
    "user_id": "Salesperson",
    "company_id": "Company",
    "currency_id": "Currency",
    "journal_id": "Journal",
    "account_id": "Account",
    "analytic_account_id": "Project",
    "stage_id": "Stage",
    "state": "Status",
    "type": "Type",
    "category_id": "Category",

    # Dates
    "date": "Date",
    "date_order": "Order Date",
    "invoice_date": "Invoice Date",
    "invoice_date_due": "Due Date",
    "date_start": "Start Date",
    "date_end": "End Date",

    # Counts and aggregates
    "__count": "Count",
    "id:count": "Total Records",

    # Time periods
    "date:day": "Day",
    "date:week": "Week",
    "date:month": "Month",
    "date:quarter": "Quarter",
    "date:year": "Year",
}

VALUE_LABELS = {
    # Status mappings
    "out_invoice": "Customer Invoice",
    "in_invoice": "Vendor Bill",
    "out_refund": "Customer Refund",
    "in_refund": "Vendor Refund",
    "draft": "Draft",
    "posted": "Posted",
    "cancel": "Cancelled",
    "paid": "Paid",
    "not_paid": "Unpaid",
    "partial": "Partially Paid",
    "open": "Open",
    "in_payment": "In Payment",
    "reversed": "Reversed",
}

def humanize_field(field: str) -> str:
    """Convert raw field name to human label."""
    return FIELD_LABELS.get(field, field.replace("_", " ").title())

def humanize_value(field: str, value) -> str:
    """Convert raw value to human label based on field context."""
    if field in ["state", "type", "payment_state"]:
        return VALUE_LABELS.get(value, value)
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return value[1]  # Display name for [id, name] tuples
    return value
```

---

## 10. NUMBER FORMATTING STANDARDS

```python
def format_currency(amount: float, currency: str = "AED") -> str:
    """Format currency amounts consistently."""
    if amount is None:
        return f"{currency} 0"
    if amount == 0:
        return f"{currency} 0"
    if abs(amount) >= 1_000_000:
        return f"{currency} {amount/1_000_000:,.1f}M"
    if abs(amount) >= 1_000:
        return f"{currency} {amount:,.0f}"
    return f"{currency} {amount:,.2f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format percentage values."""
    if value is None:
        return "0%"
    return f"{value:,.{decimals}f}%"


def format_number(value: float, decimals: int = 0) -> str:
    """Format plain numbers with thousands separator."""
    if value is None:
        return "0"
    return f"{value:,.{decimals}f}"


def format_date(date_str: str, format: str = "long") -> str:
    """Format dates consistently."""
    from datetime import datetime
    dt = datetime.fromisoformat(str(date_str).split("T")[0])
    if format == "long":
        return dt.strftime("%B %d, %Y")  # April 26, 2026
    if format == "short":
        return dt.strftime("%d %b %Y")   # 26 Apr 2026
    if format == "month":
        return dt.strftime("%B %Y")      # April 2026
    return dt.strftime("%Y-%m-%d")
```

---

## 11. AUTOMATIC RESULT VALIDATION

Add a quality gate before returning results:

```python
def validate_response_quality(response: dict) -> tuple[bool, list[str]]:
    """
    Run quality checks on response before showing to user.
    Returns (is_quality, list_of_issues).
    """
    issues = []

    # Check 1: No raw field names in text
    forbidden_patterns = [
        ":sum:", ":count:", ":avg:",
        "__count", "__domain",
        "amount_total:", "partner_id:",
    ]
    text = response.get("text", "")
    viz_str = json.dumps(response.get("visualization", {}))
    for pattern in forbidden_patterns:
        if pattern in text or pattern in viz_str:
            issues.append(f"Raw field syntax visible: {pattern}")

    # Check 2: Suspicious all-zero data
    viz = response.get("visualization", {})
    if viz.get("visual_type") == "BAR_CHART":
        values = viz.get("data", {}).get("values", [])
        if values and all(v == 0 for v in values):
            issues.append("All values are zero — likely wrong query")

    # Check 3: Currency present where expected
    if "revenue" in text.lower() or "sales" in text.lower():
        if "AED" not in text and "AED" not in viz_str:
            issues.append("Money mentioned but no currency formatting")

    # Check 4: Visualization matches intent
    if "compari" in text.lower() and viz.get("visual_type") not in ["BAR_CHART", "PIVOT_TABLE"]:
        issues.append("Comparison intent but wrong viz type")

    # Check 5: Has narrative
    if viz and not text:
        issues.append("Visualization without narrative")

    return (len(issues) == 0, issues)


# In response handler:
is_quality, issues = validate_response_quality(response)
if not is_quality:
    logger.warning(f"Quality issues detected: {issues}")
    # In dev: log and continue
    # In production: regenerate or fix automatically
```

---

## 12. CONTINUOUS QUALITY MONITORING

### Dashboards to Build

```
Quality Metrics Dashboard:
  ✦ Total queries per day
  ✦ Quality pass rate (% passing all checks)
  ✦ Average response time
  ✦ Visualization type distribution
  ✦ Most common failures
  ✦ Zero-result query rate
  ✦ User satisfaction signals (suggestion clicks)
```

### Daily Quality Report

```
Each morning at 9 AM, email summary:

QUALITY REPORT — 14 May 2026
─────────────────────────────
Total queries: 245
Quality pass: 232 (94.7%) ✓
Quality fail: 13 (5.3%) ⚠

Top failures:
  1. "X by Y" missing visualization (5 cases)
  2. All-zero results not detected (3 cases)
  3. Raw field names visible (2 cases)
  4. Wrong visualization type (3 cases)

Action items:
  → Fix issue #1: Add comparison intent detector
  → Investigate issue #2: Strengthen validation
```

---

## 13. THE NORTH STAR

Every line of code Cursor writes should serve this goal:

```
"When a CFO at Elrace asks our AI a question, they should get an
answer that feels like it came from their best financial analyst —
not from a database query. Beautiful formatting. Smart insights.
Appropriate visualizations. Actionable recommendations. Always."
```

---

## 14. ENFORCEMENT MECHANISM

### Pre-Commit Hook

```python
# .git/hooks/pre-commit
# Block commits that introduce quality regressions

import subprocess
result = subprocess.run(["python", "-m", "pytest", "tests/quality/"],
                       capture_output=True)
if result.returncode != 0:
    print("❌ Quality tests failing. Fix before committing.")
    exit(1)
```

### CI/CD Quality Gate

```yaml
# .github/workflows/quality.yml
name: Quality Check
on: [push, pull_request]
jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/quality/
      - run: python tools/lint_responses.py
      - if: failure()
        run: echo "Blocking merge — quality regression"
```

---

## 15. WHAT CURSOR SHOULD DO RIGHT NOW

When you read this document, the FIRST thing to do:

### Immediate Actions (This Week)

```
[ ] Add FIELD_LABELS dictionary to gateway/main.py
[ ] Add format_currency, format_percentage helpers
[ ] Add validate_response_quality function
[ ] Update execute_tool to apply formatting
[ ] Update system prompt with quality requirements
[ ] Re-test "Revenue comparison by client" query
[ ] Verify output looks production-quality
```

### Sprint 1 (Next 2 Weeks)

```
[ ] Build quality test suite (start with 10 queries)
[ ] Add automatic retry on zero-results
[ ] Implement visualization intent matcher
[ ] Add narrative generator
[ ] Create field-to-label mapping for all common fields
[ ] Test all 10 quality cases pass
```

### Sprint 2 (Following 2 Weeks)

```
[ ] Expand quality tests to 50 queries
[ ] Add Arabic test cases
[ ] Build monitoring dashboard
[ ] Set up daily quality report
[ ] Create CI/CD quality gate
```

---

## 16. CLOSING REMINDER

```
This is not LangChain experimentation.
This is not a hackathon project.
This is not a "good enough" demo.

This is a production AI product for a real UAE business
with real money at stake, powered by the most advanced
AI model available today.

The output quality MUST reflect that.

When in doubt, ask:
  "Would Anthropic be proud to show this output?"
  "Would Elrace's CEO trust this for decisions?"
  "Would I demo this to investors?"

If any answer is no — keep working.
```
