-- SyharikTS generation history tables (PostgreSQL)
-- Apply once: psql -U syharikts_usr -d syharikts -f backend/migrations/002_generation_history.sql

BEGIN;

CREATE TABLE IF NOT EXISTS generation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    generated_ts_code TEXT NOT NULL,
    schema_text TEXT NOT NULL,

    main_file_name VARCHAR(512) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_generation_history_user_created_at
    ON generation_history (user_id, created_at DESC);

COMMIT;

