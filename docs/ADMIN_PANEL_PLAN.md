# ADMIN PANEL & USER MANAGEMENT PLAN

> **Goal:** Build a complete enterprise-grade admin system for the AI product with role-based access control, department isolation, feature gating, audit logging, and chat history persistence — all backed by PostgreSQL.

> **Strategic principle:** Treat this as a SaaS product. Multi-department, multi-role, with proper data isolation and audit compliance.

---

# PART I — STRATEGIC OVERVIEW

## 1. The Big Picture

```
Current State:
  ❌ No user management
  ❌ No role-based access
  ❌ In-memory chat history (lost on restart)
  ❌ No audit logs
  ❌ Single "admin" user for everyone
  ❌ All features available to all users

Target State:
  ✓ Full PostgreSQL backend
  ✓ Multi-role hierarchy (5 levels)
  ✓ Department-based data isolation
  ✓ Feature flags per role
  ✓ Persistent chat history
  ✓ Comprehensive audit trail
  ✓ Admin panel UI for management
  ✓ Self-service password reset, MFA
  ✓ Row-level security on financial data
```

## 2. Architecture at 30,000 Feet

```
┌────────────────────────────────────────────────────────────┐
│              REACT FRONTEND                                │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Chat UI     │  │ Admin Panel  │  │ User Profile   │  │
│  └──────────────┘  └──────────────┘  └────────────────┘  │
└────────────────────────┬───────────────────────────────────┘
                         │ JWT Bearer Token
                         ▼
┌────────────────────────────────────────────────────────────┐
│              FASTAPI GATEWAY                               │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Auth Middleware │ RBAC Engine │  │  Audit Logger    │  │
│  └──────────────┘  └──────────────┘  └────────────────┘  │
└─────────┬──────────────────┬─────────────────────┬─────────┘
          │                  │                     │
          ▼                  ▼                     ▼
┌──────────────────┐  ┌──────────────┐  ┌───────────────┐
│ PostgreSQL       │  │ Redis Cache  │  │ Odoo 14       │
│ - users          │  │ - sessions   │  │ - business    │
│ - roles          │  │ - rate limit │  │   data only   │
│ - chat_history   │  │              │  │               │
│ - audit_logs     │  │              │  │               │
└──────────────────┘  └──────────────┘  └───────────────┘
```

## 3. PostgreSQL Status & Setup

**Current:** Not yet connected to PostgreSQL. Need to set up.

**Setup options:**
- Local Postgres for dev (Docker container)
- Hetzner managed Postgres for production
- Shared Server 2 Postgres (when read replica is built)

```bash
# Quick local setup
docker run -d \
  --name ooa-postgres \
  -e POSTGRES_PASSWORD=devpassword \
  -e POSTGRES_DB=ooa \
  -p 5432:5432 \
  -v ooa-pg-data:/var/lib/postgresql/data \
  postgres:15

# Add to .env
OOA_DB_URL=postgresql://postgres:devpassword@localhost:5432/ooa
```

---

# PART II — DATABASE SCHEMA

## 4. Complete Schema (PostgreSQL DDL)

### 4.1 Core User Management

```sql
-- Users table
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    file_id         VARCHAR(50) UNIQUE NOT NULL,        -- Elrace File ID
    odoo_user_id    INTEGER UNIQUE,                      -- Link to Odoo res.users.id
    email           VARCHAR(255) UNIQUE,
    name            VARCHAR(255) NOT NULL,
    name_arabic     VARCHAR(255),
    avatar_url      TEXT,
    phone           VARCHAR(50),
    language        VARCHAR(10) DEFAULT 'en',            -- 'en', 'ar', 'ur'
    is_active       BOOLEAN DEFAULT TRUE,
    is_super_admin  BOOLEAN DEFAULT FALSE,               -- Bypass all checks
    last_login_at   TIMESTAMPTZ,
    last_login_ip   VARCHAR(45),
    failed_attempts INTEGER DEFAULT 0,
    locked_until    TIMESTAMPTZ,
    mfa_enabled     BOOLEAN DEFAULT FALSE,
    mfa_secret      VARCHAR(255),                        -- TOTP secret (encrypted)
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      INTEGER REFERENCES users(id),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ                          -- Soft delete
);

CREATE INDEX idx_users_file_id ON users(file_id) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_users_active ON users(is_active) WHERE deleted_at IS NULL;
```

### 4.2 Roles & Permissions

