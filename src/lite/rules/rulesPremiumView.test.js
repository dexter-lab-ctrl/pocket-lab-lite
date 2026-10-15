import { describe, expect, it } from 'vitest';
import { rulesProtectionView, rulesDecisionView, rulesActivationView } from './rulesPremiumView.js';

const ready = { status: 'ready', engine: { healthy: true, loopback_only: true }, active_policy: { bundle_ready: true } };
describe('Premium Rules source-backed selectors', () => {
  it('reports ready only for current confirmed policy truth', () => {
    expect(rulesProtectionView(ready).state).toBe('ready');
    expect(rulesProtectionView(ready, { savedStateOnly: true }).state).toBe('saved');
    expect(rulesProtectionView(ready, { backendReachable: false, isExpired: true }).state).toBe('stale');
    expect(rulesProtectionView(null).state).toBe('unavailable');
    expect(rulesProtectionView({ ...ready, engine: { healthy: true, loopback_only: false } }).state).toBe('degraded');
    expect(rulesProtectionView({ ...ready, active_policy: { source_update_required: true } }).state).toBe('degraded');
  });
  it('never treats simulation as live permission or authorization as execution', () => {
    expect(rulesDecisionView({ outcome: 'allow', action_id: 'device.remove' }, { simulated: true }).status).toBe('Simulation allowed');
    expect(rulesDecisionView({ allow: true }).execution).toBe('');
    expect(rulesDecisionView({ outcome: 'step_up_required' }).status).toBe('Passkey step-up required');
    expect(rulesDecisionView({ outcome: 'approval_required' }).status).toBe('Independent approval required');
    expect(rulesDecisionView({ allow: false }).status).toBe('Blocked');
    expect(rulesDecisionView({}).status).toBe('Decision not confirmed');
  });
  it('does not invent unavailable actor, targets, reasons or revision history', () => {
    const v = rulesDecisionView({ reason_code: 'unknown_case', extra: { secret: 'SECRET_VALUE' } });
    expect(v.actor).toBe('');
    expect(v.target).toBe('');
    expect(v.revision).toBe('');
    expect(JSON.stringify(v)).not.toContain('SECRET_VALUE');
  });
  it('only accepts separately reported execution status, never a result inferred from allow', () => {
    expect(rulesDecisionView({ allow: true, execution_status: 'completed' }).execution).toBe('completed');
    expect(rulesDecisionView({ allow: true, execution_status: 'unrecognized' }).execution).toBe('');
  });
  it('models reported rollback/uncertain states without synthesized completion', () => {
    expect(rulesActivationView({ state: 'rolling_back' }).recovery).toBe(true);
    expect(rulesActivationView({ state: 'uncertain' }).steps.every(x => x.state === 'unconfirmed')).toBe(true);
    expect(rulesActivationView({ state: 'active' }).steps.every(x => x.state === 'completed')).toBe(true);
    expect(rulesActivationView(null).steps.every(x => x.state === 'unconfirmed')).toBe(true);
  });
});
