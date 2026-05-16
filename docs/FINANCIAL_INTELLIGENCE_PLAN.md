# FINANCIAL INTELLIGENCE PLAN

> **Strategic Principle:** Make the AI smart enough to handle every variation of every financial report through pure intelligence — NOT by adding 100 specific Odoo methods. We expose the AI to underlying accounting schema and let it compose answers.

> **Quality Bar:** Every report Elrace's CFO can pull from Odoo UI, our AI must produce — with better narratives, smarter insights, and beautiful visualizations.

---

# PART I — STRATEGIC ARCHITECTURE

## 1. The Core Insight

```
Traditional Approach (What We Want to AVOID):
  ❌ Build get_pandl tool
  ❌ Build get_pandl_by_project tool
  ❌ Build get_pandl_by_journal tool
  ❌ Build get_pandl_compare_periods tool
  ❌ ... 100 tools later
  ❌ Still missing variations
  ❌ Each tool needs Odoo method
  ❌ Slow to evolve

AI-First Approach (What We WILL Do):
  ✓ Give AI deep knowledge of accounting schema
  ✓ Give AI 4-5 POWERFUL primitive tools
  ✓ Give AI report TEMPLATES it can adapt
  ✓ Give AI quality guardrails
  ✓ AI composes any report variation autonomously
  ✓ Zero new Odoo methods needed
  ✓ Infinite report variations supported
```

## 2. The Three-Layer Intelligence Stack

```
┌────────────────────────────────────────────────────────┐
│  LAYER 3: REPORT INTELLIGENCE                          │
│  - Claude with rich accounting knowledge               │
│  - Template library for common reports                 │
│  - Pattern matching for query intent                   │
│  - Quality validation                                  │
└────────────────────────────────────────────────────────┘
                          ▲
                          │
┌────────────────────────────────────────────────────────┐
│  LAYER 2: QUERY COMPOSITION                            │
│  - 5 universal tools (aggregation, drill, transactions)│
│  - Filter builder                                      │
│  - Multi-dimensional grouping                          │
│  - Period comparison engine                            │
└────────────────────────────────────────────────────────┘
                          ▲
                          │
┌────────────────────────────────────────────────────────┐
│  LAYER 1: DATA ACCESS                                  │
│  - PostgreSQL (read replica when ready)                │
│  - Odoo XML-RPC for write ops                          │
│  - account.move.line as primary source                 │
└────────────────────────────────────────────────────────┘
```

---

# PART II — FINANCIAL REPORT TAXONOMY

## 3. Every Financial Report Cataloged

### 3.1 Profit & Loss (Income Statement)

```
Base Report:
  Total Income, Total Expenses, Net Profit, Margin %

Variations to support:
  ✦ By date range (any period)
  ✦ By account hierarchy (1-level, 2-level, full)
  ✦ By project (analytic account)
  ✦ By department (operating_unit)
  ✦ By client (revenue side)
  ✦ By vendor (expense side)
  ✦ By journal
  ✦ Comparative (vs last period / vs last year)
  ✦ Forecast vs Actual
  ✦ Margin analysis per dimension
  ✦ Trend (monthly/quarterly/yearly)
  ✦ Top N contributors

Drill-down levels:
  Level 1: Summary KPIs
  Level 2: Major categories (Operating, Admin, Finance)
  Level 3: Account groups (Subcontractors, Materials, Labor)
  Level 4: Individual accounts
  Level 5: Individual transactions (account.move.line)
```

### 3.2 Balance Sheet

```
Base Report:
  Assets = Liabilities + Equity
  Balanced as of a specific date

Variations:
  ✦ As of any date
  ✦ Comparative (this year vs last)
  ✦ By account category (Current vs Non-current)
  ✦ Working Capital analysis
  ✦ Liquidity ratios
  ✦ Debt-to-equity ratio
  ✦ By currency

Drill-down:
  Level 1: Total Assets, Liabilities, Equity
  Level 2: Categories (Current Assets, Fixed Assets, etc.)
  Level 3: Account groups
  Level 4: Individual accounts with balances
  Level 5: Transactions building up balance
```

### 3.3 Cash Flow Statement

```
Three sections:
  - Operating Activities
  - Investing Activities
  - Financing Activities

Variations:
  ✦ Direct method (cash receipts/payments)
  ✦ Indirect method (from net income)
  ✦ By period (monthly/quarterly/yearly)
  ✦ Forecast next 3/6/12 months
  ✦ Cash conversion cycle
```

### 3.4 Trial Balance

```
Base Report:
  Account | Debit | Credit | Balance
  Must balance (total debit = total credit)

Variations:
  ✦ All accounts vs only non-zero
  ✦ By account type
  ✦ With opening balance
  ✦ Period activity only
  ✦ Closing balance only
  ✦ By analytic account
  ✦ Currency-wise (multi-currency)
```

### 3.5 General Ledger

```
Per account, all transactions in period:
  Date | Move | Partner | Reference | Debit | Credit | Running Balance

Variations:
  ✦ Single account
  ✦ Multiple accounts
  ✦ All accounts
  ✦ By date range
  ✦ By partner
  ✦ By journal
  ✦ With opening balance
  ✦ Foreign currency view
```

### 3.6 Partner Ageing

```
Receivables (Customers) or Payables (Vendors)

Buckets:
  Not Due | 0-30 days | 31-60 | 61-90 | 91-120 | 120+

Variations:
  ✦ Customer ageing
  ✦ Vendor ageing
  ✦ Combined view
  ✦ Custom bucket definitions
  ✦ By currency
  ✦ With provision for bad debt
  ✦ Top overdue
```

### 3.7 Partner Ledger

```
All transactions for a specific partner:
  Date | Document | Description | Debit | Credit | Running Balance

Variations:
  ✦ Single partner
  ✦ Multiple partners
  ✦ All customers / all vendors
  ✦ With currency
  ✦ Reconciled vs unreconciled
  ✦ Overdue items highlighted
```

### 3.8 Cost Analysis (Project Costing)

```
Per project (analytic account):
  Budget | Actual | Variance | % Completion | Forecast

By category:
  - Local Purchase Orders (LPO)
  - Petty Cash
  - Labor / Hiring
  - Staff Salaries
  - Materials
  - Subcontractors
  - Equipment
  - Vehicles
  - Office overhead

Variations:
  ✦ Budget vs Actual
  ✦ Cost trend over time
  ✦ Top cost categories
  ✦ Cost per square meter / unit
  ✦ Profitability per project
```

