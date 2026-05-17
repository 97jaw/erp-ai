-- Phase 8: passwords, MFA pending, password reset tokens

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255),
    ADD COLUMN IF NOT EXISTS password_reset_token_hash VARCHAR(255),
    ADD COLUMN IF NOT EXISTS password_reset_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS mfa_pending_secret VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_users_reset_token
    ON users(password_reset_token_hash)
    WHERE password_reset_token_hash IS NOT NULL;
