# Parking Lot — Conversation Integrity Sprint

Items deferred or requiring manual follow-up after F1–F6 code complete.

## Live verification (manual)

Automated integration tests replay the 2026-06-09 incident with mocks. **EC2 live verify is still required** before treating the sprint as production-signed-off:

- Run `python scripts/verify_conversation_integrity_sprint.py` locally (automated tests)
- Deploy to `/opt/ooa`, then execute the 5-query sequence in one browser session
- Cache spot-check: Villa 48 → Al Mushrif → Hatta Hospital (distinct `project_id`, grep logs for stale `cached:true`)

## Known edge cases

| Area | Behavior | Notes |
|------|----------|-------|
| `search_entity` + named entities | Entity gate may clarify before `search_entities` tool runs | Acceptable — user still sees candidates, not wrong expense data |
| Vague date queries | `should_offer_date_clarification()` may still offer period choice | F5 only strips **format** clarifications from intent analyzer |
| Single confident entity match | Entity gate may auto-confirm without candidate list | By design for unambiguous names |
| Zero spend, non-zero W.O | Passes `not_all_zero` | Legitimate “not started” scenario |
| Agent loop (legacy `main.py` path) | Uses `execute_tool` thread path for `search_entities` | Intelligent handler path is primary; minimal context in standalone tool call |
| `partner` entity search | `search_entities` tool returns unsupported for non-project types | F3 scope was project search only |

## Not in scope (deliberate)

- Full WorkingMemory refactor
- Cache layer redesign beyond key scoping
- EntityResolver rewrite
- Visualize agent changes

## After sign-off

Proceed to `ELRACE_OMNI_AGENT_FINAL_PLAN.md` (Universal Odoo Access) on this foundation.