### 3.9 Tax Reports

```
VAT Reporting (5% UAE):
  - Output VAT (sales tax)
  - Input VAT (purchase tax)
  - Net VAT liability

Variations:
  ✦ Standard rated
  ✦ Zero rated
  ✦ Exempt
  ✦ Reverse charge
  ✦ By period (monthly/quarterly)
```

### 3.10 Custom Combinations

```
Examples of what AI must handle:
  - "P&L for Zayidia Project this quarter compared to last"
  - "Top 10 customers by revenue with their ageing buckets"
  - "Cash flow forecast based on current AR/AP and upcoming invoices"
  - "Profit margin by region (Abu Dhabi vs Dubai)"
  - "Cost per square meter for construction projects"
  - "VAT recovery rate by category"
```

---

# PART III — THE UNIVERSAL QUERY ENGINE

## 4. The 5 Primitive Tools (All Claude Needs)

### Tool 1: `query_accounting` — The Workhorse

```python
{
    "name": "query_accounting",
    "description": (
        "THE primary tool for all financial reports. Queries account.move.line "
        "with full flexibility — filters, grouping, aggregation, drill-down. "
        "Can produce ANY financial report by adjusting parameters.\n\n"

        "ACCOUNTING SCHEMA (memorize this):\n"
        "Table: account.move.line (one row per debit/credit entry)\n"
        "Fields:\n"
        "  - account_id: which GL account\n"
        "  - account_id.user_type_id.internal_group: 'income', 'expense', 'asset', 'liability', 'equity'\n"
        "  - account_id.code: account code (e.g., '5100')\n"
        "  - account_id.name: account name\n"
        "  - partner_id: customer or vendor\n"
        "  - analytic_account_id: project / cost center\n"
        "  - journal_id: which journal\n"
        "  - date: transaction date\n"
        "  - debit, credit: amounts\n"
        "  - balance: debit - credit\n"
        "  - amount_currency: foreign currency amount\n"
        "  - currency_id: currency\n"
        "  - reconciled: payment reconciliation status\n"
        "  - parent_state: 'posted' (always filter this)\n"
        "  - company_id: 1 for Elrace\n\n"

        "REPORT RECIPES:\n"
        "P&L:        group=[internal_group, account_id]; filter=internal_group IN ('income','expense')\n"
        "Bal Sheet:  group=[internal_group, account_id]; filter=internal_group IN ('asset','liability','equity'); as_of_date\n"
        "Trial Bal:  group=[account_id]; aggregates=[debit:sum, credit:sum, balance:sum]\n"
        "Gen Ledger: group=[account_id]; details=true (returns line items)\n"
        "Project P&L: group=[analytic_account_id, internal_group]\n"
        "Partner Ledg: filter=[partner_id=X]; details=true\n"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "report_type": {
                "type": "string",
                "enum": ["pandl", "balance_sheet", "cash_flow", "trial_balance",
                         "general_ledger", "partner_ageing", "partner_ledger",
                         "cost_analysis", "custom"],
                "description": "Pre-built recipe to use, OR 'custom' for full flexibility"
            },
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "as_of_date": {"type": "string", "description": "For balance sheet"},
            "filters": {
                "type": "array",
                "description": "Additional Odoo domain filters",
                "items": {}
            },
            "group_by": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Dimensions to group by"
            },
            "aggregates": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Fields to sum/avg/count"
            },
            "include_details": {
                "type": "boolean",
                "default": False,
                "description": "If true, return individual transactions per group"
            },
            "drill_into": {
                "type": "object",
                "description": "Drill into specific group: {dimension: value}"
            },
            "compare_with": {
                "type": "object",
                "description": "Comparative period: {date_from, date_to, label}"
            },
            "limit_per_group": {
                "type": "integer",
                "default": 100
            },
            "currency": {"type": "string", "default": "AED"},
            "company_id": {"type": "integer", "default": 1}
        },
        "required": ["report_type"]
    }
}
```

### Tool 2: `get_transactions` — Drill Down

```python
{
    "name": "get_transactions",
    "description": (
        "Get individual transactions matching specific criteria. Use after "
        "user asks to 'drill into', 'expand', 'show details of', 'see entries for' "
        "a specific account, partner, project, or category."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "account_id": {"type": "integer"},
            "account_code": {"type": "string"},
            "partner_id": {"type": "integer"},
            "partner_name": {"type": "string"},
            "analytic_account_id": {"type": "integer"},
            "project_name": {"type": "string"},
            "journal_id": {"type": "integer"},
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "min_amount": {"type": "number"},
            "max_amount": {"type": "number"},
            "limit": {"type": "integer", "default": 50},
            "order_by": {"type": "string", "default": "date desc"}
        }
    }
}
```

### Tool 3: `compare_periods` — Comparative Analysis

```python
{
    "name": "compare_periods",
    "description": (
        "Compare financial metrics across two or more periods. "
        "Returns variance analysis with percentages."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "enum": ["revenue", "expense", "profit", "margin",
                         "cash_flow", "specific_account"]
            },
            "periods": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "date_from": {"type": "string"},
                        "date_to": {"type": "string"}
                    }
                }
            },
            "dimensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional grouping: ['partner_id'], ['account_id'], etc."
            }
        },
        "required": ["metric", "periods"]
    }
}
```

### Tool 4: `calculate_ratio` — Financial Ratios

```python
{
    "name": "calculate_ratio",
    "description": (
        "Calculate financial ratios and KPIs. "
        "Profit margin, ROI, current ratio, debt-to-equity, etc."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ratio_type": {
                "type": "string",
                "enum": [
                    "profit_margin",
                    "gross_margin",
                    "operating_margin",
                    "current_ratio",
                    "quick_ratio",
                    "debt_to_equity",
                    "return_on_assets",
                    "return_on_equity",
                    "days_sales_outstanding",
                    "days_payable_outstanding",
                    "inventory_turnover",
                    "asset_turnover",
                    "custom"
                ]
            },
            "date_from": {"type": "string"},
            "date_to": {"type": "string"},
            "custom_numerator": {"type": "string"},
            "custom_denominator": {"type": "string"}
        }
    }
}
```

