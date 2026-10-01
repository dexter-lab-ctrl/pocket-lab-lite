-- Governed multi-role fleet join and capability authorization.
--
-- device_enrollment_registry.role remains a compatibility projection only.
-- Authoritative device-role assignment, desired/active convergence and role-change
-- lifecycle live in the normalized tables below.

CREATE TABLE IF NOT EXISTS device_role_assignments (
    device_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('compute','storage')),
    desired INTEGER NOT NULL DEFAULT 0 CHECK(desired IN (0,1)),
    active INTEGER NOT NULL DEFAULT 0 CHECK(active IN (0,1)),
    assignment_status TEXT NOT NULL DEFAULT 'pending',
    generation INTEGER NOT NULL DEFAULT 0 CHECK(generation >= 0),
    assigned_at TEXT,
    assigned_by_human_id TEXT NOT NULL DEFAULT '',
    authorization_version INTEGER NOT NULL DEFAULT 1 CHECK(authorization_version >= 1),
    policy_revision TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    verification_status TEXT NOT NULL DEFAULT 'pending',
    verification_reason TEXT NOT NULL DEFAULT '',
    verified_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(device_id, role)
);
CREATE INDEX IF NOT EXISTS idx_device_role_assignments_desired
    ON device_role_assignments(device_id, desired, generation DESC);
CREATE INDEX IF NOT EXISTS idx_device_role_assignments_active
    ON device_role_assignments(role, active, device_id);

