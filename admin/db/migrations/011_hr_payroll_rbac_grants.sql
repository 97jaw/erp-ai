-- Phase M6 UI: grant HR/payroll Odoo module access to standard roles and bootstrap super admin.

-- HR employee directory — available to standard users and above.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code = 'odoo.hr.access'
WHERE r.name IN ('user', 'manager', 'top_management')
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Payroll — aligned with roles that already carry data.salaries.
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r
JOIN permissions p ON p.code = 'odoo.payroll.access'
WHERE r.name IN ('manager', 'top_management')
ON CONFLICT (role_id, permission_id) DO NOTHING;

-- Bootstrap architect / dev super-admin account (documented as SUPER_ADMIN_FILE_ID=2721).
UPDATE users
SET is_super_admin = TRUE,
    updated_at = NOW()
WHERE file_id = '2721'
  AND deleted_at IS NULL;

INSERT INTO user_roles (user_id, role_id)
SELECT u.id, r.id
FROM users u
JOIN roles r ON r.name = 'super_admin'
WHERE u.file_id = '2721'
  AND u.deleted_at IS NULL
ON CONFLICT (user_id, role_id) DO NOTHING;
