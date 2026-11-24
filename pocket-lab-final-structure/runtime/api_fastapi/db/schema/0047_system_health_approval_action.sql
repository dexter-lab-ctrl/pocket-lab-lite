-- Extend the existing Enterprise approval continuation store for the one
-- qualified System Health action. All other approval semantics remain shared.
DROP TRIGGER IF EXISTS trg_policy_approvals_delegated_requester_insert;
DROP TRIGGER IF EXISTS trg_policy_approvals_delegated_requester_update;
DROP INDEX IF EXISTS idx_policy_approvals_pending;
DROP INDEX IF EXISTS idx_policy_approvals_scope;
ALTER TABLE policy_approvals RENAME TO policy_approvals_legacy_0047;

CREATE TABLE policy_approvals (
    approval_id TEXT PRIMARY KEY,
    originating_decision_id TEXT NOT NULL UNIQUE,
    correlation_id TEXT NOT NULL,
    action_id TEXT NOT NULL CHECK(action_id IN ('device.remove','device.invite','device.roles.change','app.remove','system_health.recovery')),
    target_type TEXT NOT NULL CHECK(target_type IN ('device','app','system_health_incident')),
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
SELECT approval_id,originating_decision_id,correlation_id,action_id,target_type,target_id,target_revision,
       initiating_human_id,initiating_role,initiating_authorization_version,request_fingerprint,
       required_approver_roles_json,required_assurance,policy_revision,status,created_at,expires_at,
       approved_at,approved_by_human_id,rejected_at,rejected_by_human_id,cancelled_at,cancelled_by_human_id,
       consumed_at,reason_code,evidence_ref
FROM policy_approvals_legacy_0047;
DROP TABLE policy_approvals_legacy_0047;

CREATE INDEX idx_policy_approvals_pending ON policy_approvals(status,expires_at,created_at DESC);
CREATE INDEX idx_policy_approvals_scope
    ON policy_approvals(initiating_human_id,action_id,target_type,target_id,target_revision,policy_revision,status);

CREATE TRIGGER trg_policy_approvals_delegated_requester_insert
BEFORE INSERT ON policy_approvals
WHEN NEW.initiating_role NOT IN ('Admin','Operator')
  OR NOT EXISTS (SELECT 1 FROM enterprise_configuration c WHERE c.configuration_id=1 AND c.enabled=1)
  OR NOT EXISTS (
      SELECT 1 FROM enterprise_memberships m
      JOIN human_identities h ON h.human_id=m.human_id
      WHERE m.human_id=NEW.initiating_human_id
        AND m.status='active' AND m.role=NEW.initiating_role AND h.status='active'
  )
BEGIN
    SELECT RAISE(ABORT,'policy_approval_requester_invalid');
END;

CREATE TRIGGER trg_policy_approvals_delegated_requester_update
BEFORE UPDATE OF initiating_human_id,initiating_role,action_id,target_type ON policy_approvals
WHEN NEW.initiating_role NOT IN ('Admin','Operator')
BEGIN
    SELECT RAISE(ABORT,'policy_approval_requester_invalid');
END;
