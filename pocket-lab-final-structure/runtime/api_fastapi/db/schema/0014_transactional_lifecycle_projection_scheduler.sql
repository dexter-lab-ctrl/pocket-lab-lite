-- E1/E3/E4: SQLite-authoritative device lifecycle transactions and bounded
-- cross-domain projection scheduling state. Additive and backward compatible.
ALTER TABLE device_lifecycle_events ADD COLUMN generation_key TEXT;
ALTER TABLE device_lifecycle_events ADD COLUMN state_revision INTEGER NOT NULL DEFAULT 0;
ALTER TABLE device_lifecycle_events ADD COLUMN database_instance TEXT NOT NULL DEFAULT '';
ALTER TABLE device_lifecycle_events ADD COLUMN payload_checksum TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS device_lifecycle_transactions (
    transaction_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    dedupe_key TEXT,
    generation_key TEXT,
    state_revision INTEGER NOT NULL DEFAULT 0,
    database_instance TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'committed',
    export_status TEXT NOT NULL DEFAULT 'pending',
    export_attempts INTEGER NOT NULL DEFAULT 0,
    occurred_at TEXT NOT NULL,
    occurred_at_epoch_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    UNIQUE(event_id),
    UNIQUE(dedupe_key),
    FOREIGN KEY(device_id) REFERENCES device_current_state(device_id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES device_lifecycle_events(event_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_lifecycle_generation
    ON device_lifecycle_events(device_id, event_type, generation_key, occurred_at_epoch_ms DESC);
CREATE INDEX IF NOT EXISTS idx_device_lifecycle_transactions_device
    ON device_lifecycle_transactions(device_id, occurred_at_epoch_ms DESC, transaction_id DESC);
CREATE INDEX IF NOT EXISTS idx_device_lifecycle_transactions_export
    ON device_lifecycle_transactions(export_status, updated_at, transaction_id);

CREATE TABLE IF NOT EXISTS projection_refresh_state (
    domain TEXT PRIMARY KEY,
    generation INTEGER NOT NULL DEFAULT 0,
    committed_generation INTEGER NOT NULL DEFAULT 0,
    dirty INTEGER NOT NULL DEFAULT 0 CHECK (dirty IN (0, 1)),
    active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1)),
    priority INTEGER NOT NULL DEFAULT 50,
    work_class TEXT NOT NULL DEFAULT 'io',
    failure_count INTEGER NOT NULL DEFAULT 0,
    next_retry_epoch_ms INTEGER NOT NULL DEFAULT 0,
    coalesced_count INTEGER NOT NULL DEFAULT 0,
    late_result_count INTEGER NOT NULL DEFAULT 0,
    stale_generation_count INTEGER NOT NULL DEFAULT 0,
    last_started_at TEXT,
    last_completed_at TEXT,
    last_error_type TEXT NOT NULL DEFAULT '',
    last_pressure_reason TEXT NOT NULL DEFAULT '',
    database_instance TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_projection_refresh_ready
    ON projection_refresh_state(dirty, active, next_retry_epoch_ms, priority, domain);
