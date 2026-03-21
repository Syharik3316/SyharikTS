-- Persist raw upload (base64) for client-side TS check from history (optional, size-capped in app).
BEGIN;

ALTER TABLE generation_history
    ADD COLUMN IF NOT EXISTS input_file_base64 TEXT NULL;

COMMIT;
