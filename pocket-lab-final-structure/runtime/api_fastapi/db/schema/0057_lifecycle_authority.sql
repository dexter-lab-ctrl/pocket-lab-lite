-- Local boundary and scoped standing consent, separate from human sessions.
-- No default grants. The binding remains local to this database identity.
CREATE TABLE lite_lifecycle_workspace (
    singleton_id INTEGER PRIMARY KEY CHECK(singleton_id=1),
    workspace_id TEXT NOT NULL UNIQUE,
    boundary_revision INTEGER NOT NULL DEFAULT 0 CHECK(boundary_revision>=0)
);
INSERT INTO lite_lifecycle_workspace(singleton_id,workspace_id) VALUES(1,lower(hex(randomblob(16))));
CREATE TABLE lite_lifecycle_grants (
    grant_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL REFERENCES lite_lifecycle_workspace(workspace_id),
    boundary_revision INTEGER NOT NULL CHECK(boundary_revision>0),
    owner_id TEXT NOT NULL REFERENCES human_identities(human_id),
    owner_auth_version INTEGER NOT NULL,
    membership_version INTEGER NOT NULL,
    configuration_version INTEGER NOT NULL,
    profile_revision INTEGER NOT NULL,
    registry_revision TEXT NOT NULL,
    trust_version INTEGER NOT NULL,
    root_version INTEGER NOT NULL,
    policy_revision TEXT NOT NULL,
    capability_id TEXT NOT NULL,
    capability_version INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    channel TEXT NOT NULL CHECK(channel='stable'),
    scope_json TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    UNIQUE(workspace_id,boundary_revision,capability_id,purpose)
);
CREATE INDEX idx_lite_lifecycle_grants_current ON lite_lifecycle_grants(workspace_id,revoked_at,expires_at);
