# AGENT MODE REBUILD — THE FOUNDATIONAL REFACTOR

> **What this is:** The architectural rebuild we should have done weeks ago. Replace the rigid pipeline with true agent-mode behavior — Claude makes all decisions itself.

> **What this keeps:** All existing behaviors users see — suggestions, pickers, pill buttons, visualizations, agents (Chat/Audit/Reports), bilingual support.

> **What this changes:** Everything under the hood. The IntentAnalyzer, StrategyPlanner, and rigid routing get REPLACED with one clean agent loop.

> **Timeline:** 5-7 working days. One week. No new features during this.

---

# PART I — WHY THIS REBUILD

## The Current Problem (One Sentence)

```
The AI feels dumb because there are 5 layers of code making 
decisions FOR Claude, not letting Claude make them itself.
```

## The Symptoms You Just Showed Me

```
"need HR info" → dumps 50 records 
  Why: No layer in the pipeline knows to ASK BACK when query is vague
  
"compare top 5 projects" → raw Python traceback
  Why: Tool errors leak through the pipeline without graceful recovery
  
"Show payroll by dept" after Jawad → re-asks about Jawad
  Why: Pipeline carries stale context from previous turn
  
"vehicle assigned to jawad" → "specify employee name"
  Why: Pipeline didn't recognize "jawad" as the employee name
  
Suggestions never match context
  Why: Suggestion generator runs independently from response generation
```

**Every single one of these is the same root cause: Claude isn't allowed to think.**

The pipeline pre-decides things and forces Claude into rigid response patterns.

---

# PART II — THE NEW ARCHITECTURE

## One Agent Loop, Many Capabilities

```
┌──────────────────────────────────────────────────────────────┐
│                    USER MESSAGE ARRIVES                       │
└───────────────────────────┬──────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                  AGENT CORE (Claude)                          │
│                                                               │
│  Receives:                                                    │
│    - User message                                             │
│    - Last 5 turns of history                                  │
│    - All tools (universal, specialized, ui_blocks)            │
│    - Elrace business context                                  │
│    - User permissions                                         │
│                                                               │
│  Decides (in one reasoning step):                             │
│    □ Is this clear? → call tool                               │
│    □ Is this vague? → emit ui_block (picker/pills)            │
│    □ Did tool fail? → recover, retry, or explain              │
│    □ What's the response? → text + viz + suggestions          │
└───────────────────────────┬──────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                    TOOL EXECUTION                             │
│  (only if Claude called a tool)                               │
└───────────────────────────┬──────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                  CLAUDE SYNTHESIZES RESPONSE                  │
│  Includes: text, ui_blocks, suggestions, visualization        │
└───────────────────────────┬──────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│                    STREAM TO FRONTEND                         │
└──────────────────────────────────────────────────────────────┘
```

## The Key Difference

```
OLD PIPELINE:
  Message → IntentAnalyzer (Claude #1) → 
            StrategyPlanner (Claude #2) → 
            EntityGate (Python logic) → 
            ToolExecutor (Python) → 
            ResultSynthesizer (Claude #3) → 
            QualityGate (Claude #4)
  
  4 Claude calls per query. Each one constrained by previous.
  Each stage adds rigidity.

NEW AGENT LOOP:
  Message → Agent (Claude with all tools) → 
            (tool calls happen automatically via tool_use) → 
            Final Response
  
  1-2 Claude calls per query. Claude has full context.
  Total flexibility, total intelligence.
```

---

# PART III — WHAT GETS BUILT

## Component 1 — The Agent Core (gateway/agent/core.py)