CREATE TABLE IF NOT EXISTS device_role_change_operations (
    change_id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    generation INTEGER NOT NULL CHECK(generation >= 1),
    requested_roles_json TEXT NOT NULL CHECK(length(requested_roles_json) <= 512),
    previous_roles_json TEXT NOT NULL DEFAULT '[]' CHECK(length(previous_roles_json) <= 512),
    status TEXT NOT NULL,
    reason_code TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    requested_by_human_id TEXT NOT NULL DEFAULT '',
    requested_by_role TEXT NOT NULL DEFAULT '',
    authorization_version INTEGER NOT NULL DEFAULT 1 CHECK(authorization_version >= 1),
    policy_revision TEXT NOT NULL DEFAULT '',
    correlation_id TEXT NOT NULL DEFAULT '',
    request_fingerprint TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(device_id, generation)
);
CREATE INDEX IF NOT EXISTS idx_device_role_change_status
    ON device_role_change_operations(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_device_role_change_device
    ON device_role_change_operations(device_id, generation DESC);

-- Backfill only the two joinable legacy roles. Server Host remains protected and
-- is projected directly from the local control-plane identity rather than made
-- joinable through this relation.
INSERT OR IGNORE INTO device_role_assignments(
    device_id,role,desired,active,assignment_status,generation,assigned_at,
    assigned_by_human_id,authorization_version,policy_revision,correlation_id,
    verification_status,verification_reason,verified_at,updated_at
)
SELECT device_id, role, 1,
       CASE WHEN last_known_state IN ('online','healthy','active','ready') THEN 1 ELSE 0 END,
       'legacy_compatibility', 1, enrolled_at, 'system:migration', 1, '',
       'legacy-role-compatibility',
       CASE WHEN last_known_state IN ('online','healthy','active','ready') THEN 'verified' ELSE 'stale' END,
       CASE WHEN last_known_state IN ('online','healthy','active','ready') THEN '' ELSE 'device_capability_stale' END,
       CASE WHEN last_known_state IN ('online','healthy','active','ready') THEN last_seen_at ELSE NULL END,
       updated_at
FROM device_enrollment_registry
WHERE removal_status='active' AND protected_server_host=0 AND role IN ('compute','storage');

-- Generalize the existing server-owned continuation store so the same approval
-- path can bind fleet role elevation as well as device removal.
DROP TRIGGER IF EXISTS trg_policy_approvals_delegated_requester_insert;
DROP TRIGGER IF EXISTS trg_policy_approvals_delegated_requester_update;
DROP INDEX IF EXISTS idx_policy_approvals_pending;
DROP INDEX IF EXISTS idx_policy_approvals_scope;
ALTER TABLE policy_approvals RENAME TO policy_approvals_legacy_0037;

CREATE TABLE policy_approvals (
    approval_id TEXT PRIMARY KEY,
    originating_decision_id TEXT NOT NULL UNIQUE,
    correlation_id TEXT NOT NULL,
    action_id TEXT NOT NULL CHECK(action_id IN ('device.remove','device.invite','device.roles.change')),
    target_type TEXT NOT NULL CHECK(target_type='device'),
    target_id TEXT NOT NULL,
    target_revision TEXT NOT NULL DEFAULT '',
    initiating_human_id TEXT NOT NULL,
    initiating_role TEXT NOT NULL,
    initiating_authorization_version INTEGER NOT NULL DEFAULT 1 CHECK(initiating_authorization_version >= 1),
    request_fingerprint TEXT NOT NULL DEFAULT '',
    required_approver_roles_json TEXT NOT NULL,
    required_assurance TEXT NOT NULL,
    policy_revision TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','cancelled','expired','consumed','invalidated')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    approved_at TEXT, approved_by_human_id TEXT,
    rejected_at TEXT, rejected_by_human_id TEXT,
    cancelled_at TEXT, cancelled_by_human_id TEXT,
    consumed_at TEXT,
    reason_code TEXT NOT NULL DEFAULT '',
    evidence_ref TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(initiating_human_id) REFERENCES human_identities(human_id),
    FOREIGN KEY(approved_by_human_id) REFERENCES human_identities(human_id)
);

INSERT INTO policy_approvals(
    approval_id,originating_decision_id,correlation_id,action_id,target_type,target_id,target_revision,
    initiating_human_id,initiating_role,initiating_authorization_version,request_fingerprint,
    required_approver_roles_json,required_assurance,policy_revision,status,created_at,expires_at,
    approved_at,approved_by_human_id,rejected_at,rejected_by_human_id,cancelled_at,cancelled_by_human_id,
    consumed_at,reason_code,evidence_ref
)
SELECT legacy.approval_id,legacy.originating_decision_id,legacy.correlation_id,legacy.action_id,
       legacy.target_type,legacy.target_id,
       COALESCE((SELECT d.target_revision FROM policy_decisions d WHERE d.decision_id=legacy.originating_decision_id),''),
       legacy.initiating_human_id,legacy.initiating_role,1,
       COALESCE((SELECT d.target_revision FROM policy_decisions d WHERE d.decision_id=legacy.originating_decision_id),''),
       legacy.required_approver_roles_json,legacy.required_assurance,legacy.policy_revision,legacy.status,
       legacy.created_at,legacy.expires_at,legacy.approved_at,legacy.approved_by_human_id,
       legacy.rejected_at,legacy.rejected_by_human_id,legacy.cancelled_at,legacy.cancelled_by_human_id,
       legacy.consumed_at,legacy.reason_code,legacy.evidence_ref
FROM policy_approvals_legacy_0037 AS legacy;
DROP TABLE policy_approvals_legacy_0037;

CREATE INDEX idx_policy_approvals_pending ON policy_approvals(status, expires_at, created_at DESC);
CREATE INDEX idx_policy_approvals_scope
    ON policy_approvals(initiating_human_id,action_id,target_id,target_revision,policy_revision,status);

CREATE TRIGGER trg_policy_approvals_delegated_requester_insert
BEFORE INSERT ON policy_approvals
WHEN NEW.initiating_role NOT IN ('Admin','Operator')
  OR NOT EXISTS (
      SELECT 1 FROM enterprise_configuration c
      WHERE c.configuration_id=1 AND c.enabled=1
  )
  OR NOT EXISTS (
      SELECT 1 FROM enterprise_memberships m
      JOIN human_identities h ON h.human_id=m.human_id
      WHERE m.human_id=NEW.initiating_human_id
        AND m.status='active' AND m.role=NEW.initiating_role AND h.status='active'
  )
BEGIN
    SELECT RAISE(ABORT, 'policy_approval_requester_invalid');
END;

CREATE TRIGGER trg_policy_approvals_delegated_requester_update
BEFORE UPDATE OF initiating_human_id,initiating_role,action_id ON policy_approvals
WHEN NEW.initiating_role NOT IN ('Admin','Operator')
BEGIN
    SELECT RAISE(ABORT, 'policy_approval_requester_invalid');
END;
