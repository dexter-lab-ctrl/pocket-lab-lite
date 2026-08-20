CREATE TABLE IF NOT EXISTS owner_claims (
    claim_id TEXT PRIMARY KEY,
    claim_hash TEXT NOT NULL UNIQUE,
    installation_id TEXT NOT NULL,
    rp_id TEXT NOT NULL,
    origin TEXT NOT NULL,
    webauthn_user_handle TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    authority_hash TEXT UNIQUE,
    authority_expires_at TEXT,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_owner_claims_active
ON owner_claims(expires_at, consumed_at, completed_at);

CREATE TABLE IF NOT EXISTS webauthn_users (
    human_id TEXT PRIMARY KEY,
    user_handle TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS webauthn_credentials (
    credential_id TEXT PRIMARY KEY,
    human_id TEXT NOT NULL,
    friendly_name TEXT NOT NULL,
    public_key_x TEXT NOT NULL,
    public_key_y TEXT NOT NULL,
    algorithm INTEGER NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    transports_json TEXT NOT NULL DEFAULT '[]',
    authenticator_attachment TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_webauthn_credentials_human_active
ON webauthn_credentials(human_id, revoked_at, created_at);

CREATE TABLE IF NOT EXISTS webauthn_challenges (
    challenge_id TEXT PRIMARY KEY,
    challenge_hash TEXT NOT NULL UNIQUE,
    purpose TEXT NOT NULL,
    human_id TEXT,
    session_id TEXT,
    owner_claim_id TEXT,
    rp_id TEXT NOT NULL,
    origin TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id) ON DELETE CASCADE,
    FOREIGN KEY(session_id) REFERENCES auth_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(owner_claim_id) REFERENCES owner_claims(claim_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_webauthn_challenges_expiry
ON webauthn_challenges(expires_at, consumed_at);

CREATE TABLE IF NOT EXISTS auth_session_assurance (
    assurance_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    credential_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    satisfied_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES auth_sessions(session_id) ON DELETE CASCADE,
    FOREIGN KEY(credential_id) REFERENCES webauthn_credentials(credential_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_auth_session_assurance_current
ON auth_session_assurance(session_id, purpose, expires_at);

CREATE TABLE IF NOT EXISTS policy_decision_details (
    decision_id TEXT PRIMARY KEY,
    constraints_json TEXT NOT NULL DEFAULT '[]',
    evidence_ref TEXT,
    FOREIGN KEY(decision_id) REFERENCES policy_decisions(decision_id) ON DELETE CASCADE
);
