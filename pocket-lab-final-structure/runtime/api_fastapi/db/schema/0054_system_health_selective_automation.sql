-- No policy is seeded, enabled, or promoted by this migration.
CREATE TABLE lite_system_health_automation_policy (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    revision INTEGER NOT NULL CHECK(revision>0),
    enabled INTEGER NOT NULL CHECK(enabled IN (0,1)),
    owner_id TEXT NOT NULL,
    owner_auth_version INTEGER NOT NULL,
    membership_version INTEGER NOT NULL,
    configuration_version INTEGER NOT NULL,
    policy_revision TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE lite_system_health_automation_attempts (
    attempt_id TEXT PRIMARY KEY,
    policy_version INTEGER NOT NULL,
    operation_id TEXT NOT NULL CHECK(operation_id='projection.reconcile'),
    status TEXT NOT NULL CHECK(status IN ('pending','verified','unavailable')),
    requested_at TEXT NOT NULL,
    completed_at TEXT,
    decision_id TEXT NOT NULL
);
CREATE UNIQUE INDEX lite_system_health_auto_singleflight ON lite_system_health_automation_attempts((1)) WHERE status='pending';
CREATE INDEX lite_system_health_auto_recent ON lite_system_health_automation_attempts(requested_at DESC);
