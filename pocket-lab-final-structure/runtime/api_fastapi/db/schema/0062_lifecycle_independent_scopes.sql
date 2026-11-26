-- A mutation revision fences concurrent requests; a separate epoch fences
-- the maximum local authority. Scope and delegation revisions are per-purpose.
ALTER TABLE lite_lifecycle_workspace ADD COLUMN authority_epoch INTEGER NOT NULL DEFAULT 1;
ALTER TABLE lite_lifecycle_grants ADD COLUMN authority_epoch INTEGER NOT NULL DEFAULT 0;
ALTER TABLE lite_lifecycle_grants ADD COLUMN trust_configuration_revision INTEGER NOT NULL DEFAULT 0;
CREATE TABLE lite_lifecycle_boundary_scopes (
    purpose TEXT PRIMARY KEY CHECK(purpose IN ('release-reconciler','policy-reconciler')),
    authority_epoch INTEGER NOT NULL,
    scope_revision INTEGER NOT NULL,
    owner_id TEXT NOT NULL REFERENCES human_identities(human_id),
    scope_json TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    approved_at TEXT NOT NULL
);
-- Previous records lack a configuration/epoch fence. Retain history only.
UPDATE lite_lifecycle_grants SET revoked_at=COALESCE(revoked_at,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
CREATE INDEX idx_lifecycle_grants_purpose ON lite_lifecycle_grants(purpose,revoked_at,boundary_revision);