```sql
-- Role definitions
CREATE TABLE roles (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) UNIQUE NOT NULL,         -- 'super_admin', 'top_mgmt', etc.
    display_name    VARCHAR(100) NOT NULL,
    display_name_ar VARCHAR(100),
    description     TEXT,
    level           INTEGER NOT NULL,                    -- Higher = more access
    is_system       BOOLEAN DEFAULT FALSE,               -- System roles cannot be deleted
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Seed standard roles
INSERT INTO roles (name, display_name, level, is_system) VALUES
    ('super_admin',    'Super Administrator',  100, TRUE),
    ('admin',          'Administrator',        80,  TRUE),
    ('top_management', 'Top Management',       70,  TRUE),
    ('manager',        'Department Manager',   50,  TRUE),
    ('user',           'Standard User',        30,  TRUE),
    ('auditor',        'Read-Only Auditor',    20,  TRUE),
    ('guest',          'Guest',                10,  TRUE);

-- Granular permissions
CREATE TABLE permissions (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(100) UNIQUE NOT NULL,        -- e.g., 'reports.pandl.view'
    category        VARCHAR(50) NOT NULL,                -- 'reports', 'admin', 'features'
    display_name    VARCHAR(200) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Seed standard permissions
INSERT INTO permissions (code, category, display_name) VALUES
    -- Reports
    ('reports.pandl.view',          'reports', 'View Profit & Loss'),
    ('reports.balance_sheet.view',  'reports', 'View Balance Sheet'),
    ('reports.cash_flow.view',      'reports', 'View Cash Flow'),
    ('reports.trial_balance.view',  'reports', 'View Trial Balance'),
    ('reports.general_ledger.view', 'reports', 'View General Ledger'),
    ('reports.partner_ageing.view', 'reports', 'View Partner Ageing'),
    ('reports.project_costs.view',  'reports', 'View Project Costs'),
    ('reports.drill_down',          'reports', 'Drill into Transactions'),

    -- Features
    ('features.voice_input',        'features', 'Use Voice Input'),
    ('features.voice_output',       'features', 'Hear Voice Responses'),
    ('features.pdf_generation',     'features', 'Generate PDF Reports'),
    ('features.export_excel',       'features', 'Export to Excel'),
    ('features.share_reports',      'features', 'Share Reports Externally'),
    ('features.advanced_queries',   'features', 'Run Advanced Queries'),

    -- Data access
    ('data.all_projects',           'data',    'View All Projects'),
    ('data.own_department_only',    'data',    'View Own Department Data'),
    ('data.financial_full',         'data',    'View Full Financial Data'),
    ('data.financial_summary',      'data',    'View Financial Summary Only'),
    ('data.customer_info',          'data',    'View Customer Details'),
    ('data.vendor_info',            'data',    'View Vendor Details'),
    ('data.salaries',               'data',    'View Salary Information'),

    -- AI capabilities
    ('ai.query_unlimited',          'ai',      'Unlimited AI Queries'),
    ('ai.query_50_per_day',         'ai',      'Up to 50 Queries Per Day'),
    ('ai.query_20_per_day',         'ai',      'Up to 20 Queries Per Day'),
    ('ai.write_operations',         'ai',      'Create/Modify Records'),

    -- Admin
    ('admin.users.view',            'admin',   'View Users'),
    ('admin.users.create',          'admin',   'Create Users'),
    ('admin.users.edit',            'admin',   'Edit Users'),
    ('admin.users.delete',          'admin',   'Delete Users'),
    ('admin.roles.manage',          'admin',   'Manage Roles'),
    ('admin.audit_logs.view',       'admin',   'View Audit Logs'),
    ('admin.settings.manage',       'admin',   'Manage Settings'),
    ('admin.feature_flags.manage',  'admin',   'Manage Feature Flags');

-- Role-Permission mapping
CREATE TABLE role_permissions (
    id              SERIAL PRIMARY KEY,
    role_id         INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    permission_id   INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
    granted_at      TIMESTAMPTZ DEFAULT NOW(),
    granted_by      INTEGER REFERENCES users(id),
    UNIQUE(role_id, permission_id)
);

-- User-Role mapping (users can have multiple roles)
CREATE TABLE user_roles (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    role_id         INTEGER REFERENCES roles(id) ON DELETE CASCADE,
    granted_at      TIMESTAMPTZ DEFAULT NOW(),
    granted_by      INTEGER REFERENCES users(id),
    expires_at      TIMESTAMPTZ,                          -- Temporary roles
    UNIQUE(user_id, role_id)
);

CREATE INDEX idx_user_roles_user ON user_roles(user_id);
CREATE INDEX idx_role_permissions_role ON role_permissions(role_id);
```

### 4.3 Departments

```sql
CREATE TABLE departments (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(20) UNIQUE NOT NULL,         -- 'FIN', 'PM', 'HR', etc.
    name            VARCHAR(100) NOT NULL,
    name_arabic     VARCHAR(100),
    parent_id       INTEGER REFERENCES departments(id),  -- Hierarchy support
    manager_id      INTEGER REFERENCES users(id),
    description     TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Seed standard departments
INSERT INTO departments (code, name, name_arabic) VALUES
    ('FIN',  'Finance & Accounting',     'المالية والمحاسبة'),
    ('PM',   'Project Management',       'إدارة المشاريع'),
    ('PROC', 'Procurement',              'المشتريات'),
    ('HR',   'Human Resources',          'الموارد البشرية'),
    ('SAL',  'Sales',                    'المبيعات'),
    ('OPS',  'Operations',               'العمليات'),
    ('IT',   'Information Technology',   'تقنية المعلومات'),
    ('EXEC', 'Executive Office',         'المكتب التنفيذي');

-- User-Department mapping (users can be in multiple departments)
CREATE TABLE user_departments (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    department_id   INTEGER REFERENCES departments(id) ON DELETE CASCADE,
    is_primary      BOOLEAN DEFAULT FALSE,               -- Primary department
    UNIQUE(user_id, department_id)
);

CREATE INDEX idx_user_departments_user ON user_departments(user_id);
```

