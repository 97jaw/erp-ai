-- Ensure Odoo permissions exist (safe if 006 already ran) and grant admin + super_admin.

INSERT INTO permissions (code, category, display_name) VALUES
    ('odoo.full_access',        'odoo', 'Full access to all Odoo modules'),
    ('odoo.projects.access',    'odoo', 'Projects, tasks & project planning'),
    ('odoo.timesheets.access',  'odoo', 'Timesheets & time entries'),
    ('odoo.hr.access',          'odoo', 'Human resources (employees, contracts, leave)'),
    ('odoo.payroll.access',     'odoo', 'Payroll, payslips & salary data'),
    ('odoo.accounting.access',  'odoo', 'Accounting, invoices & journal entries'),
    ('odoo.procurement.access', 'odoo', 'Purchase orders & procurement'),
    ('odoo.sales.access',       'odoo', 'Sales orders & quotations'),
    ('odoo.inventory.access',   'odoo', 'Inventory, stock & warehouses'),
    ('odoo.crm.access',         'odoo', 'CRM leads, opportunities & partners'),
    ('odoo.manufacturing.access','odoo', 'Manufacturing & work orders'),
    ('odoo.maintenance.access', 'odoo', 'Maintenance requests & equipment')
ON CONFLICT (code) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
CROSS JOIN permissions p
WHERE r.name = 'super_admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;

INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON (
    p.category = 'odoo'
    OR p.code = 'admin.roles.manage'
)
WHERE r.name = 'admin'
ON CONFLICT (role_id, permission_id) DO NOTHING;
