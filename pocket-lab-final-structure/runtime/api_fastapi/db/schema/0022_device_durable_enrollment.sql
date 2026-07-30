-- Durable device enrollment is the canonical ownership boundary for the Lite fleet.
-- Only current SQLite device rows are migrated. Validation files, workflow files,
-- command history, stale snapshots and generated artifacts are intentionally excluded.
CREATE TABLE IF NOT EXISTS device_enrollment_registry (
    device_id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT 'compute',
    enrollment_status TEXT NOT NULL DEFAULT 'enrolled',
    identity_status TEXT NOT NULL DEFAULT 'pending',
    enrolled_at TEXT NOT NULL,
    enrolled_at_epoch_ms INTEGER NOT NULL DEFAULT 0,
    last_known_state TEXT NOT NULL DEFAULT 'offline',
    last_seen_at TEXT,
    last_seen_epoch_ms INTEGER NOT NULL DEFAULT 0,
    retired_at TEXT,
    retired_at_epoch_ms INTEGER NOT NULL DEFAULT 0,
    removal_status TEXT NOT NULL DEFAULT 'active'
        CHECK(removal_status IN ('active','retired','removed')),
    removal_reason TEXT NOT NULL DEFAULT '',
    protected_server_host INTEGER NOT NULL DEFAULT 0 CHECK(protected_server_host IN (0,1)),
    canonical_identity_json TEXT NOT NULL DEFAULT '{}' CHECK(length(canonical_identity_json) <= 16384),
    last_valid_state_json TEXT NOT NULL DEFAULT '{}' CHECK(length(last_valid_state_json) <= 65536),
    registry_revision INTEGER NOT NULL DEFAULT 1 CHECK(registry_revision >= 1),
    canonical_hash TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_device_enrollment_active_order
    ON device_enrollment_registry(removal_status, protected_server_host DESC, device_name, device_id);
CREATE INDEX IF NOT EXISTS idx_device_enrollment_name
    ON device_enrollment_registry(normalized_name, removal_status, device_id);
CREATE INDEX IF NOT EXISTS idx_device_enrollment_last_seen
    ON device_enrollment_registry(removal_status, last_seen_epoch_ms, device_id);

CREATE TABLE IF NOT EXISTS device_removal_receipts (
    receipt_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    device_name TEXT NOT NULL DEFAULT '',
    removal_status TEXT NOT NULL CHECK(removal_status IN ('retired','removed')),
    reason_code TEXT NOT NULL DEFAULT 'explicit_operator_removal',
    assessment_revision TEXT NOT NULL DEFAULT '',
    awareness_revision INTEGER NOT NULL DEFAULT 0,
    requested_by TEXT NOT NULL DEFAULT 'authenticated_operator',
    created_at TEXT NOT NULL,
    created_at_epoch_ms INTEGER NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    sanitized INTEGER NOT NULL DEFAULT 1 CHECK(sanitized IN (0,1)),
    FOREIGN KEY(device_id) REFERENCES device_enrollment_registry(device_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_device_removal_receipts_device_time
    ON device_removal_receipts(device_id, created_at_epoch_ms DESC, receipt_id DESC);

-- Backfill only from the current canonical SQLite projection. Do not scan legacy
-- JSON, workflow projections, command history, validation artifacts or fixtures.
INSERT OR IGNORE INTO device_enrollment_registry(
    device_id, device_name, normalized_name, role, enrollment_status,
    identity_status, enrolled_at, enrolled_at_epoch_ms, last_known_state,
    last_seen_at, last_seen_epoch_ms, retired_at, retired_at_epoch_ms,
    removal_status, removal_reason, protected_server_host,
    canonical_identity_json, last_valid_state_json, registry_revision,
    canonical_hash, updated_at, updated_at_epoch_ms
)
SELECT
    current.device_id,
    current.device_name,
    lower(replace(replace(replace(trim(current.device_name), '-', ''), '_', ''), ' ', '')),
    current.role,
    CASE WHEN current.connection_state='removed' THEN 'retired' ELSE 'enrolled' END,
    COALESCE(NULLIF(awareness.identity_status, ''), 'pending'),
    COALESCE(NULLIF(current.last_seen_at, ''), current.updated_at),
    CASE WHEN current.last_seen_epoch_ms > 0 THEN current.last_seen_epoch_ms ELSE current.updated_at_epoch_ms END,
    CASE WHEN current.connection_state='removed' THEN 'removed' ELSE current.connection_state END,
    current.last_seen_at,
    current.last_seen_epoch_ms,
    CASE WHEN current.connection_state='removed' THEN current.updated_at ELSE NULL END,
    CASE WHEN current.connection_state='removed' THEN current.updated_at_epoch_ms ELSE 0 END,
    CASE WHEN current.connection_state='removed' THEN 'removed' ELSE 'active' END,
    CASE WHEN current.connection_state='removed' THEN 'pre_registry_explicit_removal' ELSE '' END,
    current.protected_server_host,
    '{}',
    '{}',
    1,
    '',
    current.updated_at,
    current.updated_at_epoch_ms
FROM device_current_state AS current
LEFT JOIN device_awareness_state AS awareness ON awareness.device_id=current.device_id;

-- Current rows are retained for history and last-valid state. Command, invite or
-- transient cleanup must never cascade-delete an enrolled device.
CREATE TRIGGER IF NOT EXISTS prevent_enrolled_device_current_delete
BEFORE DELETE ON device_current_state
WHEN EXISTS (
    SELECT 1 FROM device_enrollment_registry registry
    WHERE registry.device_id=OLD.device_id
)
BEGIN
    SELECT RAISE(ABORT, 'enrolled device rows must be retired explicitly');
END;

CREATE TRIGGER IF NOT EXISTS prevent_device_enrollment_delete
BEFORE DELETE ON device_enrollment_registry
BEGIN
    SELECT RAISE(ABORT, 'durable enrollment records must be retired explicitly');
END;