### 4.4 Sessions & Authentication

```sql
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_hash      VARCHAR(255) NOT NULL,               -- Hashed JWT
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

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE INDEX idx_sessions_token ON sessions(token_hash);
CREATE INDEX idx_sessions_active ON sessions(user_id, revoked_at) WHERE revoked_at IS NULL;
```

### 4.5 Chat History

```sql
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title           VARCHAR(255),                        -- Auto-generated or user-set
    title_arabic    VARCHAR(255),
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    last_message_at TIMESTAMPTZ DEFAULT NOW(),
    message_count   INTEGER DEFAULT 0,
    is_pinned       BOOLEAN DEFAULT FALSE,
    is_archived     BOOLEAN DEFAULT FALSE,
    tags            TEXT[],                              -- For categorization
    metadata        JSONB                                -- Flexible storage
);

CREATE INDEX idx_conversations_user ON conversations(user_id, last_message_at DESC);
CREATE INDEX idx_conversations_pinned ON conversations(user_id, is_pinned)
    WHERE is_pinned = TRUE;

CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    user_id         INTEGER REFERENCES users(id),
    role            VARCHAR(20) NOT NULL,                -- 'user', 'assistant', 'tool'
    content         TEXT NOT NULL,
    language        VARCHAR(10),                          -- 'en', 'ar'
    tool_calls      JSONB,                               -- Tools invoked
    visualization   JSONB,                               -- Visualization payload
    suggestions     TEXT[],                              -- Follow-up suggestions
    tokens_used     INTEGER,                             -- For cost tracking
    cost_cents      INTEGER,                             -- Cost in cents
    response_time_ms INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at);
CREATE INDEX idx_messages_user ON messages(user_id, created_at DESC);
```

### 4.6 Feature Flags

```sql
CREATE TABLE feature_flags (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(100) UNIQUE NOT NULL,        -- 'voice_arabic_premium'
    name            VARCHAR(200) NOT NULL,
    description     TEXT,
    is_enabled      BOOLEAN DEFAULT TRUE,                -- Global toggle
    rollout_percent INTEGER DEFAULT 100,                 -- Gradual rollout
    enabled_roles   INTEGER[],                           -- Specific roles
    enabled_users   INTEGER[],                           -- Specific users
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Examples
INSERT INTO feature_flags (code, name) VALUES
    ('voice_arabic_premium',  'Premium Arabic Voice'),
    ('pdf_themes_dark',       'Dark Theme PDF Reports'),
    ('ai_write_operations',   'AI Write Operations'),
    ('experimental_v1_2',     'V1.2 UI Experimental'),
    ('voice_streaming',       'Streaming Voice Output');
```

### 4.7 Audit Logs

```sql
CREATE TABLE audit_logs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    session_id      UUID,
    event_type      VARCHAR(50) NOT NULL,                -- 'login', 'query', 'admin_action'
    event_action    VARCHAR(100) NOT NULL,               -- 'user.created', 'role.assigned'
    resource_type   VARCHAR(50),                          -- 'user', 'role', 'conversation'
    resource_id     VARCHAR(100),
    changes         JSONB,                               -- Before/after values
    ip_address      VARCHAR(45),
    user_agent      TEXT,
    status          VARCHAR(20),                          -- 'success', 'failure'
    error_message   TEXT,
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_user ON audit_logs(user_id, created_at DESC);
CREATE INDEX idx_audit_event ON audit_logs(event_type, created_at DESC);
CREATE INDEX idx_audit_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at DESC);

-- Auto-rotate: keep only last 90 days in main table
-- Older records move to audit_logs_archive
CREATE TABLE audit_logs_archive (LIKE audit_logs INCLUDING ALL);
```

### 4.8 Usage Tracking

```sql
CREATE TABLE usage_stats (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    date            DATE NOT NULL,
    queries_count   INTEGER DEFAULT 0,
    tokens_used     INTEGER DEFAULT 0,
    cost_cents      INTEGER DEFAULT 0,
    pdfs_generated  INTEGER DEFAULT 0,
    voice_minutes   NUMERIC(10,2) DEFAULT 0,
    UNIQUE(user_id, date)
);

CREATE INDEX idx_usage_user_date ON usage_stats(user_id, date DESC);
```

---

# PART III — ROLE HIERARCHY

## 5. The 6-Tier Role System

