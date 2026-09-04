-- Defense in depth for independent device-removal approvals.
--
-- Existing legacy rows are intentionally preserved so they remain observable and
-- can be evidence-preservingly cancelled by reconciliation.  These triggers only
-- prevent new invalid continuations from being persisted after this migration.

CREATE TRIGGER IF NOT EXISTS trg_policy_approvals_delegated_requester_insert
BEFORE INSERT ON policy_approvals
WHEN NEW.action_id = 'device.remove'
  AND (
    NEW.initiating_role NOT IN ('Admin', 'Operator')
    OR NOT EXISTS (
      SELECT 1
      FROM enterprise_configuration c
      WHERE c.configuration_id = 1 AND c.enabled = 1
    )
    OR NOT EXISTS (
      SELECT 1
      FROM enterprise_memberships m
      JOIN human_identities h ON h.human_id = m.human_id
      WHERE m.human_id = NEW.initiating_human_id
        AND m.status = 'active'
        AND m.role = NEW.initiating_role
        AND h.status = 'active'
    )
  )
BEGIN
  SELECT RAISE(ABORT, 'policy_approval_requester_invalid');
END;

CREATE TRIGGER IF NOT EXISTS trg_policy_approvals_delegated_requester_update
BEFORE UPDATE OF initiating_human_id, initiating_role, action_id ON policy_approvals
WHEN NEW.action_id = 'device.remove'
  AND (
    NEW.initiating_role NOT IN ('Admin', 'Operator')
    OR NOT EXISTS (
      SELECT 1
      FROM enterprise_configuration c
      WHERE c.configuration_id = 1 AND c.enabled = 1
    )
    OR NOT EXISTS (
      SELECT 1
      FROM enterprise_memberships m
      JOIN human_identities h ON h.human_id = m.human_id
      WHERE m.human_id = NEW.initiating_human_id
        AND m.status = 'active'
        AND m.role = NEW.initiating_role
        AND h.status = 'active'
    )
  )
BEGIN
  SELECT RAISE(ABORT, 'policy_approval_requester_invalid');
END;
