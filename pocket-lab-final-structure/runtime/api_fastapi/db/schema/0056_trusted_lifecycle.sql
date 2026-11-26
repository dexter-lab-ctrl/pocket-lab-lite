-- Independent, default-off lifecycle preferences and historical trust evidence.
-- No row is seeded with standing consent. Existing release identity and recovery
-- activation are intentionally not changed.
CREATE TABLE lite_lifecycle_preferences (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    revision INTEGER NOT NULL CHECK(revision>0),
    profile TEXT NOT NULL CHECK(profile IN ('notify','security','recommended','enterprise_managed')),
    updated_at TEXT NOT NULL,
    owner_id TEXT NOT NULL
);
CREATE TABLE lite_lifecycle_audit (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    correlation_id TEXT NOT NULL UNIQUE,
    owner_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    revision INTEGER NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE TABLE lite_release_trust_floor (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    metadata_version INTEGER NOT NULL CHECK(metadata_version>0),
    root_version INTEGER NOT NULL CHECK(root_version>0),
    metadata_sha256 TEXT NOT NULL,
    release_tag TEXT NOT NULL
);
CREATE TABLE lite_release_trust_receipts (
    receipt_id TEXT PRIMARY KEY,
    metadata_version INTEGER NOT NULL UNIQUE,
    root_version INTEGER NOT NULL,
    release_tag TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    receipt_json TEXT NOT NULL
);
