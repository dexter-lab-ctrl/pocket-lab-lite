-- Phase D2/D3: bounded trust, lifecycle, capability, dependency, and removal awareness.
-- Raw heartbeat payloads, identity hashes, invite tokens, command bodies, and private paths are excluded.
CREATE TABLE IF NOT EXISTS device_awareness_state (
    device_id TEXT PRIMARY KEY,
    enrollment_status TEXT NOT NULL DEFAULT 'not_enrolled',
    identity_status TEXT NOT NULL DEFAULT 'pending',
    identity_verified_at TEXT,
    identity_verified_at_epoch_ms INTEGER NOT NULL DEFAULT 0,
    identity_mismatch_count INTEGER NOT NULL DEFAULT 0 CHECK(identity_mismatch_count >= 0),
    last_identity_mismatch_at TEXT,
    last_identity_mismatch_at_epoch_ms INTEGER NOT NULL DEFAULT 0,
    blocked_join_count INTEGER NOT NULL DEFAULT 0 CHECK(blocked_join_count >= 0),
    last_blocked_join_at TEXT,
    repair_required INTEGER NOT NULL DEFAULT 0 CHECK(repair_required IN (0,1)),
    last_seen_at TEXT,
    last_seen_at_epoch_ms INTEGER NOT NULL DEFAULT 0,
    last_seen_source TEXT NOT NULL DEFAULT 'unknown',
    staleness_state TEXT NOT NULL DEFAULT 'unknown',
    command_delivery_status TEXT NOT NULL DEFAULT 'unknown',
    supervisor_status TEXT NOT NULL DEFAULT 'unknown',
    recovery_status TEXT NOT NULL DEFAULT 'unknown',
    hosted_app_count INTEGER NOT NULL DEFAULT 0 CHECK(hosted_app_count >= 0),
    backup_dependency_count INTEGER NOT NULL DEFAULT 0 CHECK(backup_dependency_count >= 0),
    storage_dependency_count INTEGER NOT NULL DEFAULT 0 CHECK(storage_dependency_count >= 0),
    capability_revision TEXT NOT NULL DEFAULT '',
    capabilities_json TEXT NOT NULL DEFAULT '[]' CHECK(length(capabilities_json) <= 32768),
    dependencies_json TEXT NOT NULL DEFAULT '{}' CHECK(length(dependencies_json) <= 32768),
    removal_safe INTEGER NOT NULL DEFAULT 0 CHECK(removal_safe IN (0,1)),
    removal_assessment_revision TEXT NOT NULL DEFAULT '',
    removal_assessment_json TEXT NOT NULL DEFAULT '{}' CHECK(length(removal_assessment_json) <= 16384),
    trust_json TEXT NOT NULL DEFAULT '{}' CHECK(length(trust_json) <= 16384),
    enrollment_json TEXT NOT NULL DEFAULT '{}' CHECK(length(enrollment_json) <= 16384),
    last_seen_json TEXT NOT NULL DEFAULT '{}' CHECK(length(last_seen_json) <= 16384),
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
    FOREIGN KEY(device_id) REFERENCES device_current_state(device_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_awareness_staleness
    ON device_awareness_state(staleness_state, last_seen_at_epoch_ms, device_id);
CREATE INDEX IF NOT EXISTS idx_device_awareness_removal
    ON device_awareness_state(removal_safe, last_seen_at_epoch_ms, device_id);
CREATE INDEX IF NOT EXISTS idx_device_awareness_identity
    ON device_awareness_state(identity_status, repair_required, device_id);

CREATE TABLE IF NOT EXISTS device_lifecycle_events (
    event_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    device_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    reason_code TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'recorded',
    occurred_at TEXT NOT NULL,
    occurred_at_epoch_ms INTEGER NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    sanitized INTEGER NOT NULL DEFAULT 1 CHECK(sanitized IN (0,1)),
    source_revision INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(device_id) REFERENCES device_current_state(device_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_lifecycle_device_time
    ON device_lifecycle_events(device_id, occurred_at_epoch_ms DESC, event_id DESC);
CREATE INDEX IF NOT EXISTS idx_device_lifecycle_type_time
    ON device_lifecycle_events(event_type, occurred_at_epoch_ms DESC, event_id DESC);