```python
"""
The agent core. ONE function. Handles all queries.
Replaces IntentAnalyzer + StrategyPlanner + Routing.
"""

import anthropic
from gateway.agent.tools_registry import get_all_tools, execute_tool
from gateway.agent.system_prompt import build_system_prompt
from gateway.agent.session_state import get_session_history


class Agent:
    def __init__(self, agent_type='chat'):
        # agent_type: 'chat', 'audit', or 'reports'
        # Each has its own system prompt and tool subset
        self.agent_type = agent_type
        self.client = anthropic.AsyncAnthropic()
        self.max_turns = 5  # Max tool-use iterations
    
    async def handle(self, message, user, adapter, session_id, 
                    language='en'):
        """
        Main entry point. Single loop. Pure agent behavior.
        """
        # Build context
        history = get_session_history(session_id, last_n=5)
        system_prompt = build_system_prompt(
            agent_type=self.agent_type,
            user=user,
            language=language,
        )
        tools = get_all_tools(agent_type=self.agent_type, user=user)
        
        # Build messages
        messages = [
            *history,
            {"role": "user", "content": message},
        ]
        
        # Tool-use loop
        for turn in range(self.max_turns):
            response = await self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
            
            # If Claude returned final text — done
            if response.stop_reason == "end_turn":
                return self._format_response(response)
            
            # If Claude called tools — execute and continue
            if response.stop_reason == "tool_use":
                messages.append({
                    "role": "assistant", 
                    "content": response.content
                })
                
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    
                    try:
                        result = await execute_tool(
                            tool_name=block.name,
                            tool_input=block.input,
                            adapter=adapter,
                            user=user,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })
                    except Exception as e:
                        # CRITICAL: errors go back to Claude as 
                        # tool_result, not to user as crash
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": self._format_error(e),
                            "is_error": True,
                        })
                
                messages.append({
                    "role": "user",
                    "content": tool_results,
                })
                continue
        
        # Hit max turns — return what we have
        return self._format_response(response)
    
    def _format_response(self, response):
        """Extract text + ui_blocks + suggestions from response."""
        text = ""
        ui_blocks = []
        suggestions = []
        visualization = None
        
        for block in response.content:
            if hasattr(block, 'text'):
                text += block.text
            elif hasattr(block, 'type') and block.type == 'tool_use':
                # Special "tool" calls for UI behavior
                if block.name == 'show_ui_block':
                    ui_blocks.append(block.input)
                elif block.name == 'add_suggestions':
                    suggestions.extend(block.input['suggestions'])
                elif block.name == 'render_visualization':
                    visualization = block.input
        
        return {
            "text": text,
            "ui_blocks": ui_blocks,
            "suggestions": suggestions,
            "visualization": visualization,
        }
    
    def _format_error(self, error):
        """Format errors so Claude can reason about them."""
        error_type = type(error).__name__
        error_msg = str(error)
        
        # Parse known error patterns
        if "Invalid field" in error_msg:
            return {
                "error_type": "invalid_field",
                "message": error_msg,
                "hint": "The field doesn't exist on that model. "
                       "Try introspect_odoo_schema to see valid fields.",
            }
        if "permission" in error_msg.lower():
            return {
                "error_type": "permission_denied",
                "message": error_msg,
                "hint": "User lacks permission. Suggest alternative or explain.",
            }
        
        return {
            "error_type": error_type,
            "message": error_msg,
            "hint": "Recover gracefully — explain to user, suggest alternative.",
        }
```

## Component 2 — The System Prompt (gateway/agent/system_prompt.py)

This is THE BRAIN. Every behavior rule goes here.