### Tool 5: `generate_pdf_report` — Professional Output

(Detailed in PART V below)

---

## 5. Implementation of `query_accounting`

This is the most important tool. Implementation strategy:

```python
def execute_query_accounting(tool_input: dict, adapter, pg_conn=None) -> dict:
    """
    The universal financial query engine.
    Handles every report type via composable SQL.
    """
    report_type = tool_input["report_type"]

    # Apply recipe-specific defaults
    if report_type in REPORT_RECIPES:
        recipe = REPORT_RECIPES[report_type]
        # Merge recipe defaults with user overrides
        params = {**recipe["defaults"], **tool_input}
    else:
        params = tool_input

    # Build SQL or use Odoo read_group
    if pg_conn:
        # Direct SQL — fast, no Odoo CPU impact
        return execute_via_sql(params, pg_conn)
    else:
        # Fallback via Odoo ORM
        return execute_via_orm(params, adapter)


REPORT_RECIPES = {
    "pandl": {
        "defaults": {
            "filters": [
                ["parent_state", "=", "posted"],
                ["account_id.user_type_id.internal_group", "in",
                 ["income", "expense"]],
            ],
            "group_by": ["account_id.user_type_id.internal_group", "account_id"],
            "aggregates": ["debit:sum", "credit:sum", "balance:sum"],
            "order_by": "balance desc",
        },
        "post_process": "compute_pandl_kpis",
    },
    "balance_sheet": {
        "defaults": {
            "filters": [
                ["parent_state", "=", "posted"],
                ["account_id.user_type_id.internal_group", "in",
                 ["asset", "liability", "equity"]],
            ],
            "group_by": ["account_id.user_type_id.internal_group", "account_id"],
            "aggregates": ["balance:sum"],
            "order_by": "balance desc",
        },
        "post_process": "compute_balance_sheet",
    },
    "trial_balance": {
        "defaults": {
            "filters": [["parent_state", "=", "posted"]],
            "group_by": ["account_id"],
            "aggregates": ["debit:sum", "credit:sum", "balance:sum"],
            "order_by": "account_id asc",
        },
    },
    "general_ledger": {
        "defaults": {
            "filters": [["parent_state", "=", "posted"]],
            "group_by": ["account_id"],
            "aggregates": ["debit:sum", "credit:sum"],
            "include_details": True,
            "details_fields": ["date", "ref", "partner_id",
                              "debit", "credit", "move_id"],
        },
    },
    "partner_ageing": {
        "defaults": {
            "filters": [
                ["parent_state", "=", "posted"],
                ["reconciled", "=", False],
                ["account_id.user_type_id.type", "in", ["receivable", "payable"]],
            ],
            "group_by": ["partner_id"],
            "compute_ageing_buckets": True,  # Special post-processing
        },
    },
    "cost_analysis": {
        "defaults": {
            "filters": [
                ["parent_state", "=", "posted"],
                ["account_id.user_type_id.internal_group", "=", "expense"],
            ],
            "group_by": ["analytic_account_id", "account_id"],
            "aggregates": ["debit:sum", "credit:sum"],
        },
    },
}
```

## 6. Direct SQL Execution (Performance Critical)

```python
def execute_via_sql(params: dict, conn) -> dict:
    """
    Execute as direct SQL — bypasses Odoo ORM completely.
    10x faster than XML-RPC, zero impact on Odoo CPU.
    """

    # Build SQL dynamically based on params
    filters = params.get("filters", [])
    group_by = params.get("group_by", [])
    aggregates = params.get("aggregates", [])
    date_from = params.get("date_from")
    date_to = params.get("date_to")
    company_id = params.get("company_id", 1)

    # Required for accuracy:
    sql_where = ["am.state = 'posted'", "am.company_id = %s"]
    sql_params = [company_id]

    if date_from:
        sql_where.append("aml.date >= %s")
        sql_params.append(date_from)
    if date_to:
        sql_where.append("aml.date <= %s")
        sql_params.append(date_to)

    # Build GROUP BY clause
    sql_groups = []
    sql_select = []

    for g in group_by:
        if "internal_group" in g:
            sql_select.append("aat.internal_group")
            sql_groups.append("aat.internal_group")
        elif g == "account_id":
            sql_select.append("aa.id as account_id, aa.code as account_code, aa.name as account_name")
            sql_groups.append("aa.id, aa.code, aa.name")
        elif g == "partner_id":
            sql_select.append("rp.id as partner_id, rp.name as partner_name")
            sql_groups.append("rp.id, rp.name")
        elif g == "analytic_account_id":
            sql_select.append("aaa.id as analytic_id, aaa.name as analytic_name")
            sql_groups.append("aaa.id, aaa.name")
        elif ":month" in g:
            sql_select.append("DATE_TRUNC('month', aml.date) as month")
            sql_groups.append("DATE_TRUNC('month', aml.date)")
        elif ":year" in g:
            sql_select.append("EXTRACT(YEAR FROM aml.date) as year")
            sql_groups.append("EXTRACT(YEAR FROM aml.date)")

    # Aggregates
    for agg in aggregates:
        field, func = agg.split(":")
        sql_select.append(f"COALESCE(SUM(aml.{field}), 0) as {field}_{func}")

    # Full SQL
    sql = f"""
        SELECT {', '.join(sql_select)}
        FROM account_move_line aml
        JOIN account_move am ON aml.move_id = am.id
        JOIN account_account aa ON aml.account_id = aa.id
        JOIN account_account_type aat ON aa.user_type_id = aat.id
        LEFT JOIN res_partner rp ON aml.partner_id = rp.id
        LEFT JOIN account_analytic_account aaa ON aml.analytic_account_id = aaa.id
        WHERE {' AND '.join(sql_where)}
        GROUP BY {', '.join(sql_groups)}
        ORDER BY {params.get('order_by', 'balance_sum DESC')}
        LIMIT %s
    """
    sql_params.append(params.get("limit", 100))

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, sql_params)
        rows = cur.fetchall()

    return {
        "report_type": params.get("report_type"),
        "row_count": len(rows),
        "data": [dict(r) for r in rows],
        "params_used": params,
        "source": "direct_sql",
    }
```

---

# PART IV — DRILL-DOWN ARCHITECTURE

## 7. Hierarchical Navigation

### 7.1 The Drill-Down Pattern

