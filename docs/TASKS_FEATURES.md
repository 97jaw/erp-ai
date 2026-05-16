# TASKS — Feature Development

> Feature, UI, AI, and visualization tasks. For infra/server tasks see `TASKS_ARCHITECTURE.md`.

---

## Status Legend

```
✅ DONE       — Complete and tested in production
🔄 IN PROGRESS — Currently being worked on
📋 TODO       — Planned, not started
🐛 BUG        — Known issue to fix
💡 IDEA       — Future consideration
```

---

## ✅ COMPLETED FEATURES

### Core AI Agent
- [x] Claude Sonnet 4 agent with native function calling
- [x] Multi-turn conversation with context retention
- [x] English + Arabic full support
- [x] Streaming SSE responses
- [x] Project ambiguity handling with clarification flow
- [x] Contextual follow-up suggestions

### Odoo Integration
- [x] Custom AI gateway methods on `project.financial.service`
- [x] `get_project_expense_dashboard` — budget tracking
- [x] `get_project_financial_data` — project P&L
- [x] `get_ai_financial_report` — P&L, Balance Sheet, Cash Flow
- [x] `get_ai_general_ledger` — account transactions
- [x] `get_ai_trial_balance` — account summary
- [x] `get_ai_partner_ageing` — receivables/payables
- [x] `get_ai_partner_ledger` — partner transactions
- [x] Generic `search_odoo` for any model

### Voice Pipeline
- [x] OpenAI Whisper STT (Arabic + English)
- [x] ElevenLabs `eleven_multilingual_v2` TTS
- [x] `/voice` endpoint — audio in, audio out
- [x] Markdown stripping for TTS output

### Frontend (React)
- [x] Chat interface with bubble UI
- [x] RTL/LTR auto-detection per message
- [x] Voice recording via MediaRecorder
- [x] Voice playback of TTS response
- [x] KPI Card component
- [x] Financial Report card
- [x] Data Table component
- [x] Suggestion chips (clickable)
- [x] localStorage chat persistence
- [x] Clear chat button
- [x] Typing indicator animation
- [x] Streaming text rendering

### Visualization Types Supported
- [x] `KPI_CARD` — single metric with details
- [x] `DATA_TABLE` — rows and columns
- [x] `FINANCIAL_REPORT` — P&L with 4 KPIs
- [x] `BAR_CHART` — placeholder (UI rendering pending)
- [x] `LINE_CHART` — placeholder (UI rendering pending)

---

## 🔄 IN PROGRESS

### Visualization Polish
- [ ] BAR_CHART component (Chart.js or Recharts)
- [ ] LINE_CHART component for time series
- [ ] PIVOT_TABLE for cross-tabulations
- [ ] Export visualization as PNG/PDF

---

## 📋 TODO — Priority 1 (Next Sprint)

### Write Operations
- [ ] Add `create_invoice` tool with confirmation flow
- [ ] Add `update_project_status` tool
- [ ] Add `confirm_delivery` tool
- [ ] Two-step confirmation gate before any write
- [ ] Audit log for all write operations
- [ ] Rollback capability for accidental writes

### Drill-Down for Reports
- [ ] Detail rows for P&L (level 3+) on demand
- [ ] Click on KPI Card to fetch underlying breakdown
- [ ] Click on Financial Report row to see transactions
- [ ] Account-level drill-down for General Ledger

### Enhanced Project Queries
- [ ] Multi-project comparison view
- [ ] Project portfolio dashboard
- [ ] Budget vs Actual visualization
- [ ] Project timeline / Gantt visualization
- [ ] Top expense categories per project

### Export Features
- [ ] Export current report to Excel
- [ ] Export to PDF with company branding
- [ ] Email report directly from chat
- [ ] Schedule recurring reports

---

## 📋 TODO — Priority 2 (Future Sprint)

### Conversation Improvements
- [ ] Conversation summarization (long sessions)
- [ ] Conversation search / history
- [ ] Save important conversations
- [ ] Share conversation link
- [ ] Pin important messages

### Language Support
- [ ] Full Urdu support (currently partial)
- [ ] Hindi support
- [ ] Auto-detect user preferred language from history
- [ ] Translate responses on demand

### Smart Features
- [ ] Anomaly detection ("Why are expenses up 30%?")
- [ ] Predictive alerts ("Project X will exceed budget in 2 weeks")
- [ ] Comparison with previous periods
- [ ] Trend analysis ("Show 6-month revenue trend")
- [ ] Recommendation engine ("Top 3 cost reduction opportunities")

### Voice Improvements
- [ ] Voice ID per language (Arabic-native voice)
- [ ] Adjustable speech speed
- [ ] Streaming TTS (lower latency)
- [ ] Voice commands ("create invoice for...")
- [ ] Voice authentication

### Mobile
- [ ] PWA support (installable)
- [ ] Native iOS app (React Native)
- [ ] Native Android app (React Native)
- [ ] Mobile-optimized layouts

---

## 💡 IDEAS — Backlog

### AI Capabilities
- [ ] Multimodal: upload invoice image → extract data → create entry
- [ ] OCR for paper invoices in Arabic
- [ ] Document Q&A: upload PDF contracts and query them
- [ ] Generate reports from natural language ("Create a quarterly business review")
- [ ] Chart generation from data ("Plot expenses by month")

### Integrations
- [ ] WhatsApp Business API integration
- [ ] Microsoft Teams bot
- [ ] Slack bot
- [ ] Email integration ("Send weekly report to CFO every Monday")
- [ ] Calendar integration ("Schedule review meetings")

### Collaboration
- [ ] Multi-user shared sessions
- [ ] Comments on responses
- [ ] Tag teammates
- [ ] Notifications

---

## 🐛 KNOWN BUGS

### Minor
- [ ] BAR_CHART visualization not yet rendered (data exists)
- [ ] Long Arabic text in voice may exceed ElevenLabs limit (2500 chars)
- [ ] Voice on mobile Safari sometimes fails to record
- [ ] localStorage limit (~5MB) for very long conversations

### To Investigate
- [ ] Occasional duplicate messages when streaming is slow
- [ ] Suggestion buttons sometimes show in wrong language

---

## 🎯 FEATURE METRICS TO TRACK

```
- Response latency (target: < 2s perceived, < 5s actual)
- Query success rate (target: > 95%)
- Visualization render accuracy (target: 100%)
- Language detection accuracy
- Voice transcription accuracy (Arabic + English)
- User satisfaction (suggestion click-through rate)
```

---

## 📝 NOTES FOR DEVELOPERS

When adding a new feature:

1. **Check `PROJECT_CONTEXT.md`** for patterns and constraints
2. **Add Claude tool definition** in `gateway/main.py` TOOLS list
3. **Add tool executor** in `execute_tool()`
4. **Test with live data** before declaring done
5. **Update this file** — move task from TODO to DONE
6. **Document any new patterns** in PROJECT_CONTEXT.md
7. **No breaking changes** to existing visualization payload format