```python
"""
System prompt builder. The agent's behavior is defined here.
Modify this file to change how the AI thinks.
"""

from gateway.agent.elrace_context import ELRACE_CONTEXT


def build_system_prompt(agent_type, user, language='en'):
    base = AGENT_BASE_PROMPT
    
    if agent_type == 'chat':
        agent_specific = CHAT_AGENT_RULES
    elif agent_type == 'audit':
        agent_specific = AUDIT_AGENT_RULES
    elif agent_type == 'reports':
        agent_specific = REPORTS_AGENT_RULES
    
    return f"""
{base}

{agent_specific}

{ELRACE_CONTEXT}

{USER_PERMISSIONS_RULES.format(user_role=user.role)}

{LANGUAGE_RULES.format(default_language=language)}
"""


AGENT_BASE_PROMPT = """
You are an intelligent AI assistant for the Elrace ERP system 
(an Odoo 14-based ERP for a UAE construction company).

YOUR CORE BEHAVIORS:

1. THINK BEFORE ACTING
   Before calling any tool, decide:
   - Is the query clear enough to act on?
   - If vague, ASK BACK with picker options (don't dump random data)
   - If clear, call the right tool
   - If unsure between options, ask
   
2. ASK BACK WITH PICKERS, NOT TEXT QUESTIONS
   When a query is vague, use the show_ui_block tool to ask back 
   with clickable options. Never make the user type when they 
   can click.
   
   Example: User says "need HR info"
   → DON'T dump 50 records
   → DO call show_ui_block with type=pill_select, options:
     ["Employees", "Payroll", "Attendance", "Requests", "Compliance"]
   
   Example: User says "compare projects"  
   → DO ask "which projects?" with project picker
   
   Example: User says "vehicle for adil khan" with ONE match
   → DO act directly (clear enough)
   
3. RECOVER FROM ERRORS GRACEFULLY
   When a tool returns an error:
   - NEVER show Python tracebacks or XML-RPC faults to user
   - READ the error, understand what went wrong
   - TRY a different approach (different field, different tool)
   - If can't recover, EXPLAIN in plain language with alternative
   
   Example: "Invalid field amount_total on project.project"
   → Don't show this to user
   → Call introspect_odoo_schema to see valid fields
   → Re-query with proper fields
   
4. GENERATE CONTEXTUAL SUGGESTIONS
   After every response, use add_suggestions tool to offer 2-3 
   follow-up actions that make sense FOR THIS specific response.
   
   Example: After showing a payslip
   → Suggestions about THAT employee/payslip:
     "Show deduction breakdown"
     "Show previous month's payslip"
     "Show this employee's projects"
   → NOT generic suggestions like "Show payroll by department"
   
5. HANDLE LANGUAGE NATURALLY
   - Respond in the user's language (English or Arabic, any dialect)
   - Keep the same language throughout the conversation
   - Don't mix languages unless user does
   
6. PRESERVE CONTEXT ACROSS TURNS
   - Remember entities from previous turns (projects, employees)
   - "show breakdown" after a project query = breakdown of THAT project
   - "the deductions" after a payslip = deductions of THAT payslip
   - When suggestion changes scope, recognize it as a new query

7. WHEN UNSURE OF FIELDS, CHECK SCHEMA FIRST
   Before querying an unfamiliar model, call introspect_odoo_schema 
   to verify field names. Don't guess.

USE TOOLS — DON'T GUESS:
  - You have introspect_odoo_schema to verify any model's fields
  - You have query_odoo for any read query on any model
  - You have aggregate_odoo for sums/counts/averages
  - You have specialized tools for common reports
  - You have show_ui_block to ask back with pickers
  - You have add_suggestions to generate follow-ups
  - You have render_visualization to add charts/KPIs

OUTPUT FORMAT:
  - Brief, helpful text response
  - Visualization if applicable (KPI cards, charts, tables)
  - 2-3 contextual suggestions for next actions
  - Picker (ui_block) if you need to ask back
"""

CHAT_AGENT_RULES = """
CHAT AGENT MODE:
  You handle general ERP queries across all modules.
  When user query crosses multiple modules, compose answers.
  Default to clarifying picker if scope is unclear.
"""

AUDIT_AGENT_RULES = """
AUDIT AGENT MODE:
  Focus on change tracking, history, user activity.
  Use mail.message and mail.tracking.value for audit queries.
  Present results as timelines, not tables.
"""

REPORTS_AGENT_RULES = """
REPORTS AGENT MODE:
  Guide users through building reports via pickers.
  Generate PDF/Excel outputs.
  Use show_ui_block for date ranges, formats, departments.
"""


LANGUAGE_RULES = """
LANGUAGE HANDLING:
  Default language: {default_language}
  Mirror user's language. Arabic queries → Arabic responses.
  English queries → English responses.
"""


USER_PERMISSIONS_RULES = """
USER PERMISSIONS:
  Current user role: {user_role}
  Sensitive data (wages, bank accounts) - redact for non-super-admin.
  Read-only access - never call create/write/unlink.
"""
```

## Component 3 — Tools Registry (gateway/agent/tools_registry.py)

