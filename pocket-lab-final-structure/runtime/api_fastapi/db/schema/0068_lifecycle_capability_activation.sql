-- Explicit activation for the one locally supported optional capability.
-- Candidate consent remains separate and never creates this row.
CREATE TABLE lite_lifecycle_capability_activation (
    activation_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES lite_lifecycle_workspace(workspace_id),
    owner_id TEXT NOT NULL REFERENCES human_identities(human_id),
    capability_id TEXT NOT NULL CHECK(capability_id='system.activity_history.reconcile.activate'),
    capability_version INTEGER NOT NULL CHECK(capability_version=1),
    metadata_sha256 TEXT NOT NULL,
    scope_sha256 TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    binding_json TEXT NOT NULL,
    binding_sha256 TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    authority_epoch INTEGER NOT NULL,
    policy_revision TEXT NOT NULL,
    execution_owner TEXT NOT NULL CHECK(execution_owner='projection_scheduler'),
    state TEXT NOT NULL CHECK(state IN ('activated','declined','deferred','revoked','expired','blocked','completed')),
    claimed_at TEXT,
    claim_decision_id TEXT,
    last_attempt_id TEXT,
    terminal_evidence_sha256 TEXT,
    reason_code TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX lite_lifecycle_capability_activation_current
ON lite_lifecycle_capability_activation(workspace_id,capability_id)
WHERE state IN ('activated','blocked');
CREATE INDEX lite_lifecycle_capability_activation_history
ON lite_lifecycle_capability_activation(issued_at DESC);
