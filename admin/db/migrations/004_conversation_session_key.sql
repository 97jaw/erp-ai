-- Phase 4: map client session_id (e.g. JWT) to conversations row per user

ALTER TABLE conversations
    ADD COLUMN IF NOT EXISTS external_session_key VARCHAR(512);

CREATE UNIQUE INDEX IF NOT EXISTS idx_conversations_user_external
    ON conversations(user_id, external_session_key)
    WHERE external_session_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_conversations_title_search
    ON conversations(user_id, title)
    WHERE title IS NOT NULL;
