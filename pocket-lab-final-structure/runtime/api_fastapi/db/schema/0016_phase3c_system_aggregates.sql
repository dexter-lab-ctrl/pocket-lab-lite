-- Phase 3C extends the existing bounded prepared-current-state store.
-- No raw telemetry history, audit payloads, logs, paths, or backup contents are stored.
INSERT OR IGNORE INTO domain_revisions(domain, revision, updated_at) VALUES
    ('system.telemetry_thresholds', 0, '1970-01-01T00:00:00Z'),
    ('system.storage_pressure', 0, '1970-01-01T00:00:00Z'),
    ('system.sqlite_health', 0, '1970-01-01T00:00:00Z'),
    ('system.activity_summary', 0, '1970-01-01T00:00:00Z');

CREATE INDEX IF NOT EXISTS idx_phase3c_maintenance_status_latest
    ON security_maintenance_runs(status, requested_at DESC, maintenance_id DESC);
CREATE INDEX IF NOT EXISTS idx_phase3c_app_actions_status_latest
    ON app_action_lifecycle(status, updated_at_epoch_ms DESC, operation_id DESC);
CREATE INDEX IF NOT EXISTS idx_phase3c_recovery_status_latest
    ON recovery_operations(status, updated_at_epoch_ms DESC, operation_id DESC);
CREATE INDEX IF NOT EXISTS idx_phase3c_audit_latest
    ON audit_evidence_index(created_at_epoch_ms DESC, evidence_index_id DESC);