```
Level 1: SUMMARY
  ┌─────────────────────────┐
  │  Net Profit: AED 4.07M  │  ← User sees this first
  └─────────────────────────┘
        │
        ▼ (click "Income breakdown")
Level 2: CATEGORIES
  ┌─────────────────────────┐
  │  Income breakdown:      │
  │  • Operating: 16.97M    │  ← Click any category
  │  • Other:       0.39M   │
  └─────────────────────────┘
        │
        ▼ (click "Operating Income")
Level 3: ACCOUNT GROUPS
  ┌─────────────────────────┐
  │  Operating Income:      │
  │  • Project Revenue 16.97│  ← Click any account
  │  • Service Revenue 0.0  │
  └─────────────────────────┘
        │
        ▼ (click "Project Revenue")
Level 4: INDIVIDUAL ACCOUNTS
  ┌─────────────────────────┐
  │  Account 4001 - Revenue │
  │  Total: AED 16,978,829  │  ← Click to see transactions
  └─────────────────────────┘
        │
        ▼ (click "See entries")
Level 5: TRANSACTIONS
  ┌─────────────────────────┐
  │ Date | Move | Partner   │
  │ 04/08 | INV-001 | ADP  │
  │ 04/15 | INV-002 | NGC  │
  └─────────────────────────┘
```

### 7.2 UI Component Specifications

```jsx
// ExpandableFinancialRow.jsx
function ExpandableFinancialRow({ item, level = 0 }) {
  const [expanded, setExpanded] = useState(false);
  const [children, setChildren] = useState(null);
  const [loading, setLoading] = useState(false);

  const onExpand = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setLoading(true);
    // Fetch sub-items via drill-down API
    const subItems = await drillDown(item.dimension, item.value);
    setChildren(subItems);
    setLoading(false);
    setExpanded(true);
  };

  return (
    <>
      <div
        style={{
          paddingLeft: level * 24,
          cursor: 'pointer',
        }}
        onClick={onExpand}
      >
        <span>{expanded ? '▼' : '▶'}</span>
        <span>{item.label}</span>
        <span className="amount">{formatCurrency(item.amount)}</span>
      </div>

      {loading && <Skeleton />}

      {expanded && children && children.map(child => (
        <ExpandableFinancialRow
          key={child.id}
          item={child}
          level={level + 1}
        />
      ))}
    </>
  );
}
```

### 7.3 Drill-Down API

```python
@app.post("/drill")
async def drill_down(request: DrillRequest):
    """
    Fetch next level of detail for any financial item.

    Examples:
    - Drill into 'Operating Income' → get account groups
    - Drill into account '4001' → get transactions
    - Drill into partner '54' → get all invoices
    """
    # Use query_accounting with refined filters
    result = execute_query_accounting({
        "report_type": "custom",
        "filters": request.parent_filters + request.drill_filters,
        "group_by": request.next_dimension,
        "aggregates": request.aggregates,
        "include_details": request.level >= 4,  # Show transactions at deepest level
    })
    return result
```

---

# PART V — PROFESSIONAL PDF DESIGN SYSTEM

## 8. PDF Visual Specifications

### 8.1 Brand System

```
Company Identity:
  Logo: Elrace logo (high-res SVG or PNG with transparent bg)
  Primary color: UAE Gold #c9a84c
  Secondary: Deep Navy #1a2744
  Success: Cyan #4ecdc4
  Warning: Amber #f59e0b
  Error: Coral #ff6b6b

Typography:
  Headers: Inter Bold (modern, professional)
  Body: Inter Regular
  Numbers: Inter Tabular (monospaced figures)
  Arabic: Noto Naskh Arabic
  Accents: Italic for notes
```

### 8.2 Page Layout Specification

```
PAGE STRUCTURE (every page):

┌─────────────────────────────────────────────┐
│  ┌──────┐                          [Theme]  │
│  │ LOGO │   Elrace Cos. & Gen. Cont.       │
│  └──────┘   Construction & Facilities Mgmt   │
│                                              │
│  ─────────────────────────────────────────── │  ← Gold separator
│                                              │
│   [SECTION CONTENT]                          │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│  ─────────────────────────────────────────── │
│  Page X of Y    |    Issued by: <user>      │
│  Generated: <date>  |  Confidential          │
└─────────────────────────────────────────────┘
```

### 8.3 Cover Page Design

```
┌─────────────────────────────────────────────┐
│                                              │
│              [ELRACE LOGO - 200px]           │
│                                              │
│         Elrace Cos. & Gen. Cont. CO.         │
│      Construction & Facilities Management    │
│                                              │
│  ─────────────────────────────────────────── │
│                                              │
│                                              │
│                                              │
│          FINANCIAL PERFORMANCE               │
│                  REPORT                      │
│                                              │
│            ━━━━━━━━━━━━━━━━━━━━              │
│                                              │
│            April 2026                        │
│        Profit & Loss Statement               │
│                                              │
│                                              │
│                                              │
│                                              │
│  Issued by:  AI Financial Analyst            │
│  Generated:  May 14, 2026                    │
│  Period:     1 April - 30 April 2026         │
│  Currency:   AED                             │
│                                              │
│                                              │
│  ─────────────────────────────────────────── │
│           CONFIDENTIAL                       │
└─────────────────────────────────────────────┘
```

### 8.4 KPI Box Design

```
┌────────────────────────────────────┐
│  REVENUE                            │  ← Label (gray, uppercase, 10px)
│                                     │
│  AED 17,364,136                     │  ← Big number (28px, bold)
│                                     │
│  ↗ +12% vs March 2026               │  ← Trend (green/red)
│                                     │
└────────────────────────────────────┘

Color coding:
  Positive trend (↗): Green #10b981
  Negative trend (↘): Red #ef4444
  Neutral (→):       Gray #6b7280

Box specifications:
  Background: White with subtle shadow
  Border: 1px solid #e5e7eb
  Corner radius: 12px
  Padding: 20px
  Side accent: 4px gold bar on left
```

### 8.5 Financial Table Design

