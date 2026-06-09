# ELRACE OMNI-AGENT FINAL PLAN

> **The Final Architecture.** Four universal tools. One starter context document. Safety gates. Working memory. That is all.

> **Result:** Claude can answer ANY question about ANY of the 875 installed Odoo modules — HR, payroll, timesheet, purchase, sales, FSM, fleet, accounting, custom Elrace modules — without us writing tool code for each.

> **Replaces:** The previous department-routing plans. Throw those away.

> **Read first:** `AI_CORE_INTELLIGENCE_ARCHITECTURE.md`, `ELRACE_STARTER_CONTEXT.md`

---

# PART I — THE PHILOSOPHY

## 1. The Core Insight

Claude already knows what Odoo is. Claude already knows what HR, payroll, timesheets, purchases, accounting mean. Claude has read more about Odoo than any consultant we could hire.

What Claude does NOT know:
- Which Odoo modules YOU installed (875 of them, 228 custom)
- Which custom fields YOU added
- How YOU use standard models non-standardly
- YOUR business naming conventions

Our job is NOT to teach Claude what Odoo is.
Our job is to give Claude:
1. **Access** to your specific Odoo (the database)
2. **A brief orientation** to your non-standard conventions
3. **Safety guardrails** so it cannot break anything
4. **Memory** so it accumulates Elrace-specific knowledge over time

That is it.

## 2. The Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│   CLAUDE (the intelligence)                                      │
│                                                                  │
│   System Prompt includes:                                        │
│     ✦ Core AI behavior (existing)                                │
│     ✦ Context Stack (from AI Core plan)                          │
│     ✦ ELRACE_STARTER_CONTEXT.md (1 page, ~600 tokens)            │
│     ✦ List of installed module count + key model names           │
│     ✦ Tool definitions (specialized + universal)                 │
│                                                                  │
└────────────────────────────────────┬────────────────────────────┘
                                     │
        ┌────────────────────────────┴────────────────────────────┐
        │                                                          │
        ▼                                                          ▼
 ┌────────────────────┐                              ┌────────────────────┐
 │ SPECIALIZED TOOLS  │                              │ UNIVERSAL TOOLS    │
 │ (existing, keep)   │                              │ (NEW, this plan)   │
 ├────────────────────┤                              ├────────────────────┤
 │ get_financial_     │                              │ discover_modules   │
 │   report           │                              │ introspect_schema  │
 │ get_project_       │                              │ query_odoo         │
 │   expense_summary  │                              │ aggregate_odoo     │
 │ get_project_       │                              └────────────────────┘
 │   expense_         │                                         │
 │   breakdown        │                                         │
 │ compare_project_   │                                         │
 │   expenses         │                                         │
 │ get_trial_balance  │                                         │
 │ get_partner_       │                                         │
 │   ageing           │                                         │
 │ ...                │                                         │
 └─────────┬──────────┘                                         │
           │                                                    │
           ▼                                                    ▼
 ┌────────────────────────────────────────────────────────────────┐
 │                                                                  │
 │    SAFE_SEARCH_READ adapter (bypasses Odoo bug)                  │
 │                                                                  │
 │    SAFETY GATES (5 layers):                                      │
 │      1. Forbidden models (credentials, system tables)            │
 │      2. Permission-based access (super admin vs roles)           │
 │      3. Read-only enforcement (no create/write/unlink)           │
 │      4. Query limits (max 500 records, must specify fields)      │
 │      5. PII redaction (wages, bank details for non-super-admin)  │
 │                                                                  │
 └──────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
                ┌──────────────────────────────┐
                │   ODOO 14 — odoo.elrace.com  │
                │   875 installed modules      │
                │   1,571 models                │
                │   ~40,000 fields              │
                └──────────────────────────────┘
```

## 3. The Working Memory Layer

```
WorkingMemory (already exists in AI Core architecture)
   │
   ├── Per-session memory (recent entities, recent queries)
   ├── Per-user memory (preferences, patterns)
   └── Cross-session Elrace knowledge (NEW)
       │
       ├── Discovered business rules
       │   "agreement.expense.civil_costs aggregates from these accounts..."
       │
       ├── User-provided explanations
       │   "WO means agreement.code"
       │
       ├── Successful query patterns
       │   "For payroll totals by OU: aggregate hr.payslip on operating_unit_id"
       │
       └── Failed assumptions
           "Tried to fetch x_field_xyz — does not exist"