```python
"""
Single source of truth for all tools.
Add new tools here. Customize what each agent can do.
"""

from gateway.tools import universal_odoo, financial, project_expense
from gateway.agent.ui_block_tools import (
    show_ui_block_tool,
    add_suggestions_tool,
    render_visualization_tool,
)


# All available tools, organized by category
ALL_TOOLS = {
    # Universal data access (any model)
    'universal': [
        universal_odoo.QUERY_ODOO_TOOL,
        universal_odoo.AGGREGATE_ODOO_TOOL,
        universal_odoo.INTROSPECT_SCHEMA_TOOL,
    ],
    
    # Specialized financial tools  
    'financial': [
        financial.GET_FINANCIAL_REPORT_TOOL,
        financial.GET_TRIAL_BALANCE_TOOL,
        financial.GET_GENERAL_LEDGER_TOOL,
        financial.GET_PARTNER_AGEING_TOOL,
    ],
    
    # Specialized project tools
    'project': [
        project_expense.GET_PROJECT_EXPENSE_SUMMARY_TOOL,
        project_expense.GET_PROJECT_EXPENSE_BREAKDOWN_TOOL,
        project_expense.COMPARE_PROJECT_EXPENSES_TOOL,
    ],
    
    # UI interaction tools — Claude uses these to:
    # - Ask back with pickers
    # - Generate contextual suggestions
    # - Render visualizations
    'ui_interaction': [
        show_ui_block_tool,
        add_suggestions_tool,
        render_visualization_tool,
    ],
}


def get_all_tools(agent_type, user):
    """Return tools available for this agent and this user."""
    tools = []
    
    if agent_type == 'chat':
        tools.extend(ALL_TOOLS['universal'])
        tools.extend(ALL_TOOLS['financial'])
        tools.extend(ALL_TOOLS['project'])
        tools.extend(ALL_TOOLS['ui_interaction'])
    elif agent_type == 'audit':
        tools.extend(ALL_TOOLS['universal'])
        # Add audit-specific tools
        tools.extend(ALL_TOOLS['ui_interaction'])
    elif agent_type == 'reports':
        tools.extend(ALL_TOOLS['universal'])
        tools.extend(ALL_TOOLS['financial'])
        tools.extend(ALL_TOOLS['project'])
        # Add report-specific tools
        tools.extend(ALL_TOOLS['ui_interaction'])
    
    # Filter by user permissions
    if user.role < 100:  # Not super admin
        tools = [t for t in tools if not t.get('super_admin_only')]
    
    return tools


async def execute_tool(tool_name, tool_input, adapter, user):
    """Execute a tool by name. Centralized dispatch."""
    from gateway.tools.universal_odoo import (
        execute_query_odoo,
        execute_aggregate_odoo,
        execute_introspect_schema,
    )
    # ... import all tool implementations ...
    
    # UI tools just return their input — frontend handles them
    if tool_name in ('show_ui_block', 'add_suggestions', 'render_visualization'):
        return {"status": "ui_directive", "data": tool_input}
    
    # Real data tools
    dispatch = {
        'query_odoo': execute_query_odoo,
        'aggregate_odoo': execute_aggregate_odoo,
        'introspect_odoo_schema': execute_introspect_schema,
        # ... all other tools ...
    }
    
    if tool_name not in dispatch:
        raise ValueError(f"Unknown tool: {tool_name}")
    
    return await dispatch[tool_name](
        tool_input=tool_input,
        adapter=adapter,
        user=user,
    )
```

## Component 4 — UI Block Tools (gateway/agent/ui_block_tools.py)

Claude uses these to ask back with pickers and generate suggestions.

