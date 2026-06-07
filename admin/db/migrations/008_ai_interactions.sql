-- Phase 8: AI interaction telemetry and learning patterns

CREATE TABLE IF NOT EXISTS ai_interactions (
    id                      UUID PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id              VARCHAR(512) NOT NULL DEFAULT '',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_query              TEXT NOT NULL,
    user_query_language     VARCHAR(10) NOT NULL DEFAULT 'en',
    intent                  JSONB,
    strategy                JSONB,
    tools_called            TEXT[] NOT NULL DEFAULT '{}',
    tool_durations_ms       JSONB NOT NULL DEFAULT '{}',
    orchestration_log       JSONB NOT NULL DEFAULT '[]',
    quality_review          JSONB,
    retries_needed          INTEGER NOT NULL DEFAULT 0,
    quality_passed          BOOLEAN NOT NULL DEFAULT TRUE,
    quality_pass_rate       DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    confidence              DOUBLE PRECISION,
    response_text           TEXT NOT NULL DEFAULT '',
    response_length         INTEGER NOT NULL DEFAULT 0,
    visualization_type      VARCHAR(50) NOT NULL DEFAULT 'NONE',
    suggestions_offered     TEXT[] NOT NULL DEFAULT '{}',
    failure_mode            VARCHAR(50),
    cache_hit               BOOLEAN NOT NULL DEFAULT FALSE,
    proactive_cache_keys    TEXT[] NOT NULL DEFAULT '{}',
    user_satisfaction_signal VARCHAR(20),
    suggestion_clicked      TEXT,
    next_query_within_60s   TEXT,
    chat_continued          BOOLEAN NOT NULL DEFAULT FALSE,
    tokens_input            INTEGER NOT NULL DEFAULT 0,
    tokens_output           INTEGER NOT NULL DEFAULT 0,
    cost_cents              INTEGER NOT NULL DEFAULT 0,
    total_duration_ms       INTEGER NOT NULL DEFAULT 0,
    orchestration_duration_ms INTEGER NOT NULL DEFAULT 0,
    metadata                JSONB NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_ai_interactions_user_created
    ON ai_interactions(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_interactions_session
    ON ai_interactions(session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_ai_interactions_created
    ON ai_interactions(created_at DESC);

CREATE TABLE IF NOT EXISTS user_learning_patterns (
    user_id                 INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    patterns                JSONB NOT NULL DEFAULT '{}',
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS learning_job_runs (
    id                      BIGSERIAL PRIMARY KEY,
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at             TIMESTAMPTZ,
    hours_analyzed          INTEGER NOT NULL,
    interactions_analyzed   INTEGER NOT NULL DEFAULT 0,
    status                  VARCHAR(20) NOT NULL DEFAULT 'running',
    summary                 JSONB NOT NULL DEFAULT '{}',
    error_message           TEXT
);

CREATE INDEX IF NOT EXISTS idx_learning_job_runs_started
    ON learning_job_runs(started_at DESC);
