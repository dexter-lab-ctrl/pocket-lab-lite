// Pure presentation selectors. Identity, membership and authorization remain server-owned.
export const IDENTITY_MANAGE_SECTIONS = Object.freeze([
  ['overview', 'Overview'], ['passkeys', 'Passkeys'], ['sessions', 'Sessions'],
  ['recovery', 'Recovery'], ['activity', 'Activity'], ['settings', 'Settings'],
]);
export const IDENTITY_ENTERPRISE_SECTIONS = Object.freeze([['people', 'People'], ['roles', 'Roles & Access']]);

const eventFamilies = Object.freeze({
  sign_in: 'sign-ins', sign_out: 'sign-ins', login: 'sign-ins', logout: 'sign-ins',
  passkey_added: 'access', passkey_removed: 'access', passkey_renamed: 'access',
  session_revoked: 'access', recovery_generated: 'access', recovery_used: 'access',
  membership_changed: 'access', role_changed: 'access', mode_changed: 'access',
});
const outcomes = new Set(['allowed', 'approved', 'denied', 'blocked', 'failed', 'pending', 'completed', 'revoked']);

const countActive = (value) => Array.isArray(value) ? value.filter((item) => item?.active === true).length : null;
export function identityPremiumProjection(data, { fresh = true } = {}) {
  const current = Array.isArray(data?.sessions) ? data.sessions.find((item) => item?.current === true && item?.active === true) : null;
  const recovery = data?.recovery;
  const remaining = Number.isInteger(recovery?.remaining) && recovery.remaining >= 0 ? recovery.remaining : null;
  const role = data?.enterprise?.current_membership?.role || data?.person?.role || (data?.person?.is_local_owner || data?.owner?.human_id ? 'Owner' : null);
  const signedIn = data?.authenticated === true;
  const mode = typeof data?.enterprise?.enabled === 'boolean' ? (data.enterprise.enabled ? 'Enterprise Mode' : 'Personal Mode') : 'Unavailable';
  const reportedAuth = typeof current?.auth_method === 'string' && ['passkey', 'password', 'recovery', 'session'].includes(current.auth_method)
    ? current.auth_method : null;
  return {
    name: data?.person?.display_name || data?.owner?.display_name || 'Pocket Lab person',
    role: role || 'Unavailable',
    mode,
    signedIn,
    authentication: reportedAuth ? ({ passkey: 'Passkey', password: 'Password', recovery: 'Recovery', session: 'Session' })[reportedAuth] : 'Not reported',
    passkeys: countActive(data?.passkeys),
    sessions: countActive(data?.sessions),
    currentSessionKnown: Boolean(current),
    recoveryConfigured: typeof recovery?.configured === 'boolean' ? recovery.configured : null,
    remaining,
    fresh: Boolean(fresh),
  };
}
export function identityJourneyStages(view) {
  const unavailable = !view.fresh || !view.signedIn;
  return [
    { id: 'identity', title: 'Identity', value: view.name, detail: view.role, state: unavailable ? 'saved' : 'confirmed' },
    { id: 'authentication', title: 'Authentication', value: view.authentication, detail: view.passkeys == null ? 'Passkeys unavailable' : view.passkeys + ' active passkeys', state: unavailable ? 'saved' : view.passkeys === 0 ? 'attention' : view.authentication === 'Not reported' ? 'unavailable' : 'confirmed' },
    { id: 'authorization', title: 'Authorization', value: view.mode, detail: view.role, state: unavailable ? 'saved' : view.role === 'Unavailable' ? 'unavailable' : 'confirmed' },
    { id: 'recovery', title: 'Recovery', value: view.recoveryConfigured === true ? 'Configured' : view.recoveryConfigured === false ? 'Not configured' : 'Unavailable', detail: view.remaining == null ? 'Code count unavailable' : view.remaining + ' unused codes', state: unavailable ? 'saved' : view.recoveryConfigured === true ? 'confirmed' : view.recoveryConfigured === false ? 'attention' : 'unavailable' },
  ];
}
export function identityActivityView(items) {
  if (!Array.isArray(items)) return [];
  return items.slice(0, 30).map((event, index) => {
    // Only explicit normalized backend fields; never guess event families from free-form summaries.
    const type = typeof event?.event_type === 'string' ? event.event_type : typeof event?.type === 'string' ? event.type : '';
    const family = eventFamilies[type] || 'other';
    const result = outcomes.has(event?.outcome) ? event.outcome : 'Not reported';
    const timestamp = typeof event?.occurred_at === 'string' ? event.occurred_at : '';
    return {
      key: [event?.correlation_id || event?.event_id || '', timestamp, type, index].join(':'),
      family, type, title: typeof event?.summary === 'string' ? event.summary : 'Access activity',
      outcome: result, timestamp,
      reasonCode: typeof event?.reason_code === 'string' ? event.reason_code : '',
      // No payload, actor, credential identifiers, environment or raw audit evidence carried into the view.
    };
  });
}
export function identityDecisionLabel(value) {
  return ({ allow: 'Direct', approval: 'Requires review', step_up: 'Passkey confirmation', temporary_access: 'Temporary access', deny: 'Blocked', blocked: 'Blocked' })[value] || 'Not reported';
}