```
LEVEL 100 — Super Administrator
  ✦ Full system access
  ✦ Manage all users, roles, departments
  ✦ View all data including financials
  ✦ Manage feature flags
  ✦ Access audit logs
  ✦ Bypass all permission checks
  Example: CTO, Lead Developer

LEVEL 80 — Administrator
  ✦ Manage users in their organization
  ✦ Configure department settings
  ✦ View audit logs for their dept
  ✦ Cannot delete super admins
  Example: HR Manager, IT Admin

LEVEL 70 — Top Management
  ✦ View ALL financial reports
  ✦ View ALL projects
  ✦ Generate executive PDFs
  ✦ Unlimited AI queries
  ✦ Cannot modify users/permissions
  Example: CEO, CFO, COO, Board Members

LEVEL 50 — Department Manager
  ✦ View ALL data within own department
  ✦ View limited cross-department data
  ✦ Generate department PDFs
  ✦ 50 queries/day
  ✦ Can drill into transactions
  Example: Finance Manager, Project Manager

LEVEL 30 — Standard User
  ✦ View summary data for their department
  ✦ Limited financial details
  ✦ 20 queries/day
  ✦ Can ask questions, view dashboards
  Example: Accountant, Project Coordinator

LEVEL 20 — Read-Only Auditor
  ✦ View specific reports (assigned)
  ✦ Cannot drill into transactions
  ✦ Cannot generate PDFs
  ✦ Cannot use voice
  Example: External Auditor, Compliance Officer

LEVEL 10 — Guest
  ✦ Demo access only
  ✦ Limited queries (5/day)
  ✦ Sample data only
  Example: Trial user, prospect demo
```

## 6. Role-Permission Matrix

```
                                Super  Admin  TopMgt Manager User  Auditor Guest
                                Admin
─────────────────────────────────────────────────────────────────────────────
P&L View                          ✓     ✓      ✓      ✓       ✓      ✓      −
Balance Sheet                     ✓     ✓      ✓      ✓       ✓      ✓      −
Cash Flow                         ✓     ✓      ✓      ✓       ✓      ✓      −
Trial Balance                     ✓     ✓      ✓      ✓       −      ✓      −
General Ledger Drill              ✓     ✓      ✓      ✓       −      −      −
View All Projects                 ✓     ✓      ✓      −       −      −      −
Own Dept Projects                 ✓     ✓      ✓      ✓       ✓      ✓      −
Customer Details                  ✓     ✓      ✓      ✓       ✓      ✓      −
Vendor Details                    ✓     ✓      ✓      ✓       −      −      −
View Salaries                     ✓     −      ✓      ✓(HR)   −      −      −
PDF Generation                    ✓     ✓      ✓      ✓       ✓      −      −
Voice Input                       ✓     ✓      ✓      ✓       ✓      −      −
Export Excel                      ✓     ✓      ✓      ✓       ✓      −      −
Write Operations                  ✓     −      −      −       −      −      −
Manage Users                      ✓     ✓      −      −       −      −      −
Manage Roles                      ✓     −      −      −       −      −      −
View Audit Logs                   ✓     ✓      −      −       −      −      −
Daily Query Limit               ∞     ∞      ∞     50      20     20     5
─────────────────────────────────────────────────────────────────────────────
```

---

# PART IV — AUTHENTICATION & AUTHORIZATION

## 7. JWT-Based Authentication

### 7.1 Login Flow

```python
# gateway/auth.py

from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
import hashlib

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.environ["JWT_SECRET"]  # Strong random key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8
REFRESH_TOKEN_EXPIRE_DAYS = 30


@app.post("/auth/login")
async def login(request: LoginRequest):
    """
    Login flow:
    1. Validate File ID against Odoo
    2. Check user exists in our DB
    3. Auto-provision if needed
    4. Generate JWT
    5. Create session record
    6. Return token + user info
    """
    # 1. Validate Elrace File ID format
    if not re.match(r'^ELR-\d{4}-\d{3,}$', request.file_id):
        raise HTTPException(400, "Invalid File ID format")

    # 2. Verify against Odoo
    user_data = await verify_with_odoo(request.file_id)
    if not user_data:
        await log_failed_attempt(request.file_id, request.client_ip)
        raise HTTPException(401, "File ID not found")

    # 3. Get or create user in our DB
    user = await get_or_create_user(user_data)

    # 4. Check if active
    if not user.is_active:
        raise HTTPException(403, "Account is disabled")

    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(403, f"Account locked until {user.locked_until}")

    # 5. Generate tokens
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    # 6. Create session
    session = await create_session(user, request, access_token)

    # 7. Audit log
    await audit_log(
        user_id=user.id,
        event_type="auth",
        event_action="user.login",
        ip=request.client_ip,
        status="success",
    )

    # 8. Update last login
    await update_last_login(user.id, request.client_ip)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        "user": {
            "id": user.id,
            "name": user.name,
            "name_arabic": user.name_arabic,
            "language": user.language,
            "roles": [r.name for r in user.roles],
            "permissions": await get_user_permissions(user.id),
            "departments": [d.code for d in user.departments],
            "feature_flags": await get_user_feature_flags(user.id),
        },
    }


def create_access_token(user) -> str:
    payload = {
        "sub": str(user.id),
        "fid": user.file_id,
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
        "type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


async def verify_with_odoo(file_id: str):
    """
    Verify File ID against Odoo's res.users.
    Returns user data if found.
    """
    adapter = get_adapter()
    users = await asyncio.to_thread(
        adapter.search_read,
        "res.users",
        [["login", "=", file_id]],
        ["id", "name", "email", "active"],
    )
    if users and users[0]["active"]:
        return users[0]
    return None
```

