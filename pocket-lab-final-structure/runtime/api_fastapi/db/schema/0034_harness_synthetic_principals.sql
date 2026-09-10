-- Synthetic machine principals for the explicitly enabled qualification
-- harness. These records are intentionally separate from human identities,
-- credentials, memberships, and browser sessions.

CREATE TABLE synthetic_principals (
    principal_id TEXT PRIMARY KEY,
    principal_type TEXT NOT NULL DEFAULT 'synthetic_machine'
        CHECK (principal_type = 'synthetic_machine'),
    principal_class TEXT NOT NULL
        CHECK (principal_class IN ('debug', 'test', 'qualification', 'maintenance')),
    display_name TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1 CHECK (enabled IN (0, 1)),
    environment_scope TEXT NOT NULL,
    target_scope TEXT NOT NULL
        CHECK (target_scope = 'local_server_host_only'),
    allowed_profiles_json TEXT NOT NULL,
    default_profile TEXT NOT NULL,
    algorithm TEXT NOT NULL DEFAULT 'ed25519'
        CHECK (algorithm = 'ed25519'),
    public_key TEXT NOT NULL,
    public_key_fingerprint TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT,
    revoke_reason TEXT NOT NULL DEFAULT ''
);

CREATE INDEX idx_synthetic_principals_status
    ON synthetic_principals(enabled, revoked_at, expires_at);

CREATE TABLE harness_challenges (
    challenge_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    nonce_hash TEXT NOT NULL UNIQUE,
    signing_payload_hash TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    purpose TEXT NOT NULL,
    requested_profile TEXT NOT NULL,
    target_scope TEXT NOT NULL
        CHECK (target_scope = 'local_server_host_only'),
    runtime_id TEXT NOT NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
    consumed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (principal_id) REFERENCES synthetic_principals(principal_id)
);

CREATE INDEX idx_harness_challenges_expiry
    ON harness_challenges(expires_at, consumed_at);

CREATE TABLE harness_sessions (
    harness_session_id TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL,
    principal_class TEXT NOT NULL,
    purpose TEXT NOT NULL,
    capability_profile TEXT NOT NULL,
    capabilities_json TEXT NOT NULL,
    target_scope TEXT NOT NULL
        CHECK (target_scope = 'local_server_host_only'),
    runtime_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    started_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_used_at TEXT,
    destructive_allowed INTEGER NOT NULL DEFAULT 0 CHECK (destructive_allowed IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'expired', 'revoked')),
    revoked_at TEXT,
    revoke_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (principal_id) REFERENCES synthetic_principals(principal_id)
);

CREATE INDEX idx_harness_sessions_status
    ON harness_sessions(status, expires_at, principal_id);

CREATE TABLE harness_audit_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    occurred_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    principal_id TEXT,
    principal_class TEXT,
    harness_session_id TEXT,
    purpose TEXT,
    capability TEXT,
    target_scope TEXT,
    environment TEXT NOT NULL,
    operation_id TEXT,
    result TEXT NOT NULL,
    summary TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    FOREIGN KEY (principal_id) REFERENCES synthetic_principals(principal_id)
);

CREATE INDEX idx_harness_audit_events_time
    ON harness_audit_events(occurred_at DESC, event_id DESC);

CREATE INDEX idx_harness_audit_events_session
    ON harness_audit_events(harness_session_id, occurred_at DESC, event_id DESC);
