CREATE TABLE IF NOT EXISTS policy_approvals (
    approval_id TEXT PRIMARY KEY,
    originating_decision_id TEXT NOT NULL UNIQUE,
    correlation_id TEXT NOT NULL,
    action_id TEXT NOT NULL CHECK (action_id = 'device.remove'),
    target_type TEXT NOT NULL CHECK (target_type = 'device'),
    target_id TEXT NOT NULL,
    initiating_human_id TEXT NOT NULL,
    initiating_role TEXT NOT NULL,
    required_approver_roles_json TEXT NOT NULL,
    required_assurance TEXT NOT NULL CHECK (required_assurance = 'policy.approval.device.remove'),
    policy_revision TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending','approved','rejected','cancelled','expired','consumed','invalidated')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    approved_at TEXT, approved_by_human_id TEXT,
    rejected_at TEXT, rejected_by_human_id TEXT,
    cancelled_at TEXT, cancelled_by_human_id TEXT,
    consumed_at TEXT,
    reason_code TEXT NOT NULL DEFAULT '', evidence_ref TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(initiating_human_id) REFERENCES human_identities(human_id),
    FOREIGN KEY(approved_by_human_id) REFERENCES human_identities(human_id)
);
CREATE INDEX IF NOT EXISTS idx_policy_approvals_pending ON policy_approvals(status, expires_at, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_policy_approvals_scope ON policy_approvals(initiating_human_id, action_id, target_id, policy_revision, status);

CREATE TABLE IF NOT EXISTS policy_continuation_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('approval','exception')),
    subject_id TEXT NOT NULL,
    actor_human_id TEXT,
    event_type TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    summary TEXT NOT NULL,
    correlation_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_policy_continuation_events_subject ON policy_continuation_events(kind, subject_id, event_id DESC);

CREATE TABLE IF NOT EXISTS policy_temporary_exceptions (
    exception_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL CHECK (action_id = 'catalog.install'),
    app_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    human_id TEXT NOT NULL,
    policy_revision TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_by_human_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active','revoked','expired','consumed')),
    created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
    revoked_at TEXT, revoked_by_human_id TEXT,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id),
    FOREIGN KEY(created_by_human_id) REFERENCES human_identities(human_id)
);
CREATE INDEX IF NOT EXISTS idx_policy_exceptions_scope ON policy_temporary_exceptions(human_id, action_id, app_id, device_id, policy_revision, status, expires_at);