### 7.2 Auth Middleware

```python
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Extract and validate user from JWT token.
    Used as dependency in all protected endpoints.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        user_id = int(payload["sub"])
    except JWTError:
        raise HTTPException(401, "Invalid token")

    # Check session is still active
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    session = await db.fetch_one(
        "SELECT * FROM sessions WHERE token_hash = $1 AND revoked_at IS NULL",
        token_hash,
    )
    if not session:
        raise HTTPException(401, "Session expired or revoked")

    # Update last activity
    await db.execute(
        "UPDATE sessions SET last_activity = NOW() WHERE id = $1",
        session["id"],
    )

    # Load user
    user = await get_user_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(403, "User not active")

    return user
```

### 7.3 Permission Checks

```python
def require_permission(permission_code: str):
    """
    Decorator to enforce permission on endpoints.

    Usage:
        @app.post("/admin/users")
        async def create_user(
            user: User = Depends(get_current_user),
            _: None = Depends(require_permission("admin.users.create"))
        ):
            ...
    """
    async def check(user: User = Depends(get_current_user)):
        if user.is_super_admin:
            return  # Bypass

        permissions = await get_user_permissions(user.id)
        if permission_code not in permissions:
            await audit_log(
                user_id=user.id,
                event_type="security",
                event_action="permission.denied",
                metadata={"permission": permission_code},
                status="failure",
            )
            raise HTTPException(
                403,
                f"Missing permission: {permission_code}"
            )
    return check


def require_role(role_name: str):
    """Decorator to enforce role."""
    async def check(user: User = Depends(get_current_user)):
        roles = [r.name for r in user.roles]
        if role_name not in roles and not user.is_super_admin:
            raise HTTPException(403, f"Requires role: {role_name}")
    return check
```

### 7.4 Data Isolation

```python
def apply_department_filter(query_params: dict, user: User) -> dict:
    """
    Inject department filter based on user permissions.

    - Super admin: no filter
    - Top management: no filter
    - Manager+: filter by their department's projects
    - User: filter by their department only
    """
    permissions = user.permissions

    if "data.all_projects" in permissions:
        return query_params  # Full access

    if "data.own_department_only" in permissions:
        dept_ids = [d.id for d in user.departments]
        # Add filter to limit data
        if "filters" not in query_params:
            query_params["filters"] = []
        query_params["filters"].append(
            ["department_id", "in", dept_ids]
        )

    return query_params


# Usage in chat endpoint:
@app.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user: User = Depends(get_current_user),
):
    # Inject user context into AI prompt
    user_context = build_user_context(user)
    # ... existing logic
```

---

# PART V — ADMIN PANEL UI

## 8. Pages & Routes

```
/admin                                  Dashboard (overview, recent activity)
/admin/users                            User list, search, filters
/admin/users/new                        Create user form
/admin/users/:id                        User detail / edit
/admin/users/:id/permissions            User permissions matrix
/admin/users/:id/sessions               Active sessions, force logout
/admin/users/:id/audit                  User's audit trail

/admin/roles                            Role list
/admin/roles/new                        Create custom role
/admin/roles/:id                        Edit role, assign permissions

/admin/departments                      Department list
/admin/departments/new                  Create department
/admin/departments/:id                  Edit department, assign users

/admin/permissions                      Permission catalog (read-only)

/admin/feature-flags                    Feature flag management
/admin/feature-flags/:id                Toggle, gradual rollout

/admin/audit-logs                       Audit log viewer
/admin/audit-logs/:id                   Detail view

/admin/sessions                         All active sessions
/admin/usage                            Usage statistics, costs

/admin/settings                         System settings
/admin/settings/api-keys                API key management
/admin/settings/integrations            Odoo, OpenAI, ElevenLabs configs

/profile                                User's own profile
/profile/sessions                       Manage own sessions
/profile/security                       Password, MFA settings
/profile/chat-history                   Own conversations
```

## 9. Admin Dashboard Wireframe

