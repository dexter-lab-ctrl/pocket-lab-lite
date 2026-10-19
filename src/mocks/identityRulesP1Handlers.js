import { http, HttpResponse } from 'msw';

// Keep Identity screenshots and fixture assertions reproducible across runs.
const MOCK_NOW_MS = Date.parse('2026-09-24T08:54:00.000Z');
const now = () => new Date(MOCK_NOW_MS).toISOString();
const future = (ms) => new Date(MOCK_NOW_MS + ms).toISOString();
const scenario = () => (typeof window !== 'undefined' ? window.localStorage.getItem('POCKETLAB_MOCK_SCENARIO') || 'identity-summary' : 'identity-summary');

function enterpriseRole() {
  const value = scenario();
  if (value.includes('admin')) return 'Admin';
  if (value.includes('operator') || value === 'rules-approval-required') return 'Operator';
  if (value.includes('auditor')) return 'Auditor';
  if (value.includes('viewer')) return 'Viewer';
  return 'Owner';
}

function enterpriseEnabled() {
  const value = scenario();
  return value.includes('enterprise') || value === 'identity-role-aware-fixture' || value === 'rules-approval-required';
}

const OWNER_OPERATION_DISCLOSURES = [
  'Target: Secondary Phone.',
  'Destination: PhotoPrism on this server.',
  'The server may create a persistent destination identity anchor if one is absent.',
  'One generated synthetic test photo may remain in the destination.',
  'The workflow includes one safe repeat of the same fixture.',
  'This approval expires and cannot authorize another request.',
];

function ownerOperation(operationId, status = 'pending_approval', overrides = {}) {
  return {
    operation_id: operationId,
    contract_version: 1,
    operation: 'photo_backup.bounded_acceptance.v1',
    status,
    requester_display_name: 'Registered qualification client',
    target_node_id: 'secondary-phone',
    target_label: 'Secondary Phone',
    destination: 'PhotoPrism on this server',
    scope: { fixture: 'one_server_generated_jpeg', collection: 'pictures', repeat: 'same_fixture_once' },
    reason: 'Production Photo Backup acceptance',
    approval_deadline: future(15 * 60 * 1000),
    execution_deadline: future(55 * 60 * 1000),
    execution_stage: status === 'executing' ? 'transfer' : status === 'verifying' ? 'verify' : status,
    disclosures: OWNER_OPERATION_DISCLOSURES,
    evidence: status === 'completed' ? { transfer: 'verified', indexing: 'unvalidated', repeat: 'verified' } : {},
    sanitized: true,
    ...overrides,
  };
}

function ownerClientPairing(pairingId, status = 'pending', overrides = {}) {
  return {
    pairing_id: pairingId,
    client_id: 'registered-qualification-client',
    display_name: 'Registered qualification client',
    public_key_fingerprint: 'sha256:0c0b0319cbdc382555faeb3dfd0d465870c6e6c287b2e81acd425f34ce6cf39d',
    capabilities: ['photo_backup.bounded_acceptance.v1'],
    status,
    created_at: now(),
    expires_at: future(15 * 60 * 1000),
    reviewed_at: status === 'registered' ? now() : null,
    registered_at: status === 'registered' ? now() : null,
    terminal_reason: status === 'expired' ? 'Pairing window expired.' : status === 'rejected' ? 'Rejected by Owner.' : null,
    updated_at: now(),
    sanitized: true,
    ...overrides,
  };
}

function ownerClient(clientId = 'registered-qualification-client', status = 'active', overrides = {}) {
  return {
    status,
    client_id: clientId,
    display_name: 'Registered qualification client',
    public_key_fingerprint: 'sha256:0c0b0319cbdc382555faeb3dfd0d465870c6e6c287b2e81acd425f34ce6cf39d',
    capabilities: ['photo_backup.bounded_acceptance.v1'],
    created_at: now(),
    expires_at: null,
    revoked_at: status === 'revoked' ? now() : null,
    sanitized: true,
    ...overrides,
  };
}

