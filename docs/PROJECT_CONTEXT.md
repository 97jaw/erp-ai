# Odoo Omni-Agent (OOA) — Project Context

> **Read this file first before making ANY code changes.**
> This is a production codebase, not a prototype.

---

## 1. What This Project Is

OOA is a production AI-powered natural language interface for Odoo 14 ERP, built for **Elrace** — a Construction & Facilities Management company in UAE.

Users query their ERP system in English or Arabic via text or voice and receive intelligent responses with structured visualizations. The AI replaces complex Odoo menu navigation with natural conversation.

**This is a real business product** serving real users with real money on the line. No prototype-level code.

---

## 2. Tech Stack

### Backend
- **Python 3.11+** (Python 3.13 ready)
- **FastAPI** (async, SSE support)
- **Anthropic Claude Sonnet 4** (`claude-sonnet-4-20250514`) — agent brain with native tool use
- **OpenAI Whisper v3** — speech to text (Arabic + English regional accents)
- **ElevenLabs `eleven_multilingual_v2`** — text to speech
- **XML-RPC** — Odoo 14 communication
- **Pydantic v2** — schema validation
- **Server-Sent Events (SSE)** — response streaming

### Frontend
- **React 18** (Create React App)
- **Bilingual RTL/LTR** auto-detection
- **SSE streaming consumer**
- **MediaRecorder API** for voice input

### Infrastructure
- **Docker** — containerization
- **Ubuntu 22.04 LTS** — production target
- **PostgreSQL 14** — Odoo backend
- **Redis** — caching (planned for Server 2)
- **GitHub** — version control

### External Systems
- **Odoo 14 ERP** at `odoo.elrace.com`
- **Custom Odoo module:** `project.financial.service`
- **Accounting Reports module:** `account_dynamic_reports`
- **Financial Report module:** `account_financial_report`

---

## 3. Architecture Overview

```
User (Browser)
    │ Text or Voice
    ▼
React UI (port 3000)
    │ HTTPS / SSE
    ▼
FastAPI Gateway (port 8000)
    │
    ▼
Claude Agent (native tool use)
    │ Autonomous tool decisions
    ▼
Odoo Adapter Layer (XML-RPC)
    │ Custom AI Gateway Methods
    ▼
Odoo 14 (UAE production server)
    │
    ▼
PostgreSQL Database
```

### Target Future Architecture (In Progress)

```
                            ┌─── Read Replica PG ───┐
                            │   (AI queries only)   │
Production Odoo ────────────┤                       │
   (writes only)            └──── Redis Cache ──────┤
                                  (5 min TTL)       │
                                                    ▼
                                          FastAPI Gateway
                                                    │
                                                    ▼
                                            Claude Agent
```

---

## 4. Key Architectural Decisions

### 4.1 Claude as Brain, Not Pipeline
Replaced earlier LangGraph state machine with native Claude function calling. Claude autonomously decides which Odoo tools to invoke based on user query. **No rigid pipelines. No intent classifiers. Trust Claude.**

### 4.2 No Phrase Mapping
Removed all rigid phrase-to-intent mappings. Claude classifies intent in any language naturally. Only **format switches** (table view, bar chart) remain as preprocessor rules.

### 4.3 Custom AI Gateway Methods in Odoo
Standard Odoo TransientModel report methods return ORM recordset objects that **cannot be serialized over XML-RPC**. Solution: custom `get_ai_*` methods on `project.financial.service` that:
1. Create the wizard internally
2. Pass full UI context (journals, operating units, financial year)
3. Call the computation method
4. Extract clean data into Python dicts
5. Unlink the wizard

This pattern is **critical** and must be replicated for any new report.

### 4.4 Conversation Context via Claude
`ConversationStore` keeps full message history per session. Claude maintains context naturally — no manual sticky domain or intent inheritance logic.

### 4.5 SSE Streaming
Endpoint `/chat/stream` streams text chunks as Claude generates them. UI renders progressively for perceived speed (5s → feels instant).

### 4.6 Visualization Block Convention
Claude appends `<visualization>{...}</visualization>` JSON at the end of responses. Frontend parses this for KPI cards, charts, tables.

---

## 5. File Structure

