-- Latest review is separate from immutable first-acceptance receipts.
ALTER TABLE lite_release_trust_observation ADD COLUMN review_json TEXT NOT NULL DEFAULT '{}';
ALTER TABLE lite_lifecycle_workspace ADD COLUMN delegation_revision INTEGER NOT NULL DEFAULT 0;
CREATE TABLE lite_lifecycle_service_delegations (
    delegation_id TEXT PRIMARY KEY,
    grant_id TEXT NOT NULL UNIQUE REFERENCES lite_lifecycle_grants(grant_id) ON DELETE RESTRICT,
    purpose TEXT NOT NULL,
    contract_version INTEGER NOT NULL CHECK(contract_version>0),
    delegation_revision INTEGER NOT NULL CHECK(delegation_revision>0),
    created_at TEXT NOT NULL
);
CREATE INDEX idx_lifecycle_delegation_purpose ON lite_lifecycle_service_delegations(purpose,delegation_revision);
