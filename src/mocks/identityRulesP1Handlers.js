import { http, HttpResponse } from 'msw';

const now = () => new Date().toISOString();
const future = (ms) => new Date(Date.now() + ms).toISOString();
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

function identityPayload() {
  const enabled = enterpriseEnabled();
  const role = enabled ? enterpriseRole() : 'Owner';
  return {
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
  };
}

const ROLE_SUMMARIES = {
  Owner: 'Full Pocket Lab authority. Owners do not need another person’s approval, but root-level changes can still require passkey confirmation.',
  Admin: 'Broad delegated administration. High-risk actions can require independent review.',
  Operator: 'Day-to-day operational access. Protected changes can require independent review.',
  Auditor: 'Read-only governance and evidence access, including non-executing Rules simulation.',
  Viewer: 'Read-only workspace evidence without administrative authority.',
};

function actionMode(action, role) {
  if (role === 'Owner') return ['rules.activate', 'rules.rollback', 'enterprise.mode.change'].includes(action) ? 'step_up' : 'allow';
  if (role === 'Admin') {
    if (action === 'device.remove') return 'approval';
    return ['people.manage','catalog.install','rules.draft','rules.simulate','approvals.review','exceptions.manage','evidence.read'].includes(action) ? 'allow' : 'deny';
  }
  if (role === 'Operator') {
    if (action === 'device.remove') return 'approval';
    return ['catalog.install','rules.simulate','evidence.read'].includes(action) ? 'allow' : 'deny';
  }
  if (role === 'Auditor') return ['rules.simulate','evidence.read'].includes(action) ? 'allow' : 'deny';
  return action === 'evidence.read' ? 'allow' : 'deny';
}

const ACTIONS = [
  ['people.manage','Manage people','Create, suspend, reactivate, remove and assign access to people.'],
  ['enterprise.mode.change','Change workspace mode','Switch between Personal and Enterprise Mode.'],
  ['device.remove','Remove devices','Retire a confirmed non-server device from Pocket Lab.'],
  ['catalog.install','Install apps','Install an approved app through the server-owned execution path.'],
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
  return {
    mode: enterpriseEnabled() ? 'enterprise' : 'personal', enterprise_enabled: enterpriseEnabled(), current_role: role, owner_authority: role === 'Owner',
    role: { id: role, label: role, summary: ROLE_SUMMARIES[role] },
    roles: roles.map((id) => ({ id, label: id, summary: ROLE_SUMMARIES[id] })),
    capabilities,
    policy_parameters: { admin_device_remove_approval: 1, operator_device_remove_approval: 1 },
    action_matrix: ACTIONS.map(([action_id,label,summary]) => ({ action_id, label, summary, roles: Object.fromEntries(roles.map((candidate) => [candidate, actionMode(action_id, candidate)])) })),
    topology: { active_people: 5, invited_people: 1, active_owners: 1, active_admins: 1, active_operators: 1, active_auditors: 1, active_viewers: 1, independent_approvers: 2 },
    summary: role === 'Owner' ? 'Owner has complete supported Pocket Lab authority without peer approval.' : 'Your server-resolved role and current Safety Rules determine what you can do.',
    updated_at: now(),
  };
}

