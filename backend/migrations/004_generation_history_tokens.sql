-- Persist token usage per generation request for user-level analytics.
BEGIN;

ALTER TABLE generation_history
    ADD COLUMN IF NOT EXISTS prompt_tokens INTEGER NULL,
    ADD COLUMN IF NOT EXISTS completion_tokens INTEGER NULL,
    ADD COLUMN IF NOT EXISTS total_tokens INTEGER NULL;

COMMIT;
