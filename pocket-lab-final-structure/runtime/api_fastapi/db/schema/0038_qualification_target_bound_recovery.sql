-- Bind synthetic qualification sessions to one operator-selected target and
-- issue one-use receipts for the narrow offline main-database handoff.
-- The transport scope remains loopback/local-server; target_device_id is the
-- additional server-owned authorization binding for fleet qualification.

ALTER TABLE synthetic_principals ADD COLUMN target_device_id TEXT NOT NULL DEFAULT '';
ALTER TABLE harness_challenges ADD COLUMN target_device_id TEXT NOT NULL DEFAULT '';
ALTER TABLE harness_sessions ADD COLUMN target_device_id TEXT NOT NULL DEFAULT '';
ALTER TABLE harness_audit_events ADD COLUMN target_device_id TEXT NOT NULL DEFAULT '';

CREATE INDEX idx_synthetic_principals_target_device
    ON synthetic_principals(target_device_id, enabled, revoked_at);
CREATE INDEX idx_harness_sessions_target_device
    ON harness_sessions(target_device_id, status, expires_at);
CREATE INDEX idx_harness_audit_target_device
    ON harness_audit_events(target_device_id, occurred_at DESC, event_id DESC);

CREATE TABLE harness_recovery_receipts (
    receipt_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    principal_id TEXT NOT NULL,
    harness_session_id TEXT NOT NULL,
    action_id TEXT NOT NULL CHECK(action_id = 'recovery.authorize'),
    backup_id TEXT NOT NULL,
    preview_id TEXT NOT NULL,
    target_schema INTEGER NOT NULL CHECK(target_schema >= 1),
    target_runtime_sha TEXT NOT NULL,
    issued_runtime_id TEXT NOT NULL,
    issued_runtime_revision TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    status TEXT NOT NULL DEFAULT 'issued'
        CHECK(status IN ('issued', 'consumed', 'expired', 'revoked')),
    FOREIGN KEY (principal_id) REFERENCES synthetic_principals(principal_id),
    FOREIGN KEY (harness_session_id) REFERENCES harness_sessions(harness_session_id)
);

CREATE INDEX idx_harness_recovery_receipts_status
    ON harness_recovery_receipts(status, expires_at, issued_at DESC);
CREATE INDEX idx_harness_recovery_receipts_binding
    ON harness_recovery_receipts(backup_id, preview_id, target_schema, status);