This memory GROWS over time. After 90 days, Claude knows Elrace 
better than any starter context document could ever describe.
```

---

# PART II — THE FOUR UNIVERSAL TOOLS

## 4. Tool 1: `discover_modules`

```python
{
    "name": "discover_modules",
    "description": (
        "Discover what Odoo modules are installed and what they do. "
        "Use this FIRST when starting on a new topic area, especially "
        "for custom Elrace modules you have not seen before.\n\n"
        
        "Returns: matching modules with name, description, and category.\n\n"
        
        "USE WHEN:\n"
        "- User mentions a term you don't recognize (might be a module name)\n"
        "- You need to know if a feature exists\n"
        "- Confirming module availability before claiming a capability"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": (
                    "Search hint. Examples: 'payroll', 'wps', 'pdc', "
                    "'subcontract', 'fleet'."
                )
            },
            "author": {
                "type": "string",
                "description": (
                    "Filter by author. Useful filters: 'Elrace', 'Pandoratech', "
                    "'Odoo S.A.' to find custom vs standard modules."
                )
            },
        },
    },
}
```

**Implementation:**

```python
# gateway/tools/universal_odoo.py

async def execute_discover_modules(
    tool_input: dict,
    adapter,
    context: ContextStack,
) -> dict:
    """List installed Odoo modules matching the search."""
    search = tool_input.get("search", "").strip()
    author = tool_input.get("author", "").strip()
    
    domain = [["state", "=", "installed"]]
    if search:
        domain.append("|")
        domain.append("|")
        domain.append(["name", "ilike", search])
        domain.append(["shortdesc", "ilike", search])
        domain.append(["summary", "ilike", search])
    if author:
        domain.append(["author", "ilike", author])
    
    try:
        modules = await asyncio.to_thread(
            adapter.safe_search_read,
            "ir.module.module",
            domain,
            ["name", "shortdesc", "summary", "author", "category_id"],
            limit=50,
        )
    except Exception as e:
        return {
            "status": "error",
            "error_code": "discovery_failed",
            "message": str(e),
        }
    
    return {
        "status": "success",
        "search": search,
        "author_filter": author,
        "module_count": len(modules),
        "modules": [
            {
                "name": m["name"],
                "label": m["shortdesc"],
                "summary": m.get("summary", ""),
                "author": m.get("author", ""),
                "is_custom": m.get("author") not in ["Odoo S.A.", "OCA"],
            }
            for m in modules
        ],
        "_source": "discover_modules",
    }
```

## 5. Tool 2: `introspect_schema`

```python
{
    "name": "introspect_schema",
    "description": (
        "Discover Odoo models and their fields. Use this when you need to "
        "know what models exist or what fields a specific model has.\n\n"
        
        "Two modes:\n"
        "1. Search mode: pass 'search' to find models matching a keyword\n"
        "2. Detail mode: pass 'model' to get full field details for one model\n\n"
        
        "USE WHEN:\n"
        "- User asks about an area you haven't explored (HR, inventory, etc.)\n"
        "- You don't know what fields a model has\n"
        "- You need to find the right relationship field\n\n"
        
        "WORKFLOW:\n"
        "1. First: introspect_schema(search='employee') to find hr.employee\n"
        "2. Then: introspect_schema(model='hr.employee') to see all fields\n"
        "3. Then: query_odoo to fetch the data"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Search hint to find matching models"
            },
            "model": {
                "type": "string",
                "description": "Specific model name to get full field details"
            },
        },
    },
}
```

**Implementation:**

```python
FORBIDDEN_MODELS = {
    "res.users", "res.users.log", "ir.config_parameter",
    "ir.mail_server", "auth.totp.device", "fetchmail.server",
    "res.users.apikeys", "res.users.apikeys.description",
}

SENSITIVE_MODELS = {
    "hr.payslip", "hr.payslip.line", "hr.payslip.run",
    "hr.contract", "account.payment", "res.bank",
    "res.partner.bank", "elrace.offer.letter",
    "elrace.recruitment.request",
}


async def execute_introspect_schema(
    tool_input: dict,
    adapter,
    context: ContextStack,
) -> dict:
    """Discover models or get full field details."""
    search = tool_input.get("search", "").strip().lower()
    specific_model = tool_input.get("model", "").strip()
    
    if specific_model:
        return await _describe_model(specific_model, adapter, context)
    return await _list_models(search, adapter, context)


async def _list_models(search, adapter, context):
    """List models matching search."""
    domain = []
    if search:
        domain = [
            "|", "|",
            ["model", "ilike", search],
            ["name", "ilike", search],
            ["info", "ilike", search],
        ]
    
    models = await asyncio.to_thread(
        adapter.safe_search_read,
        "ir.model",
        domain,
        ["model", "name", "info", "transient"],
        limit=50,
    )
    
    accessible = []
    for m in models:
        if m.get("transient"):
            continue  # Skip wizards
        if m["model"] in FORBIDDEN_MODELS:
            continue
        if not _user_can_see_model(m["model"], context.user):
            continue
        accessible.append({
            "model": m["model"],
            "label": m["name"],
            "description": (m.get("info") or "").strip()[:200],
            "is_sensitive": m["model"] in SENSITIVE_MODELS,
        })
    
    return {
        "status": "success",
        "search": search,
        "model_count": len(accessible),
        "models": accessible,
        "_note": "Call again with 'model' param to get field details.",
    }