function policyPayload() {
  return {
    status: 'ready', summary: 'Safety Rules are active and ready for protected changes.',
    engine: { name: 'Open Policy Agent', version: '1.19.0', healthy: true, loopback_only: true, endpoint_exposed_to_browser: false, reason_code: '' },
    active_policy: { revision: 'mock-policy-revision', bundle_ready: true, package_status: 'active', protected_actions: ['catalog.install','device.remove','identity.passkey.revoke'], activation_model: 'supervisor_proved_revision', last_known_good: true },
    degraded_reason: '', last_decision_at: now(),
    policy_groups: [{ id: 'apps', label: 'Apps', actions: ['catalog.install'] }, { id: 'devices', label: 'Devices', actions: ['device.remove'] }, { id: 'identity', label: 'Identity', actions: ['identity.passkey.revoke'] }],
    templates: [{ id: 'passkey_step_up', label: 'Passkey confirmation for sensitive Identity changes', summary: 'Requires recent server-verified passkey confirmation before removing a passkey.', status: 'active', enforcement: 'server-derived assurance', actions: ['identity.passkey.revoke'] }],
    recent_decisions: [{ decision_id: 'decision-recent', action_id: 'device.remove', target_type: 'device', target_id: 'old-phone', allow: enterpriseRole() === 'Owner', reason_code: enterpriseRole() === 'Owner' ? 'owner_authority_device_removal' : 'approval_required', policy_revision: 'mock-policy-revision', evaluation_ms: 0.4, occurred_at: now() }],
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
  http.get('/api/lite/policy', () => HttpResponse.json(policyPayload())),

  http.get('/api/lite/identity/owner-claim/status', () => HttpResponse.json({ active: false, status: 'owner_claim_authority_invalid' })),
  http.post('/api/lite/identity/owner-claim/consume', () => HttpResponse.json({ status: 'claim_verified', expires_at: future(5 * 60 * 1000), summary: 'Owner claim verified. Create a passkey to finish setup.' })),
  http.post('/api/lite/identity/owner-claim/passkey/options', () => HttpResponse.json({ publicKey: { challenge: 'bW9jay1jaGFsbGVuZ2U', rp: { name: 'Pocket Lab Lite', id: 'localhost' }, user: { id: 'bW9jay11c2Vy', name: 'owner', displayName: 'Pocket Lab Owner' }, pubKeyCredParams: [{ type: 'public-key', alg: -7 }] } })),
  http.post('/api/lite/identity/owner-claim/passkey/verify', () => HttpResponse.json({ ...identityPayload(), csrf_token: 'mock-csrf', recovery_codes: ['MOCK-RECOVERY-CODE'] }, { status: 201 })),

  http.get('/api/lite/enterprise/identity/enrollment/status', () => HttpResponse.json(scenario() === 'identity-enterprise-invited' ? { active: true, status: 'claim_verified', expires_at: future(5 * 60 * 1000), person: { display_name: 'New Person', username: 'new-person', role: 'Operator' }, summary: 'Connect link verified. Create a passkey to finish joining Pocket Lab.' } : { active: false, status: 'person_claim_authority_invalid' })),
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

  http.get('/api/lite/enterprise/access', () => enterpriseEnabled() ? HttpResponse.json(accessPayload()) : HttpResponse.json({ detail: { reason_code: 'enterprise_mode_required', message: 'Enterprise Mode is not enabled.' } }, { status: 404 })),
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
  http.get('/api/lite/enterprise/rules/health', () => HttpResponse.json({ consistency_state: 'ready', db_active_revision: 'mock-policy-revision', filesystem_active_revision: 'mock-policy-revision', known_good_revision: 'mock-policy-revision', opa_observed_revision: 'mock-policy-revision', activation_operation_state: null, opa_loopback_configured: true, opa_reachable: true, manifest_integrity: true, analysis_status: ['Owner','Admin','Auditor'].includes(enterpriseRole()) ? 'complete' : 'not_authorized', deterministic_findings_count: 0, registered_protected_actions: ['catalog.install','device.remove','identity.passkey.revoke'], represented_protected_actions: ['catalog.install','device.remove','identity.passkey.revoke'], raw_input_exposed: false })),
  http.get('/api/lite/enterprise/rules/analysis', () => HttpResponse.json({ status: 'complete', proof_rule: 'Only direct registered-action coverage is provable.', registered_protected_actions: ['catalog.install','device.remove','identity.passkey.revoke'], represented_actions: ['catalog.install','device.remove','identity.passkey.revoke'], unmapped_actions: [], unsupported_categories: ['contradiction','shadowing','unreachable_rule'], findings: [] })),
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
  http.get('/api/lite/enterprise/rules/exceptions', () => EXCEPTION_READ_ROLES.has(enterpriseRole()) ? HttpResponse.json({ exceptions: [{ exception_id: 'exc-mock', action_id: 'catalog.install', app_id: 'photoprism', device_id: 'mock-device', reason: 'Maintenance window', status: 'active', policy_revision: 'mock-policy-revision', expires_at: future(60 * 60 * 1000) }], eligible_people: peoplePayload().people.filter((person) => person.status === 'active').map((person) => ({ human_id: person.human_id, display_name: person.display_name, role: person.role })) }) : HttpResponse.json({ detail: { reason_code: 'enterprise_rules_role_required', message: 'Your Enterprise role is not authorized.' } }, { status: 403 })),
  http.post('/api/lite/enterprise/rules/exceptions', ({ request }) => request.json().then((payload) => HttpResponse.json({ exception: { exception_id: 'exc-created', action_id: 'catalog.install', ...payload, status: 'active', policy_revision: 'mock-policy-revision', expires_at: future(15 * 60 * 1000) } }, { status: 201 }))),
  http.post('/api/lite/enterprise/rules/exceptions/:exceptionId/revoke', ({ params }) => HttpResponse.json({ exception: { exception_id: params.exceptionId, status: 'revoked' } })),
];

const EXCEPTION_READ_ROLES = new Set(['Owner', 'Admin', 'Auditor']);
