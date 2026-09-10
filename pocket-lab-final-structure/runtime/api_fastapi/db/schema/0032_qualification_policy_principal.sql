-- Allow the explicitly isolated qualification principal to be recorded as an
-- actor without creating a human identity or Enterprise membership row.
-- Existing human provenance remains linked through the legacy nullable FK;
-- principal_type/principal_id is the authoritative actor classification.

ALTER TABLE policy_recovery_resolutions RENAME TO policy_recovery_resolutions__qualification_old;
ALTER TABLE policy_activation_operations RENAME TO policy_activation_operations__qualification_old;
ALTER TABLE policy_runtime_state RENAME TO policy_runtime_state__qualification_old;
ALTER TABLE policy_revisions RENAME TO policy_revisions__qualification_old;

DROP INDEX IF EXISTS idx_policy_recovery_resolutions_operation;
DROP INDEX IF EXISTS idx_policy_activation_operations_state;
DROP INDEX IF EXISTS idx_policy_activation_single_nonterminal;
DROP INDEX IF EXISTS idx_policy_revisions_lifecycle;

CREATE TABLE policy_revisions (
    revision_id TEXT PRIMARY KEY,
    parent_revision_id TEXT,
    template_id TEXT NOT NULL,
    template_version TEXT NOT NULL,
    canonical_parameters_json TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    content_hash TEXT NOT NULL UNIQUE,
    created_by_human_id TEXT,
    created_by_principal_type TEXT NOT NULL DEFAULT 'human' CHECK (created_by_principal_type IN ('human','qualification')),
    created_by_principal_id TEXT NOT NULL DEFAULT '',
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

INSERT INTO policy_revisions(
    revision_id,parent_revision_id,template_id,template_version,
    canonical_parameters_json,manifest_json,content_hash,created_by_human_id,
    created_by_principal_type,created_by_principal_id,created_at,validation_status,
    validated_at,validation_reason_code,lifecycle_status,activated_at,change_summary
)
SELECT revision_id,NULL,template_id,template_version,
       canonical_parameters_json,manifest_json,content_hash,created_by_human_id,
       'human',COALESCE(created_by_human_id,''),created_at,validation_status,
       validated_at,validation_reason_code,lifecycle_status,activated_at,change_summary
FROM policy_revisions__qualification_old;

UPDATE policy_revisions
SET parent_revision_id = (
    SELECT old.parent_revision_id
    FROM policy_revisions__qualification_old AS old
    WHERE old.revision_id = policy_revisions.revision_id
);

CREATE INDEX idx_policy_revisions_lifecycle ON policy_revisions(lifecycle_status, created_at DESC);

CREATE TABLE policy_runtime_state (
    state_id INTEGER PRIMARY KEY CHECK (state_id = 1),
    active_revision_id TEXT,
    known_good_revision_id TEXT,
    updated_at TEXT NOT NULL,
    updated_by_operation_id TEXT,
    FOREIGN KEY(active_revision_id) REFERENCES policy_revisions(revision_id),
    FOREIGN KEY(known_good_revision_id) REFERENCES policy_revisions(revision_id)
);

INSERT INTO policy_runtime_state(state_id,active_revision_id,known_good_revision_id,updated_at,updated_by_operation_id)
SELECT state_id,active_revision_id,known_good_revision_id,updated_at,updated_by_operation_id
FROM policy_runtime_state__qualification_old;

CREATE TABLE policy_activation_operations (
    operation_id TEXT PRIMARY KEY,
    requested_by_human_id TEXT,
    requested_by_principal_type TEXT NOT NULL DEFAULT 'human' CHECK (requested_by_principal_type IN ('human','qualification')),
    requested_by_principal_id TEXT NOT NULL DEFAULT '',
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

INSERT INTO policy_activation_operations(
    operation_id,requested_by_human_id,requested_by_principal_type,requested_by_principal_id,
    correlation_id,candidate_revision_id,prior_known_good_revision_id,state,created_at,
    updated_at,reason_code,observed_filesystem_revision,observed_opa_revision,evidence_ref
)
SELECT operation_id,requested_by_human_id,'human',COALESCE(requested_by_human_id,''),
       correlation_id,candidate_revision_id,prior_known_good_revision_id,state,created_at,
       updated_at,reason_code,observed_filesystem_revision,observed_opa_revision,evidence_ref
FROM policy_activation_operations__qualification_old;

CREATE INDEX idx_policy_activation_operations_state ON policy_activation_operations(state, created_at DESC);
CREATE UNIQUE INDEX idx_policy_activation_single_nonterminal
ON policy_activation_operations((1))
WHERE state IN ('pending','validating','switching','restarting','verifying','rolling_back','uncertain');

CREATE TABLE policy_recovery_resolutions (
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

INSERT INTO policy_recovery_resolutions(
    resolution_id,operation_id,requested_by_human_id,requested_at,resolved_at,
    original_reason_code,recovered_revision_id,status,evidence_ref,summary
)
SELECT resolution_id,operation_id,requested_by_human_id,requested_at,resolved_at,
       original_reason_code,recovered_revision_id,status,evidence_ref,summary
FROM policy_recovery_resolutions__qualification_old;

CREATE INDEX idx_policy_recovery_resolutions_operation
ON policy_recovery_resolutions(operation_id, resolved_at DESC);

DROP TABLE policy_recovery_resolutions__qualification_old;
DROP TABLE policy_activation_operations__qualification_old;
DROP TABLE policy_runtime_state__qualification_old;
DROP TABLE policy_revisions__qualification_old;
