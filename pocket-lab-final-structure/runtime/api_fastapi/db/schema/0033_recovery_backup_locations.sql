-- Durable, backend-owned encrypted backup location registry.
--
-- root_path is private control-plane state and is never returned by the Lite
-- API.  The browser receives only opaque location ids and safe labels.  A
-- location event is deliberately bounded and sanitized so selecting a
-- repository remains auditable without copying filesystem paths into the
-- event stream.

CREATE TABLE recovery_backup_locations (
    location_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('private_default', 'android_internal', 'android_removable', 'configured')),
    display_name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    canonical_root TEXT NOT NULL,
    repository_id TEXT NOT NULL,
    repository_fingerprint TEXT NOT NULL DEFAULT '',
    is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
    is_selected INTEGER NOT NULL DEFAULT 0 CHECK (is_selected IN (0, 1)),
    is_removable INTEGER NOT NULL DEFAULT 0 CHECK (is_removable IN (0, 1)),
    is_forgotten INTEGER NOT NULL DEFAULT 0 CHECK (is_forgotten IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'checking',
    reason_code TEXT NOT NULL DEFAULT '',
    free_bytes INTEGER,
    capacity_bytes INTEGER,
    repository_present INTEGER NOT NULL DEFAULT 0 CHECK (repository_present IN (0, 1)),
    last_checked_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE UNIQUE INDEX idx_recovery_backup_locations_default
    ON recovery_backup_locations(is_default)
    WHERE is_default = 1;

CREATE UNIQUE INDEX idx_recovery_backup_locations_selected
    ON recovery_backup_locations(is_selected)
    WHERE is_selected = 1;

CREATE TABLE recovery_backup_location_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    location_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    reason_code TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    actor_type TEXT NOT NULL DEFAULT 'authenticated',
    auth_method TEXT NOT NULL DEFAULT '',
    sanitized INTEGER NOT NULL DEFAULT 1 CHECK (sanitized = 1)
);

CREATE INDEX idx_recovery_backup_location_events_time
    ON recovery_backup_location_events(occurred_at DESC, event_id DESC);

CREATE INDEX idx_recovery_backup_location_events_location
    ON recovery_backup_location_events(location_id, occurred_at DESC, event_id DESC);
