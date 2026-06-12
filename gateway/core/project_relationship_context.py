"""Project relational model context for Claude system prompt (Phase R2).

Static relationship graph — no runtime tool changes. Claude composes
query_odoo / aggregate_odoo using this map.
"""

PROJECT_RELATIONSHIP_PROMPT_SECTION = """
=== PROJECT RELATIONAL MODEL ===

project.project is linked to these models:

  project.project.agreement_id → agreement
    The agreement (contract) is the MASTER entity. When user
    says "contract" or "agreement", they mean the agreement model.
    Fields: code (AG number), name, partner_id (client), amount,
    start_date, end_date, state, operating_unit_id, project_code,
    duration, duration_days, stage_id
    agreement_id on project.project links project to its agreement.

  project.attachment → linked via project_id
    Project documents. Fields: project_id, name,
    lead_attachment_type (estimation/wo/invoice/other),
    x_folder_id, x_client_project_attach, x_client_agreement_attach
    Use to check: "does this project have WO docs uploaded?"

  agreement.attachment → linked via agreement_id
    Contract documents. Fields: agreement_id, name,
    attachment_type, file_type (pdf/image), x_folder_id,
    start_date_agreement, end_date_agreement, agreement_name

  res.partner → the client/vendor/supplier/subcontractor
    Distinguish by:
      customer_rank > 0 → customer / client
      supplier_rank > 0 → vendor / supplier
      is_company=True + supplier_rank > 0 → may be subcontractor
    project.project.partner_id = the client
    agreement.partner_id = the contracting client

COMMON RELATIONSHIP QUERIES:

  "projects with no attachments"
    → Step 1: aggregate project.attachment by project_id to get
      projects WITH attachments
    → Step 2: query project.project where id NOT IN those ids

  "agreement for project X"
    → query project.project for agreement_id
    → query agreement by that id

  "all projects for [client]"
    → resolve client name to res.partner id
    → query project.project where partner_id = that id

  "subcontractors on project X"
    → check agreement fields or purchase.order linked to project

  "projects missing WO documents"
    → find projects WITHOUT project.attachment of type 'wo'

  "agreements expiring this month"
    → query agreement where end_date in current month range

=== MULTI-STEP QUERY COMPOSITION ===

For relationship queries, compose multiple tool calls. Do NOT answer in one vague search.

PATTERN 1: "projects with no [thing]"
  Step 1: aggregate_odoo("project.attachment", [], ["project_id"], ["id:count"])
  Step 2: extract project_ids from step 1
  Step 3: query_odoo("project.project",
             [["id","not in", ids], ["active","=",true]],
             ["id","name","partner_id"], limit=50)
  Step 4: narrate the list

PATTERN 2: "agreement/contract for [project]"
  Step 1: query_odoo("project.project", [["name","ilike", name]],
             ["id","name","agreement_id","partner_id"])
  Step 2: query_odoo("agreement", [["id","=", agreement_id]],
             ["code","name","partner_id","amount","start_date","end_date","state"])
  Step 3: narrate agreement details

PATTERN 3: "all projects for [client]"
  Step 1: query_odoo("res.partner",
             [["name","ilike", client], ["customer_rank",">",0]],
             ["id","name"], limit=5)
  Step 2: query_odoo("project.project",
             [["partner_id","=", partner_id], ["active","=",true]],
             ["id","name","agreement_id"], limit=50)

PATTERN 4: "attachments for [project]"
  Step 1: resolve project_id
  Step 2: query_odoo("project.attachment", [["project_id","=", project_id]],
             ["name","lead_attachment_type","create_date"])

PATTERN 5: "[entity] details for [project]" (client, agreement, etc.)
  Step 1: read linking field from project.project
  Step 2: query related model
  Step 3: narrate

CRITICAL: When a query needs 2+ models, ALWAYS use multiple tool calls.
Each step's result feeds the next step's domain filter.

=== END RELATIONSHIP CONTEXT ===
"""
