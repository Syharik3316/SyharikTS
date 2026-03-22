-- SyharikTS auth tables (PostgreSQL)
-- Apply once: bash scripts/run_migrations.sh
-- Or: psql -U syharikts_usr -d syharikts -f backend/migrations/001_auth_tables.sql
--
-- Уникальность email/login без учёта регистра — через UNIQUE INDEX на lower(...),
-- совместимо с PostgreSQL < 15 (в CREATE TABLE выражения в UNIQUE — только с PG15+).

BEGIN;

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) NOT NULL,
    login VARCHAR(64) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    is_email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS users_email_lower ON users (lower(email));
CREATE UNIQUE INDEX IF NOT EXISTS users_login_lower ON users (lower(login));

CREATE TABLE IF NOT EXISTS email_verification_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    code_hash VARCHAR(128) NOT NULL,
    purpose VARCHAR(32) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT email_verification_codes_purpose_check CHECK (
        purpose IN ('registration', 'password_reset')
    )
);

CREATE INDEX IF NOT EXISTS idx_email_codes_user_purpose ON email_verification_codes (user_id, purpose);
CREATE INDEX IF NOT EXISTS idx_email_codes_expires ON email_verification_codes (expires_at);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    token_hash VARCHAR(128) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens (user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens (expires_at);

COMMIT;
