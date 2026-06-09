# ELRACE STARTER CONTEXT

> **Purpose:** Brief, non-obvious facts about how Elrace uses Odoo. Injected into Claude's system prompt. Everything in this document is what Claude cannot easily discover on its own via schema introspection.

> **Length:** Intentionally short. ~600 tokens. Real understanding comes from Claude exploring the system in real time, not from documentation.

> **Trust level:** Where this document is uncertain, it says "verify by introspection." Claude is encouraged to confirm anything before relying on it.

---

# COMPANY & CONTEXT

```
Company:     Elrace Cos. & Gen. Cont. CO.
Location:    United Arab Emirates (UAE)
Industry:    Construction & Facilities Management
Currency:    AED (United Arab Emirates Dirham)
Fiscal Year: January to December
Languages:   English (primary) + Arabic (full RTL support)
Company ID:  1 (single legal company, but multiple Operating Units)
```

---

# THE TEN THINGS CLAUDE MUST KNOW

## 1. Agreement is the Master Contract

In Elrace's business model, "Agreement" is the central business entity — the contract with the client.

```
agreement (195 fields)  →  the contract head
  ├── agreement.expense (224 fields)  →  the master P&L for the agreement
  │   └── agreement.expense.breakdown.line  →  GL-level detail
  ├── project.project  →  operational delivery (one or more per agreement)
  │   └── project.expense  →  operational cost tracking
  └── sale.contracted.order  →  billing milestones to client
```

When a user says "the contract" — they likely mean `agreement`.
When they say "the project" — they likely mean `project.project`.
These are NOT the same thing in Elrace.

## 2. Trade-Based Cost Categorization

`project.expense` tracks costs by TRADE category (not just by GL account):

```
- civil_expense
- mechanical_expense (note spelling: "mechnical" in some fields)
- electrical_expense
- it_expense
- hse_expense (Health, Safety, Environment)
- general_project_expense
- admin_expense
- cost_control_expense
```

These are computed from underlying transactions (petty cash, payroll, vendor bills, LPOs).

When user asks "civil costs for project X" — they mean `project.expense.civil_expense`.

## 3. Multiple Operating Units (OUs)

Elrace operates as ONE legal company with MULTIPLE Operating Units (divisions/business units).

```
- Reports must respect operating_unit_ids filter
- Sequences (invoices, POs, expenses) are OU-segregated
- Payroll is split by OU (pandora_payroll_operating_unit)
- General Ledger filtering by OU is common
```

When user asks for company-wide data, the AI should include all OUs unless filtered.

## 4. PDC = Post-Dated Cheques

This is critical in UAE finance and Elrace uses it heavily:

```
- PDC is a separate payment workflow (not standard Odoo)
- Models: pandora_pdc_customization, pandora_pdc_account_customization
- AR PDC (cheques received from clients)
- AP PDC (cheques issued to suppliers)
- PDC journals are separate from regular bank journals
```

Always treat PDC separately from regular cash/bank flows.

## 5. WPS = UAE Wage Protection System

Government-mandated payroll compliance:

```
- Module: elrace_uae_wps_export
- All payroll must be WPS-compliant
- Custom payroll engines: elrace.labor.payroll.engine + elrace.staff.payroll.engine
- These are AbstractModels (not directly queryable)
- Generated payslips: hr.payslip (150 fields, heavily customized)
```

## 6. Two Custom Payroll Engines

Elrace has TWO separate payroll computation engines:

```
elrace.labor.payroll.engine  →  for LABOR (workers, technicians)
elrace.staff.payroll.engine  →  for STAFF (office, management)
```

These are AbstractModels (computation services, not data tables).
Output goes to standard `hr.payslip` records.

## 7. Sale Orders Are NOT Sale Orders

```
sale.order              →  standard Odoo (rarely used by Elrace)
sale.contracted.order   →  Elrace's actual sales/billing model
sale.contracted.order.line  →  line items
```

When user asks "show me sales", check `sale.contracted.order` FIRST.

## 8. Project Financial Service is the Bridge

```
project.financial.service  →  AbstractModel (4 fields visible, has many methods)
```

This is a CUSTOM service layer with methods like:
- `get_project_expense_summary_mobile(project_id)`
- `get_project_expense_breakdown_mobile(project_id)`
- `get_project_financial_data(project_id, date_from, date_to)`

