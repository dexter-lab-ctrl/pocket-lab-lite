import { createActor } from 'xstate';
import { describe, expect, it } from 'vitest';
import { liteHotPathDiagnosticsMachine } from './liteHotPathDiagnosticsMachine.js';

describe('lite hot path diagnostics machine', () => {
  it('captures explicitly without introducing polling state', () => {
    const actor = createActor(liteHotPathDiagnosticsMachine).start();
    actor.send({ type: 'CAPTURE' });
    expect(actor.getSnapshot().value).toBe('capturing');
    actor.send({ type: 'SUCCESS', capturedAt: '2026-07-24T00:00:00Z' });
    expect(actor.getSnapshot().value).toBe('ready');
    expect(actor.getSnapshot().context.failureCount).toBe(0);
  });
});
