const REASON_PRESENTATIONS = {
  passkey_step_up_required: {
    title: 'Confirm with your passkey',
    message: 'This sensitive change needs a recent passkey confirmation before Pocket Lab can continue.',
    tone: 'review',
  },
  approval_step_up_required: {
    title: 'Confirm with your passkey',
    message: 'Approving a protected device removal needs a recent passkey confirmation.',
    tone: 'review',
  },
  approval_required: {
    title: 'Approval required',
    message: 'Another active Owner or Admin needs to approve this protected device removal.',
    tone: 'review',
  },
  approval_self_forbidden: {
    title: 'Another person must approve',
    message: 'The person who requested this removal cannot approve their own request.',
    tone: 'blocked',
  },
  approval_approver_role_required: {
    title: 'Owner or Admin required',
    message: 'Only an active Enterprise Owner or Admin can approve or reject this request.',
    tone: 'blocked',
  },
  approval_unusable: {
    title: 'Approval no longer available',
    message: 'This approval is no longer pending. Review the latest request before taking action.',
    tone: 'neutral',
  },
  approval_continuation_unavailable: {
    title: 'Approval can no longer continue',
    message: 'The independent approval is no longer valid or has already been used. Request a new approval.',
    tone: 'blocked',
  },
  exception_scope_invalid: {
    title: 'Choose an exact scope',
    message: 'Temporary exceptions must target one exact app, device and active person. Wildcards and global scope are not allowed.',
    tone: 'blocked',
  },
  exception_identity_unknown: {
    title: 'Person is not available',
    message: 'Choose an active Pocket Lab person for this temporary exception.',
    tone: 'blocked',
  },
  exception_unusable: {
    title: 'Exception is no longer active',
    message: 'This temporary exception is expired or revoked and cannot be used.',
    tone: 'neutral',
  },
  policy_revision_uncertain: {
    title: 'Rules need attention',
    message: 'Pocket Lab cannot prove which Safety Rules revision is active, so protected changes remain blocked.',
    tone: 'degraded',
  },
  policy_revision_unavailable: {
    title: 'Rules revision unavailable',
    message: 'A proved active Safety Rules revision is required before this protected change can continue.',
    tone: 'degraded',
  },
  policy_activation_uncertain: {
    title: 'Rules need attention',
    message: 'The last Rules activation could not be proved. Pocket Lab keeps protected changes blocked until recovery is verified.',
    tone: 'degraded',
  },
  policy_activation_degraded: {
    title: 'Rules need attention',
    message: 'The Rules activation path is degraded. Protected changes remain fail-closed.',
    tone: 'degraded',
  },
  policy_recovery_required: {
    title: 'Rules recovery required',
    message: 'Pocket Lab needs a server-proved Rules recovery before protected changes can resume.',
    tone: 'degraded',
  },
  enterprise_rules_role_required: {
    title: 'Your role cannot do this',
    message: 'Your current Enterprise role does not have permission for this Rules action.',
    tone: 'blocked',
  },
  enterprise_owner_required: {
    title: 'Owner required',
    message: 'An active Enterprise Owner is required for this access change.',
    tone: 'blocked',
  },
  enterprise_final_owner_protected: {
    title: 'Keep one active Owner',
    message: 'Pocket Lab must retain at least one active Enterprise Owner.',
    tone: 'blocked',
  },
};

const STATUS_PRESENTATIONS = {
  ready: { label: 'Ready', tone: 'healthy' },
  healthy: { label: 'Ready', tone: 'healthy' },
  active: { label: 'Active', tone: 'healthy' },
  approved: { label: 'Approved', tone: 'healthy' },
  consumed: { label: 'Consumed', tone: 'neutral' },
  pending: { label: 'Waiting', tone: 'review' },
  waiting: { label: 'Waiting', tone: 'review' },
  review: { label: 'Needs attention', tone: 'review' },
  blocked: { label: 'Blocked', tone: 'blocked' },
  degraded: { label: 'Degraded', tone: 'degraded' },
  unavailable: { label: 'Degraded', tone: 'degraded' },
  failed: { label: 'Needs attention', tone: 'degraded' },
  rejected: { label: 'Rejected', tone: 'degraded' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
  revoked: { label: 'Revoked', tone: 'neutral' },
  expired: { label: 'Expired', tone: 'neutral' },
  inactive: { label: 'Inactive', tone: 'neutral' },
};

export function getLiteReasonPresentation(reasonCode, fallback = '') {
  const code = String(reasonCode || '').trim();
  if (REASON_PRESENTATIONS[code]) return { code, ...REASON_PRESENTATIONS[code] };
  const readable = code
    ? code.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase())
    : 'No additional reason';
  return {
    code,
    title: fallback || readable,
    message: fallback || readable,
    tone: 'neutral',
  };
}

export function getLiteStatusPresentation(status, fallback = 'Unknown') {
  const normalized = String(status || '').trim().toLowerCase();
  return STATUS_PRESENTATIONS[normalized] || {
    label: normalized ? normalized.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase()) : fallback,
    tone: 'neutral',
  };
}

export function getApprovalPresentation(approval = {}) {
  const status = getLiteStatusPresentation(approval.status, 'Unknown');
  const actions = approval.viewer_actions || {};
  const eligibleApprovers = Number(approval.eligible_approver_count || 0);
  let guidance = 'Review the exact action, target and Rules revision before continuing.';
  if (approval.status === 'pending' && approval.viewer_relationship === 'requester') {
    guidance = eligibleApprovers > 0
      ? 'Another Owner or Admin needs to approve this. You cannot approve your own request.'
      : 'Another Owner or Admin is required before this protected removal can continue.';
  } else if (approval.status === 'pending' && actions.approve) {
    guidance = 'You can review this independent request. Approval requires passkey confirmation.';
  } else if (approval.status === 'approved') {
    guidance = 'Approved. The original requester must retry the exact protected action before this approval expires.';
  } else if (approval.status === 'consumed') {
    guidance = 'This approval was already used for one execution attempt and cannot be replayed.';
  }
  return { ...status, guidance, actions, eligibleApprovers };
}

export function shortRevision(value) {
  const revision = String(value || '').trim();
  if (!revision) return 'Unavailable';
  if (revision.length <= 22) return revision;
  return `${revision.slice(0, 12)}…${revision.slice(-6)}`;
}

export function identityActionStageLabel(stage = '') {
  return ({
    preparing: 'Preparing…',
    pending: 'Waiting for Pocket Lab…',
    accepted: 'Server accepted',
    verifying: 'Verifying…',
    completed: 'Completed',
    blocked: 'Blocked',
    failed: 'Failed',
  })[stage] || '';
}

export const IDENTITY_RULES_PRESENTATION_READY = true;