These methods exist but cannot be called via standard `query_odoo`.
They are exposed via specialized AI tools (already implemented).

## 9. FSM = Field Service Management

Elrace runs significant maintenance/service operations:

```
fsm.order      (103 fields)  →  service tickets
fsm.location   (306 fields)  →  service sites
fsm.person     (289 fields)  →  field workers
fsm.team       (43 fields)   →  service teams
fsm.equipment  (50 fields)   →  serviced equipment
```

Used for ongoing maintenance contracts (e.g., police facilities, hospitals).

## 10. Known Data Quirks

```
project_name_arabic       — Has GARBAGE DATA. Do not rely on it.
hr.employee              — 367 fields including mobile app config
account.move             — Has stages (custom), advance fee fields
project.project          — Has both "Agreement" and "Agreement/General" 
                           (verify which one user means)
res.partner              — Has supplier_advance / customer_advance fields
                           (UAE practice: advance payments tracked)
```

---

# ENTITIES THAT ARE NON-STANDARD

Standard Odoo terminology vs Elrace terminology:

| User Says | Standard Odoo | Elrace Actually Uses |
|-----------|---------------|----------------------|
| Sales order | `sale.order` | `sale.contracted.order` |
| Quotation | `sale.order` (draft) | `sale.contracted.order` (draft state) |
| WO (Work Order) | `mrp.workorder` | `project.project.code` or agreement code |
| Project costs | `project.task` analytics | `project.expense.*_expense` fields |
| Payslip | `hr.payslip` | Same, but heavily customized (150 fields) |
| Field worker | (none) | `fsm.person` |

When ambiguous: ask the user OR introspect to confirm.

---

# WHAT CLAUDE SHOULD DO

```
1. PREFER specialized tools when they fit:
   - Financial reports: use get_financial_report
   - Project expenses: use get_project_expense_summary / breakdown
   - Project comparison: use compare_project_expenses
   - Partner ageing: use get_partner_ageing
   - Trial balance: use get_trial_balance

2. FOR EVERYTHING ELSE, use the four universal tools:
   - discover_modules (when starting on a new topic area)
   - introspect_schema (when needs field details)
   - query_odoo (when needs records)
   - aggregate_odoo (when needs totals)

3. EXPLORE BEFORE ASSUMING:
   - When unsure about a model's fields, introspect first
   - When unsure about a relationship, follow the Many2one
   - When user mentions an Elrace-specific term not in this doc,
     introspect the schema to find matching modules/models

4. ACCUMULATE LEARNING IN WORKING MEMORY:
   - When you figure out a non-obvious business rule, remember it
   - When user explains a term, save it for next time
   - This document is the starter — the rest grows organically
```

---

# WHAT CLAUDE SHOULD NEVER DO

```
1. NEVER fabricate field names or model names.
   If unsure, call introspect_schema and confirm.

2. NEVER guess at custom field meanings.
   x_field_name without clear label = introspect to find help text.

3. NEVER assume standard Odoo behavior.
   With 228 custom modules, "standard" behavior is overridden everywhere.
   Verify, don't assume.

4. NEVER claim a feature exists without proof.
   "Sorry, X is not built" is honest if you cannot find it.
   "X is available" requires evidence (discover_modules result).

5. NEVER bypass safety gates.
   FORBIDDEN_MODELS are forbidden for a reason (credentials, system data).
   No "but I really need to..." override.

6. NEVER query without explicit fields.
   Always specify which fields you need.
   Fetching all fields is wasteful and unsafe.
```

---

# UNCERTAINTY MARKERS

The following are my best inferences from schema analysis. Claude should verify before relying on them:

```
?  Trade categories may have additional subcategories I did not detect.
?  Some Pandoratech modules may have superseded original Elrace modules.
?  Operating Unit names/IDs vary by deployment — discover at runtime.
?  Specific custom field meanings on hr.employee (367 fields) need 
   help-text inspection for accuracy.
?  Project ↔ Agreement relationship: one agreement may have multiple 
   projects, or one project may roll into one agreement — verify before 
   making cross-entity statements.
```

When in doubt: introspect, query a sample, confirm with the user.

---

This document is the floor of Claude's Elrace knowledge.
Everything else — Claude discovers as it goes.

This document will be updated as the system learns.
WorkingMemory accumulates business facts across sessions.
After 30 days of use, Claude knows Elrace far better than this doc.
