-- Add cache fingerprints for generation reuse.
BEGIN;

ALTER TABLE generation_history
    ADD COLUMN IF NOT EXISTS input_fingerprint VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS generator_fingerprint VARCHAR(64) NULL,
    ADD COLUMN IF NOT EXISTS cache_hit BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS cache_source_generation_id UUID NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_generation_history_cache_source'
    ) THEN
        ALTER TABLE generation_history
            ADD CONSTRAINT fk_generation_history_cache_source
            FOREIGN KEY (cache_source_generation_id)
            REFERENCES generation_history (id)
            ON DELETE SET NULL;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS ix_generation_history_cache_lookup
    ON generation_history (input_fingerprint, generator_fingerprint, created_at DESC);

COMMIT;