```
┌─────────────────────────────────────────────────────┐
│ ACCOUNT          │   DEBIT  │  CREDIT │  BALANCE   │  ← Header
│ ════════════════ │ ════════ │ ═══════ │ ═════════ │
│ 4001 Revenue     │      0   │  17.4M  │  +17.4M   │  ← Striped row
│ 5100 Direct Cost │   11.6M  │      0  │  -11.6M   │
│ 6100 Admin Exp   │    1.6M  │      0  │   -1.6M   │
│ ════════════════ │ ════════ │ ═══════ │ ═════════ │
│ TOTAL            │   13.2M  │  17.4M  │   +4.2M   │  ← Total row
└─────────────────────────────────────────────────────┘

Specifications:
  Header background: #f9fafb
  Header border-bottom: 2px solid #c9a84c (gold)
  Row alternating: white / #f9fafb
  Total row: bold, top border 2px solid #1a2744
  Numbers: tabular, right-aligned
  Positive: text-green-600
  Negative: text-red-600
  Currency: AED prefix on totals only
```

### 8.6 Chart Embedding

```
Charts rendered server-side via Matplotlib → PNG:
  Resolution: 300 DPI for print quality
  Width: 600px (fits page width with margin)
  Background: transparent
  Font: matches PDF body font
  Colors: Elrace brand palette

Bar Chart:
  Vertical bars
  Gold gradient fill
  Labels above bars (AED values)
  Light gridlines
  Title in deep navy

Line Chart:
  Smooth curves
  Gold line, cyan dots
  Subtle area fill underneath
  Markers for key points

Pie Chart:
  Gold/Cyan/Coral/Navy palette
  Donut style (modern)
  Legend on right
  Percentage labels inside slices
```

### 8.7 Section Header Design

```
─────────────────────────────────────────────
█ EXECUTIVE SUMMARY                          ← 4px gold left bar
─────────────────────────────────────────────
Lorem ipsum dolor sit amet, consectetur 
adipiscing elit...
```

### 8.8 Insight Callout Design

```
╭─ KEY INSIGHT ────────────────────────────╮
│ 💡                                        │
│  Revenue is concentrated with your top 3 │
│  clients (60% of total). Consider        │
│  diversification to reduce risk.         │
╰──────────────────────────────────────────╯

Specifications:
  Background: #fef3c7 (soft yellow)
  Border-left: 4px solid #f59e0b (amber)
  Icon: 💡 emoji or custom SVG
  Padding: 16px
  Italic emphasis on key fact
```

### 8.9 Footer Design

```
─────────────────────────────────────────────
Page 3 of 8    Elrace AI    Confidential
─────────────────────────────────────────────
```

## 9. PDF Generation Implementation

### 9.1 Updated Tool Definition

```python
{
    "name": "generate_pdf_report",
    "description": (
        "Generate a professional, branded PDF report. You design the entire "
        "structure: cover, sections, charts, tables, insights. The output is "
        "a beautifully formatted PDF with company branding.\n\n"

        "AVAILABLE SECTIONS:\n"
        "- cover: Logo, title, period, issued_by\n"
        "- executive_summary: Key findings in 2-3 sentences\n"
        "- kpi_grid: 2x2 or 3x2 grid of KPI boxes\n"
        "- financial_table: Account-by-account breakdown\n"
        "- bar_chart, line_chart, pie_chart: Embedded chart images\n"
        "- insight_callout: Highlighted observation with icon\n"
        "- two_column: Side-by-side content\n"
        "- comparative_table: Period vs period comparison\n"
        "- text_section: Markdown text\n"
        "- table_of_contents: Auto-generated TOC\n"
        "- page_break: Force new page\n\n"

        "REPORT TYPES (recipes):\n"
        "- monthly_pandl: Full P&L with sections\n"
        "- executive_dashboard: KPI-heavy summary\n"
        "- detailed_balance_sheet: Multi-level breakdown\n"
        "- project_review: Specific project deep-dive\n"
        "- client_portfolio: Client-by-client analysis\n"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "report_recipe": {
                "type": "string",
                "enum": ["monthly_pandl", "executive_dashboard",
                         "detailed_balance_sheet", "project_review",
                         "client_portfolio", "custom"]
            },
            "title": {"type": "string"},
            "subtitle": {"type": "string"},
            "period": {"type": "string"},
            "issued_by": {"type": "string"},
            "language": {"type": "string", "enum": ["en", "ar"]},
            "theme": {"type": "string", "enum": ["light", "dark"], "default": "light"},
            "include_logo": {"type": "boolean", "default": True},
            "include_toc": {"type": "boolean", "default": True},
            "watermark": {"type": "string"},
            "sections": {
                "type": "array",
                "items": {"$ref": "#/definitions/Section"}
            }
        },
        "required": ["title", "sections"]
    }
}
```

### 9.2 HTML Template (Master)

