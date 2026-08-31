import { describe, expect, it } from 'vitest';
import { claimObservedSecurityCompletion } from './securityCompletion.js';

const CASE_SENSITIVE_RUN_ID = 'security-2026-08-31T165957Z-2226321f';
const activeObservation = { active: true, runId: CASE_SENSITIVE_RUN_ID };
const terminalEvent = {
  type: 'security.scan.completed',
  run_id: CASE_SENSITIVE_RUN_ID,
  profile: 'quick',
  status: 'succeeded',
  snapshot: false,
};

describe('observed Security completion', () => {
  it('claims exactly one exact-case terminal completion and supplies its canonical feedback', () => {
    const completions = new Set();
    const completion = claimObservedSecurityCompletion(terminalEvent, activeObservation, completions);

    expect(completion).toMatchObject({
      id: `security-completion:${CASE_SENSITIVE_RUN_ID}`,
      runId: CASE_SENSITIVE_RUN_ID,
      observation: { active: false, runId: '' },
      haptic: 'success',
      toast: { title: 'Safety check completed', kind: 'success' },
    });
    expect(claimObservedSecurityCompletion(terminalEvent, activeObservation, completions)).toBeNull();
    expect(completions).toHaveLength(1);
  });

  it('does not notify for a wrong, case-different, or historical terminal event', () => {
    const completions = new Set();
    expect(claimObservedSecurityCompletion(
      { ...terminalEvent, run_id: 'security-2026-08-31T165957Z-wrong-run' },
      activeObservation,
      completions,
    )).toBeNull();
    expect(claimObservedSecurityCompletion(
      { ...terminalEvent, run_id: CASE_SENSITIVE_RUN_ID.replace('T', 't') },
      activeObservation,
      completions,
    )).toBeNull();
    expect(claimObservedSecurityCompletion(
      { ...terminalEvent, snapshot: true },
      { active: false, runId: '' },
      completions,
    )).toBeNull();
    expect(completions).toHaveLength(0);
  });
});
