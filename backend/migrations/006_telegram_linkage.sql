-- Add Telegram linkage fields and one-time link codes.
BEGIN;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS telegram_username VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS telegram_first_name VARCHAR(255) NULL,
    ADD COLUMN IF NOT EXISTS telegram_linked_at TIMESTAMPTZ NULL;

CREATE UNIQUE INDEX IF NOT EXISTS ux_users_telegram_chat_id
    ON users (telegram_chat_id)
    WHERE telegram_chat_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS telegram_link_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    code_hash VARCHAR(128) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    consumed_at TIMESTAMPTZ NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_telegram_link_codes_user_created
    ON telegram_link_codes (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_telegram_link_codes_expires_at
    ON telegram_link_codes (expires_at);

COMMIT;
