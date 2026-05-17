-- OOA Admin Panel — seed roles, permissions, departments, feature flags

INSERT INTO roles (name, display_name, level, is_system) VALUES
    ('super_admin',    'Super Administrator',  100, TRUE),
    ('admin',          'Administrator',        80,  TRUE),
    ('top_management', 'Top Management',       70,  TRUE),
    ('manager',        'Department Manager',   50,  TRUE),
    ('user',           'Standard User',        30,  TRUE),
    ('auditor',        'Read-Only Auditor',    20,  TRUE),
    ('guest',          'Guest',                10,  TRUE)
ON CONFLICT (name) DO NOTHING;

INSERT INTO permissions (code, category, display_name) VALUES
    ('reports.pandl.view',          'reports', 'View Profit & Loss'),
    ('reports.balance_sheet.view',  'reports', 'View Balance Sheet'),
    ('reports.cash_flow.view',      'reports', 'View Cash Flow'),
    ('reports.trial_balance.view',  'reports', 'View Trial Balance'),
    ('reports.general_ledger.view', 'reports', 'View General Ledger'),
    ('reports.partner_ageing.view', 'reports', 'View Partner Ageing'),
    ('reports.project_costs.view',  'reports', 'View Project Costs'),
    ('reports.drill_down',          'reports', 'Drill into Transactions'),
    ('features.voice_input',        'features', 'Use Voice Input'),
    ('features.voice_output',       'features', 'Hear Voice Responses'),
    ('features.pdf_generation',     'features', 'Generate PDF Reports'),
    ('features.export_excel',       'features', 'Export to Excel'),
    ('features.share_reports',      'features', 'Share Reports Externally'),
    ('features.advanced_queries',   'features', 'Run Advanced Queries'),
    ('data.all_projects',           'data',    'View All Projects'),
    ('data.own_department_only',    'data',    'View Own Department Data'),
    ('data.financial_full',         'data',    'View Full Financial Data'),
    ('data.financial_summary',      'data',    'View Financial Summary Only'),
    ('data.customer_info',          'data',    'View Customer Details'),
    ('data.vendor_info',            'data',    'View Vendor Details'),
    ('data.salaries',               'data',    'View Salary Information'),
    ('ai.query_unlimited',          'ai',      'Unlimited AI Queries'),
    ('ai.query_50_per_day',         'ai',      'Up to 50 Queries Per Day'),
    ('ai.query_20_per_day',         'ai',      'Up to 20 Queries Per Day'),
    ('ai.write_operations',         'ai',      'Create/Modify Records'),
    ('admin.users.view',            'admin',   'View Users'),
    ('admin.users.create',          'admin',   'Create Users'),
    ('admin.users.edit',            'admin',   'Edit Users'),
    ('admin.users.delete',          'admin',   'Delete Users'),
    ('admin.roles.manage',          'admin',   'Manage Roles'),
    ('admin.audit_logs.view',       'admin',   'View Audit Logs'),
    ('admin.settings.manage',       'admin',   'Manage Settings'),
    ('admin.feature_flags.manage',  'admin',   'Manage Feature Flags')
ON CONFLICT (code) DO NOTHING;

INSERT INTO departments (code, name, name_arabic) VALUES
    ('FIN',  'Finance & Accounting',     'المالية والمحاسبة'),
    ('PM',   'Project Management',       'إدارة المشاريع'),
    ('PROC', 'Procurement',              'المشتريات'),
    ('HR',   'Human Resources',          'الموارد البشرية'),
    ('SAL',  'Sales',                    'المبيعات'),
    ('OPS',  'Operations',               'العمليات'),
    ('IT',   'Information Technology',   'تقنية المعلومات'),
    ('EXEC', 'Executive Office',         'المكتب التنفيذي')
ON CONFLICT (code) DO NOTHING;

INSERT INTO feature_flags (code, name) VALUES
    ('voice_arabic_premium',  'Premium Arabic Voice'),
    ('pdf_themes_dark',       'Dark Theme PDF Reports'),
    ('ai_write_operations',   'AI Write Operations'),
    ('experimental_v1_2',     'V1.2 UI Experimental'),
    ('voice_streaming',       'Streaming Voice Output')
ON CONFLICT (code) DO NOTHING;
