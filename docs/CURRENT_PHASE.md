# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** `docs/CONVERSATION_INTEGRITY_FIX_PLAN.md` — Conversation Integrity Fix Sprint

> **BLOCKER:** Must complete F1–F6 before `ELRACE_OMNI_AGENT_FINAL_PLAN.md` / Universal Odoo Access.

---

## 📍 ACTIVE PHASE

**Phase:** F1 — Cache Integrity
**Status:** COMPLETE (unit tests pass; live verify pending on EC2)
**Completed:** 2026-06-09

---

## ✅ F1 DELIVERABLES

| Task | Deliverable | Status |
|------|-------------|--------|
| Explicit cache key | `build_tool_cache_key()` in `gateway/tool_cache.py` | ✅ |
| User scoping | `user_id` passed from `execute_tool()` | ✅ |
| Entity TTL | `ENTITY_CACHE_TTL_SECONDS = 300` for entity-bound tools | ✅ |
| Unit tests | `tests/test_tool_cache_integrity.py` (4 tests) | ✅ |
| Live verify | Villa 48 → Al Mushrif → Hatta Hospital sequence | ⏳ deploy + manual |

**Key shape:** `{user_id}:{tool_name}:{entity_id|noid}:{hint_hash}`

**Run tests:**
```bash
pytest tests/test_tool_cache_integrity.py tests/test_backend_hardening.py -q
```

**Live verify (same session, after deploy):**
```
1. Villa No. 48 expense this year
2. Al Mushrif expense this year
3. Hatta Hospital expense this year
```
Expect 3 distinct `project_id`s; grep logs for `cached:true` only when same entity repeats.

**Deploy:**
```bash
git push origin main
# EC2:
cd /opt/ooa && git pull && ./deploy/aws/scripts/deploy-code.sh
```

---

## ⏭ NEXT PHASE

**Phase F2 — Topic-Shift Detection + EntityGate Always Runs** (see `CONVERSATION_INTEGRITY_FIX_PLAN.md` §4)

---

## 📊 SPRINT PROGRESS

```
F1 Cache integrity          ✅ (live verify pending)
F2 Topic-shift / EntityGate ⬜
F3 search_entity routing    ⬜
F4 Quality gate AED 0       ⬜
F5 Format clarification     ⬜
F6 Integration + sign-off   ⬜
```

---

## 📋 PRIOR WORK (COMPLETE)

- Phase 10 Hardening — production readiness (2026-06-07)
- Phase 9 Integration & Migration — entity gate, safe_search_read
- Villa expense pipeline + breakdown follow-up context (commits dc1d269, 4a6f363)

---

## 🎯 NORTH STAR

> Fix the five conversation-integrity bugs from the 2026-06-09 incident **before** expanding to Universal Odoo Access.
