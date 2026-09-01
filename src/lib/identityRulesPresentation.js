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

function identityFreshness({ savedStateOnly = false, backendReachable = true, lastUpdatedLabel = '', isExpired = false } = {}) {
  if (savedStateOnly || !backendReachable) {
    return {
      label: 'Saved information',
      detail: `${isExpired ? 'Older saved state' : lastUpdatedLabel || 'Live status unavailable'}`,
      state: isExpired ? 'stale' : 'saved',
    };
  }
  return null;
}

/**
 * Maps only the prepared Identity read into the default Access Center story.
 * Browser WebAuthn support is deliberately an input, not identity authority.
 */
export function buildLiteIdentityAccessOverview(identity, {
  savedStateOnly = false,
  backendReachable = true,
  lastUpdatedLabel = '',
  isExpired = false,
  passkeyEligible = false,
  claimActive = false,
} = {}) {
  const source = identity && typeof identity === 'object' ? identity : null;
  const passkeys = Array.isArray(source?.passkeys) ? source.passkeys : [];
  const sessions = Array.isArray(source?.sessions) ? source.sessions : [];
  const activePasskeys = passkeys.filter((item) => item?.active);
  const activeSessions = sessions.filter((item) => item?.active);
  const recoveryConfigured = typeof source?.recovery?.configured === 'boolean' ? source.recovery.configured : null;
  const enterpriseEnabled = typeof source?.enterprise?.enabled === 'boolean' ? source.enterprise.enabled : null;
  const freshness = identityFreshness({ savedStateOnly, backendReachable, lastUpdatedLabel, isExpired });
  const knownAuthentication = typeof source?.authenticated === 'boolean';
  const knownSetup = typeof source?.setup_required === 'boolean';
  const isSaved = Boolean(savedStateOnly || (!backendReachable && source));

  let workspaceStory;
  if (isSaved) {
    workspaceStory = {
      state: isExpired ? 'stale' : 'saved',
      tone: isExpired ? 'stale' : 'saved',
      headline: 'Showing saved access information',
      summary: 'Live authentication and session status cannot currently be confirmed.',
      consequence: 'Protected changes still require the live server.',
      freshness,
      nextAction: { id: 'refresh', label: 'Refresh access' },
    };
  } else if (!source || (!knownAuthentication && !knownSetup)) {
    workspaceStory = {
      state: 'unknown',
      tone: 'unknown',
      headline: 'Access status is not confirmed yet',
      summary: 'Pocket Lab is still checking the prepared access state.',
      freshness,
    };
  } else if (source.setup_required) {
    workspaceStory = claimActive && passkeyEligible
      ? {
          state: 'setup',
          tone: 'review',
          headline: 'Owner setup needed',
          summary: 'Create the local Pocket Lab owner with a passkey.',
          consequence: 'The owner claim remains server-verified until setup completes.',
          freshness,
          nextAction: { id: 'create_owner', label: 'Create Owner' },
        }
      : {
          state: 'setup',
          tone: 'review',
          headline: 'Owner setup needed',
          summary: 'Open a trusted owner setup link to continue.',
          consequence: passkeyEligible ? 'A passkey is the recommended way to protect local access.' : 'Passkeys are not available in this browser; the supported fallback remains available below.',
          freshness,
        };
  } else if (source.authenticated === false && source.owner) {
    const canUsePasskey = source?.sign_in_methods?.passkey === true && passkeyEligible;
    workspaceStory = {
      state: 'signed_out',
      tone: 'attention',
      headline: 'Sign in before making protected changes',
      summary: canUsePasskey ? 'Use your passkey for normal Pocket Lab access.' : 'A supported sign-in method is required before protected changes.',
      freshness,
      nextAction: canUsePasskey ? { id: 'sign_in_passkey', label: 'Sign in with Passkey' } : null,
    };
  } else if (source.authenticated === true) {
    const missingPasskey = activePasskeys.length === 0;
    const recoveryNeedsAttention = recoveryConfigured === false;
    workspaceStory = missingPasskey
      ? {
          state: 'signed_in',
          tone: 'review',
          headline: 'Signed in — add a passkey',
          summary: 'Passkeys are the recommended way to sign in and confirm sensitive changes.',
          freshness,
          nextAction: passkeyEligible ? { id: 'add_passkey', label: 'Add Passkey' } : null,
        }
      : recoveryNeedsAttention
        ? {
            state: 'signed_in',
            tone: 'review',
            headline: 'Signed in — set up recovery',
            summary: 'A recovery set helps restore owner access if normal sign-in is unavailable.',
            freshness,
            nextAction: { id: 'review_recovery', label: 'Review Recovery' },
          }
        : {
            state: 'signed_in',
            tone: 'ready',
            headline: 'Signed in with protected local access',
            summary: 'Your passkey, sessions, and recovery state are available to review.',
            freshness,
          };
  } else {
    workspaceStory = {
      state: 'unknown',
      tone: 'unknown',
      headline: 'Access status is not confirmed yet',
      summary: 'Pocket Lab did not provide enough prepared Identity state to determine sign-in status.',
      freshness,
    };
  }

  const previous = isSaved ? 'Previously known ' : '';
  const keyAreas = [
    {
      key: 'passkeys',
      label: 'Passkeys',
      value: source ? (activePasskeys.length ? `${activePasskeys.length} active` : 'Not set up') : 'Unknown',
      summary: source ? (activePasskeys.length ? `${previous}passkeys can protect sign-in and sensitive confirmation.` : 'Add a passkey to use the preferred sign-in path.') : 'Passkey state is not available yet.',
      attention: Boolean(source && activePasskeys.length === 0),
    },
    {
      key: 'sessions',
      label: 'Sessions',
      value: source ? `${activeSessions.length} active` : 'Unknown',
      summary: source ? `${previous}current and other sessions stay separate.` : 'Session state is not available yet.',
      attention: false,
    },
    {
      key: 'recovery',
      label: 'Recovery',
      value: recoveryConfigured === true ? 'Ready' : recoveryConfigured === false ? 'Needs attention' : 'Unknown',
      summary: recoveryConfigured === true ? `${previous}recovery codes are configured.` : recoveryConfigured === false ? 'Create or review recovery codes before relying on them.' : 'Recovery state is not available yet.',
      attention: recoveryConfigured === false,
    },
    {
      key: 'enterprise',
      label: 'Enterprise Mode',
      value: enterpriseEnabled === true ? 'Enabled' : enterpriseEnabled === false ? 'Personal Mode' : 'Unknown',
      summary: enterpriseEnabled === true ? `${previous}server-managed membership and role are available in Manage access.` : enterpriseEnabled === false ? 'Personal access remains the default experience.' : 'Enterprise Mode state is not available yet.',
      attention: false,
    },
  ];

  return { workspaceStory, keyAreas };
}

export const IDENTITY_RULES_PRESENTATION_READY = true;
