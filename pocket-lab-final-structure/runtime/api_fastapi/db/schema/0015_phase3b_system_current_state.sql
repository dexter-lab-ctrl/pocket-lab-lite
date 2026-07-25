-- Phase 3B: bounded semantic current-state projections for Security and system probes.
-- Collectors run outside request handlers. Rows contain sanitized state only;
-- raw logs, command lines, environment values, scanner output, credentials,
-- peer lists, and unbounded telemetry are intentionally excluded.
CREATE TABLE IF NOT EXISTS phase3b_current_state (
    domain TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'unknown',
    generation INTEGER NOT NULL DEFAULT 0,
    source_revision INTEGER NOT NULL DEFAULT 0,
    projection_revision INTEGER NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL DEFAULT '{}',
    item_count INTEGER NOT NULL DEFAULT 0,
    collector_duration_ms REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL,
    sanitized INTEGER NOT NULL DEFAULT 1 CHECK (sanitized IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_phase3b_current_state_status
    ON phase3b_current_state(status, domain);
CREATE INDEX IF NOT EXISTS idx_phase3b_current_state_revision
    ON phase3b_current_state(domain, projection_revision DESC);

CREATE TABLE IF NOT EXISTS phase3b_revision_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    database_instance TEXT NOT NULL,
    domain TEXT NOT NULL,
    projection_revision INTEGER NOT NULL,
    source_revision INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT 'semantic_state_changed',
    occurred_at TEXT NOT NULL,
    occurred_at_epoch_ms INTEGER NOT NULL,
    sanitized INTEGER NOT NULL DEFAULT 1 CHECK (sanitized IN (0, 1)),
    UNIQUE(database_instance, domain, projection_revision)
);

CREATE INDEX IF NOT EXISTS idx_phase3b_revision_events_replay
    ON phase3b_revision_events(database_instance, event_id);
CREATE INDEX IF NOT EXISTS idx_phase3b_revision_events_retention
    ON phase3b_revision_events(occurred_at_epoch_ms, event_id);

INSERT OR IGNORE INTO domain_revisions(domain, revision, updated_at) VALUES
    ('security.progress', 0, '1970-01-01T00:00:00Z'),
    ('security.summary', 0, '1970-01-01T00:00:00Z'),
    ('system.status', 0, '1970-01-01T00:00:00Z'),
    ('system.health', 0, '1970-01-01T00:00:00Z'),
    ('system.processes', 0, '1970-01-01T00:00:00Z'),
    ('system.agent', 0, '1970-01-01T00:00:00Z'),
    ('system.supervisor', 0, '1970-01-01T00:00:00Z'),
    ('system.remote_access', 0, '1970-01-01T00:00:00Z'),
    ('system.nats_remote', 0, '1970-01-01T00:00:00Z'),
    ('system.fleet_probe', 0, '1970-01-01T00:00:00Z');
