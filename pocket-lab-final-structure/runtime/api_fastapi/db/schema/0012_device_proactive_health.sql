-- Phase D4: bounded proactive device-health current state, active attention, and coarse transitions.
-- Raw telemetry, heartbeat payloads, command bodies, private paths, and evidence are intentionally excluded.
CREATE TABLE IF NOT EXISTS device_health_current (
    device_id TEXT PRIMARY KEY,
    health_status TEXT NOT NULL DEFAULT 'unknown',
    health_severity TEXT NOT NULL DEFAULT 'none',
    resource_status TEXT NOT NULL DEFAULT 'unknown',
    connection_status TEXT NOT NULL DEFAULT 'unknown',
    recovery_status TEXT NOT NULL DEFAULT 'unknown',
    version_status TEXT NOT NULL DEFAULT 'unknown',
    dependency_impact_status TEXT NOT NULL DEFAULT 'unknown',
    reason_codes_json TEXT NOT NULL DEFAULT '[]' CHECK(length(reason_codes_json) <= 4096),
    recommendation_code TEXT NOT NULL DEFAULT 'review_device',
    recommendation_target TEXT,
    attention_count INTEGER NOT NULL DEFAULT 0 CHECK(attention_count BETWEEN 0 AND 64),
    health_revision TEXT NOT NULL DEFAULT '',
    source_revision INTEGER NOT NULL DEFAULT 0 CHECK(source_revision >= 0),
    source_freshness_json TEXT NOT NULL DEFAULT '{}' CHECK(length(source_freshness_json) <= 8192),
    resources_json TEXT NOT NULL DEFAULT '{}' CHECK(length(resources_json) <= 12288),
    connection_json TEXT NOT NULL DEFAULT '{}' CHECK(length(connection_json) <= 8192),
    recovery_json TEXT NOT NULL DEFAULT '{}' CHECK(length(recovery_json) <= 8192),
    versions_json TEXT NOT NULL DEFAULT '{}' CHECK(length(versions_json) <= 8192),
    dependency_impact_json TEXT NOT NULL DEFAULT '{}' CHECK(length(dependency_impact_json) <= 12288),
    summary TEXT NOT NULL DEFAULT '',
    last_evaluated_at TEXT NOT NULL,
    last_evaluated_at_epoch_ms INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
    FOREIGN KEY(device_id) REFERENCES device_current_state(device_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_health_status
    ON device_health_current(health_status, health_severity, device_id);
CREATE INDEX IF NOT EXISTS idx_device_health_attention
    ON device_health_current(attention_count DESC, health_severity, device_id);

CREATE TABLE IF NOT EXISTS device_health_attention (
    attention_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    category TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    summary TEXT NOT NULL DEFAULT '',
    recommendation TEXT NOT NULL DEFAULT '',
    recommendation_code TEXT NOT NULL DEFAULT 'review_device',
    created_at TEXT NOT NULL,
    created_at_epoch_ms INTEGER NOT NULL,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    resolved_at TEXT,
    resolved_at_epoch_ms INTEGER NOT NULL DEFAULT 0,
    source_revision INTEGER NOT NULL DEFAULT 0 CHECK(source_revision >= 0),
    FOREIGN KEY(device_id) REFERENCES device_current_state(device_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_device_health_attention_active_reason
    ON device_health_attention(device_id, reason_code)
    WHERE status IN ('active', 'acknowledged');
CREATE INDEX IF NOT EXISTS idx_device_health_attention_device_status
    ON device_health_attention(device_id, status, updated_at_epoch_ms DESC, attention_id DESC);

CREATE TABLE IF NOT EXISTS device_health_transitions (
    transition_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,
    device_id TEXT NOT NULL,
    previous_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    reason_codes_json TEXT NOT NULL DEFAULT '[]' CHECK(length(reason_codes_json) <= 4096),
    summary TEXT NOT NULL DEFAULT '',
    occurred_at TEXT NOT NULL,
    occurred_at_epoch_ms INTEGER NOT NULL,
    resolved_at TEXT,
    source_revision INTEGER NOT NULL DEFAULT 0 CHECK(source_revision >= 0),
    FOREIGN KEY(device_id) REFERENCES device_current_state(device_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_device_health_transitions_device_time
    ON device_health_transitions(device_id, occurred_at_epoch_ms DESC, event_id DESC);
CREATE INDEX IF NOT EXISTS idx_device_health_attention_active_time
    ON device_health_attention(device_id, updated_at_epoch_ms DESC, attention_id DESC)
    WHERE status IN ('active', 'acknowledged');
