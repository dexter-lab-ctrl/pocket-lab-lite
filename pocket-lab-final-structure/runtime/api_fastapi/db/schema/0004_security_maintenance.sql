CREATE TABLE IF NOT EXISTS security_maintenance_runs (
    maintenance_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('retention', 'wal_passive', 'wal_truncate', 'database_backup', 'database_restore')),
    mode TEXT NOT NULL DEFAULT 'apply',
    status TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'blocked')),
    requested_at TEXT NOT NULL,
    completed_at TEXT,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT,
    sanitized INTEGER NOT NULL DEFAULT 1 CHECK (sanitized IN (0, 1))
);

CREATE TABLE IF NOT EXISTS security_database_backups (
    backup_id TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK (status IN ('creating', 'verified', 'failed')),
    created_at TEXT NOT NULL,
    verified_at TEXT,
    file_name TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    sha256 TEXT NOT NULL DEFAULT '',
    schema_version INTEGER NOT NULL DEFAULT 0,
    sqlite_version TEXT NOT NULL DEFAULT '',
    manifest_json TEXT NOT NULL DEFAULT '{}',
    sanitized INTEGER NOT NULL DEFAULT 1 CHECK (sanitized IN (0, 1))
);

CREATE TABLE IF NOT EXISTS security_database_restores (
    restore_id TEXT PRIMARY KEY,
    backup_id TEXT NOT NULL,
    preview_id TEXT NOT NULL,
    state TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    completed_at TEXT,
    rollback_file_name TEXT,
    summary TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    sanitized INTEGER NOT NULL DEFAULT 1 CHECK (sanitized IN (0, 1)),
    FOREIGN KEY (backup_id) REFERENCES security_database_backups(backup_id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_security_maintenance_kind_requested
    ON security_maintenance_runs(kind, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_database_backups_created
    ON security_database_backups(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_database_restores_requested
    ON security_database_restores(requested_at DESC);
