# CURRENT PHASE

> **Purpose:** This file tracks exactly what we are working on RIGHT NOW. Update it as you progress. Cursor reads this FIRST every session to know where to pick up.

---

## 🎯 ACTIVE PLAN

**File:** `docs/CONVERSATION_INTEGRITY_FIX_PLAN.md` — Conversation Integrity Fix Sprint

**Status:** CODE COMPLETE — live verify on EC2 pending

---

## 📍 SPRINT SIGN-OFF

| Phase | Description | Code | Automated tests | Live verify |
|-------|-------------|------|-----------------|-------------|
| F1 | Cache integrity | ✅ | ✅ | ⏳ |
| F2 | Topic-shift + EntityGate | ✅ | ✅ | ⏳ |
| F3 | search_entity routing | ✅ | ✅ | ⏳ |
| F4 | Zero-data quality gate | ✅ | ✅ | ⏳ |
| F5 | Format clarification suppress | ✅ | ✅ | ⏳ |
| F6 | Integration replay + sign-off | ✅ | ✅ | ⏳ |

**Run full sprint test suite:**
```bash
python scripts/verify_conversation_integrity_sprint.py
# or:
pytest tests/integration/test_conversation_integrity_sprint.py \
  tests/test_tool_cache_integrity.py tests/core/test_topic_shift.py \
  tests/core/test_search_entity_routing.py tests/core/test_quality_gate.py \
  tests/core/test_clarification_validation.py -q
```

**Live verify (same session, after deploy):**
```
1. Villa Maintenance No. 48 expense for this year
2. General maintenance work need expense report
3. now General maintenance work
4. give General maintenance work need expense report
5. General maintenance work - Al Mushrif need expense report
```
Plus cache spot-check: Villa 48 → Al Mushrif → Hatta Hospital (3 distinct `project_id`s).

**Deploy:**
```bash
git push origin main
# EC2:
cd /opt/ooa && git pull && ./deploy/aws/scripts/deploy-code.sh
```

**Edge cases / deferred items:** `docs/PARKING_LOT.md`

---

## ⏭ NEXT

**Unblocked after live verify:** `ELRACE_OMNI_AGENT_FINAL_PLAN.md` — Universal Odoo Access (4 tools on this foundation)

---

## 🎯 NORTH STAR

> Fix the five conversation-integrity bugs from the 2026-06-09 incident **before** expanding to Universal Odoo Access.
