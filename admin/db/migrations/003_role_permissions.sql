-- Role-permission matrix (PART III) — idempotent grants

-- Super admin: all permissions
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'super_admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Administrator: all except salaries + role management
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code NOT IN ('data.salaries', 'admin.roles.manage')
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Top management
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'reports.pandl.view', 'reports.balance_sheet.view', 'reports.cash_flow.view',
    'reports.trial_balance.view', 'reports.general_ledger.view', 'reports.partner_ageing.view',
    'reports.project_costs.view', 'reports.drill_down',
    'features.voice_input', 'features.voice_output', 'features.pdf_generation',
    'features.export_excel', 'features.share_reports', 'features.advanced_queries',
    'data.all_projects', 'data.financial_full', 'data.customer_info', 'data.vendor_info',
    'data.salaries', 'ai.query_unlimited',
    'admin.users.view', 'admin.audit_logs.view'
)
WHERE r.name = 'top_management'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Department manager
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'reports.pandl.view', 'reports.balance_sheet.view', 'reports.cash_flow.view',
    'reports.trial_balance.view', 'reports.general_ledger.view', 'reports.partner_ageing.view',
    'reports.project_costs.view', 'reports.drill_down',
    'features.voice_input', 'features.voice_output', 'features.pdf_generation',
    'features.export_excel', 'data.own_department_only', 'data.financial_full',
    'data.customer_info', 'data.vendor_info', 'data.salaries',
    'ai.query_50_per_day'
)
WHERE r.name = 'manager'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Standard user
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'reports.pandl.view', 'reports.balance_sheet.view', 'reports.cash_flow.view',
    'reports.partner_ageing.view', 'reports.project_costs.view',
    'features.voice_input', 'features.voice_output', 'features.pdf_generation',
    'data.own_department_only', 'data.financial_summary', 'data.customer_info',
    'ai.query_20_per_day'
)
WHERE r.name = 'user'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Auditor
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'reports.pandl.view', 'reports.balance_sheet.view', 'reports.cash_flow.view',
    'reports.trial_balance.view', 'reports.partner_ageing.view',
    'data.own_department_only', 'data.customer_info', 'ai.query_20_per_day'
)
WHERE r.name = 'auditor'
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Guest: minimal demo access
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code IN (
    'reports.pandl.view', 'data.own_department_only', 'data.financial_summary',
    'ai.query_20_per_day'
)
WHERE r.name = 'guest'
ON CONFLICT (role_id, permission_id) DO NOTHING;
