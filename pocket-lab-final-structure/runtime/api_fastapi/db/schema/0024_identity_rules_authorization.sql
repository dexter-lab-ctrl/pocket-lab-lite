CREATE TABLE IF NOT EXISTS human_identities (
    human_id TEXT PRIMARY KEY,
    username_normalized TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    auth_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_authenticated_at TEXT
);

CREATE TABLE IF NOT EXISTS human_credentials (
    credential_id TEXT PRIMARY KEY,
    human_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    verifier TEXT NOT NULL,
    salt TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    rotated_at TEXT,
    disabled_at TEXT,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_human_credentials_active_password
ON human_credentials(human_id, kind) WHERE disabled_at IS NULL;

CREATE TABLE IF NOT EXISTS auth_sessions (
    session_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_hash TEXT NOT NULL,
    human_id TEXT NOT NULL,
    auth_version INTEGER NOT NULL,
    auth_method TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    idle_expires_at TEXT NOT NULL,
    absolute_expires_at TEXT NOT NULL,
    revoked_at TEXT,
    revoke_reason TEXT,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_human_active
ON auth_sessions(human_id, revoked_at, absolute_expires_at);

CREATE TABLE IF NOT EXISTS recovery_code_batches (
    batch_id TEXT PRIMARY KEY,
    human_id TEXT NOT NULL,
    generation INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    invalidated_at TEXT,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_recovery_code_batch_generation
ON recovery_code_batches(human_id, generation);

CREATE TABLE IF NOT EXISTS recovery_codes (
    code_id TEXT PRIMARY KEY,
    batch_id TEXT NOT NULL,
    code_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    consumed_at TEXT,
    FOREIGN KEY(batch_id) REFERENCES recovery_code_batches(batch_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_recovery_codes_batch_active
ON recovery_codes(batch_id, consumed_at);

CREATE TABLE IF NOT EXISTS identity_audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    human_id TEXT,
    session_id TEXT,
    event_type TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    summary TEXT NOT NULL,
    correlation_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_identity_audit_recent
ON identity_audit_events(event_id DESC);

CREATE TABLE IF NOT EXISTS policy_decisions (
    decision_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    decision_id TEXT NOT NULL UNIQUE,
    correlation_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    target_revision TEXT NOT NULL,
    allow INTEGER NOT NULL,
    reason_code TEXT NOT NULL,
    policy_revision TEXT NOT NULL,
    evaluation_ms REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_policy_decisions_recent
ON policy_decisions(decision_row_id DESC);
CREATE INDEX IF NOT EXISTS idx_policy_decisions_action
ON policy_decisions(action_id, decision_row_id DESC);