async def _describe_model(model_name, adapter, context):
    """Get full field details for one model."""
    if model_name in FORBIDDEN_MODELS:
        return {
            "status": "error",
            "error_code": "model_forbidden",
            "message": f"'{model_name}' is permanently restricted.",
        }
    
    if not _user_can_see_model(model_name, context.user):
        return {
            "status": "error",
            "error_code": "permission_denied",
            "message": f"Your role does not have access to '{model_name}'.",
        }
    
    try:
        fields = await asyncio.to_thread(
            adapter.execute_kw,
            model_name, "fields_get", [],
            {"attributes": [
                "string", "type", "required", "readonly",
                "help", "relation", "selection",
            ]},
        )
    except Exception as e:
        return {
            "status": "error",
            "error_code": "model_not_found",
            "message": f"Model '{model_name}' not accessible: {e}",
        }
    
    useful = {}
    for fname, finfo in fields.items():
        if fname.startswith("_") or fname == "__last_update":
            continue
        useful[fname] = {
            "label": finfo.get("string", fname),
            "type": finfo.get("type"),
            "required": finfo.get("required", False),
            "readonly": finfo.get("readonly", False),
            "help": (finfo.get("help") or "").strip()[:300],
        }
        # Include relation for Many2one / One2many / Many2many
        if finfo.get("relation"):
            useful[fname]["relation"] = finfo["relation"]
        # Include selection values
        if finfo.get("selection"):
            useful[fname]["values"] = finfo["selection"]
    
    return {
        "status": "success",
        "model": model_name,
        "field_count": len(useful),
        "fields": useful,
        "is_sensitive": model_name in SENSITIVE_MODELS,
    }


def _user_can_see_model(model_name, user):
    """Permission check for model access."""
    if user.level >= 100:  # Super admin
        return model_name not in FORBIDDEN_MODELS
    if user.level >= 70:  # Top management
        return (
            model_name not in FORBIDDEN_MODELS
            and model_name not in SENSITIVE_MODELS
        )
    # Lower roles: explicit permission required
    return (
        model_name in (user.permissions or set())
        and model_name not in FORBIDDEN_MODELS
    )
```

## 6. Tool 3: `query_odoo`

```python
{
    "name": "query_odoo",
    "description": (
        "Query Odoo records directly. Read-only. Use for any data not "
        "covered by specialized tools.\n\n"
        
        "WORKFLOW:\n"
        "1. If unsure what model/fields to use, call introspect_schema first.\n"
        "2. Build a precise domain to limit results.\n"
        "3. Specify only the fields you need.\n"
        "4. Use a reasonable limit (default 50, max 500).\n\n"
        
        "USE FOR:\n"
        "- HR (hr.employee, hr.department, hr.job)\n"
        "- Payroll (hr.payslip — sensitive, super admin or authorized only)\n"
        "- Timesheet (account.analytic.line)\n"
        "- Inventory (stock.quant, product.product)\n"
        "- Purchase (purchase.order, purchase.request)\n"
        "- Sales (sale.contracted.order — Elrace uses this, not sale.order)\n"
        "- CRM (crm.lead)\n"
        "- Fleet (fleet.vehicle)\n"
        "- FSM (fsm.order, fsm.location, fsm.person)\n"
        "- Any custom Elrace model\n\n"
        
        "DO NOT USE FOR:\n"
        "- P&L, balance sheet, cash flow → get_financial_report\n"
        "- Project expenses → get_project_expense_summary/breakdown\n"
        "- Partner ageing → get_partner_ageing\n"
        "- Trial balance → get_trial_balance"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "model": {"type": "string"},
            "domain": {
                "type": "array",
                "description": (
                    "Odoo search domain. Examples: "
                    "[['active', '=', true]] or "
                    "[['date_from', '>=', '2026-05-01'], "
                    "['state', '=', 'done']]"
                ),
                "default": []
            },
            "fields": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific fields to retrieve. REQUIRED."
            },
            "limit": {
                "type": "integer",
                "default": 50,
                "maximum": 500
            },
            "order": {"type": "string"},
        },
        "required": ["model", "fields"],
    },
}
```

**Implementation:**

```python
async def execute_query_odoo(
    tool_input: dict,
    adapter,
    context: ContextStack,
) -> dict:
    """Generic read-only Odoo query."""
    model = tool_input["model"]
    domain = tool_input.get("domain", [])
    fields = tool_input.get("fields", [])
    limit = min(tool_input.get("limit", 50), 500)
    order = tool_input.get("order")
    
    # SAFETY LAYER 1: Forbidden models
    if model in FORBIDDEN_MODELS:
        return {
            "status": "error",
            "error_code": "model_forbidden",
            "message": f"'{model}' is permanently restricted.",
        }
    
    # SAFETY LAYER 2: Permission check
    if not _user_can_see_model(model, context.user):
        return {
            "status": "error",
            "error_code": "permission_denied",
            "message": (
                f"Your role does not have read access to '{model}'. "
                f"Required: super admin or explicit model permission."
            ),
        }
    
    # SAFETY LAYER 3: Required fields
    if not fields:
        return {
            "status": "error",
            "error_code": "fields_required",
            "message": (
                "You must specify which fields to retrieve. "
                "Call introspect_schema first if unsure."
            ),
        }
    
    # SAFETY LAYER 4: Strip dangerous fields
    fields = _strip_dangerous_fields(model, fields, context.user)
    
    # SAFETY LAYER 5: Augment domain with permission filters
    domain = _augment_domain(model, domain, context.user)
    
    try:
        kwargs = {"limit": limit}
        if order:
            kwargs["order"] = order
        
        records = await asyncio.to_thread(
            adapter.safe_search_read,
            model, domain, fields, **kwargs,
        )
    except Exception as e:
        return {
            "status": "error",
            "error_code": "query_failed",
            "message": str(e),
            "model": model,
            "domain": domain,
        }
    
    # SAFETY LAYER 6: PII redaction
    if model in SENSITIVE_MODELS:
        records = _redact_sensitive(model, records, context.user)
    
    # Audit log
    await _audit_query(
        user=context.user, tool="query_odoo", model=model,
        domain=domain, fields=fields, record_count=len(records),
    )
    
    return {
        "status": "success",
        "model": model,
        "domain_used": domain,
        "fields_returned": fields,
        "record_count": len(records),
        "records": records,
        "truncated": len(records) == limit,
        "_source": "universal_odoo_query",
    }