function ownerOperationsPayload() {
  const kind = scenario();
  const states = {
    'identity-owner-operation-pending': [ownerOperation('oo-mock-pending')],
    'identity-owner-operations-multiple': [ownerOperation('oo-mock-pending'), ownerOperation('oo-mock-pending-2', 'pending_approval', { requester_display_name: 'Registered backup client' })],
    'identity-owner-operation-expired': [ownerOperation('oo-mock-expired', 'expired', { terminal_reason: 'Approval window expired before a decision.' })],
    'identity-owner-operation-approved': [ownerOperation('oo-mock-approved', 'approved')],
    'identity-owner-operation-executing': [ownerOperation('oo-mock-executing', 'executing', { execution_stage: 'transfer' })],
    'identity-owner-operation-completed': [ownerOperation('oo-mock-completed', 'completed', { execution_stage: 'completed' })],
    'identity-owner-operation-failed': [ownerOperation('oo-mock-failed', 'failed', { terminal_reason: 'The bounded workflow stopped safely after a prerequisite failed.' })],
    'identity-owner-operation-offline': [ownerOperation('oo-mock-offline')],
  };
  const operations = states[kind] || [];
  const clientStates = {
    'identity-owner-client-pairing-pending': { pairings: [ownerClientPairing('ocp-mock-pending')], clients: [] },
    'identity-owner-client-registered': { pairings: [], clients: [ownerClient()] },
    'identity-owner-client-multiple': { pairings: [ownerClientPairing('ocp-mock-pending')], clients: [ownerClient()] },
    'identity-owner-client-expired': { pairings: [ownerClientPairing('ocp-mock-expired', 'expired')], clients: [] },
    'identity-owner-client-revoked': { pairings: [], clients: [ownerClient('registered-qualification-client', 'revoked')] },
    'identity-owner-client-offline': { pairings: [ownerClientPairing('ocp-mock-offline')], clients: [] },
  };
  const clients = clientStates[kind] || { pairings: [], clients: [] };
  return { status: kind === 'identity-owner-operation-offline' || kind === 'identity-owner-client-offline' ? 'saved' : 'ok', operations, ...clients, sanitized: true };
}

function identityPayload() {
  const enabled = enterpriseEnabled();
  const role = enabled ? enterpriseRole() : 'Owner';
  const payload = {
    status: 'ready',
    summary: enabled ? 'Your access is protected by server-side identity, role and Safety Rules checks.' : 'Owner access is protected by server-side sessions.',
    setup_required: false,
    authenticated: true,
    owner: enabled ? { configured: true, status: 'active' } : {
      human_id: 'human-owner', username: 'owner', display_name: 'Pocket Lab Owner', status: 'active', password_configured: true, password_algorithm: 'scrypt',
    },
    person: {
      human_id: role === 'Owner' ? 'human-owner' : `human-${role.toLowerCase()}`,
      username: role.toLowerCase(),
      display_name: role === 'Owner' ? 'Pocket Lab Owner' : `Alex ${role}`,
      status: 'active', role, is_local_owner: role === 'Owner', password_configured: role === 'Owner',
    },
    session: { session_id: 'sess-current', authenticated: true, auth_method: 'passkey', idle_expires_at: future(30 * 60 * 1000), absolute_expires_at: future(8 * 60 * 60 * 1000), expiry_mode: 'fixed', assurance: [] },
    sessions: [{ session_id: 'sess-current', auth_method: 'passkey', created_at: now(), absolute_expires_at: future(8 * 60 * 60 * 1000), active: true, current: true }],
    passkeys: [{ credential_id: 'mock-passkey', friendly_name: 'Primary passkey', authenticator_attachment: 'platform', created_at: now(), last_used_at: now(), active: true, transports: ['internal'] }],
    recovery: { configured: true, remaining: 8, generation: 1 },
    recent_activity: [{ occurred_at: now(), event_type: 'session.signed_in', reason_code: 'passkey_verified', summary: `${role} signed in with a passkey.`, correlation_id: 'mock-corr' }],
    sign_in_methods: { password: role === 'Owner', passkey: true, oidc: false },
    session_expiry_mode: 'fixed',
    enterprise: {
      enabled,
      authorization_version: 3,
      current_membership: enabled ? { role, active: true, authorization_version: 2 } : null,
      roles: ['Admin', 'Auditor', 'Operator', 'Owner', 'Viewer'],
      topology: { owners: 1, admins: 1, operators: 1, auditors: 1, viewers: 1, invited: 1, independent_approvers: 2 },
      updated_at: now(),
    },
    identity_classes: {
      human: { label: enabled ? 'People' : 'Owner', managed_by: 'Identity', configured: true },
      device: { label: 'Device identities', managed_by: 'Devices', summary: 'Device enrollment identity remains protected by the Devices flow.' },
      service: { label: 'Service identities', managed_by: 'Backend', summary: 'Service identities stay backend-owned.' },
    },
    updated_at: now(),
    owner_operations: ownerOperationsPayload(),
  };
  const kind = scenario();
  if (kind === 'identity-premium-signed-out') return { ...payload, authenticated: false, sessions: [], session: null };
  if (kind === 'identity-premium-first-owner') return { ...payload, setup_required: true, authenticated: false, owner: null, person: null, sessions: [], passkeys: [], recovery: { configured: false, remaining: null } };
  if (kind === 'identity-premium-enrollment') return { ...payload, authenticated: false, sessions: [], session: null };
  if (kind === 'identity-premium-no-passkeys') return { ...payload, passkeys: [] };
  if (kind === 'identity-premium-recovery-missing') return { ...payload, recovery: { configured: false, remaining: null } };
  if (kind === 'identity-premium-unavailable-facts') return { ...payload, passkeys: undefined, sessions: undefined, recovery: undefined };
  if (kind === 'identity-premium-multiple') return {
    ...payload,
    passkeys: [
      ...payload.passkeys,
      { credential_id: 'mock-second-passkey', friendly_name: 'Second passkey', created_at: now(), active: true },
    ],
    sessions: [
      ...payload.sessions,
      { session_id: 'sess-other', auth_method: 'password', active: true, current: false, absolute_expires_at: future(3600000) },
    ],
    recent_activity: [
      ...payload.recent_activity,
      { event_type: 'passkey.added', occurred_at: now(), summary: 'Passkey registered', outcome: 'completed', correlation_id: 'mock-event-2' },
      { event_type: 'identity.access_denied', occurred_at: now(), summary: 'Access denied', outcome: 'denied', reason_code: 'enterprise_owner_required', correlation_id: 'mock-event-3' },
    ],
  };
  if (kind === 'identity-premium-long-text') return {
    ...payload,
    person: { ...payload.person, display_name: 'Long identity name '.repeat(16) },
    passkeys: [{ ...payload.passkeys[0], friendly_name: 'Long passkey name '.repeat(15) }],
  };
  return payload;
}

