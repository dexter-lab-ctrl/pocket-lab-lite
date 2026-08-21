CREATE TABLE IF NOT EXISTS enterprise_configuration (
    configuration_id INTEGER PRIMARY KEY CHECK (configuration_id = 1),
    enabled INTEGER NOT NULL DEFAULT 0 CHECK (enabled IN (0, 1)),
    authorization_version INTEGER NOT NULL DEFAULT 1,
    enabled_at TEXT,
    disabled_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by_human_id TEXT,
    FOREIGN KEY(updated_by_human_id) REFERENCES human_identities(human_id)
);

CREATE TABLE IF NOT EXISTS enterprise_memberships (
    human_id TEXT PRIMARY KEY,
    role TEXT NOT NULL CHECK (role IN ('Owner', 'Admin', 'Operator', 'Viewer', 'Auditor')),
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'removed')),
    authorization_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    created_by_human_id TEXT,
    updated_by_human_id TEXT,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id) ON DELETE RESTRICT,
    FOREIGN KEY(created_by_human_id) REFERENCES human_identities(human_id),
    FOREIGN KEY(updated_by_human_id) REFERENCES human_identities(human_id)
);
CREATE INDEX IF NOT EXISTS idx_enterprise_memberships_active_role
ON enterprise_memberships(status, role, updated_at);