```
odoo_ai_bridge/
├── gateway/
│   └── main.py                    # FastAPI gateway + Claude agent + tool executor
├── core/
│   ├── state.py                   # Pydantic schemas
│   ├── base_adapter.py            # Abstract adapter + KPIRequest/Response
│   ├── session_store.py           # Session persistence
│   ├── query_preprocessor.py      # Format switch detection only
│   └── nodes/                     # Legacy LangGraph nodes (kept for reference)
├── adapters/v14/
│   ├── connector.py               # OdooV14Adapter — XML-RPC client
│   └── accounting_connector.py    # Wraps AI gateway methods
├── integrations/
│   └── voice_engine.py            # WhisperSTT + ElevenLabsTTS
├── docker/
│   └── Dockerfile
├── tests/                         # Unit tests
├── docker-compose.yml
├── requirements.txt
└── .env                           # Credentials (NEVER commit)

ooa-ui/
├── src/
│   ├── App.jsx                    # React chat interface (bilingual)
│   └── index.js
├── package.json
└── public/

Odoo Module (deployed to Odoo server):
└── project.financial.service       # AbstractModel with AI gateway methods
```

---

## 6. Claude Agent Tools

```python
TOOLS = [
    "get_financial_report",       # P&L, Balance Sheet, Cash Flow
    "get_project_expenses",        # Project expense dashboard
    "get_project_financial_data",  # Project P&L with date range
    "get_general_ledger",          # Account transactions
    "get_trial_balance",           # Account-level summary
    "get_partner_ageing",          # Receivables/payables by age
    "get_partner_ledger",          # Per-partner transactions
    "get_projects_summary",        # Active projects list
    "search_odoo",                 # Generic any-model search
]
```

---

## 7. Critical Business Context

```
Company        : Elrace Cos. & Gen. Cont. CO. (ID: 1)
Region         : UAE — Abu Dhabi + Dubai
Currency       : AED
Financial Year : January to December
Languages      : English (primary), Arabic (full support)
Odoo User      : dev (uid: 4291)
Journals       : 55 active
Operating Units: Multiple — MUST include in queries for accurate numbers

Test Projects:
  Zayidia Boys School         (id: 14549, WO: RCC-AA-MOE-2025-016)
  Zayidia Girls School Al Ain (id: 14610, WO: RCC-AA-MOE-2025-018)
```

---

## 8. Critical Implementation Patterns

### Pattern 1 — Adding a New Odoo Report

```
1. Write get_ai_<report_name>() in project.financial.service
2. Pass full context: company_id, journals, operating_units, financial_year
3. Use wizard.with_context(used_context) — match UI exactly
4. Return clean Python dict (zero ORM objects)
5. Unlink wizard after use
6. Add tool definition in gateway/main.py TOOLS list
7. Add executor branch in execute_tool()
8. Test via adapter.call_method() BEFORE wiring to agent
9. Verify numbers match Odoo UI exactly
```

### Pattern 2 — TransientModel Serialization Fix

```python
# WRONG — fails with: cannot marshal <odoo.api.account.analytic.account>
wizard.get_report_values()

# RIGHT — custom AI gateway method
@api.model
def get_ai_financial_report(self, ...):
    wizard = self.env['ins.financial.report'].create({...})
    # Build full context matching UI
    used_context = {
        'date_from': date_from,
        'date_to': date_to,
        'strict_range': True,
        'company_id': self.env.company.id,
        'journal_ids': all_journals.ids,
        'operating_unit_ids': ou_ids,
        ...
    }
    report_lines, ib, cb, eb = wizard.with_context(used_context).get_account_lines(form_data)
    clean_lines = [{'name': ..., 'balance': float(...)} for l in report_lines]
    wizard.unlink()
    return {...}
```

### Pattern 3 — Project Name Resolution

```
1. project_id given → use directly
2. Otherwise search by name in English
3. Arabic input → translate via Claude (UAE proper noun aware)
4. Multiple matches → raise ProjectAmbiguousError(candidates)
5. Claude shows candidates and asks user to pick
6. Zero matches → raise ProjectNotFoundError
```

### Pattern 4 — Visualization Block

```python
# Claude appends this at end of response:
<visualization>
{
  "visual_type": "KPI_CARD|BAR_CHART|DATA_TABLE|FINANCIAL_REPORT",
  "label": "...",
  "value": 0,
  "unit": "AED",
  "data": {...},
  "suggestions": ["follow-up 1", "follow-up 2", "follow-up 3"]
}
</visualization>

# Frontend strips block from displayed text, renders viz separately
```

---

## 9. Critical Gotchas