const ROLE_SUMMARIES = {
  Owner: 'Full Pocket Lab authority. Owners do not need another person’s approval, but root-level changes can still require passkey confirmation.',
  Admin: 'Broad delegated administration. High-risk actions can require independent review.',
  Operator: 'Day-to-day operational access. Protected changes can require independent review.',
  Auditor: 'Read-only governance and evidence access, including non-executing Rules simulation.',
  Viewer: 'Read-only workspace evidence without administrative authority.',
};

function actionMode(action, role) {
  if (role === 'Owner') return ['rules.activate', 'rules.rollback', 'enterprise.mode.change', 'owner.operations.approve', 'owner.operations.client.register'].includes(action) ? 'step_up' : 'allow';
  if (role === 'Admin') {
    if (action === 'device.remove') return 'approval';
    return ['people.manage','catalog.install','app.install','rules.draft','rules.simulate','approvals.review','exceptions.manage','evidence.read'].includes(action) ? 'allow' : 'deny';
  }
  if (role === 'Operator') {
    if (action === 'device.remove') return 'approval';
    if (action === 'app.install') return 'temporary_access';
    return ['catalog.install','rules.simulate','evidence.read'].includes(action) ? 'allow' : 'deny';
  }
  if (role === 'Auditor') return ['rules.simulate','evidence.read'].includes(action) ? 'allow' : 'deny';
  return action === 'evidence.read' ? 'allow' : 'deny';
}

const ACTIONS = [
  ['people.manage','Manage people','Create, suspend, reactivate, remove and assign access to people.'],
  ['owner.operations.approve','Approve bounded operations','Approve one exact server-owned workflow after reviewing its target and scope.'],
  ['owner.operations.client.register','Register trusted automation client','Register one cryptographically verified requester with a fixed bounded-operation capability.'],
  ['enterprise.mode.change','Change workspace mode','Switch between Personal and Enterprise Mode.'],
  ['device.remove','Remove devices','Retire a confirmed non-server device from Pocket Lab.'],
  ['catalog.install','Install apps','Install an approved app through the server-owned execution path.'],
  ['app.install','Install app resource','Install a registered app through server-owned execution.'],
  ['rules.draft','Draft Rules','Create a typed immutable Rules candidate for review.'],
  ['rules.activate','Activate Rules','Activate a validated Rules revision through the supervisor-owned lifecycle.'],
  ['rules.rollback','Restore known-good Rules','Request restoration of the proved known-good Rules revision.'],
  ['rules.simulate','Test Rules','Run a non-executing Rules simulation.'],
  ['approvals.review','Review requests','Approve or reject another person’s protected request.'],
  ['exceptions.manage','Temporary access','Create and revoke narrow, expiring policy exceptions.'],
  ['evidence.read','Review activity','Read sanitized Identity and Rules evidence.'],
];

