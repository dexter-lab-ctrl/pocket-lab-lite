-- Allow the coordinated owner to record a verified live qualification
-- terminal state. The prior migration intentionally admitted rehearsal only;
-- this forward-only rebuild preserves every row and keeps the single-flight
-- index unchanged while adding the separately verified disposition.
PRAGMA foreign_keys=OFF;
ALTER TABLE lite_lifecycle_release_execution RENAME TO lite_lifecycle_release_execution_0069_previous;
CREATE TABLE lite_lifecycle_release_execution (
    grant_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    metadata_sha256 TEXT NOT NULL,
    executor_principal TEXT NOT NULL CHECK(executor_principal='release-reconciler'),
    binding_json TEXT NOT NULL,
    binding_sha256 TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('pending','claimed','prepared','cutover_claimed','rehearsed','committed','failed','revoked')),
    command_id TEXT,
    lease_generation INTEGER,
    worker_generation TEXT,
    claim_decision_id TEXT,
    handoff_sha256 TEXT,
    cutover_authorization_sha256 TEXT,
    revoked_at TEXT,
    reason_code TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
INSERT INTO lite_lifecycle_release_execution(
    grant_id,owner_id,metadata_sha256,executor_principal,binding_json,binding_sha256,
    decision_id,issued_at,expires_at,state,command_id,lease_generation,worker_generation,
    claim_decision_id,handoff_sha256,cutover_authorization_sha256,revoked_at,reason_code,updated_at
)
SELECT grant_id,owner_id,metadata_sha256,executor_principal,binding_json,binding_sha256,
    decision_id,issued_at,expires_at,state,command_id,lease_generation,worker_generation,
    claim_decision_id,handoff_sha256,cutover_authorization_sha256,revoked_at,reason_code,updated_at
FROM lite_lifecycle_release_execution_0069_previous;
DROP TABLE lite_lifecycle_release_execution_0069_previous;
CREATE UNIQUE INDEX lite_lifecycle_release_execution_single_flight
ON lite_lifecycle_release_execution(executor_principal)
WHERE state IN ('pending','claimed','prepared','cutover_claimed');
CREATE INDEX lite_lifecycle_release_execution_history
ON lite_lifecycle_release_execution(issued_at DESC);
PRAGMA foreign_keys=ON;
