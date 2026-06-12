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

=== END RELATIONSHIP CONTEXT ===
"""
