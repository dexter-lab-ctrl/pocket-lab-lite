CREATE TABLE IF NOT EXISTS policy_revisions (
    revision_id TEXT PRIMARY KEY,
    parent_revision_id TEXT,
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL,
    canonical_parameters_json TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    created_by_human_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    validation_status TEXT NOT NULL CHECK (validation_status IN ('pending','valid','invalid','corrupt')),
    validated_at TEXT,
    validation_reason_code TEXT NOT NULL DEFAULT '',
    lifecycle_status TEXT NOT NULL CHECK (lifecycle_status IN ('draft','validated','active','failed','superseded')),
    activated_at TEXT,
    change_summary TEXT NOT NULL,
    FOREIGN KEY(parent_revision_id) REFERENCES policy_revisions(revision_id),
    FOREIGN KEY(created_by_human_id) REFERENCES human_identities(human_id)
);
CREATE INDEX IF NOT EXISTS idx_policy_revisions_lifecycle ON policy_revisions(lifecycle_status, created_at DESC);

CREATE TABLE IF NOT EXISTS policy_runtime_state (
    state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
    active_revision_id TEXT,
    known_good_revision_id TEXT,
    updated_at TEXT NOT NULL,
    updated_by_operation_id TEXT,
    FOREIGN KEY(active_revision_id) REFERENCES policy_revisions(revision_id),
    FOREIGN KEY(known_good_revision_id) REFERENCES policy_revisions(revision_id)
);

CREATE TABLE IF NOT EXISTS policy_activation_operations (
    operation_id TEXT PRIMARY KEY,
    requested_by_human_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    candidate_revision_id TEXT NOT NULL,
    prior_known_good_revision_id TEXT,
    state TEXT NOT NULL CHECK (state IN ('pending','validating','switching','restarting','verifying','active','rolling_back','rolled_back','uncertain','failed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reason_code TEXT NOT NULL DEFAULT '',
    observed_filesystem_revision TEXT,
    observed_opa_revision TEXT,
    evidence_ref TEXT,
    FOREIGN KEY(requested_by_human_id) REFERENCES human_identities(human_id),
    FOREIGN KEY(candidate_revision_id) REFERENCES policy_revisions(revision_id),
    FOREIGN KEY(prior_known_good_revision_id) REFERENCES policy_revisions(revision_id)
);
CREATE INDEX IF NOT EXISTS idx_policy_activation_operations_state ON policy_activation_operations(state, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_policy_activation_single_nonterminal
ON policy_activation_operations((1))
WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain');
