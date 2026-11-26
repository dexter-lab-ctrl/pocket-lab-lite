-- One independently provisioned root pin. Rotation requires a future explicit contract.
CREATE TABLE IF NOT EXISTS lite_release_trust_pin (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    root_sha256 TEXT NOT NULL,
    root_version INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS lite_release_trust_observation (
    singleton_id INTEGER PRIMARY KEY CHECK (singleton_id = 1),
    state TEXT NOT NULL CHECK (state IN ('trust_setup_required','metadata_unavailable','verification_failed','historical_evidence')),
    reason_code TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    release_tag TEXT NOT NULL
);
