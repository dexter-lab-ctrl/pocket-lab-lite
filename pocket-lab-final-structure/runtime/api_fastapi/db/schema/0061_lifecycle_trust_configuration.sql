-- Durable opt-in latch, independent of successful release acceptance.
CREATE TABLE lite_release_trust_configuration (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    root_sha256 TEXT NOT NULL,
    attestation_root_sha256 TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('configured','suspended')),
    revision INTEGER NOT NULL CHECK(revision>0)
);
CREATE TABLE lite_release_trust_transitions (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    state TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    release_tag TEXT NOT NULL
);
