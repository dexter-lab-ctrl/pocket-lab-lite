CREATE TABLE IF NOT EXISTS lite_installed_release_identity (
    owner TEXT PRIMARY KEY,
    schema_version INTEGER NOT NULL DEFAULT 1,
    identity_revision INTEGER NOT NULL DEFAULT 0,
    product TEXT NOT NULL DEFAULT 'pocket-lab-lite',
    install_mode TEXT NOT NULL DEFAULT 'unknown',
    source_repository TEXT NOT NULL DEFAULT '',
    source_commit TEXT NOT NULL DEFAULT '',
    release_tag TEXT NOT NULL DEFAULT '',
    artifact_name TEXT NOT NULL DEFAULT '',
    artifact_sha256 TEXT NOT NULL DEFAULT '',
    installed_at TEXT,
    installer_schema INTEGER NOT NULL DEFAULT 1,
    verified INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1)),
    migration_status TEXT NOT NULL DEFAULT '',
    canonical_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_at_epoch_ms INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lite_installed_release_identity_mode
    ON lite_installed_release_identity(install_mode, verified, updated_at_epoch_ms DESC);

ALTER TABLE release_runtime_projection ADD COLUMN configured_repository TEXT NOT NULL DEFAULT '';
ALTER TABLE release_runtime_projection ADD COLUMN verified_repository TEXT NOT NULL DEFAULT '';
ALTER TABLE release_runtime_projection ADD COLUMN repository_match INTEGER NOT NULL DEFAULT 0 CHECK (repository_match IN (0, 1));
ALTER TABLE release_runtime_projection ADD COLUMN install_mode TEXT NOT NULL DEFAULT 'unknown';
ALTER TABLE release_runtime_projection ADD COLUMN installed_release_tag TEXT NOT NULL DEFAULT '';
ALTER TABLE release_runtime_projection ADD COLUMN installed_source_commit TEXT NOT NULL DEFAULT '';
ALTER TABLE release_runtime_projection ADD COLUMN comparison TEXT NOT NULL DEFAULT 'unknown_installed_identity';
ALTER TABLE release_runtime_projection ADD COLUMN manifest_verified INTEGER NOT NULL DEFAULT 0 CHECK (manifest_verified IN (0, 1));
ALTER TABLE release_runtime_projection ADD COLUMN artifact_verified INTEGER NOT NULL DEFAULT 0 CHECK (artifact_verified IN (0, 1));
ALTER TABLE release_runtime_projection ADD COLUMN staging_status TEXT NOT NULL DEFAULT 'idle';
ALTER TABLE release_runtime_projection ADD COLUMN promotion_status TEXT NOT NULL DEFAULT 'idle';
ALTER TABLE release_runtime_projection ADD COLUMN rollback_available INTEGER NOT NULL DEFAULT 0 CHECK (rollback_available IN (0, 1));
ALTER TABLE release_runtime_projection ADD COLUMN last_failure_stage TEXT NOT NULL DEFAULT '';
ALTER TABLE release_runtime_projection ADD COLUMN last_rollback_status TEXT NOT NULL DEFAULT '';
ALTER TABLE release_runtime_projection ADD COLUMN next_check_epoch_ms INTEGER NOT NULL DEFAULT 0;
ALTER TABLE release_runtime_projection ADD COLUMN stable_interval_seconds INTEGER NOT NULL DEFAULT 43200;