```
┌──────────────────────────────────────────────────────────────────┐
│ ELRACE AI ADMIN                              [Profile] [Logout]  │
├──────────┬───────────────────────────────────────────────────────┤
│ Dashboard│                                                       │
│ Users    │  System Overview                                      │
│ Roles    │                                                       │
│ Depts    │  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │
│ Audit    │  │ Total  │ │ Active │ │ Today's│ │ Active │        │
│ Flags    │  │ Users  │ │ Users  │ │Queries │ │Sessions│        │
│ Sessions │  │  847   │ │   42   │ │ 2,341  │ │   18   │        │
│ Usage    │  └────────┘ └────────┘ └────────┘ └────────┘        │
│ Settings │                                                       │
│          │  Recent Activity                                      │
│          │  ┌─────────────────────────────────────────────┐    │
│          │  │ 10:42 ahmed.k logged in                    │    │
│          │  │ 10:38 sara.m generated PDF report          │    │
│          │  │ 10:35 m.jawad updated role: Manager        │    │
│          │  │ 10:30 ali.h failed login attempt           │    │
│          │  │ ...                                         │    │
│          │  └─────────────────────────────────────────────┘    │
│          │                                                       │
│          │  Cost This Month                  Usage by Department│
│          │  ┌────────────────┐               ┌────────────────┐│
│          │  │ AED 4,234      │               │ [Pie chart]    ││
│          │  │ ↗ +12% vs last │               │                ││
│          │  └────────────────┘               └────────────────┘│
└──────────┴───────────────────────────────────────────────────────┘
```

## 10. User Management Page

```
┌──────────────────────────────────────────────────────────────────┐
│ Users (847)                              [+ Add User] [Export]   │
├──────────────────────────────────────────────────────────────────┤
│ Search: [_______________]   Role: [All ▼]  Dept: [All ▼]         │
│                                              Status: [Active ▼]   │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ □ Name              Role       Dept    Status   Last Login       │
│ ─────────────────────────────────────────────────────────────────│
│ □ Ahmed Al-Maktoum  Manager    Finance Active   2 min ago        │
│ □ Sara Mohammed     User       PM      Active   1 hour ago       │
│ □ M Jawad           Admin      IT      Active   Today            │
│ □ Ali Hassan        User       Sales   Locked   3 days ago       │
│ ...                                                              │
│                                                                  │
│                                              Page 1 of 17 [▶]    │
└──────────────────────────────────────────────────────────────────┘
```

## 11. User Detail / Edit Page

```
┌──────────────────────────────────────────────────────────────────┐
│ Ahmed Al-Maktoum                          [Save] [Cancel]        │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Basic Info                          Status                       │
│ ─────────────────────────           ─────────────────────────    │
│ File ID:  ELR-2024-042              Active:     [✓] Enabled     │
│ Email:    ahmed@elrace.com          Locked:     [ ] Locked       │
│ Phone:    +971-50-XXXXXXX           MFA:        [✓] Enabled     │
│ Language: English ▼                 Last Login: May 14, 10:42    │
│                                                                  │
│ Roles                               Departments                  │
│ ─────────────────────────           ─────────────────────────    │
│ [✓] Manager                         [✓] Finance (Primary)        │
│ [ ] Admin                           [ ] HR                       │
│ [ ] Top Management                  [ ] Procurement              │
│                                                                  │
│ Permissions (Effective)                                          │
│ ─────────────────────────────────────────────────────────────    │
│ ✓ View P&L Reports                                              │
│ ✓ Generate PDF Reports                                          │
│ ✓ View Customer Details                                         │
│ ✗ View Salary Information                                       │
│ ...                                                              │
│                                                                  │
│ Custom Permissions (Override)                                    │
│ ─────────────────────────────────────────────────────────────    │
│ + Grant: data.salaries (until [date]___)                        │
│ + Deny:  features.share_reports                                 │
│                                                                  │
│ [View Audit Log]  [View Sessions]  [Reset Password]              │
└──────────────────────────────────────────────────────────────────┘
```

## 12. Audit Log Viewer

```
┌──────────────────────────────────────────────────────────────────┐
│ Audit Logs                                  [Export] [Filters]   │
├──────────────────────────────────────────────────────────────────┤
│ User: [All ▼]  Event: [All ▼]  Date: [Last 7 days ▼]            │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│ Time     User        Event              Resource    Status       │
│ ─────────────────────────────────────────────────────────────────│
│ 10:42:35 ahmed.k    user.login         self         ✓ success    │
│ 10:41:02 sara.m     query.executed     P&L report   ✓ success    │
│ 10:38:15 ahmed.k    pdf.generated      Apr Report   ✓ success    │
│ 10:35:00 m.jawad    role.assigned      user:42      ✓ success    │
│ 10:32:18 unknown    user.login_failed  ELR-XXX      ✗ failure    │
│ 10:30:45 sara.m     permission.denied  data.salary  ✗ failure    │
│                                                                  │
│                                            [Load More]            │
└──────────────────────────────────────────────────────────────────┘
```

---

# PART VI — API ENDPOINTS

## 13. Complete API Specification

### 13.1 Authentication

```
POST   /auth/login                  Login with File ID
POST   /auth/logout                 Logout (revoke session)
POST   /auth/refresh                Refresh access token
POST   /auth/mfa/setup              Setup MFA
POST   /auth/mfa/verify             Verify MFA code
POST   /auth/password/reset/request Request password reset
POST   /auth/password/reset         Reset password
GET    /auth/me                     Current user info
```

### 13.2 User Management

