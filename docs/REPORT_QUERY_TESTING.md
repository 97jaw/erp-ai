# Report query testing guide

Use this checklist to validate chat report behavior after gateway/UI changes.

## Automated tests (run first)

```bash
cd odoo_ai_bridge
pytest tests/test_cost_categories_visual.py \
       tests/test_backend_hardening.py \
       tests/test_quality_response.py \
       tests/quality/test_query_quality.py \
       tests/test_cost_analysis_normalize.py -q
```

## Odoo API scripts (live data)

Requires `.env` with `ODOO_V14_*` credentials:

```bash
python scripts/verify_cost_analysis_odoo_api.py
python scripts/verify_pandl_odoo_api.py
python scripts/verify_trial_balance_odoo_api.py
python scripts/verify_general_ledger_odoo_api.py
python scripts/verify_balance_sheet_odoo_api.py
python scripts/verify_partner_ageing_odoo_api.py
```

## Manual chat queries (expected behavior)

| # | Query | Tool(s) | Expected UI |
|---|--------|---------|-------------|
| 1 | Cost distribution of **National Guard** — category amounts **and chart** | `get_project_cost_categories` | Text summary + **bar chart** (LPO, Invoices, …) |
| 2 | Expense summary for National Guard | `get_project_expenses` | KPI / financial card (not category chart) |
| 3 | Top 5 projects by net profit | `get_top_projects_by_metric` | Table or bar chart |
| 4 | Revenue comparison by client | `group_and_aggregate` | Bar chart |
| 5 | Monthly revenue trend 2026 | `group_and_aggregate` / SQL | Line chart |
| 6 | Trial balance as of today | `get_trial_balance` | Data table |
| 7 | P&L for Q1 2026 | `get_financial_report` | Financial report widget |
| 8 | Company-wide cost analysis | `query_accounting` (cost_analysis) | Table (not project bar chart) |
| 9 | Generate PDF report for project X | `generate_pdf_report` | PDF card + download |
| 10 | Show LPO breakdown (follow-up) | `get_project_cost_categories` | Bar chart or table with line items |

## Pass criteria

- **Text**: No raw Odoo field syntax (`partner_id[`, `amount_total:sum`).
- **Chart**: When the query asks for graphics/chart/distribution by category, a **BAR_CHART** appears under the message.
- **Suggestions**: 3 follow-up chips (e.g. LPO breakdown, budget compare, monthly trend).
- **Session**: Follow-ups reuse `project_id` / `project_name` from scope (no re-asking project name).

## Debugging text-only responses

1. Browser devtools → Network → `chat/stream` → final `done` event: check `visualization.visual_type`.
2. Gateway logs: `[Agent]` / `[Quality]` lines; confirm `get_project_cost_categories` ran.
3. If `visual_type` is `BAR_CHART` but UI empty → rebuild `ooa-ui` (`npm run build`).
4. If `visualization` is null → wrong tool, empty categories, or polish stripped chart rows (fixed in `quality_response.py` for dict rows).

## Known limits

- In-chat charts: **BAR_CHART** and **LINE_CHART** only (no pie chart in UI yet).
- Pie charts exist in **PDF** reports only (`gateway/pdf_reports.py`).
- Voice endpoint returns text only (no visualization).
