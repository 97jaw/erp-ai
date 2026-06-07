-- Phase 10: benchmark / load-test query telemetry (hardening)

CREATE TABLE IF NOT EXISTS phase10_query_telemetry (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID NOT NULL,
    run_label       VARCHAR(100) NOT NULL DEFAULT 'baseline',
    query_label     VARCHAR(120) NOT NULL,
    query_text      TEXT NOT NULL,
    duration_ms     INTEGER NOT NULL,
    cost_cents      INTEGER,
    failure_mode    VARCHAR(50),
    http_status     INTEGER,
    stream_status   VARCHAR(30) NOT NULL DEFAULT 'ok',
    interaction_id  UUID,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_phase10_query_telemetry_run
    ON phase10_query_telemetry(run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_phase10_query_telemetry_label
    ON phase10_query_telemetry(query_label, created_at DESC);
