-- Universal App Platform governance continuations and credential metadata.
-- Rebuild existing continuation tables so app-resource approvals/exceptions
-- remain exact-action, exact-target and exact-contract-revision scoped.

DROP TRIGGER IF EXISTS trg_policy_approvals_delegated_requester_insert;
DROP TRIGGER IF EXISTS trg_policy_approvals_delegated_requester_update;
DROP INDEX IF EXISTS idx_policy_approvals_pending;
DROP INDEX IF EXISTS idx_policy_approvals_scope;
ALTER TABLE policy_approvals RENAME TO policy_approvals_legacy_0039;

CREATE TABLE policy_approvals (
    approval_id TEXT PRIMARY KEY,
    originating_decision_id TEXT NOT NULL UNIQUE,
    correlation_id TEXT NOT NULL,
    action_id TEXT NOT NULL CHECK(action_id IN ('device.remove','device.invite','device.roles.change','app.remove')),
    target_type TEXT NOT NULL CHECK(target_type IN ('device','app')),
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
FROM policy_approvals_legacy_0039;
DROP TABLE policy_approvals_legacy_0039;

CREATE INDEX idx_policy_approvals_pending ON policy_approvals(status, expires_at, created_at DESC);
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
    SELECT RAISE(ABORT, 'policy_approval_requester_invalid');
END;

CREATE TRIGGER trg_policy_approvals_delegated_requester_update
BEFORE UPDATE OF initiating_human_id,initiating_role,action_id,target_type ON policy_approvals
WHEN NEW.initiating_role NOT IN ('Admin','Operator')
BEGIN
    SELECT RAISE(ABORT, 'policy_approval_requester_invalid');
END;

DROP INDEX IF EXISTS idx_policy_exceptions_scope;
ALTER TABLE policy_temporary_exceptions RENAME TO policy_temporary_exceptions_legacy_0039;

CREATE TABLE policy_temporary_exceptions (
    exception_id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL CHECK(action_id IN ('catalog.install','app.install')),
    app_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    human_id TEXT NOT NULL,
    required_capability TEXT NOT NULL DEFAULT '',
    target_revision TEXT NOT NULL DEFAULT '',
    policy_revision TEXT NOT NULL,
    reason TEXT NOT NULL,
    created_by_human_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('active','revoked','expired','consumed')),
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    revoked_by_human_id TEXT,
    FOREIGN KEY(human_id) REFERENCES human_identities(human_id),
    FOREIGN KEY(created_by_human_id) REFERENCES human_identities(human_id)
);

INSERT INTO policy_temporary_exceptions(
    exception_id,action_id,app_id,device_id,human_id,required_capability,target_revision,
    policy_revision,reason,created_by_human_id,status,created_at,expires_at,revoked_at,revoked_by_human_id
)
SELECT exception_id,
       CASE WHEN action_id='catalog.install' THEN 'app.install' ELSE action_id END,
       app_id,device_id,human_id,'install','',policy_revision,reason,created_by_human_id,
       status,created_at,expires_at,revoked_at,revoked_by_human_id
FROM policy_temporary_exceptions_legacy_0039;
DROP TABLE policy_temporary_exceptions_legacy_0039;

CREATE INDEX idx_policy_exceptions_scope
    ON policy_temporary_exceptions(human_id,action_id,app_id,device_id,required_capability,target_revision,policy_revision,status,expires_at);

CREATE TABLE IF NOT EXISTS app_credential_metadata (
    app_id TEXT NOT NULL,
    credential_id TEXT NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('configured','missing','needs_rotation','invalid','external_manual','not_required')),
    management TEXT NOT NULL CHECK(management IN ('pocket_lab_metadata','external_or_manual')),
    last_verified_at TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(app_id,credential_id)
);
CREATE INDEX IF NOT EXISTS idx_app_credential_status
    ON app_credential_metadata(app_id,status,updated_at DESC);