```
GET    /admin/users                 List users (paginated, filterable)
POST   /admin/users                 Create user
GET    /admin/users/:id             Get user details
PATCH  /admin/users/:id             Update user
DELETE /admin/users/:id             Soft delete user
POST   /admin/users/:id/activate    Activate user
POST   /admin/users/:id/deactivate  Deactivate user
POST   /admin/users/:id/unlock      Unlock account
POST   /admin/users/:id/reset_mfa   Reset MFA
GET    /admin/users/:id/sessions    User's sessions
DELETE /admin/users/:id/sessions    Revoke all user sessions
GET    /admin/users/:id/audit       User's audit trail
```

### 13.3 Roles & Permissions

```
GET    /admin/roles                 List roles
POST   /admin/roles                 Create custom role
PATCH  /admin/roles/:id             Update role
DELETE /admin/roles/:id             Delete custom role (not system)
GET    /admin/roles/:id/permissions Role's permissions
POST   /admin/roles/:id/permissions Add permission to role
DELETE /admin/roles/:id/permissions/:permId  Remove permission

GET    /admin/permissions           List all permissions

POST   /admin/users/:id/roles       Assign role to user
DELETE /admin/users/:id/roles/:roleId  Remove role from user

POST   /admin/users/:id/permissions Grant permission directly
DELETE /admin/users/:id/permissions/:permId  Revoke direct permission
```

### 13.4 Departments

```
GET    /admin/departments           List departments
POST   /admin/departments           Create department
PATCH  /admin/departments/:id       Update department
DELETE /admin/departments/:id       Delete department
GET    /admin/departments/:id/users Users in department
POST   /admin/departments/:id/users Add user to department
```

### 13.5 Feature Flags

```
GET    /admin/feature-flags         List all flags
POST   /admin/feature-flags         Create flag
PATCH  /admin/feature-flags/:id     Update flag
DELETE /admin/feature-flags/:id     Delete flag
POST   /admin/feature-flags/:id/enable_for_role/:roleId
POST   /admin/feature-flags/:id/enable_for_user/:userId
```

### 13.6 Audit Logs

```
GET    /admin/audit                 List audit events (filterable)
GET    /admin/audit/:id             Detail view
GET    /admin/audit/export          Export to CSV
```

### 13.7 Usage & Analytics

```
GET    /admin/usage                 System usage stats
GET    /admin/usage/by-user         Per-user usage
GET    /admin/usage/by-department   Per-department usage
GET    /admin/usage/costs           Cost breakdown
```

### 13.8 User Profile (Self-Service)

```
GET    /profile                     Own profile
PATCH  /profile                     Update own profile
POST   /profile/avatar              Upload avatar
GET    /profile/sessions            Own sessions
DELETE /profile/sessions/:id        Revoke own session
GET    /profile/audit               Own audit trail
GET    /profile/conversations       Own chat history
POST   /profile/mfa/setup           Setup own MFA
DELETE /profile/mfa                 Disable own MFA
```

---

# PART VII — IMPLEMENTATION PLAN

## 14. Build Order (10 Weeks)

### Phase 1 — Foundation (Week 1-2)
```
[ ] Set up PostgreSQL (local + production)
[ ] Run schema migration scripts
[ ] Create database access layer (asyncpg + SQLAlchemy)
[ ] Seed initial roles, permissions, departments
[ ] Create super admin user
```

### Phase 2 — Authentication (Week 3)
```
[ ] Build /auth/login with File ID + Odoo verification
[ ] JWT token generation
[ ] Session management
[ ] Auth middleware for all endpoints
[ ] Auto-provisioning logic
[ ] Login audit logging
```

### Phase 3 — RBAC Engine (Week 4)
```
[ ] Permission checking decorators
[ ] Role assignment APIs
[ ] User permission queries
[ ] Department filtering for data
[ ] Test permission scenarios
```

### Phase 4 — Chat History (Week 5)
```
[ ] Move ConversationStore from memory to Postgres
[ ] Implement conversation creation/retrieval
[ ] Message persistence with metadata
[ ] User-specific history isolation
[ ] Search/filter conversations
```

### Phase 5 — Admin Panel Backend (Week 6)
```
[ ] User management CRUD APIs
[ ] Role management APIs
[ ] Department management APIs
[ ] Permission assignment APIs
[ ] Feature flag APIs
```

### Phase 6 — Admin Panel UI (Week 7-8)
```
[ ] Set up admin route in React
[ ] Build user list page with filters
[ ] User detail/edit page
[ ] Role management page
[ ] Department page
[ ] Audit log viewer
[ ] Feature flag toggles
```

### Phase 7 — Audit & Usage (Week 9)
```
[ ] Comprehensive audit logging
[ ] Usage tracking per user
[ ] Cost calculation
[ ] Usage dashboard
[ ] Daily/monthly reports
```

### Phase 8 — Security Hardening (Week 10)
```
[ ] Rate limiting per user/role
[ ] MFA implementation (TOTP)
[ ] Session timeout policies
[ ] Failed login lockout
[ ] Password reset flow
[ ] Security audit
```

---

# PART VIII — SECURITY CONSIDERATIONS

