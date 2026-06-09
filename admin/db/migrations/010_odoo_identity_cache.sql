-- Cache Odoo identity at login to avoid redundant verify RPC calls.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS odoo_employee_id INTEGER,
    ADD COLUMN IF NOT EXISTS odoo_verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS odoo_identity_json JSONB;

CREATE INDEX IF NOT EXISTS idx_users_odoo_verified_at
    ON users (odoo_verified_at)
    WHERE deleted_at IS NULL AND odoo_verified_at IS NOT NULL;