```html
<!DOCTYPE html>
<html lang="{{ lang }}" dir="{{ 'rtl' if is_rtl else 'ltr' }}">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <style>
    @page {
      size: A4;
      margin: 25mm 20mm 25mm 20mm;
      @top-center {
        content: element(header);
      }
      @bottom-center {
        content: element(footer);
      }
    }

    body {
      font-family: 'Inter', 'Noto Naskh Arabic', sans-serif;
      color: #1a2744;
      line-height: 1.6;
      font-size: 11pt;
    }

    /* Header */
    .page-header {
      position: running(header);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding-bottom: 8px;
      border-bottom: 1px solid #e5e7eb;
    }

    .logo-area img { height: 32px; }
    .company-name {
      font-size: 10pt;
      color: #6b7280;
      font-weight: 500;
    }

    /* Footer */
    .page-footer {
      position: running(footer);
      text-align: center;
      font-size: 9pt;
      color: #9ca3af;
      padding-top: 8px;
      border-top: 1px solid #e5e7eb;
    }

    .page-footer::after {
      content: "Page " counter(page) " of " counter(pages);
    }

    /* Cover */
    .cover {
      page-break-after: always;
      text-align: center;
      padding-top: 80px;
    }
    .cover .logo { width: 200px; }
    .cover .title {
      font-size: 36pt;
      font-weight: 800;
      color: #1a2744;
      margin-top: 60px;
      letter-spacing: -1px;
    }
    .cover .period {
      font-size: 14pt;
      color: #c9a84c;
      margin-top: 16px;
      font-weight: 500;
    }
    .cover .meta {
      margin-top: 100px;
      font-size: 10pt;
      color: #6b7280;
      line-height: 2;
    }

    /* Section header */
    .section-header {
      font-size: 18pt;
      font-weight: 700;
      color: #1a2744;
      padding-left: 12px;
      border-left: 4px solid #c9a84c;
      margin: 32px 0 16px 0;
    }

    /* KPI Grid */
    .kpi-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin: 16px 0;
    }

    .kpi-box {
      background: white;
      border: 1px solid #e5e7eb;
      border-left: 4px solid #c9a84c;
      border-radius: 12px;
      padding: 16px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    .kpi-label {
      font-size: 9pt;
      color: #6b7280;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      font-weight: 600;
    }

    .kpi-value {
      font-size: 24pt;
      font-weight: 700;
      color: #1a2744;
      margin-top: 8px;
      font-variant-numeric: tabular-nums;
    }

    .kpi-trend {
      font-size: 10pt;
      margin-top: 6px;
      font-weight: 500;
    }

    .kpi-trend.up { color: #10b981; }
    .kpi-trend.down { color: #ef4444; }
    .kpi-trend.neutral { color: #6b7280; }

    /* Tables */
    table.financial {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      font-size: 10pt;
    }

    table.financial thead th {
      background: #f9fafb;
      padding: 10px 12px;
      text-align: left;
      font-weight: 600;
      color: #1a2744;
      border-bottom: 2px solid #c9a84c;
      text-transform: uppercase;
      font-size: 9pt;
      letter-spacing: 0.04em;
    }

    table.financial tbody tr:nth-child(even) {
      background: #f9fafb;
    }

    table.financial tbody td {
      padding: 8px 12px;
      border-bottom: 1px solid #f3f4f6;
    }

    table.financial td.number,
    table.financial th.number {
      text-align: right;
      font-variant-numeric: tabular-nums;
    }

    table.financial tr.total {
      font-weight: 700;
      border-top: 2px solid #1a2744;
      background: #fef3c7 !important;
    }

    table.financial td.positive { color: #10b981; }
    table.financial td.negative { color: #ef4444; }

    /* Insight callout */
    .insight {
      background: #fef3c7;
      border-left: 4px solid #f59e0b;
      padding: 16px 20px;
      border-radius: 8px;
      margin: 16px 0;
      font-style: italic;
    }

    .insight .icon { font-size: 18pt; margin-right: 8px; }
    .insight strong { font-style: normal; color: #92400e; }

    /* Charts */
    .chart-container {
      margin: 16px 0;
      text-align: center;
    }

    .chart-container img {
      max-width: 100%;
      height: auto;
    }

    .chart-title {
      font-size: 12pt;
      font-weight: 600;
      color: #1a2744;
      margin-bottom: 8px;
      text-align: center;
    }

    /* RTL adjustments */
    [dir="rtl"] .section-header {
      padding-left: 0;
      padding-right: 12px;
      border-left: none;
      border-right: 4px solid #c9a84c;
    }
    [dir="rtl"] .kpi-box {
      border-left: 1px solid #e5e7eb;
      border-right: 4px solid #c9a84c;
    }

    .page-break { page-break-after: always; }
  </style>
</head>
<body>

  <div class="page-header">
    <div class="logo-area">
      <img src="{{ logo_url }}" alt="Elrace">
    </div>
    <div class="company-name">
      Elrace Cos. & Gen. Cont. CO.<br>
      Construction & Facilities Management
    </div>
  </div>

  <div class="page-footer">
    <span>Confidential | {{ generation_date }} | Issued by: {{ issued_by }} | </span>
  </div>

  {% if include_cover %}
  <div class="cover">
    <img src="{{ logo_url }}" class="logo">
    <div class="title">{{ title }}</div>
    <div class="period">{{ period }}</div>
    <div class="meta">
      Issued by: {{ issued_by }}<br>
      Generated: {{ generation_date }}<br>
      Currency: AED<br>
      Company: Elrace Cos. & Gen. Cont. CO.
    </div>
  </div>
  {% endif %}

  {% for section in sections %}
    {{ section.html | safe }}
  {% endfor %}

</body>
</html>
```

### 9.3 Section Renderers

```python
def render_kpi_grid(data: dict, theme: dict) -> str:
    """Render 2x2 or 3x2 KPI grid."""
    kpis = data.get("kpis", [])
    html = '<div class="kpi-grid">'
    for kpi in kpis:
        trend_class = "up" if kpi.get("trend_value", 0) > 0 else "down" if kpi.get("trend_value", 0) < 0 else "neutral"
        trend_arrow = "↗" if trend_class == "up" else "↘" if trend_class == "down" else "→"
        html += f'''
        <div class="kpi-box">
            <div class="kpi-label">{kpi["label"]}</div>
            <div class="kpi-value">{format_currency(kpi["value"])}</div>
            {f'<div class="kpi-trend {trend_class}">{trend_arrow} {kpi["trend"]}</div>' if kpi.get("trend") else ''}
        </div>
        '''
    html += '</div>'
    return html


def render_financial_table(data: dict, theme: dict) -> str:
    """Render account table with totals."""
    headers = data.get("headers", ["Account", "Debit", "Credit", "Balance"])
    rows = data.get("rows", [])
    total = data.get("total")

    html = '<table class="financial"><thead><tr>'
    for h in headers:
        cls = ' class="number"' if h.lower() in ["debit", "credit", "balance", "amount"] else ''
        html += f'<th{cls}>{h}</th>'
    html += '</tr></thead><tbody>'

    for row in rows:
        html += '<tr>'
        for i, cell in enumerate(row):
            cls = ''
            if i > 0 and isinstance(cell, (int, float)):
                cls = ' class="number'
                if cell > 0: cls += ' positive'
                elif cell < 0: cls += ' negative'
                cls += '"'
                cell = format_currency(cell)
            html += f'<td{cls}>{cell}</td>'
        html += '</tr>'

    if total:
        html += '<tr class="total">'
        for i, cell in enumerate(total):
            cls = ' class="number"' if i > 0 else ''
            if i > 0 and isinstance(cell, (int, float)):
                cell = format_currency(cell)
            html += f'<td{cls}>{cell}</td>'
        html += '</tr>'

    html += '</tbody></table>'
    return html


def render_bar_chart(data: dict, theme: dict) -> str:
    """Render bar chart as PNG and embed."""
    import matplotlib.pyplot as plt
    import io, base64

    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)

    labels = data["labels"]
    values = data["values"]

    bars = ax.bar(labels, values, color=theme["chart_colors"][0], edgecolor='none')

    # Gold gradient fill
    for bar in bars:
        bar.set_alpha(0.85)

    ax.set_title(data.get("title", ""), fontsize=14, color=theme["text"], pad=20)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.tick_params(colors=theme["text_secondary"])

    # Format y-axis as currency
    ax.yaxis.set_major_formatter(plt.FuncFormatter(
        lambda x, _: f'AED {x/1e6:.1f}M' if abs(x) >= 1e6 else f'AED {x/1e3:.0f}K'
    ))

    # Value labels above bars
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f'AED {height/1e6:.1f}M' if abs(height) >= 1e6 else f'AED {height:,.0f}',
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 3), textcoords="offset points",
            ha='center', va='bottom', fontsize=9, color=theme["text"]
        )

    plt.xticks(rotation=30, ha='right')
    plt.tight_layout()

    # Save to base64
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', transparent=True, dpi=150)
    plt.close()
    img_b64 = base64.b64encode(buf.getvalue()).decode()

    return f'''
    <div class="chart-container">
        <div class="chart-title">{data.get("title", "")}</div>
        <img src="data:image/png;base64,{img_b64}" alt="Chart">
    </div>
    '''


def render_insight(data: dict, theme: dict) -> str:
    """Render insight callout."""
    return f'''
    <div class="insight">
        <span class="icon">💡</span>
        <strong>{data.get("title", "Key Insight")}:</strong>
        {data.get("content", "")}
    </div>
    '''
```