def _strip_dangerous_fields(model, fields, user):
    """Remove fields the user is not allowed to see."""
    danger_map = {
        "res.users": ["password", "password_crypt", "api_key"],
        "res.partner.bank": ["acc_number"] if user.level < 70 else [],
        "hr.applicant": ["partner_phone", "email_from"] if user.level < 70 else [],
    }
    blocked = set(danger_map.get(model, []))
    return [f for f in fields if f not in blocked]


def _augment_domain(model, domain, user):
    """Add permission-based filters to the domain."""
    if user.level >= 100:
        return domain  # Super admin: no restriction
    
    if user.access_breadth() == "department" and user.department_id:
        if model == "hr.employee":
            return domain + [["department_id", "=", user.department_id]]
        if model == "hr.payslip":
            return domain + [
                ["employee_id.department_id", "=", user.department_id]
            ]
    
    return domain


def _redact_sensitive(model, records, user):
    """Redact sensitive fields for non-super-admin."""
    if user.level >= 100:
        return records
    
    redactions = {
        "hr.payslip": [
            "net_wage", "gross_wage", "amount", "total",
            "basic", "salary", "addition", "deduction",
        ] if user.level < 70 else [],
        "hr.contract": ["wage", "salary"] if user.level < 70 else [],
    }
    fields_to_redact = redactions.get(model, [])
    if not fields_to_redact:
        return records
    
    for r in records:
        for f in fields_to_redact:
            if f in r:
                r[f] = "***redacted***"
    return records
```

## 7. Tool 4: `aggregate_odoo`

```python
{
    "name": "aggregate_odoo",
    "description": (
        "Aggregate Odoo records — sum, count, average, max, min — grouped "
        "by fields. Use when you need totals or summary stats rather than "
        "individual records.\n\n"
        
        "USE FOR:\n"
        "- 'Total payroll for May' → aggregate hr.payslip\n"
        "- 'Employee count per department' → aggregate hr.employee\n"
        "- 'PO total by supplier' → aggregate purchase.order\n"
        "- 'Stock value by location' → aggregate stock.quant\n\n"
        
        "Returns grouped results."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "model": {"type": "string"},
            "domain": {"type": "array", "default": []},
            "group_by": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Fields to group by. Examples: ['department_id']"
            },
            "aggregates": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Format: 'field:operation'. "
                    "Operations: sum, count, avg, max, min. "
                    "Examples: ['net_wage:sum', 'id:count']"
                )
            },
            "limit": {"type": "integer", "default": 50}
        },
        "required": ["model", "group_by", "aggregates"],
    },
}
```

**Implementation:**

```python
async def execute_aggregate_odoo(
    tool_input: dict,
    adapter,
    context: ContextStack,
) -> dict:
    """Aggregate Odoo records via read_group."""
    model = tool_input["model"]
    domain = tool_input.get("domain", [])
    group_by = tool_input["group_by"]
    aggregates = tool_input["aggregates"]
    limit = min(tool_input.get("limit", 50), 200)
    
    # Same safety layers as query_odoo
    if model in FORBIDDEN_MODELS:
        return {
            "status": "error",
            "error_code": "model_forbidden",
            "message": f"'{model}' is restricted.",
        }
    
    if not _user_can_see_model(model, context.user):
        return {
            "status": "error",
            "error_code": "permission_denied",
            "message": f"No access to '{model}'.",
        }
    
    domain = _augment_domain(model, domain, context.user)
    
    try:
        results = await asyncio.to_thread(
            adapter.execute_kw,
            model, "read_group",
            [domain, aggregates, group_by],
            {"limit": limit},
        )
    except Exception as e:
        return {
            "status": "error",
            "error_code": "aggregation_failed",
            "message": str(e),
        }
    
    # PII redaction for sensitive aggregates
    if model in SENSITIVE_MODELS and context.user.level < 100:
        results = _redact_aggregates(model, results, context.user)
    
    await _audit_query(
        user=context.user, tool="aggregate_odoo", model=model,
        domain=domain, fields=aggregates + group_by, record_count=len(results),
    )
    
    return {
        "status": "success",
        "model": model,
        "domain_used": domain,
        "group_by": group_by,
        "aggregates": aggregates,
        "group_count": len(results),
        "groups": results,
        "_source": "universal_odoo_aggregate",
    }


