-- Exact candidate decisions are independent of standing review grants.
-- A recorded acceptance is not execution authority.
CREATE TABLE lite_lifecycle_candidate_consent (
    consent_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES lite_lifecycle_workspace(workspace_id),
    owner_id TEXT NOT NULL REFERENCES human_identities(human_id),
    capability_id TEXT NOT NULL,
    metadata_sha256 TEXT NOT NULL,
    scope_sha256 TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    binding_json TEXT NOT NULL,
    disposition TEXT NOT NULL CHECK(disposition IN ('accepted_for_review','declined','deferred')),
    decision_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);
CREATE UNIQUE INDEX idx_lifecycle_candidate_consent_current ON lite_lifecycle_candidate_consent(workspace_id,metadata_sha256,capability_id) WHERE revoked_at IS NULL;
CREATE INDEX idx_lifecycle_candidate_consent_history ON lite_lifecycle_candidate_consent(issued_at DESC);
