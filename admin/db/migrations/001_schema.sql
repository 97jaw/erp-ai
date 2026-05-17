-- OOA Admin Panel — core schema (PART II)
-- Requires PostgreSQL 15+

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 4.1 Users
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    file_id         VARCHAR(50) UNIQUE NOT NULL,
    odoo_user_id    INTEGER UNIQUE,
    email           VARCHAR(255) UNIQUE,
    name            VARCHAR(255) NOT NULL,
    name_arabic     VARCHAR(255),
    avatar_url      TEXT,
    phone           VARCHAR(50),
    language        VARCHAR(10) DEFAULT 'en',
    is_active       BOOLEAN DEFAULT TRUE,
    is_super_admin  BOOLEAN DEFAULT FALSE,
    last_login_at   TIMESTAMPTZ,
    last_login_ip   VARCHAR(45),
    failed_attempts INTEGER DEFAULT 0,
    locked_until    TIMESTAMPTZ,
    mfa_enabled     BOOLEAN DEFAULT FALSE,
    mfa_secret      VARCHAR(255),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      INTEGER REFERENCES users(id),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_users_file_id ON users(file_id) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active) WHERE deleted_at IS NULL;

-- 4.2 Roles & permissions
CREATE TABLE IF NOT EXISTS roles (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) UNIQUE NOT NULL,
    display_name    VARCHAR(100) NOT NULL,
    display_name_ar VARCHAR(100),
    description     TEXT,
    level           INTEGER NOT NULL,
    is_system       BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS permissions (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(100) UNIQUE NOT NULL,
    category        VARCHAR(50) NOT NULL,
    display_name    VARCHAR(200) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id              SERIAL PRIMARY KEY,
    role_id         INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id   INTEGER NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    granted_at      TIMESTAMPTZ DEFAULT NOW(),
    granted_by      INTEGER REFERENCES users(id),
    UNIQUE(role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         INTEGER NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    granted_at      TIMESTAMPTZ DEFAULT NOW(),
    granted_by      INTEGER REFERENCES users(id),
    expires_at      TIMESTAMPTZ,
    UNIQUE(user_id, role_id)
);

CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);

-- 4.3 Departments
CREATE TABLE IF NOT EXISTS departments (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(20) UNIQUE NOT NULL,
    name            VARCHAR(100) NOT NULL,
    name_arabic     VARCHAR(100),
    parent_id       INTEGER REFERENCES departments(id),
    manager_id      INTEGER REFERENCES users(id),
    description     TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_departments (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    department_id   INTEGER NOT NULL REFERENCES departments(id) ON DELETE CASCADE,
    is_primary      BOOLEAN DEFAULT FALSE,
    UNIQUE(user_id, department_id)
);

CREATE INDEX IF NOT EXISTS idx_user_departments_user ON user_departments(user_id);

-- 4.4 Sessions
CREATE TABLE IF NOT EXISTS sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,
    refresh_token   VARCHAR(255),
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    device_info     JSONB,
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    last_activity   TIMESTAMPTZ DEFAULT NOW(),
    revoked_at      TIMESTAMPTZ,
    revoked_reason  VARCHAR(255)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(user_id, revoked_at) WHERE revoked_at IS NULL;

-- 4.5 Chat history
CREATE TABLE IF NOT EXISTS conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255),
    title_arabic    VARCHAR(255),
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    message_count   INTEGER DEFAULT 0,
    is_pinned       BOOLEAN DEFAULT FALSE,
    is_archived     BOOLEAN DEFAULT FALSE,
    tags            TEXT[],
    metadata        JSONB
);

CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id, last_message_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_pinned ON conversations(user_id, is_pinned)
    WHERE is_pinned = TRUE;

CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id),
    role            VARCHAR(20) NOT NULL,
    content         TEXT NOT NULL,
    language        VARCHAR(10),
    tool_calls      JSONB,
    visualization   JSONB,
    suggestions     TEXT[],
    tokens_used     INTEGER,
    cost_cents      INTEGER,
    response_time_ms INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, created_at DESC);

-- 4.6 Feature flags
CREATE TABLE IF NOT EXISTS feature_flags (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(100) UNIQUE NOT NULL,
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    is_enabled      BOOLEAN DEFAULT TRUE,
    rollout_percent INTEGER DEFAULT 100,
    enabled_roles   INTEGER[],
    enabled_users   INTEGER[],
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 4.7 Audit logs
CREATE TABLE IF NOT EXISTS audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    session_id      UUID,
    event_type      VARCHAR(50) NOT NULL,
    event_action    VARCHAR(100) NOT NULL,
    resource_type   VARCHAR(50),
    resource_id     VARCHAR(100),
    changes         JSONB,
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    status          VARCHAR(20),
    error_message   TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_logs(event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at DESC);

CREATE TABLE IF NOT EXISTS audit_logs_archive (LIKE audit_logs INCLUDING ALL);

-- 4.8 Usage tracking
CREATE TABLE IF NOT EXISTS usage_stats (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    date            DATE NOT NULL,
    queries_count   INTEGER DEFAULT 0,
    tokens_used     INTEGER DEFAULT 0,
    cost_cents      INTEGER DEFAULT 0,
    pdfs_generated  INTEGER DEFAULT 0,
    voice_minutes   NUMERIC(10,2) DEFAULT 0,
    UNIQUE(user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_usage_user_date ON usage_stats(user_id, date DESC);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version         VARCHAR(255) PRIMARY KEY,
    applied_at      TIMESTAMPTZ DEFAULT NOW()
);