def _redact_aggregates(model, results, user):
    """Redact sensitive aggregate fields."""
    if model == "hr.payslip" and user.level < 70:
        for r in results:
            for key in list(r.keys()):
                if any(s in key.lower() for s in ["wage", "salary", "amount", "total"]):
                    r[key] = "***redacted***"
    return results
```

---

# PART III — SAFETY GATES

## 8. The Five Safety Layers

```
LAYER 1: FORBIDDEN MODELS
  Hard-coded list. Never queryable by anyone.
  - res.users (credentials)
  - ir.config_parameter (system secrets)
  - ir.mail_server (SMTP creds)
  - res.partner.bank.acc_number (partial — field-level)
  - auth.totp.device (2FA)

LAYER 2: PERMISSION-BASED MODEL ACCESS
  Super admin (level 100): all except FORBIDDEN
  Top management (level 70): all except SENSITIVE
  Manager (level 50): department-scoped only
  User (level 30): explicit permissions only

LAYER 3: READ-ONLY ENFORCEMENT
  Only safe_search_read and read_group exposed
  Create/write/unlink methods not callable
  No admin/system actions possible

LAYER 4: QUERY LIMITS
  Max 500 records per query (hard cap)
  Max 200 groups per aggregation
  Must specify fields (no fetch-all)
  30 second timeout per query

LAYER 5: PII REDACTION
  Sensitive fields hidden for non-super-admin:
    - hr.payslip wages → "***redacted***"
    - hr.contract salary → "***redacted***"
    - res.partner.bank.acc_number → "***redacted***"
  Audit log records every sensitive query
```

## 9. Audit Logging

```python
# gateway/core/odoo_audit.py

@dataclass
class OdooQueryAudit:
    user_id: int
    user_role: str
    timestamp: datetime
    tool_used: str
    model: str
    domain: list
    fields: list[str]
    record_count: int
    duration_ms: int
    was_redacted: bool


