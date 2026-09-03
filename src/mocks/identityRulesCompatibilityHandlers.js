import { http, HttpResponse } from 'msw';

// Compatibility-only reads retained for older tests/components while the main
// Identity + Rules stories exercise the joined Enterprise endpoints. These do
// not add mutation authority and expose only bounded mock evidence.
export const identityRulesCompatibilityHandlers = [
  http.get('/api/lite/policy/templates', () => HttpResponse.json({
    templates: [{ id: 'passkey_step_up', label: 'Passkey confirmation for sensitive Identity changes', status: 'active' }],
    mutation_enabled: false,
  })),
  http.get('/api/lite/policy/decisions/:decisionId', ({ params }) => HttpResponse.json({
    decision_id: params.decisionId,
    correlation_id: 'mock-corr',
    actor_type: 'human',
    action_id: 'identity.passkey.revoke',
    target_type: 'passkey',
    target_id: 'mock-passkey',
    target_revision: 'mock-rev',
    allow: false,
    reason_code: 'passkey_step_up_required',
    policy_revision: 'mock-policy-revision',
    evaluation_ms: 0.4,
    constraints: ['passkey_step_up'],
    evidence_ref: 'policy:mock',
    raw_input_exposed: false,
  })),
];
