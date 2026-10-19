-- Short-lived, server-owned automation-client pairing requests.
-- A pending pairing has no requester authority.  It becomes an active client
-- only in the same transaction as a real Owner decision.

CREATE TABLE IF NOT EXISTS owner_operation_client_pairings (
    pairing_id TEXT PRIMARY KEY
        CHECK (pairing_id GLOB 'ocp-*' AND length(pairing_id) = 28),
    client_id TEXT NOT NULL
        CHECK (length(client_id) BETWEEN 3 AND 80),
    display_name TEXT NOT NULL
        CHECK (length(display_name) BETWEEN 1 AND 120),
    public_key TEXT NOT NULL,
    public_key_fingerprint TEXT NOT NULL,
    capabilities_json TEXT NOT NULL
        CHECK (capabilities_json = '["photo_backup.bounded_acceptance.v1"]'),
    pairing_binding_digest TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'registered', 'rejected', 'expired', 'cancelled')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    reviewed_by_human_id TEXT,
    reviewed_at TEXT,
    approval_assurance_ref TEXT,
    registered_at TEXT,
    terminal_reason TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (reviewed_by_human_id) REFERENCES human_identities(human_id)
);

CREATE INDEX IF NOT EXISTS idx_owner_operation_client_pairings_lifecycle
    ON owner_operation_client_pairings(status, expires_at, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_owner_operation_client_pairings_client
    ON owner_operation_client_pairings(client_id, created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_owner_operation_client_pairings_active_key
    ON owner_operation_client_pairings(public_key_fingerprint)
    WHERE status IN ('pending', 'registered');

CREATE TABLE IF NOT EXISTS owner_operation_client_pairing_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    pairing_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor_type TEXT NOT NULL
        CHECK (actor_type IN ('requester', 'owner', 'system')),
    actor_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    reason_code TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    FOREIGN KEY (pairing_id) REFERENCES owner_operation_client_pairings(pairing_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_owner_operation_client_pairing_events_pairing
    ON owner_operation_client_pairing_events(pairing_id, event_id DESC);
