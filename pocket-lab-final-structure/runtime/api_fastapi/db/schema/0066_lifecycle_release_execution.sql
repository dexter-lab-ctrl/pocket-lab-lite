-- Exact candidate preparation grant. This does not confer native cutover
-- authority: the external promotion and recovery signatures remain separate.
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
    state TEXT NOT NULL CHECK(state IN ('pending','claimed','prepared','cutover_claimed','rehearsed','failed','revoked')),
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
CREATE UNIQUE INDEX lite_lifecycle_release_execution_single_flight
ON lite_lifecycle_release_execution(executor_principal)
WHERE state IN ('pending','claimed','prepared','cutover_claimed');
CREATE INDEX lite_lifecycle_release_execution_history
ON lite_lifecycle_release_execution(issued_at DESC);