async def _audit_query(user, tool, model, domain, fields, record_count):
    """Log to PostgreSQL."""
    audit = OdooQueryAudit(
        user_id=user.user_id,
        user_role=user.primary_role,
        timestamp=datetime.utcnow(),
        tool_used=tool,
        model=model,
        domain=domain,
        fields=fields,
        record_count=record_count,
        duration_ms=0,
        was_redacted=model in SENSITIVE_MODELS and user.level < 100,
    )
    
    await db.execute(
        """
        INSERT INTO odoo_query_audit
        (user_id, user_role, timestamp, tool_used, model, 
         domain, fields, record_count, was_redacted)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        audit.user_id, audit.user_role, audit.timestamp,
        audit.tool_used, audit.model, json.dumps(audit.domain),
        audit.fields, audit.record_count, audit.was_redacted,
    )
```

---

# PART IV — STARTER CONTEXT INJECTION

## 10. How The Starter Context Is Used

```python
# gateway/core/context_stack_builder.py

class ContextStackBuilder:
    """Already exists from AI Core plan. Add this method:"""
    
    async def _build_elrace_context(self) -> str:
        """Load ELRACE_STARTER_CONTEXT.md into prompt."""
        path = Path(__file__).parent.parent.parent / "ELRACE_STARTER_CONTEXT.md"
        if not path.exists():
            return ""
        return path.read_text()
    
    async def build(self, user, request) -> ContextStack:
        # ... existing code ...
        elrace_context = await self._build_elrace_context()
        
        return ContextStack(
            user=user_context,
            capability_manifest=self.manifest,
            working_memory=working_memory,
            business_context=business_context,
            temporal_context=temporal_context,
            elrace_context=elrace_context,  # NEW
            # ...
        )


# In ContextStack.to_prompt_section():
def to_prompt_section(self) -> str:
    return f"""
=== USER CONTEXT ===
{self.user.summary()}

=== CAPABILITIES ===
{self.capability_manifest.summary()}

=== ELRACE BUSINESS CONTEXT ===
{self.elrace_context}

=== WORKING MEMORY ===
{self.working_memory.summary()}

=== TEMPORAL CONTEXT ===
{self.temporal_context.summary()}
"""
```

## 11. Capability Manifest Updates

```python
# In gateway/core/capability_manifest.py

# BEFORE (had departments as unavailable):
unavailable=[
    Capability("hr.payslips", "Payslip access", ...),
    ...
]

# AFTER:
available=[
    # Existing specialized capabilities
    Capability("financial.pandl", "Profit & Loss reports"),
    Capability("project.expense_summary", "Project expense summary"),
    ...
    
    # NEW universal capabilities
    Capability(
        "universal.odoo_query",
        "Query any Odoo model (read-only) — HR, payroll, inventory, "
        "sales, purchase, CRM, manufacturing, fleet, FSM, and all custom "
        "Elrace modules. 875 modules accessible."
    ),
    Capability(
        "universal.odoo_aggregate",
        "Aggregate any Odoo data — totals, counts, averages, sums."
    ),
    Capability(
        "universal.schema_discovery",
        "Discover what Odoo models and fields exist."
    ),
    Capability(
        "universal.module_discovery",
        "Find installed Odoo modules by name or topic."
    ),
],

# Only write operations stay unavailable:
unavailable=[
    Capability("write.create_records", "Create new records",
        alternative="Use Odoo directly"),
    Capability("write.modify_records", "Modify existing records",
        alternative="Use Odoo directly"),
    Capability("write.delete_records", "Delete records",
        alternative="Use Odoo directly"),
    Capability("write.approve_payments", "Approve payments",
        alternative="Use Odoo approval flow"),
],
```

---

# PART V — IMPLEMENTATION PHASES

## 12. Build Order (3 Weeks Total)

### Phase O1 — Universal Tools (Week 1)

```
[ ] Create gateway/tools/universal_odoo.py
[ ] Implement discover_modules
[ ] Implement introspect_schema  
[ ] Implement query_odoo with all 5 safety layers
[ ] Implement aggregate_odoo with safety layers
[ ] Define FORBIDDEN_MODELS, SENSITIVE_MODELS constants
[ ] Build _user_can_see_model, _strip_dangerous_fields,
    _augment_domain, _redact_sensitive helpers
[ ] Create gateway/core/odoo_audit.py
[ ] Create odoo_query_audit table in PostgreSQL
[ ] Add to gateway/main.py TOOLS array (after specialized tools)
[ ] Add to gateway/tools/__init__.py exports

UNIT TESTS in tests/tools/test_universal_odoo.py:

1. discover_modules(search="payroll") returns Elrace payroll modules
2. discover_modules(author="Elrace") returns only Elrace modules
3. introspect_schema(search="employee") returns hr.employee
4. introspect_schema(model="hr.employee") returns field details
5. introspect_schema blocks FORBIDDEN_MODELS
6. query_odoo without fields → "fields_required" error
7. query_odoo with limit > 500 → capped to 500
8. query_odoo of FORBIDDEN_MODELS → blocked
9. query_odoo by non-super-admin of SENSITIVE_MODELS → wages redacted
10. query_odoo augments domain for department-scoped user
11. aggregate_odoo basic count works
12. aggregate_odoo sum with grouping works
13. aggregate_odoo on hr.payslip redacts wage aggregates for non-super-admin
14. All tools write to odoo_query_audit table
15. Super admin can query any non-forbidden model

DONE WHEN: All 15 tests pass.
```

### Phase O2 — Context Integration (Week 2)

```
[ ] Place ELRACE_STARTER_CONTEXT.md in repo root
[ ] Update ContextStackBuilder to load it
[ ] Add elrace_context field to ContextStack
[ ] Update to_prompt_section() to include it
[ ] Update CAPABILITY_MANIFEST (move from unavailable to available)
[ ] Verify system prompt size stays under 8000 tokens
[ ] Update IntelligentQueryHandler if needed

INTEGRATION TESTS in tests/integration/test_elrace_context.py:
1. ELRACE_STARTER_CONTEXT.md exists at repo root
2. ContextStackBuilder loads it without error
3. Context appears in to_prompt_section() output
4. Context contains "Agreement is the Master Contract"
5. Context contains "PDC" reference
6. Context contains "WPS" reference
7. CAPABILITY_MANIFEST shows universal capabilities as available
8. CAPABILITY_MANIFEST no longer shows hr.payslips as unavailable
9. System prompt total size < 8000 tokens
10. Super admin context includes elrace context

DONE WHEN: All 10 tests pass.
```

### Phase O3 — Real-World Testing (Week 3)

```
[ ] Write 25 canonical queries covering all departments
[ ] Run each through the full pipeline
[ ] Verify Claude picks the right tool
[ ] Verify response quality
[ ] Verify no fabrication
[ ] Update CURRENT_PHASE.md
[ ] Documentation for team

THE 25 CANONICAL QUERIES (Phase O3 acceptance):

EMPLOYEE & HR:
1. "list all active employees"
2. "employees in Engineering department"
3. "how many employees joined this year"
4. "department list with employee counts"

PAYROLL (super admin only — verify permission):
5. "total payroll cost for May 2026"
6. "payroll batch summary last quarter"
7. "average gross wage by department" (super admin)
8. "payslips for employee Ahmed Hassan last 6 months"

TIMESHEET:
9. "total hours logged on Zayidia Boys School project"
10. "top 5 employees by hours this month"
11. "attendance for engineering team last week"

INVENTORY:
12. "current stock of cement"
13. "products below minimum stock"
14. "stock movements last week"

PURCHASE:
15. "open POs from Al Hewar Contracting"
16. "total purchases this quarter by supplier"
17. "PO 2025-001 line items"

SALES (use sale.contracted.order, not sale.order):
18. "active contracted orders"
19. "top customers by contracted value"

FSM (Field Service):
20. "open FSM orders this month"
21. "FSM workers (fsm.person) active count"

CRM:
22. "leads in negotiation stage"

FLEET:
23. "vehicles with services due"

CUSTOM ELRACE:
24. "recruitment requests in progress" (elrace.recruitment.request)
25. "active offer letters" (elrace.offer.letter)

ACCEPTANCE CRITERIA:
- 23 of 25 must return real data correctly
- No fabricated errors (no "database issue" or "not built")
- Sensitive fields redacted for appropriate roles
- Multi-step queries handled gracefully

For each: log which tool Claude chose, response quality 1-5.

DONE WHEN: 23/25 work + permission system verified.
```

---

# PART VI — INTEGRATION WITH EXISTING ARCHITECTURE

## 13. What This Plan Touches

```
ADDS:
  + gateway/tools/universal_odoo.py
  + gateway/core/odoo_audit.py
  + ELRACE_STARTER_CONTEXT.md
  + tests/tools/test_universal_odoo.py
  + tests/integration/test_elrace_context.py
  + DB: odoo_query_audit table

MODIFIES:
  ~ gateway/main.py (add 4 tools to TOOLS array)
  ~ gateway/tools/__init__.py (export new tools)
  ~ gateway/core/context_stack.py (add elrace_context field)
  ~ gateway/core/context_stack_builder.py (load elrace context)
  ~ gateway/core/capability_manifest.py (update available list)

DOES NOT TOUCH:
  ✗ Existing specialized tools (financial, expense, partner)
  ✗ Existing Odoo modules (no Odoo changes)
  ✗ EntityResolver (existing logic stays)
  ✗ Quality gate (existing 8 checks stay)
  ✗ Failure handler (existing modes stay)
  ✗ UI components (no UI changes needed for Phase O1-O2)
```

## 14. UI Consideration For Phase O3+

The four universal tools work entirely behind the scenes. No new UI needed for them to function. However, response visualization may benefit from:

```
NEW (optional, future):
  GenericTableViz.jsx — render any query_odoo result as a table
  GenericAggregateViz.jsx — render aggregate_odoo results as bar/pie
  ModelExplorer.jsx (admin only) — browse the schema like Odoo's debug menu

These are NICE-TO-HAVE. Existing chat visualization handles most cases.
Skip until Phase O3 reveals specific UI gaps.
```

---

# PART VII — WHY THIS WORKS

## 15. The Math

```
Old approaches I tried:
  Plan v1 (departments):   2,500 lines, 8 weeks
  Plan v2 (registries):    1,800 lines, 6 weeks  
  Plan v3 (this one):        600 lines, 3 weeks

The reduction is not laziness — it's correctness.
Claude already knows Odoo. Stop teaching it.
```

## 16. What Claude Can Now Do

```
User: "list employees in engineering"
  Claude → introspect_schema(search="employee")
        → query_odoo("hr.employee", 
                     [["department_id.name", "ilike", "engineering"],
                      ["active", "=", true]],
                     ["id", "name", "job_title", "work_email"])
  Returns list. Done in 2 tool calls.

User: "total payroll for May"
  Claude → aggregate_odoo("hr.payslip",
                          [["date_from", ">=", "2026-05-01"],
                           ["date_from", "<=", "2026-05-31"],
                           ["state", "=", "done"]],
                          [],
                          ["net_wage:sum", "id:count"])
  Returns total. Done in 1 tool call.

User: "stock levels for cement at Al Ain warehouse"
  Claude → introspect_schema(search="stock") (if first time)
        → query_odoo("stock.quant",
                     [["product_id.name", "ilike", "cement"],
                      ["location_id.warehouse_id.name", "ilike", "Al Ain"]],
                     ["product_id", "location_id", "quantity"])
  Returns inventory. Done in 2 tool calls.

User: "show me all Elrace recruitment requests pending"
  Claude → introspect_schema(search="recruitment")
        → query_odoo("elrace.recruitment.request",
                     [["state", "=", "in_progress"]],
                     ["name", "department_id", "applications", "create_date"])
  Returns custom Elrace data. Done in 2 tool calls.

User: "what's the WPS export module"
  Claude → discover_modules(search="wps")
  Returns module info. Done in 1 tool call.

Pattern: 1-2 tool calls per query.
All 875 modules accessible. Zero new code needed.
```

## 17. What Claude Cannot Do

```
✗ Create records (read-only enforced)
✗ Modify records (read-only enforced)
✗ Delete records (read-only enforced)
✗ Query credentials (FORBIDDEN_MODELS)
✗ See PII (redacted for non-super-admin)
✗ Bypass safety gates (hard-coded)
✗ Run admin/system operations (not exposed)
```

This is the right trade-off. Read everything, write nothing. Until we add write capability with proper audit/approval (future plan).

---

# PART VIII — TELL CURSOR

```
"Read ELRACE_OMNI_AGENT_FINAL_PLAN.md and ELRACE_STARTER_CONTEXT.md.

CRITICAL: This REPLACES the previous department-routing plans.
Throw away UNIVERSAL_DEPARTMENT_ACCESS_PLAN and 
UNIVERSAL_ODOO_ACCESS_PLAN_V2. Use this one only.

3-week plan in 3 phases.

Start Phase O1: Universal Tools (Week 1).

1. Create gateway/tools/universal_odoo.py
2. Implement all 4 tools (discover_modules, introspect_schema, 
   query_odoo, aggregate_odoo)
3. Define FORBIDDEN_MODELS, SENSITIVE_MODELS
4. Create gateway/core/odoo_audit.py
5. Create odoo_query_audit table in PostgreSQL
6. Add to gateway/main.py TOOLS array
7. Write all 15 unit tests
8. Tests must pass before moving on

Critical rules:
- All Odoo calls via safe_search_read (the bug-fix method)
- Read-only — never expose create/write/unlink methods
- Hard cap 500 records per query
- Must require explicit fields parameter
- Audit log every call to PostgreSQL
- Existing specialized tools STAY UNTOUCHED (financial, expense)
- Permission check before every query
- PII redaction for non-super-admin

Then Phase O2: Context Integration (Week 2).
Place ELRACE_STARTER_CONTEXT.md at repo root, wire into ContextStackBuilder.

Then Phase O3: Real-World Testing (Week 3).
Run all 25 canonical queries, verify 23+ pass.

After all 3 phases done, super admin can query ANY of 875 modules
naturally. Other roles get scoped + redacted access.

This is the final answer to 'universal access'."
```

---

# PART IX — THE ENDGAME

```
After this plan ships (3 weeks):

A super admin can ask in natural language:
  ✓ "Show me all FSM orders for Abu Dhabi Police this month"
  ✓ "Top 10 suppliers by purchase value Q1"  
  ✓ "Employees on long-term sick leave"
  ✓ "Vehicles needing fitness renewal this month"
  ✓ "Pending PDC payments due next week"
  ✓ "Recruitment funnel by stage"
  ✓ "Stock value tied up at each warehouse"
  ✓ "Active contracted orders not yet billed"

And Claude returns real data. From the real Odoo. In real time.
No "not built". No "not accessible". No fake errors.

Just intelligent access to the entire business.

This is the Elrace Omni-Agent. This is the goal.
```

---

# PART X — FINAL NOTES

```
What this plan achieves:
  ✓ Universal access to all 875 modules
  ✓ 3 weeks of build (vs 8+ for previous plans)
  ✓ 600 lines of code (vs 2,500+)
  ✓ Zero new code per future module
  ✓ Safe (5-layer protection)
  ✓ Auditable (every query logged)
  ✓ Honest (no fabrication possible)
  ✓ Grows smarter over time (WorkingMemory)

What this plan does NOT do:
  ✗ Write operations (intentionally — future plan)
  ✗ Cross-database queries (single Odoo only)
  ✗ Real-time streaming (request/response model)
  ✗ Replace specialized tools (they stay for complex logic)

What success looks like:
  After 30 days of use, Claude knows Elrace better than this 
  starter document. WorkingMemory has accumulated dozens of 
  business rules. Users stop asking simple questions because 
  the AI anticipates them. Super admin uses it daily. Other 
  roles use it for their scope.

  No more "not accessible".
  No more fake errors.
  No more silos.
```

This is the plan. Three weeks. Then we are done with the universal access problem forever.