## 15. Critical Security Practices

### 15.1 Password & Token Storage
```
✓ Bcrypt for any passwords (cost factor 12)
✓ JWT secrets in environment variables, never in code
✓ Token hashes stored, not plaintext tokens
✓ MFA secrets encrypted at rest (Fernet)
```

### 15.2 SQL Injection Prevention
```
✓ All queries parameterized (asyncpg/SQLAlchemy)
✓ Never concatenate user input into SQL
✓ Validate field names against allowlist for dynamic queries
```

### 15.3 Rate Limiting
```
By role:
  super_admin:    unlimited
  admin:          200 req/min
  top_management: 150 req/min
  manager:        100 req/min
  user:           60 req/min
  auditor:        30 req/min
  guest:          10 req/min

By endpoint:
  /auth/login:    5 attempts/15min per IP
  /chat/stream:   per-role limits
  /admin/*:       60 req/min
```

### 15.4 Audit Everything
```
Auto-audit these events:
- All logins (success + failure)
- Permission changes
- Role assignments
- User creation/deletion
- Failed authentication
- Permission denied events
- Data exports
- PDF generations
- Configuration changes
```

### 15.5 Data Privacy
```
✓ Soft delete users (preserve audit history)
✓ GDPR-style data export endpoint
✓ Data deletion on request (anonymize, don't hard-delete)
✓ Conversation isolation per user
✓ Department-level data filtering enforced server-side
```

---

# PART IX — QUALITY ASSURANCE

## 16. Test Coverage Requirements

### 16.1 Unit Tests
```
- Permission check logic (all combinations)
- Role hierarchy validation
- JWT generation/validation
- Password hashing
- MFA flow
```

### 16.2 Integration Tests
```
- Login flow end-to-end
- Permission enforcement on each endpoint
- Department data isolation
- Audit logging completeness
- Session lifecycle
```

### 16.3 Security Tests
```
- SQL injection attempts (should fail safely)
- JWT tampering
- Expired token handling
- Privilege escalation attempts
- CSRF protection
- Rate limit enforcement
```

### 16.4 Load Tests
```
- 1000 concurrent users
- 10,000 audit log writes/min
- Permission check latency < 50ms
- Database connection pooling
```

---

# PART X — DEPLOYMENT CHECKLIST

## 17. Production Readiness

```
DATABASE:
[ ] PostgreSQL 15+ on production server
[ ] Connection pooling (PgBouncer)
[ ] Daily automated backups
[ ] Point-in-time recovery configured
[ ] Read replica for analytics (future)

SECRETS:
[ ] JWT_SECRET in production .env (256-bit random)
[ ] MFA encryption key separate from JWT
[ ] Database credentials rotated quarterly
[ ] API keys for Odoo/OpenAI/ElevenLabs secured

NETWORK:
[ ] HTTPS only (no HTTP fallback)
[ ] Strong TLS (1.2+, modern ciphers)
[ ] Firewall: only 443 + SSH exposed
[ ] PostgreSQL accessible only from app servers

MONITORING:
[ ] Sentry for error tracking
[ ] Prometheus metrics export
[ ] Grafana dashboards
[ ] Alert on: failed logins spike, 5xx errors, permission denials
[ ] Daily audit log summary email to admins

COMPLIANCE:
[ ] Privacy policy documented
[ ] Terms of service signed by users
[ ] Data retention policy (90 days audit logs)
[ ] Right to be forgotten endpoint
```

---

# PART XI — TELL CURSOR

```
Start Phase 1 from ADMIN_PANEL_PLAN.md.

Step 1: Set up PostgreSQL locally via Docker
Step 2: Create migration scripts for all tables in PART II
Step 3: Build database access layer using asyncpg
Step 4: Seed roles, permissions, departments
Step 5: Create initial super admin user
Step 6: Verify with a simple SELECT query

Reference PROJECT_CONTEXT.md for code patterns.
After Phase 1 works, move to Phase 2 (Authentication).

Critical: Use parameterized queries everywhere. Never concatenate user input.
```

---

# PART XII — FUTURE ENHANCEMENTS

```
v2 Features:
- SSO integration (Microsoft, Google)
- SCIM provisioning
- Multi-tenant support (other Odoo clients)
- Role templates per industry
- Approval workflows (e.g., budget overrides)
- API rate limit tiers (paid plans)
- White-label admin panel
- Custom roles per organization
```

---

## Summary

This plan gives you:
- ✦ Complete PostgreSQL schema (10 tables)
- ✦ 6-tier role hierarchy with full permission matrix
- ✦ Department-based data isolation
- ✦ JWT authentication with sessions
- ✦ Granular permissions (40+ defined)
- ✦ Feature flags for gradual rollout
- ✦ Comprehensive audit logging
- ✦ Admin panel UI specs
- ✦ All API endpoints documented
- ✦ Security best practices baked in
- ✦ 10-week build plan
- ✦ Test coverage requirements
- ✦ Production deployment checklist

This is enterprise-grade. Build it and you have a real SaaS-ready product.
