-- Bounded current-state and searchable metadata projections for Lite domains.
-- Runtime heartbeats/events remain authoritative; these rows are read-optimized copies.
CREATE TABLE IF NOT EXISTS device_heartbeats (
    heartbeat_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    heartbeat_id TEXT NOT NULL,
    source_revision INTEGER NOT NULL DEFAULT 0,
    connection_state TEXT NOT NULL DEFAULT 'unknown',
    agent_status TEXT NOT NULL DEFAULT 'unknown',
    supervisor_status TEXT NOT NULL DEFAULT 'unknown',
    pm2_status TEXT NOT NULL DEFAULT 'unknown',
    remote_access_ready INTEGER NOT NULL DEFAULT 0 CHECK (remote_access_ready IN (0, 1)),
    protected_server_host INTEGER NOT NULL DEFAULT 0 CHECK (protected_server_host IN (0, 1)),
    observed_at TEXT NOT NULL,
    observed_at_epoch_ms INTEGER NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    UNIQUE(device_id, heartbeat_id)
);

CREATE TABLE IF NOT EXISTS device_invite_lifecycle (
    invite_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL DEFAULT '',
    device_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    created_at TEXT,
    expires_at TEXT,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    source_revision INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS device_identity_guards (
    identity_key TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    normalized_name TEXT NOT NULL DEFAULT '',
    protected_server_host INTEGER NOT NULL DEFAULT 0 CHECK (protected_server_host IN (0, 1)),
    source TEXT NOT NULL DEFAULT 'fleet-projection',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS command_lifecycle (
    command_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation_type TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'published', 'received', 'accepted', 'running', 'succeeded',
        'failed', 'cancelled', 'undeliverable', 'timed_out', 'unknown'
    )),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    deadline_at TEXT,
    source_ref TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS device_recovery_history (
    recovery_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    action TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'unknown',
    command_id TEXT,
    created_at TEXT NOT NULL,
    created_at_epoch_ms INTEGER NOT NULL,
    source_ref TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS device_current_state (
    device_id TEXT PRIMARY KEY,
    device_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'compute',
    ui_state TEXT NOT NULL DEFAULT 'Waiting',
    connection_state TEXT NOT NULL DEFAULT 'unknown',
    agent_status TEXT NOT NULL DEFAULT 'unknown',
    supervisor_status TEXT NOT NULL DEFAULT 'unknown',
    pm2_status TEXT NOT NULL DEFAULT 'unknown',
    remote_access_ready INTEGER NOT NULL DEFAULT 0 CHECK (remote_access_ready IN (0, 1)),
    protected_server_host INTEGER NOT NULL DEFAULT 0 CHECK (protected_server_host IN (0, 1)),
    source_heartbeat_id TEXT,
    latest_command_id TEXT,
    latest_invite_id TEXT,
    latest_recovery_id TEXT,
    source_revision INTEGER NOT NULL DEFAULT 0,
    last_seen_at TEXT,
    last_seen_epoch_ms INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS app_action_lifecycle (
    operation_id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    source_ref TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS app_current_state (
    app_id TEXT PRIMARY KEY,
    app_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'unknown',
    installed INTEGER NOT NULL DEFAULT 0 CHECK (installed IN (0, 1)),
    health_state TEXT NOT NULL DEFAULT 'unknown',
    latest_action_id TEXT,
    latest_action_status TEXT,
    latest_backup_id TEXT,
    source_revision INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS recovery_operations (
    operation_id TEXT PRIMARY KEY,
    operation_type TEXT NOT NULL,
    status TEXT NOT NULL,
    backup_id TEXT,
    preview_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    source_ref TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS backup_manifest_index (
    backup_id TEXT PRIMARY KEY,
    backup_type TEXT NOT NULL DEFAULT 'lite',
    status TEXT NOT NULL DEFAULT 'unknown',
    verification_status TEXT NOT NULL DEFAULT 'unknown',
    created_at TEXT,
    verified_at TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    source_ref TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS recovery_current_state (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    status TEXT NOT NULL DEFAULT 'unknown',
    active_operation_id TEXT,
    latest_backup_id TEXT,
    latest_preview_id TEXT,
    latest_restore_id TEXT,
    maintenance_status TEXT NOT NULL DEFAULT 'idle',
    source_revision INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    summary TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_evidence_index (
    evidence_index_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'unknown',
    evidence_ref TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    created_at_epoch_ms INTEGER NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    UNIQUE(event_type, entity_type, entity_id, operation_id, evidence_ref)
);

CREATE INDEX IF NOT EXISTS idx_device_heartbeats_latest
    ON device_heartbeats(device_id, observed_at_epoch_ms DESC, heartbeat_row_id DESC);
CREATE INDEX IF NOT EXISTS idx_device_heartbeats_stale
    ON device_heartbeats(observed_at_epoch_ms, device_id);
CREATE INDEX IF NOT EXISTS idx_device_current_fleet_order
    ON device_current_state(protected_server_host DESC, device_name, device_id);
CREATE INDEX IF NOT EXISTS idx_device_current_stale
    ON device_current_state(connection_state, last_seen_epoch_ms, device_id);
CREATE INDEX IF NOT EXISTS idx_device_current_stale_order
    ON device_current_state(last_seen_epoch_ms, device_id)
    WHERE connection_state IN ('offline', 'stale');
CREATE INDEX IF NOT EXISTS idx_device_invites_identity
    ON device_invite_lifecycle(device_id, status, updated_at_epoch_ms DESC);
CREATE INDEX IF NOT EXISTS idx_device_invites_active_latest
    ON device_invite_lifecycle(device_id, updated_at_epoch_ms DESC, invite_id DESC)
    WHERE status IN ('pending', 'accepted', 'joining');
CREATE INDEX IF NOT EXISTS idx_device_invites_status
    ON device_invite_lifecycle(status, updated_at_epoch_ms DESC, invite_id DESC);
CREATE INDEX IF NOT EXISTS idx_commands_entity_active
    ON command_lifecycle(entity_type, entity_id, status, updated_at_epoch_ms DESC, command_id DESC);
CREATE INDEX IF NOT EXISTS idx_commands_entity_active_latest
    ON command_lifecycle(entity_type, entity_id, updated_at_epoch_ms DESC, command_id DESC)
    WHERE status IN ('queued', 'published', 'received', 'accepted', 'running');
CREATE INDEX IF NOT EXISTS idx_commands_status_updated
    ON command_lifecycle(status, updated_at_epoch_ms DESC, command_id DESC);
CREATE INDEX IF NOT EXISTS idx_commands_entity_history
    ON command_lifecycle(entity_type, entity_id, updated_at_epoch_ms DESC, command_id DESC);
CREATE INDEX IF NOT EXISTS idx_device_recovery_history
    ON device_recovery_history(device_id, created_at_epoch_ms DESC, recovery_id DESC);
CREATE INDEX IF NOT EXISTS idx_app_actions_history
    ON app_action_lifecycle(app_id, updated_at_epoch_ms DESC, operation_id DESC);
CREATE INDEX IF NOT EXISTS idx_app_actions_active
    ON app_action_lifecycle(app_id, status, updated_at_epoch_ms DESC, operation_id DESC);
CREATE INDEX IF NOT EXISTS idx_app_current_order
    ON app_current_state(status, app_name, app_id);
CREATE INDEX IF NOT EXISTS idx_recovery_operations_history
    ON recovery_operations(operation_type, updated_at_epoch_ms DESC, operation_id DESC);
CREATE INDEX IF NOT EXISTS idx_recovery_operations_updated
    ON recovery_operations(updated_at_epoch_ms DESC, operation_id DESC);
CREATE INDEX IF NOT EXISTS idx_backup_manifest_created
    ON backup_manifest_index(updated_at_epoch_ms DESC, backup_id DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entity_created
    ON audit_evidence_index(entity_type, entity_id, created_at_epoch_ms DESC, evidence_index_id DESC);
CREATE INDEX IF NOT EXISTS idx_audit_operation_created
    ON audit_evidence_index(operation_id, created_at_epoch_ms DESC, evidence_index_id DESC);

INSERT OR IGNORE INTO domain_revisions(domain, revision, updated_at) VALUES
    ('fleet', 0, '1970-01-01T00:00:00Z'),
    ('apps', 0, '1970-01-01T00:00:00Z'),
    ('recovery', 0, '1970-01-01T00:00:00Z'),
    ('commands', 0, '1970-01-01T00:00:00Z'),
    ('storage', 0, '1970-01-01T00:00:00Z'),
    ('audit', 0, '1970-01-01T00:00:00Z');