function accessPayload() {
  const role = enterpriseRole();
  const roles = ['Owner','Admin','Operator','Auditor','Viewer'];
  const capabilities = {};
  for (const [action] of ACTIONS) {
    const mode = actionMode(action, role);
    capabilities[action] = mode !== 'deny';
    capabilities[`${action}.mode`] = mode;
    capabilities[`${action}.requires_approval`] = mode === 'approval';
    capabilities[`${action}.requires_step_up`] = mode === 'step_up';
  }
  const appMode = role === 'Owner' || role === 'Admin' ? 'allow' : role === 'Operator' ? 'temporary_access' : 'deny';
  return {
    mode: enterpriseEnabled() ? 'enterprise' : 'personal', enterprise_enabled: enterpriseEnabled(), current_role: role, owner_authority: role === 'Owner',
    role: { id: role, label: role, summary: ROLE_SUMMARIES[role] },
    roles: roles.map((id) => ({ id, label: id, summary: ROLE_SUMMARIES[id] })),
    capabilities,
    policy_parameters: { admin_device_remove_approval: 1, operator_device_remove_approval: 1 },
    action_matrix: ACTIONS.map(([action_id,label,summary]) => ({ action_id, label, summary, roles: Object.fromEntries(roles.map((candidate) => [candidate, actionMode(action_id, candidate)])) })),
    app_resources: [{
      resource_type: 'app',
      app_id: 'photoprism',
      app_label: 'PhotoPrism',
      role,
      mode: 'enterprise',
      summary: role === 'Owner' ? 'You can manage this app.' : role === 'Viewer' ? 'Read-only access.' : 'Access follows current Safety Rules.',
      actions: [
        { action_id: 'app.open', mode: 'allow', allowed: true },
        { action_id: 'app.install', mode: appMode, allowed: appMode === 'allow', requires_temporary_access: appMode === 'temporary_access', temporary_access_supported: true },
        { action_id: 'app.remove', mode: role === 'Owner' ? 'allow' : role === 'Viewer' ? 'deny' : 'approval', allowed: role === 'Owner', requires_approval: !['Owner', 'Viewer'].includes(role) },
      ],
    }],
    topology: { active_people: 5, invited_people: 1, active_owners: 1, active_admins: 1, active_operators: 1, active_auditors: 1, active_viewers: 1, independent_approvers: 2 },
    summary: role === 'Owner' ? 'Owner has complete supported Pocket Lab authority without peer approval.' : 'Your server-resolved role and current Safety Rules determine what you can do.',
    updated_at: now(),
  };
}

function peoplePayload() {
  return {
    roles: ['Admin','Auditor','Operator','Owner','Viewer'],
    people: [
      { human_id: 'human-owner', username: 'owner', display_name: 'Pocket Lab Owner', status: 'active', role: 'Owner', membership_status: 'active', active_passkeys: 2, active_sessions: 1, recovery_codes_remaining: 8 },
      { human_id: 'human-admin', username: 'alex-admin', display_name: 'Alex Admin', status: 'active', role: 'Admin', membership_status: 'active', active_passkeys: 1, active_sessions: 1, recovery_codes_remaining: 7 },
      { human_id: 'human-operator', username: 'sam-operator', display_name: 'Sam Operator', status: 'active', role: 'Operator', membership_status: 'active', active_passkeys: 1, active_sessions: 0, recovery_codes_remaining: 8 },
      { human_id: 'human-auditor', username: 'avery-auditor', display_name: 'Avery Auditor', status: 'active', role: 'Auditor', membership_status: 'active', active_passkeys: 1, active_sessions: 0, recovery_codes_remaining: 8 },
      { human_id: 'human-viewer', username: 'victor-viewer', display_name: 'Victor Viewer', status: 'active', role: 'Viewer', membership_status: 'active', active_passkeys: 1, active_sessions: 0, recovery_codes_remaining: 8 },
      { human_id: 'human-invited', username: 'new-person', display_name: 'New Person', status: 'invited', role: 'Operator', membership_status: 'active', active_passkeys: 0, active_sessions: 0, recovery_codes_remaining: 0, invite: { claim_id: 'claim-existing', expires_at: future(10 * 60 * 1000) } },
    ],
  };
}

function approvalPayload() {
  const role = enterpriseRole();
  if (role === 'Viewer') return { approvals: [] };
  const requester = role === 'Operator';
  return { approvals: [{ approval_id: 'apr-mock', action_id: 'device.remove', target_id: 'old-phone', status: 'pending', initiating_role: 'Operator', required_assurance: 'policy.approval.device.remove', required_approver_roles: ['Admin','Owner'], policy_revision: 'mock-policy-revision', created_at: now(), expires_at: future(15 * 60 * 1000), viewer_relationship: requester ? 'requester' : ['Owner','Admin'].includes(role) ? 'reviewer' : 'observer', viewer_actions: { approve: ['Owner','Admin'].includes(role), reject: ['Owner','Admin'].includes(role), cancel: requester }, eligible_approver_count: 2 }] };
}

