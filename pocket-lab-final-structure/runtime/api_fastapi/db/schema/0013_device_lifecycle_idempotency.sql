-- Lifecycle correctness: semantic idempotency for durable device evidence.
-- Existing rows remain valid; only newly projected semantic keys are deduplicated.
ALTER TABLE device_lifecycle_events ADD COLUMN dedupe_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS idx_device_lifecycle_events_dedupe
    ON device_lifecycle_events(dedupe_key)
    WHERE dedupe_key IS NOT NULL AND dedupe_key <> '';