```python
"""
UI interaction tools. Claude uses these to control the frontend.
"""

show_ui_block_tool = {
    "name": "show_ui_block",
    "description": (
        "Show an interactive UI element to the user. "
        "Use when you need to ask the user a question and want them "
        "to click rather than type. ALWAYS prefer this over text "
        "questions when there are predictable options."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": [
                    "pill_select",      # 2-6 buttons
                    "multi_check",       # checkbox list
                    "date_picker",       # date range
                    "date_quick",        # this month/last month etc
                    "search_picker",     # search + scrollable list
                    "format_select",     # PDF/Excel/Both
                    "toggle",            # yes/no
                    "text_input",        # only when truly open
                ],
            },
            "label": {"type": "string", "description": "Question to ask"},
            "options": {
                "type": "array",
                "description": "Options for pill_select, multi_check",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "label": {"type": "string"},
                        "icon": {"type": "string"},
                    },
                },
            },
            "allow_typed_input": {
                "type": "boolean",
                "description": "Allow user to also type instead of pick",
                "default": True,
            },
        },
        "required": ["type", "label"],
    },
}


add_suggestions_tool = {
    "name": "add_suggestions",
    "description": (
        "Add 2-3 contextual follow-up suggestions to the response. "
        "These appear as clickable chips. MUST be relevant to "
        "what was just discussed — don't add generic suggestions."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "suggestions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "query": {
                            "type": "string", 
                            "description": "The query to run when clicked"
                        },
                    },
                },
                "minItems": 1,
                "maxItems": 3,
            },
        },
        "required": ["suggestions"],
    },
}


render_visualization_tool = {
    "name": "render_visualization",
    "description": (
        "Render a visualization (KPI card, chart, table) alongside the text. "
        "Use when data is better shown visually than as text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "enum": ["kpi_card", "bar_chart", "line_chart", 
                        "pie_chart", "table", "timeline"],
            },
            "data": {"type": "object"},
            "title": {"type": "string"},
        },
        "required": ["type", "data"],
    },
}
```

## Component 5 — Session State (gateway/agent/session_state.py)

```python
"""
Lightweight conversation state. Just history, no overcomplication.
"""

# In-memory for v1. Can move to Redis/Postgres later.
_sessions = {}


def get_session_history(session_id, last_n=5):
    """Get last N turns of conversation."""
    history = _sessions.get(session_id, [])
    return history[-last_n*2:]  # *2 because user + assistant per turn


def add_to_session(session_id, role, content):
    """Append a turn to session history."""
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": role, "content": content})


def clear_session(session_id):
    """Wipe session history."""
    _sessions.pop(session_id, None)
```

---

# PART IV — MIGRATION STRATEGY

## The Critical Risk

```
RISK: Replacing the pipeline breaks existing working queries.
MITIGATION: Run NEW agent and OLD pipeline in PARALLEL initially.
            Compare outputs. Switch over only when confidence is high.
```

## The 7-Day Migration Plan

```
DAY 1 (MONDAY): Build the new agent in isolation
  - Create gateway/agent/ folder with all 5 components
  - Wire to a NEW endpoint /agent/stream
  - Old /chat/stream untouched
  - Test the new endpoint with 10 queries directly

DAY 2 (TUESDAY): Add ui_block + suggestions support to frontend
  - Frontend handles new response format
  - Renders ui_blocks (pickers, pills)
  - Renders contextual suggestions
  - Tests with the new /agent/stream endpoint

DAY 3 (WEDNESDAY): Migrate Audit Agent first
  - Audit agent is simpler, lower risk
  - Replace audit handler with new agent core (audit_type)
  - Verify all audit queries still work
  - This proves the architecture

DAY 4 (THURSDAY): Migrate Reports Agent  
  - Replace reports handler with new agent core (reports_type)
  - Verify report generation still works
  - This proves multi-agent support

DAY 5 (FRIDAY): Migrate Chat Agent (the big one)
  - Replace /chat/stream with new agent core (chat_type)
  - Verify all 30 demo queries still work
  - This is the critical milestone

DAY 6 (SATURDAY): Polish + Customization Points
  - Verify all 7 customization files exist and are easy to edit
  - Document each customization point
  - Add example "how to add a new tool"
  - Add example "how to add a new ui_block type"

DAY 7 (SUNDAY): Full Regression Testing
  - Run ALL test queries (demo script + edge cases)
  - Run cross-module flagships
  - Run Arabic queries
  - Run audit queries
  - Run report queries
  - 90%+ pass rate required
```

---

# PART V — THE 7 CUSTOMIZATION POINTS

Where you can modify behavior easily after the rebuild:

### Customization 1: How the AI thinks
```
File: gateway/agent/system_prompt.py
Edit: AGENT_BASE_PROMPT, CHAT_AGENT_RULES, etc.
Effect: Changes core behavior across all queries
Example: "Always show top 5 by default, not top 10"
```

### Customization 2: What the AI knows
```
File: gateway/agent/elrace_context.py
Edit: Add business rules, model relationships, common queries
Effect: AI better understands Elrace-specific patterns
Example: "When user says 'maintenance', it usually means 
         project.project category=maintenance"
```

### Customization 3: What tools are available
```
File: gateway/agent/tools_registry.py
Edit: Add new tool definitions, restrict by user/agent
Effect: New capabilities OR new permission rules
Example: "Add a 'list_invoices' specialized tool"
```

### Customization 4: How AI asks back
```
File: gateway/agent/ui_block_tools.py
Edit: Add new ui_block types
Effect: New interaction patterns
Example: "Add 'project_picker' as a special ui_block type"
```

### Customization 5: How suggestions are made
```
File: gateway/agent/system_prompt.py (suggestion rules section)
Edit: Examples of good/bad suggestions
Effect: More contextual follow-ups
Example: "After showing a project, suggest comparing with similar"
```

### Customization 6: How errors recover
```
File: gateway/agent/core.py (_format_error method)
Edit: Add new error patterns to recognize
Effect: More graceful error handling
Example: "When OdooSecurityError, redirect to permission check"
```

### Customization 7: Per-user permissions
```
File: gateway/agent/permissions.py
Edit: Role-based tool/data access rules
Effect: Different users see different things
Example: "Top management sees aggregates but not individual wages"
```

---

# PART VI — VERIFICATION TESTS

After the rebuild, ALL of these must work correctly:

## Smart Clarification Tests (the new behavior)

```
TEST 1: "need HR info"
  EXPECTED: AI calls show_ui_block with options:
            [Employees, Payroll, Attendance, Requests, Compliance]
  NOT EXPECTED: Dump of 50 records

TEST 2: "compare projects"
  EXPECTED: AI asks "which projects?" with project picker
  NOT EXPECTED: Random comparison

TEST 3: "vehicle for adil khan"
  EXPECTED: If 1 employee match → directly show their vehicle
           If multiple matches → show picker of Adil Khans
  NOT EXPECTED: 27 random vehicles

TEST 4: "show me a report"
  EXPECTED: Show report type picker
  NOT EXPECTED: Random report
```

## Error Recovery Tests

```
TEST 5: "compare top 5 projects by expense"
  EXPECTED: AI tries query, gets field error, recovers, 
            tries the proper tool, shows top 5
  NOT EXPECTED: Python traceback

TEST 6: Query that hits Odoo timeout
  EXPECTED: AI says "took too long, let me try a different way"
            and tries an alternative
  NOT EXPECTED: 500 error to user
```

## Contextual Suggestions Tests

```
TEST 7: After showing Jawad's payslip:
  EXPECTED: Suggestions about JAWAD or HIS payslip:
            - "Show Jawad's deductions breakdown"
            - "Show Jawad's last 3 months payslips"
            - "Show Jawad's project allocation"
  NOT EXPECTED: Generic suggestions like "Payroll by department"

TEST 8: After showing P&L:
  EXPECTED: Suggestions about THIS P&L:
            - "Compare with last quarter"
            - "Drill into expense categories"
            - "Show monthly trend"
  NOT EXPECTED: Random suggestions
```

## Context Preservation Tests

```
TEST 9: "Villa 34 expense" then "show breakdown"
  EXPECTED: Breakdown of Villa 34 directly
  NOT EXPECTED: Asks "which project"

TEST 10: "Jawad payslip" then "show deductions"
  EXPECTED: Deductions of Jawad's payslip
  NOT EXPECTED: Asks "which payslip"
```

## Regression Tests (must still work)

```
TEST 11-20: All 10 queries from the demo script
  All must continue to work as before or better
```

---

# PART VII — WHAT WE KEEP FROM CURRENT SYSTEM

