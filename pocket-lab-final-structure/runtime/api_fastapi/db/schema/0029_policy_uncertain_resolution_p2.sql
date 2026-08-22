CREATE TABLE IF NOT EXISTS policy_recovery_resolutions (
    resolution_id TEXT PRIMARY KEY,
    operation_id TEXT NOT NULL UNIQUE,
    requested_by_human_id TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    resolved_at TEXT NOT NULL,
    original_reason_code TEXT NOT NULL,
    recovered_revision_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status = 'proved'),
    evidence_ref TEXT NOT NULL CHECK (evidence_ref = 'policy:manual-recovery-proved'),
    summary TEXT NOT NULL,
    FOREIGN KEY(operation_id) REFERENCES policy_activation_operations(operation_id),
    FOREIGN KEY(requested_by_human_id) REFERENCES human_identities(human_id)
);
CREATE INDEX IF NOT EXISTS idx_policy_recovery_resolutions_operation
ON policy_recovery_resolutions(operation_id, resolved_at DESC);
