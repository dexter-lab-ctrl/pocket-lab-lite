-- One exact execution authorization is separate from review grants and consent.
-- The human initiator remains the actual human; the local executor is separately
-- attributed to the existing core supervisor, not a synthetic human session.
CREATE TABLE lite_lifecycle_policy_execution (
    operation_id TEXT PRIMARY KEY REFERENCES policy_activation_operations(operation_id),
    grant_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL REFERENCES human_identities(human_id),
    executor_principal TEXT NOT NULL CHECK(executor_principal='policy-reconciler'),
    binding_json TEXT NOT NULL,
    binding_sha256 TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    claimed_at TEXT,
    claim_decision_id TEXT,
    proof_sha256 TEXT
);
CREATE INDEX idx_lifecycle_policy_execution_owner ON lite_lifecycle_policy_execution(owner_id,issued_at DESC);
