CREATE TABLE IF NOT EXISTS human_enrollment_claims (
    claim_id TEXT PRIMARY KEY,
    claim_hash TEXT NOT NULL UNIQUE,
    human_id TEXT NOT NULL,
    created_by_human_id TEXT NOT NULL,
    requested_role TEXT NOT NULL,
    installation_id TEXT NOT NULL,
    rp_id TEXT NOT NULL,
    origin TEXT NOT NULL,
    webauthn_user_handle TEXT NOT NULL,
    authority_hash TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    authority_expires_at TEXT,
    completed_at TEXT,
    revoked_at TEXT,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id),
    FOREIGN KEY(created_by_human_id) REFERENCES human_identities(human_id)
);

CREATE INDEX IF NOT EXISTS idx_human_enrollment_claim_hash
ON human_enrollment_claims(claim_hash);

CREATE INDEX IF NOT EXISTS idx_human_enrollment_claim_human
ON human_enrollment_claims(human_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_human_enrollment_claim_expiry
ON human_enrollment_claims(expires_at, completed_at, revoked_at);