Important — we are NOT throwing away everything. We keep:

```
✓ All existing tools (universal_odoo, financial, project, audit)
✓ Adapter with cached uid (Odoo XML-RPC)
✓ All Odoo integration logic
✓ Database/admin panel structure
✓ Frontend UI components (just update response handler)
✓ Audit agent capabilities
✓ Reports agent capabilities  
✓ Visualization rendering
✓ Authentication
✓ Permissions/RBAC

We replace:
✗ IntentAnalyzer (gateway/core/intent_analyzer.py)
✗ StrategyPlanner (gateway/core/strategy_planner.py)
✗ Routing rules in intelligent_handler.py
✗ EntityGate forced confirmation logic
✗ QualityGate retry logic
✗ Rigid response synthesizer
```

---

# PART VIII — POST-REBUILD ROADMAP

After this rebuild succeeds (Week 1), continue with the master plan:

```
WEEK 2: Launchpad (P2 from master plan)
  - Built on TOP of new agent
  - Pickers now work natively (Claude generates them)

WEEK 3-5: Module breadth (P3)
  - Each module is just system prompt context updates
  - No code changes needed for new query patterns

WEEK 5-6: Reports breadth (P4)
  - Reports agent already has the new architecture
  - Adding templates is just config

WEEK 7-8: Production hardening (P5)

... continues per master plan
```

The rebuild makes EVERYTHING that comes after faster and cleaner.

---

# PART IX — WHY THIS WILL ACTUALLY WORK

```
1. Claude IS smart enough for this.
   - Look at how I (claude.ai) handle your messages
   - I understand context, recover from misunderstandings, 
     ask back when unclear
   - The new architecture lets your Claude do the same

2. The pattern is proven.
   - Cursor, Claude Code, Anthropic's own products use this
   - It's the modern agent pattern
   - Your existing audit_agent already uses a similar loop

3. Customization is preserved.
   - 7 distinct files for 7 distinct customization concerns
   - Each one is text/config, not deep architecture changes
   - You can modify behavior without touching the agent core

4. Migration is gradual.
   - New endpoint runs parallel to old
   - Switch agents one at a time
   - Roll back any agent independently if issues
   
5. The "feel" is what you wanted.
   - Pickers for ambiguous queries
   - Contextual suggestions
   - Graceful error recovery
   - Smart clarification
   - These come naturally with this architecture
```

---

# PART X — START COMMAND

```
Send to Claude Code:

"Read POST_DEMO_MASTER_PLAN.md (Phase notes) and 
AGENT_MODE_REBUILD.md (this document) before starting.

GOAL: Rebuild the chat/audit/reports agents into a unified 
agent-mode architecture as described in AGENT_MODE_REBUILD.md.

STEP 1: Create gateway/agent/ folder with all 5 components:
  - core.py (the agent loop)
  - system_prompt.py (the brain)
  - tools_registry.py (tool definitions)
  - ui_block_tools.py (UI interaction tools)
  - session_state.py (conversation history)

STEP 2: Wire to NEW endpoint /agent/stream
  - DO NOT touch existing /chat/stream yet
  - Test the new endpoint in isolation

STEP 3: Verify with 10 test queries
  - 4 smart clarification tests
  - 2 error recovery tests
  - 2 contextual suggestion tests
  - 2 context preservation tests

SHOW ME the new architecture working before migrating 
existing agents to it.

DO NOT touch existing chat agent until I approve the new 
agent works in isolation."
```

---

# THE TRUTH

```
You said: "We integrated Claude best of all but still we are not 
          intelligently make our AI."

You are 100% right. We integrated Claude. We did not unleash Claude.

This rebuild unleashes Claude.

1 week of focused work. No new features during this. 
Just the foundational shift from "pipeline calling Claude" to 
"Claude IS the pipeline."

After this, modifying behavior is editing text files, not 
debugging pipeline stages. Adding modules is updating context, 
not building new routing. Improving smartness is improving the 
prompt, not restructuring code.

This is the rebuild that ends the "feels dumb" problem 
permanently.

Approve it. Start Monday. Ship it Sunday. Then everything 
else gets easier.
```
