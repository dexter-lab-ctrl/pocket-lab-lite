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

-- The raw connect claim is single-use. The service first exchanges its hash for
-- a short-lived HTTP-only enrollment authority. Once consumed, replace the
-- reusable lookup hash with a non-secret deterministic tombstone so replaying
-- the original URL can no longer resolve the claim while the authority cookie
-- can still complete the passkey ceremony.
CREATE TRIGGER IF NOT EXISTS trg_human_enrollment_claim_single_use
AFTER UPDATE OF consumed_at ON human_enrollment_claims
WHEN OLD.consumed_at IS NULL AND NEW.consumed_at IS NOT NULL
BEGIN
    UPDATE human_enrollment_claims
    SET claim_hash = 'consumed:' || NEW.claim_id
    WHERE claim_id = NEW.claim_id;
END;