---

# PART VI — SYSTEM PROMPT FOR FINANCIAL INTELLIGENCE

## 10. The Comprehensive Financial Prompt

```python
FINANCIAL_INTELLIGENCE_PROMPT = """
You are a financial intelligence assistant for Elrace, with deep expertise in:
- Accounting principles and GAAP
- UAE business context and VAT
- Construction industry economics
- Multi-dimensional financial analysis

TODAY: {today}
COMPANY: Elrace Cos. & Gen. Cont. CO. (ID: 1)
CURRENCY: AED
FISCAL YEAR: January to December

═══════════════════════════════════════════════════════════
ACCOUNTING SCHEMA (you must know this cold):
═══════════════════════════════════════════════════════════

Primary table: account.move.line
  Joins: account.move (state, type), account.account (code, name, type),
         res.partner (name), account.analytic.account (project),
         account.journal

Key field: account.account.user_type_id.internal_group
  Values: 'income', 'expense', 'asset', 'liability', 'equity', 'off_balance'

Key field: account.move.type
  Values: 'out_invoice' (customer invoice), 'in_invoice' (vendor bill),
          'out_refund', 'in_refund', 'entry' (journal entry)

Always filter: state = 'posted' AND company_id = 1

═══════════════════════════════════════════════════════════
REPORT RECIPES (use query_accounting with these report_types):
═══════════════════════════════════════════════════════════

PROFIT & LOSS:
  query_accounting(report_type='pandl', date_from, date_to)
  Returns: KPIs (income, expense, profit, margin), income lines, expense lines
  Variations:
    - By project: add group_by=['analytic_account_id']
    - By journal: add group_by=['journal_id']
    - Compared: use compare_periods tool

BALANCE SHEET:
  query_accounting(report_type='balance_sheet', as_of_date)
  Returns: Assets, Liabilities, Equity (with subtotals)

CASH FLOW:
  query_accounting(report_type='cash_flow', date_from, date_to)
  Returns: Operating, Investing, Financing

TRIAL BALANCE:
  query_accounting(report_type='trial_balance', date_from, date_to)
  Returns: All accounts with debit, credit, balance

GENERAL LEDGER:
  query_accounting(report_type='general_ledger', date_from, date_to,
                   filters=[['account_id', '=', X]])
  include_details=True for individual transactions

PARTNER AGEING:
  query_accounting(report_type='partner_ageing', as_of_date)
  Returns: Partners grouped by bucket (0-30, 31-60, etc.)

PROJECT COSTING:
  query_accounting(report_type='cost_analysis',
                   filters=[['analytic_account_id', '=', X]])

═══════════════════════════════════════════════════════════
RESPONSE QUALITY RULES (NON-NEGOTIABLE):
═══════════════════════════════════════════════════════════

1. NEVER show raw field syntax (amount_total:sum, __count, partner_id[...])
2. ALWAYS format money as "AED 1,234,567" or "AED 1.2M"
3. ALWAYS provide narrative insight (2-3 sentences)
4. ALWAYS choose right visualization:
   - Comparison/ranking → BAR_CHART (sorted descending)
   - Time series → LINE_CHART
   - Distribution → PIE_CHART
   - List/table → DATA_TABLE
   - Single metric → KPI_CARD
   - P&L/Balance Sheet → FINANCIAL_REPORT
5. ALWAYS validate data — if all zeros, retry with different filters
6. ALWAYS allow drill-down — append drill suggestions

═══════════════════════════════════════════════════════════
HANDLING USER VARIATIONS:
═══════════════════════════════════════════════════════════

User says "P&L" without details:
  → Ask: "Which period? This month / Last month / This quarter / Custom range?"

User says "P&L for Zayidia":
  → Resolve project → query_accounting with analytic_account_id filter

User says "P&L by project":
  → query_accounting with group_by=['analytic_account_id']
  → Show top 10, suggest drill-down

User says "compare with last month":
  → Use compare_periods tool with current and previous periods

User says "show details" or "drill into X":
  → get_transactions with appropriate filter
  → Show as expandable list

User asks for PDF:
  → generate_pdf_report with appropriate sections
  → Include: cover, summary, KPIs, charts, tables, insights

═══════════════════════════════════════════════════════════
PROACTIVE INTELLIGENCE:
═══════════════════════════════════════════════════════════

After providing data, ALWAYS suggest 3 follow-ups:
  - Drill into the most interesting/largest item
  - Compare with another period
  - Look at it from another angle (by client, by project, etc.)

Recognize patterns:
  - Revenue concentration → suggest diversification analysis
  - Margin decline → suggest cost breakdown analysis
  - Overdue invoices → suggest collection priorities
  - Budget overrun → suggest deep-dive into specific costs

Use accounting expertise:
  - If gross margin < 15% → flag as concerning for construction industry
  - If days sales outstanding > 90 → flag collection issue
  - If quick ratio < 1 → flag liquidity concern
  - If specific project margin negative → highlight prominently
"""
```