```
1. Income accounts in Odoo store as NEGATIVE credit balances
   → Take abs() for display only

2. P&L numbers MUST include all journals + operating units
   → Or numbers differ from Odoo UI

3. project_name_arabic field has garbage data ("a", "ىى")
   → Do not rely for search

4. SYSTEM_PROMPT contains JSON braces — use .replace() NOT .format()
   → .format() interprets {visual_type} as placeholder

5. Anthropic SDK message content blocks cannot JSON.dumps()
   → Only save user TEXT and assistant TEXT to ConversationStore
   → Never save the raw response.content array

6. HTTP headers must be ASCII (X-Transcript, X-Response)
   → .encode('ascii', errors='ignore').decode('ascii')

7. Visualization block must be stripped from displayed text
   → Frontend parses <visualization>...</visualization> separately

8. TransientModel methods cannot be called directly via XML-RPC
   → Always use custom AI gateway methods on AbstractModel

9. .env values without quotes
   → ODOO_V14_DB=odoo.elrace.com (NOT 'odoo.elrace.com')

10. CORS must allow all origins for dev
    → allow_origins=["*"] in FastAPI

11. Odoo search_read() is overridden on live Elrace server
    → project.project search_read returns wrong IDs (e.g. HATTA HOSPITAL for Zayidia)
    → Entity resolution MUST use adapter.safe_search_read() = search() + read()
    → Do NOT fix the Odoo module (elrace_employee_transfer_request)
    → Entity gate always requires user confirmation before financial tools run
```

---

## 10. Environment Variables

```
ODOO_V14_URL=https://odoo.elrace.com
ODOO_V14_DB=odoo.elrace.com
ODOO_V14_USER=dev
ODOO_V14_PASSWORD=***

ANTHROPIC_API_KEY=sk-ant-***
OPENAI_API_KEY=sk-proj-***
ELEVENLABS_API_KEY=sk_***

# Future (Server 2):
PG_HOST=          # read replica
PG_PORT=5432
PG_DB=
PG_USER=ai_reader
PG_PASSWORD=

REDIS_URL=redis://localhost:6379
```

---

## 11. Running the Project

### Backend
```bash
cd odoo_ai_bridge
source venv/bin/activate
uvicorn gateway.main:app --reload --port 8000
```

### Frontend
```bash
cd ooa-ui
npm start
```

### Docker
```bash
docker build -f docker/Dockerfile -t ooa:latest .
docker run -p 8000:8000 --env-file .env ooa:latest
```

### Kill processes
```bash
# Backend
lsof -i :8000 | grep Python | awk '{print $2}' | xargs kill -9

# Frontend
lsof -i :3000 | grep node | awk '{print $2}' | xargs kill -9
```

---

## 12. Coding Standards

```
✓ Production mindset — no prototype patterns
✓ No over-engineering — minimal, elegant solutions
✓ Trust Claude — avoid manual phrase matching
✓ Type hints everywhere (Python 3.11 syntax)
✓ Pydantic v2 syntax: model_config = {...}
✓ datetime.now(UTC) not utcnow()
✓ XML-RPC requires allow_none=True
✓ Log meaningfully: logger.info("[Component] ...")
✓ Comments explain WHY not WHAT
✗ No emojis in code or logs
✓ Match Odoo UI behavior exactly for financial data
✓ Always test with live Odoo data before declaring done
```

---

## 13. How To Work With Cursor / AI On This Project

1. **State the goal, not the implementation**
   - Good: "Add caching for P&L reports"
   - Bad: "Add a Redis call here on line 42"

2. **Reference the patterns**
   - "Follow Pattern 1 to add Cash Flow report"

3. **Mention the constraints**
   - "This must work with read replica architecture"

4. **Test against real data**
   - All changes verified with live Elrace Odoo data

5. **No breaking changes without approval**
   - Especially API contract or visualization payload

6. **Read TASKS files**
   - `TASKS_FEATURES.md` for feature work
   - `TASKS_ARCHITECTURE.md` for infra/devops/architecture

---

## 14. Status Summary

```
✅ Claude agent with native tool use
✅ Odoo 14 adapter with custom gateway methods + safe_search_read()
✅ Entity gate with mandatory confirmation (Phase 9)
✅ Voice pipeline (Whisper + ElevenLabs)
✅ SSE streaming
✅ React bilingual UI
✅ Docker containerization
✅ Telemetry + learning engine (Phase 8)
✅ Phase 10 hardening — k6 load test, baseline, edge cases, logging review
✅ Live testing against Elrace production data

🔄 Server 2 infrastructure setup
📋 Read replica + Redis caching
📋 Write operations with confirmation
📋 Postgres session persistence
```

### Phase 10 Hardening

| Script | Purpose |
|--------|---------|
| `scripts/load/phase10_chat_stream.js` | k6 — 10 VUs, 5 min, mixed queries |
| `scripts/phase10_baseline.py` | Sequential baseline → `phase10_query_telemetry` |
| `scripts/phase10_acceptance.py` | Edge cases + log fabrication scan |
| `docs/PHASE_10_HARDENING_REPORT.md` | Sign-off report |

See `TASKS_FEATURES.md` and `TASKS_ARCHITECTURE.md` for active work.