export const identityRulesP1Handlers = [
  http.get('/api/lite/identity', () => HttpResponse.json(identityPayload())),
  http.get('/api/lite/enterprise/identity/self', () => HttpResponse.json(identityPayload())),
  http.get('/api/lite/identity/owner-claim/status', () => HttpResponse.json({ active: false, status: 'owner_claim_authority_invalid' })),
  http.post('/api/lite/identity/owner-claim/consume', () => HttpResponse.json({ status: 'claim_verified', expires_at: future(5 * 60 * 1000), summary: 'Owner claim verified. Create a passkey to finish setup.' })),
  http.post('/api/lite/identity/owner-claim/passkey/options', () => HttpResponse.json({ publicKey: { challenge: 'bW9jay1jaGFsbGVuZ2U', rp: { name: 'Pocket Lab Lite', id: 'localhost' }, user: { id: 'bW9jay11c2Vy', name: 'owner', displayName: 'Pocket Lab Owner' }, pubKeyCredParams: [{ type: 'public-key', alg: -7 }] } })),
  http.post('/api/lite/identity/owner-claim/passkey/verify', () => HttpResponse.json({ ...identityPayload(), csrf_token: 'mock-csrf', recovery_codes: ['MOCK-RECOVERY-CODE'] }, { status: 201 })),

  http.get('/api/lite/enterprise/identity/enrollment/status', () => HttpResponse.json(['identity-enterprise-invited', 'identity-premium-enrollment'].includes(scenario()) ? { active: true, status: 'claim_verified', expires_at: future(5 * 60 * 1000), person: { display_name: 'New Person', username: 'new-person', role: 'Operator' }, summary: 'Connect link verified. Create a passkey to finish joining Pocket Lab.' } : { active: false, status: 'person_claim_authority_invalid' })),
  http.post('/api/lite/enterprise/identity/enrollment/consume', () => HttpResponse.json({ status: 'claim_verified', expires_at: future(5 * 60 * 1000), summary: 'Connect link verified.' })),
  http.post('/api/lite/enterprise/identity/enrollment/passkey/options', () => HttpResponse.json({ publicKey: { challenge: 'bW9jay1jaGFsbGVuZ2U', rp: { name: 'Pocket Lab Lite', id: 'localhost' }, user: { id: 'bW9jay11c2Vy', name: 'new-person', displayName: 'New Person' }, pubKeyCredParams: [{ type: 'public-key', alg: -7 }] } })),
  http.post('/api/lite/enterprise/identity/enrollment/passkey/verify', () => HttpResponse.json({ ...identityPayload(), csrf_token: 'mock-csrf', recovery_codes: ['MOCK-PERSON-RECOVERY'] }, { status: 201 })),

  http.post('/api/lite/enterprise/identity/passkeys/login/options', () => HttpResponse.json({ publicKey: { challenge: 'bW9jay1jaGFsbGVuZ2U', rpId: 'localhost', allowCredentials: [{ type: 'public-key', id: 'bW9jay1wYXNza2V5' }], userVerification: 'required' } })),
  http.post('/api/lite/enterprise/identity/passkeys/login/verify', () => HttpResponse.json({ ...identityPayload(), csrf_token: 'mock-csrf' })),
  http.post('/api/lite/identity/passkeys/login/options', () => HttpResponse.json({ publicKey: { challenge: 'bW9jay1jaGFsbGVuZ2U', rpId: 'localhost', allowCredentials: [{ type: 'public-key', id: 'bW9jay1wYXNza2V5' }], userVerification: 'required' } })),
  http.post('/api/lite/identity/passkeys/login/verify', () => HttpResponse.json({ ...identityPayload(), csrf_token: 'mock-csrf' })),
  http.post('/api/lite/identity/passkeys/registration/options', () => HttpResponse.json({ publicKey: { challenge: 'bW9jay1jaGFsbGVuZ2U', rp: { name: 'Pocket Lab Lite', id: 'localhost' }, user: { id: 'bW9jay11c2Vy', name: 'owner', displayName: 'Pocket Lab Owner' }, pubKeyCredParams: [{ type: 'public-key', alg: -7 }] } })),
  http.post('/api/lite/identity/passkeys/registration/verify', () => HttpResponse.json({ status: 'created', credential: { credential_id: 'mock-passkey-2', friendly_name: 'Passkey 2' }, summary: 'Passkey added.' }, { status: 201 })),
  http.post('/api/lite/identity/step-up/options', ({ request }) => request.json().then((payload) => HttpResponse.json({ purpose: payload.purpose, publicKey: { challenge: 'bW9jay1jaGFsbGVuZ2U', rpId: 'localhost', allowCredentials: [{ type: 'public-key', id: 'bW9jay1wYXNza2V5' }], userVerification: 'required' } }))),
  http.post('/api/lite/identity/step-up/verify', ({ request }) => request.json().then((payload) => HttpResponse.json({ status: 'satisfied', purpose: payload.purpose, expires_at: future(5 * 60 * 1000) }))),
  http.put('/api/lite/identity/passkeys/:credentialId', ({ params }) => HttpResponse.json({ status: 'renamed', credential_id: params.credentialId, friendly_name: 'Renamed passkey' })),
  http.delete('/api/lite/identity/passkeys/:credentialId', ({ params }) => HttpResponse.json({ status: 'revoked', credential_id: params.credentialId, summary: 'Passkey removed.' })),
  http.post('/api/lite/identity/recovery/regenerate', () => HttpResponse.json({ codes: ['MOCK-RECOVERY-ONE','MOCK-RECOVERY-TWO'], summary: 'New recovery codes generated.' })),
  http.post('/api/lite/identity/logout', () => HttpResponse.json({ status: 'signed_out', summary: 'Signed out of Pocket Lab.' })),
  http.post('/api/lite/identity/sessions/revoke-others', () => HttpResponse.json({ status: 'completed', revoked_sessions: 1, summary: 'Other sessions were signed out.' })),
  http.delete('/api/lite/identity/sessions/:sessionId', ({ params }) => HttpResponse.json({ status: 'revoked', session_id: params.sessionId, summary: 'Session signed out.' })),
  http.post('/api/lite/owner-operations/pending/:operationId/approve', ({ params }) => HttpResponse.json(ownerOperation(params.operationId, 'approved'))),
  http.post('/api/lite/owner-operations/pending/:operationId/reject', ({ params }) => HttpResponse.json(ownerOperation(params.operationId, 'rejected', { terminal_reason: 'Rejected by Owner.' }))),
  http.post('/api/lite/owner-operations/clients/pairings/:pairingId/approve', ({ params }) => HttpResponse.json({ status: 'registered', pairing: ownerClientPairing(params.pairingId, 'registered'), client: ownerClient(), sanitized: true })),
  http.post('/api/lite/owner-operations/clients/pairings/:pairingId/reject', ({ params }) => HttpResponse.json(ownerClientPairing(params.pairingId, 'rejected'))),
  http.post('/api/lite/owner-operations/clients/:clientId/revoke', ({ params }) => HttpResponse.json(ownerClient(params.clientId, 'revoked'))),

  http.get('/api/lite/enterprise/access', () => HttpResponse.json(accessPayload())),
  http.get('/api/lite/enterprise/identity', () => enterpriseEnabled() ? HttpResponse.json(identityPayload().enterprise) : HttpResponse.json({ detail: { reason_code: 'enterprise_mode_disabled', message: 'Enterprise Mode is not enabled.' } }, { status: 404 })),
  http.get('/api/lite/enterprise/identity/mode/preview', () => HttpResponse.json({ current_mode: enterpriseEnabled() ? 'enterprise' : 'personal', target_mode: enterpriseEnabled() ? 'personal' : 'enterprise', changes: ['All active sessions will be signed out so the new authorization model takes effect.', 'Enterprise memberships are retained.', 'Pending approvals and temporary access are closed when returning to Personal Mode.'], topology: accessPayload().topology, pending_approvals: 1, active_exceptions: 1 })),
  http.put('/api/lite/enterprise/identity/mode', ({ request }) => request.json().then((payload) => HttpResponse.json({ enabled: Boolean(payload.enabled), summary: payload.enabled ? 'Enterprise Mode enabled.' : 'Personal Mode enabled.' }))),
  http.get('/api/lite/enterprise/identity/members', () => HttpResponse.json({ members: peoplePayload().people.map((person) => ({ human_id: person.human_id, display_name: person.display_name, username_normalized: person.username, identity_status: person.status, role: person.role, status: person.membership_status, authorization_version: 1 })), roles: peoplePayload().roles })),
  http.put('/api/lite/enterprise/identity/members/:humanId', ({ params, request }) => request.json().then((payload) => HttpResponse.json({ member: { human_id: params.humanId, role: payload.role, status: payload.status || 'active', authorization_version: 2 }, summary: 'Role updated.' }))),
  http.get('/api/lite/enterprise/identity/people', () => HttpResponse.json(peoplePayload())),
  http.get('/api/lite/enterprise/identity/people/:humanId', ({ params }) => HttpResponse.json({ person: peoplePayload().people.find((person) => person.human_id === params.humanId) || peoplePayload().people[0] })),
  http.post('/api/lite/enterprise/identity/people', ({ request }) => request.json().then((payload) => HttpResponse.json({ person: { human_id: 'human-created', ...payload, status: 'invited', membership_status: 'active', active_passkeys: 0, active_sessions: 0, recovery_codes_remaining: 0 }, invite: { claim_id: 'claim-created', claim_url: 'https://pocketlab.example/?person_claim=one-time-mock-claim', expires_at: future(15 * 60 * 1000) }, summary: 'Person invited.' }, { status: 201 }))),
  http.post('/api/lite/enterprise/identity/people/:humanId/invite', ({ params }) => HttpResponse.json({ person: peoplePayload().people.find((person) => person.human_id === params.humanId), invite: { claim_id: 'claim-replacement', claim_url: 'https://pocketlab.example/?person_claim=replacement-mock-claim', expires_at: future(15 * 60 * 1000) }, summary: 'Replacement connect link created.' })),
  http.post('/api/lite/enterprise/identity/people/:humanId/suspend', ({ params }) => HttpResponse.json({ person: { ...(peoplePayload().people.find((person) => person.human_id === params.humanId) || {}), status: 'suspended' }, summary: 'Access suspended.' })),
  http.post('/api/lite/enterprise/identity/people/:humanId/reactivate', ({ params }) => HttpResponse.json({ person: { ...(peoplePayload().people.find((person) => person.human_id === params.humanId) || {}), status: 'active' }, summary: 'Access reactivated.' })),
  http.post('/api/lite/enterprise/identity/people/:humanId/reset-access', ({ params }) => HttpResponse.json({ person: { ...(peoplePayload().people.find((person) => person.human_id === params.humanId) || {}), status: 'invited' }, invite: { claim_id: 'claim-reset', claim_url: 'https://pocketlab.example/?person_claim=reset-mock-claim', expires_at: future(15 * 60 * 1000) }, summary: 'Access reset.' })),
  http.delete('/api/lite/enterprise/identity/people/:humanId', ({ params }) => HttpResponse.json({ person: { ...(peoplePayload().people.find((person) => person.human_id === params.humanId) || {}), status: 'removed' }, summary: 'Person removed from active access.' })),

  http.get('/api/lite/enterprise/rules/templates', () => HttpResponse.json({ templates: [{ template_id: 'enterprise_governance', label: 'Enterprise governance', summary: 'Typed role behavior for protected device removal.', parameters: { admin_device_remove_approval: { type: 'boolean', default: true, label: 'Require review for Admin device removal' }, operator_device_remove_approval: { type: 'boolean', default: true, label: 'Require review for Operator device removal' } } }], effective_parameters: { admin_device_remove_approval: 1, operator_device_remove_approval: 1 }, free_form_rego: false })),
  http.get('/api/lite/enterprise/rules/health', () => HttpResponse.json({ consistency_state: 'ready', db_active_revision: 'mock-policy-revision', filesystem_active_revision: 'mock-policy-revision', known_good_revision: 'mock-policy-revision', opa_observed_revision: 'mock-policy-revision', activation_operation_state: null, opa_loopback_configured: true, opa_reachable: true, manifest_integrity: true, analysis_status: ['Owner','Admin','Auditor'].includes(enterpriseRole()) ? 'complete' : 'not_authorized', deterministic_findings_count: 0, registered_protected_actions: ['catalog.install','app.install','device.remove','identity.passkey.revoke'], represented_protected_actions: ['catalog.install','app.install','device.remove','identity.passkey.revoke'], raw_input_exposed: false })),
  http.get('/api/lite/enterprise/rules/analysis', () => HttpResponse.json({ status: 'complete', proof_rule: 'Only direct registered-action coverage is provable.', registered_protected_actions: ['catalog.install','app.install','device.remove','identity.passkey.revoke'], represented_actions: ['catalog.install','app.install','device.remove','identity.passkey.revoke'], unmapped_actions: [], unsupported_categories: ['contradiction','shadowing','unreachable_rule'], findings: [] })),
  http.get('/api/lite/enterprise/rules/revisions', () => HttpResponse.json({ revisions: [{ revision_id: 'mock-policy-revision', template_id: 'enterprise_governance', template_version: '1', validation_status: 'valid', lifecycle_status: 'active', change_summary: 'Require independent review for delegated device retirement.', created_at: now() }, { revision_id: 'mock-candidate-revision', template_id: 'enterprise_governance', template_version: '1', validation_status: 'valid', lifecycle_status: 'draft', change_summary: 'Candidate delegated-review adjustment.', created_at: now() }] })),
  http.post('/api/lite/enterprise/rules/revisions', ({ request }) => request.json().then((payload) => HttpResponse.json({ revision: { revision_id: 'mock-created-revision', template_id: payload.template_id, template_version: '1', validation_status: 'pending', lifecycle_status: 'draft', change_summary: payload.change_summary, created_at: now() }, created: true }, { status: 201 }))),
  http.get('/api/lite/enterprise/rules/revisions/:revisionId', ({ params }) => HttpResponse.json({ revision: { revision_id: params.revisionId, template_id: 'enterprise_governance', template_version: '1', validation_status: 'valid', lifecycle_status: 'draft', change_summary: 'Mock revision', created_at: now() } })),
  http.post('/api/lite/enterprise/rules/activations', ({ request }) => request.json().then((payload) => HttpResponse.json({ operation: { operation_id: 'plo-mock', candidate_revision_id: payload.revision_id, prior_known_good_revision_id: 'mock-policy-revision', state: 'pending', created_at: now(), updated_at: now() } }, { status: 202 }))),
  http.get('/api/lite/enterprise/rules/activations/:operationId', ({ params }) => HttpResponse.json({ operation: { operation_id: params.operationId, candidate_revision_id: 'mock-created-revision', state: 'active', observed_filesystem_revision: 'mock-created-revision', observed_opa_revision: 'mock-created-revision', updated_at: now() } })),
  http.post('/api/lite/enterprise/rules/activations/:operationId/resolve', ({ params }) => HttpResponse.json({ operation: { operation_id: params.operationId, state: 'rolled_back', observed_filesystem_revision: 'mock-policy-revision', observed_opa_revision: 'mock-policy-revision' }, resolution: { status: 'proved', recovered_revision_id: 'mock-policy-revision' } })),
  http.post('/api/lite/enterprise/rules/rollbacks', () => HttpResponse.json({ operation: { operation_id: 'plo-rollback', candidate_revision_id: 'mock-policy-revision', state: 'pending', created_at: now(), updated_at: now() } }, { status: 202 })),
  http.post('/api/lite/enterprise/rules/simulations', ({ request }) => request.json().then((payload) => HttpResponse.json({ simulation_id: 'sim-mock', revision_id: payload.revision_id, policy_revision: payload.revision_id, action_id: payload.action_id, target_type: payload.action_id === 'device.remove' ? 'device' : 'app', target_id: payload.target_id, input_mode: payload.mode, outcome: payload.action_id === 'device.remove' && enterpriseRole() !== 'Owner' ? 'block' : 'allow', reason_code: payload.action_id === 'device.remove' && enterpriseRole() !== 'Owner' ? 'approval_required' : payload.action_id === 'device.remove' ? 'owner_authority_device_removal' : 'authenticated_app_install', constraints: [], synthetic_fields: payload.mode === 'synthetic' ? Object.keys(payload.scenario || {}) : [], evaluated_at: now(), raw_input_exposed: false }))),
  http.get('/api/lite/enterprise/rules/decisions', () => HttpResponse.json({ decisions: [{ decision_id: 'decision-enterprise', action_id: 'device.remove', target_type: 'device', target_id: 'old-phone', allow: enterpriseRole() === 'Owner', reason_code: enterpriseRole() === 'Owner' ? 'owner_authority_device_removal' : 'approval_required', policy_revision: 'mock-policy-revision', evaluation_ms: 0.3, occurred_at: now() }], next_cursor: null, raw_input_exposed: false })),
  http.get('/api/lite/enterprise/rules/decisions/:decisionId', ({ params }) => HttpResponse.json({ decision_id: params.decisionId, correlation_id: 'mock-corr', action_id: 'device.remove', target_type: 'device', target_id: 'old-phone', allow: enterpriseRole() === 'Owner', reason_code: enterpriseRole() === 'Owner' ? 'owner_authority_device_removal' : 'approval_required', policy_revision: 'mock-policy-revision', evaluation_ms: 0.3, constraints: enterpriseRole() === 'Owner' ? ['confirmed_retirement','validated_revision','owner_authority'] : ['independent_approval'], raw_input_exposed: false })),
  http.get('/api/lite/enterprise/rules/approvals', () => HttpResponse.json(approvalPayload())),
  http.get('/api/lite/enterprise/rules/approvals/:approvalId', ({ params }) => HttpResponse.json({ approval: { approval_id: params.approvalId, status: 'pending' }, history: [{ occurred_at: now(), event_type: 'approval.requested', reason_code: 'approval_required', summary: 'Independent approval requested for delegated device removal.' }] })),
  http.post('/api/lite/enterprise/rules/approvals/:approvalId', ({ params, request }) => request.json().then((payload) => HttpResponse.json({ approval: { approval_id: params.approvalId, status: payload.action === 'approve' ? 'approved' : payload.action === 'reject' ? 'rejected' : 'cancelled' }, message: 'Request state updated.' }))),
  http.get('/api/lite/enterprise/rules/exceptions', () => EXCEPTION_READ_ROLES.has(enterpriseRole()) ? HttpResponse.json({ exceptions: [{ exception_id: 'exc-mock', action_id: 'app.install', app_id: 'photoprism', device_id: 'mock-device', reason: 'Maintenance window', status: 'active', policy_revision: 'mock-policy-revision', expires_at: future(60 * 60 * 1000) }], eligible_people: peoplePayload().people.filter((person) => person.status === 'active').map((person) => ({ human_id: person.human_id, display_name: person.display_name, role: person.role })) }) : HttpResponse.json({ detail: { reason_code: 'enterprise_rules_role_required', message: 'Your Enterprise role is not authorized.' } }, { status: 403 })),
  http.post('/api/lite/enterprise/rules/exceptions', ({ request }) => request.json().then((payload) => HttpResponse.json({ exception: { exception_id: 'exc-created', action_id: 'app.install', ...payload, status: 'active', policy_revision: 'mock-policy-revision', expires_at: future(15 * 60 * 1000) } }, { status: 201 }))),
  http.post('/api/lite/enterprise/rules/exceptions/:exceptionId/revoke', ({ params }) => HttpResponse.json({ exception: { exception_id: params.exceptionId, status: 'revoked' } })),
];

const EXCEPTION_READ_ROLES = new Set(['Owner', 'Admin', 'Auditor']);