---

# PART VII — IMPLEMENTATION PHASES

## 11. Build Order

### Phase 1 — Universal Query Engine (Week 1-2)
```
[ ] Implement query_accounting tool with all report recipes
[ ] Implement direct SQL execution
[ ] Test each recipe: P&L, Balance Sheet, Trial Balance, GL, Ageing
[ ] Match Odoo UI numbers exactly
[ ] Add validation layer
```

### Phase 2 — Drill-Down System (Week 3)
```
[ ] Implement get_transactions tool
[ ] Implement /drill API endpoint
[ ] Build ExpandableFinancialRow component
[ ] Add lazy loading for drill levels
[ ] Test 5-level deep navigation
```

### Phase 3 — Comparative Analysis (Week 4)
```
[ ] Implement compare_periods tool
[ ] Build variance calculation
[ ] Add comparison visualizations
[ ] Add period comparison to all report types
```

### Phase 4 — Financial Ratios (Week 5)
```
[ ] Implement calculate_ratio tool
[ ] Add 15 standard ratios
[ ] Add ratio interpretations
[ ] Build ratio dashboard view
```

### Phase 5 — Professional PDF (Week 6-7)
```
[ ] Install WeasyPrint, Matplotlib, Jinja2
[ ] Build master HTML template
[ ] Build all section renderers
[ ] Build chart generation (PNG embedding)
[ ] Brand assets (logo, colors)
[ ] Cover page design
[ ] Footer with page numbers
[ ] Test in English and Arabic (RTL)
```

### Phase 6 — System Prompt Enhancement (Week 8)
```
[ ] Implement full financial intelligence prompt
[ ] Add all recipes and patterns
[ ] Quality validation checks
[ ] Test 50 canonical financial queries
```

### Phase 7 — Quality Test Suite (Week 9)
```
[ ] Build automated tests for each report type
[ ] Test all variations and edge cases
[ ] Performance testing (response time < 3s)
[ ] CFO acceptance test
```

---

# PART VIII — QUALITY ACCEPTANCE TESTS

## 12. The 50 Financial Test Queries

Every one must produce production-quality output:

```
SUMMARY REPORTS:
1.  "P&L this month"
2.  "Balance sheet as of today"
3.  "Cash flow Q1 2026"
4.  "Trial balance for April"
5.  "Receivables ageing"

DETAILED REPORTS:
6.  "Show all income accounts with totals"
7.  "Detailed expense breakdown"
8.  "General ledger for account 4001"
9.  "All transactions for Abu Dhabi Police"
10. "Account 5100 transactions April 2026"

GROUPED REPORTS:
11. "P&L by project"
12. "Expenses by category"
13. "Revenue by client"
14. "Costs by project and category"
15. "Sales by month for 2026"

COMPARATIVE:
16. "Compare this month vs last month"
17. "Q1 2026 vs Q1 2025"
18. "Revenue trend last 12 months"
19. "Top project: budget vs actual"
20. "Year-over-year growth"

DRILL-DOWN:
21. (after #11) "Expand the top project"
22. (after #12) "Drill into LPO category"
23. (after #6) "Show transactions for revenue"
24. (after #13) "Drill into Abu Dhabi Police"

RATIOS:
25. "What is our profit margin?"
26. "Calculate gross margin"
27. "Days sales outstanding"
28. "Current ratio"
29. "Debt to equity ratio"

PDFs:
30. "Generate PDF of this month's P&L"
31. "Create executive dashboard PDF"
32. "Export detailed balance sheet to PDF"
33. "PDF report for Zayidia project"
34. "Quarterly summary PDF in Arabic"

ARABIC:
35. "الأرباح والخسائر لهذا الشهر"
36. "الميزانية العمومية"
37. "تحليل العملاء"
38. "تقرير المشاريع"

COMPLEX:
39. "Which clients pay slowest?"
40. "Top 5 most profitable projects this year"
41. "Are we collecting cash fast enough?"
42. "What is our biggest cost category?"
43. "Cash flow forecast next 3 months"
44. "Which project has worst margin?"

ANALYTICAL:
45. "Why did profit decrease?"
46. "What is unusual in this month?"
47. "Suggest cost reduction opportunities"
48. "Identify revenue risks"

EDGE CASES:
49. "P&L for 2050" (future)
50. "Show data for Project XYZ" (doesn't exist)
```

---

# PART IX — SUCCESS METRICS

## 13. What "Done" Looks Like

```
For each financial report type:
  ✓ Works in English and Arabic
  ✓ Numbers match Odoo UI exactly
  ✓ Drill-down works to transaction level
  ✓ Supports any date range
  ✓ Comparative variants work
  ✓ Visualization auto-selected correctly
  ✓ Insights generated automatically
  ✓ PDF export available
  ✓ Response time < 3 seconds
  ✓ Zero raw API syntax visible
  ✓ Cost: < $0.10 per query in tokens

For PDFs specifically:
  ✓ Cover page with logo and metadata
  ✓ Branded headers and footers
  ✓ Color-coded KPI boxes
  ✓ Striped tables with totals
  ✓ Embedded charts (300 DPI)
  ✓ Insight callouts
  ✓ Multi-page support with auto TOC
  ✓ Arabic RTL rendering
  ✓ Both light and dark themes
  ✓ File size < 2MB typical
```

---

# PART X — TELL CURSOR

When you give this to Cursor:

```
"Start with Phase 1 from FINANCIAL_INTELLIGENCE_PLAN.md.

Build query_accounting as the primary tool. Use direct SQL via 
psycopg2 (not Odoo XML-RPC) for performance. Implement all 6 
report recipes: pandl, balance_sheet, cash_flow, trial_balance, 
general_ledger, partner_ageing.

Test each recipe produces numbers matching Odoo UI exactly.

Reference:
- PROJECT_CONTEXT.md for patterns
- PRODUCT_QUALITY_FRAMEWORK.md for output standards
- This document for accounting schema knowledge

After Phase 1 works, move to Phase 2 (drill-down)."
```

This is the architecture. Now Cursor has a complete blueprint to build a financial intelligence system that rivals Odoo's UI in capability, exceeds it in usability, and adds professional PDF export — all without adding new Odoo methods.
