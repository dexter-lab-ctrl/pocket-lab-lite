-- Server-owned, single-use Owner approvals.  This contract deliberately does
-- not share the Enterprise continuation-approval table: a registered
-- automation client is not an Enterprise person, and this operation has a
-- different requester/approver/executor lifecycle.

CREATE TABLE IF NOT EXISTS owner_operation_clients (
    client_id TEXT PRIMARY KEY
        CHECK (length(client_id) BETWEEN 3 AND 80),
    display_name TEXT NOT NULL
        CHECK (length(display_name) BETWEEN 1 AND 120),
    public_key TEXT NOT NULL,
    public_key_fingerprint TEXT NOT NULL UNIQUE,
    capabilities_json TEXT NOT NULL
        CHECK (capabilities_json = '["photo_backup.bounded_acceptance.v1"]'),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'revoked')),
    created_by_human_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    last_used_at TEXT,
    revoked_at TEXT,
    revoke_reason TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (created_by_human_id) REFERENCES human_identities(human_id)
);

CREATE INDEX IF NOT EXISTS idx_owner_operation_clients_status
    ON owner_operation_clients(status, expires_at, created_at DESC);

CREATE TABLE IF NOT EXISTS owner_operation_challenges (
    challenge_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    purpose TEXT NOT NULL
        CHECK (purpose IN ('client_registration', 'request', 'observe', 'cancel')),
    operation_id TEXT,
    binding_json TEXT NOT NULL,
    binding_digest TEXT NOT NULL,
    signing_payload_json TEXT NOT NULL,
    nonce_hash TEXT NOT NULL UNIQUE,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    failed_attempts INTEGER NOT NULL DEFAULT 0
        CHECK (failed_attempts >= 0),
    consumed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_owner_operation_challenges_expiry
    ON owner_operation_challenges(expires_at, consumed_at, client_id);

CREATE TABLE IF NOT EXISTS owner_approved_operations (
    operation_id TEXT PRIMARY KEY,
    contract_version INTEGER NOT NULL DEFAULT 1
        CHECK (contract_version = 1),
    operation_type TEXT NOT NULL
        CHECK (operation_type = 'photo_backup.bounded_acceptance.v1'),
    requester_client_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    target_identity_revision INTEGER NOT NULL
        CHECK (target_identity_revision >= 1),
    target_binding_digest TEXT NOT NULL,
    destination_id TEXT NOT NULL
        CHECK (destination_id = 'server-photoprism-originals'),
    destination_contract_version INTEGER NOT NULL
        CHECK (destination_contract_version >= 1),
    descriptor_json TEXT NOT NULL,
    scope_json TEXT NOT NULL,
    scope_digest TEXT NOT NULL,
    reason TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL
        CHECK (status IN ('created', 'pending_approval', 'approved', 'executing', 'verifying',
                          'completed', 'rejected', 'expired', 'cancelled', 'failed', 'blocked')),
    created_at TEXT NOT NULL,
    approval_deadline TEXT NOT NULL,
    approved_by_human_id TEXT,
    approved_at TEXT,
    approval_assurance_ref TEXT,
    execution_deadline TEXT,
    execution_stage TEXT NOT NULL DEFAULT 'awaiting_approval',
    fixture_id TEXT,
    backup_id TEXT,
    repeat_backup_id TEXT,
    terminal_reason TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '{}',
    updated_at TEXT NOT NULL,
    UNIQUE (requester_client_id, idempotency_key),
    FOREIGN KEY (requester_client_id) REFERENCES owner_operation_clients(client_id),
    FOREIGN KEY (approved_by_human_id) REFERENCES human_identities(human_id)
);

CREATE INDEX IF NOT EXISTS idx_owner_approved_operations_lifecycle
    ON owner_approved_operations(status, approval_deadline, execution_deadline, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_owner_approved_operations_requester
    ON owner_approved_operations(requester_client_id, created_at DESC);

CREATE TABLE IF NOT EXISTS owner_operation_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    actor_type TEXT NOT NULL
        CHECK (actor_type IN ('requester', 'owner', 'executor', 'observer', 'system')),
    actor_id TEXT NOT NULL DEFAULT '',
    event_type TEXT NOT NULL,
    reason_code TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (operation_id) REFERENCES owner_approved_operations(operation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_owner_operation_events_operation
    ON owner_operation_events(operation_id, event_id DESC);
