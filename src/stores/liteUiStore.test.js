import { describe, expect, it } from 'vitest';
import { useLiteUiStore } from './liteUiStore.js';

const CASE_SENSITIVE_RUN_ID = 'security-2026-08-31T165957Z-2226321f';

describe('Lite Security UI state', () => {
  it('preserves opaque backend run IDs while retaining lowercase finding IDs', () => {
    const store = useLiteUiStore.getState();
    store.setSecurityObservation({ active: true, runId: `  ${CASE_SENSITIVE_RUN_ID}  ` });
    store.setLastSecurityRunIdViewed(`  ${CASE_SENSITIVE_RUN_ID}  `);
    store.setActiveSecurityEvidenceRunId(`  ${CASE_SENSITIVE_RUN_ID}  `);
    store.setActiveSecurityDetailsPanel('evidence', `  ${CASE_SENSITIVE_RUN_ID}  `);

    const state = useLiteUiStore.getState();
    expect(state.securityObservation).toEqual({ active: true, runId: CASE_SENSITIVE_RUN_ID });
    expect(state.lastSecurityRunIdViewed).toBe(CASE_SENSITIVE_RUN_ID);
    expect(state.activeSecurityEvidenceRunId).toBe(CASE_SENSITIVE_RUN_ID);
    expect(state.activeSecurityDetailsRunId).toBe(CASE_SENSITIVE_RUN_ID);

    store.setExpandedSecurityFindingId('  Finding-UPPER-42  ');
    expect(useLiteUiStore.getState().expandedSecurityFindingId).toBe('finding-upper-42');
  });
});
