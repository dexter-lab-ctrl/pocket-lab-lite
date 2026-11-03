// Access presentation is derived exclusively from the Identity API read.
// This module has no credential, authorization, persistence or mutation authority.
import { identityActivityView } from './identityPremiumView.js';

export function accessCenterReadiness(view, data) {
  if (!view?.signedIn) return { state: 'signed-out', title: 'Sign-in required', detail: 'Sign in to review current access.' };
  if (!view.fresh) return { state: 'saved', title: 'Showing saved access information', detail: 'Protected changes are unavailable until the server confirms your access.' };
  if (data?.person?.password_change_required === true || data?.owner?.password_change_required === true) {
    return { state: 'attention', title: 'Password change required', detail: 'Review account settings for the next sign-in step.' };
  }
  if (view.passkeys === 0) return { state: 'attention', title: 'Sign-in protection needs attention', detail: 'No active passkeys were reported for this account.' };
  if (view.recoveryConfigured === false) return { state: 'attention', title: 'Recovery is not configured', detail: 'Review account recovery to protect future access.' };
  if (view.passkeys == null || view.sessions == null || view.recoveryConfigured == null ||
    view.role === 'Unavailable' || view.mode === 'Unavailable') {
    return { state: 'unavailable', title: 'Access information unavailable', detail: 'Pocket Lab has not confirmed every protection detail.' };
  }
  if (view.passkeys > 0 && view.sessions > 0 && view.recoveryConfigured === true) {
    return { state: 'ready', title: 'Access is ready', detail: 'Passkeys, active sessions and recovery were reported by Pocket Lab.' };
  }
  return { state: 'attention', title: 'Sign-in protection needs attention', detail: 'Review your active sessions and sign-in methods.' };
}

export function accessCenterProtectionRows(view) {
  return [
    { id: 'passkeys', title: 'Passkeys', description: view.passkeys == null ? 'Not reported' : view.passkeys === 1 ? '1 active' : `${view.passkeys} active` },
    { id: 'sessions', title: 'Sessions', description: view.sessions == null ? 'Not reported' : view.sessions === 1 ? '1 active' : `${view.sessions} active` },
    { id: 'recovery', title: 'Account recovery', description: view.recoveryConfigured == null ? 'Not reported' : view.recoveryConfigured ? 'Configured' : 'Not configured' },
  ];
}

export function accessCenterLatestActivity(data) {
  return identityActivityView(data?.recent_activity).slice(0, 1)[0] || null;
}

export function accessManageGroups({ enterpriseEnabled = false, hasApprovals = false, hasClients = false } = {}) {
  return [
    { label: 'Your account', items: [
      { id: 'overview', label: 'Overview', description: 'Account and protection status', icon: 'user' },
      { id: 'passkeys', label: 'Passkeys', description: 'Trusted sign-in methods', icon: 'fingerprint' },
      { id: 'sessions', label: 'Sessions', description: 'Signed-in devices', icon: 'monitor' },
      { id: 'recovery', label: 'Recovery', description: 'Codes and password', icon: 'key' },
    ] },
    { label: 'Activity', items: [
      { id: 'activity', label: 'Access activity', description: 'Recent account changes', icon: 'activity' },
      ...(hasApprovals ? [{ id: 'approvals', label: 'Pending approvals', description: 'Requests awaiting your decision', icon: 'shield' }] : []),
      ...(hasClients ? [{ id: 'automation', label: 'Trusted automation clients', description: 'Authorized local clients', icon: 'shield' }] : []),
    ] },
    { label: 'Access management', items: [
      ...(enterpriseEnabled ? [
        { id: 'people', label: 'People & roles', description: 'Enterprise identities', icon: 'users' },
        { id: 'roles', label: 'Roles & Access', description: 'Server-reported capabilities', icon: 'shield' },
      ] : []),
      { id: 'settings', label: 'Access settings', description: 'Mode and preferences', icon: 'settings' },
    ] },
  ];
}
