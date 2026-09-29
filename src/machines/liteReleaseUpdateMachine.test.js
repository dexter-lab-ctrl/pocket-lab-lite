import { describe, expect, it } from 'vitest';
import { createActor } from 'xstate';
import { liteReleaseUpdateMachine } from './liteReleaseUpdateMachine.js';

describe('liteReleaseUpdateMachine', () => {
  it('clears a local failure when the backend later reports success', () => {
    const actor = createActor(liteReleaseUpdateMachine).start();

    actor.send({ type: 'CHECK' });
    actor.send({ type: 'FAILED', error: new Error('temporary check failure') });
    expect(actor.getSnapshot().value).toBe('failed');
    expect(actor.getSnapshot().context.failureReason).toContain('temporary check failure');

    actor.send({ type: 'BACKEND_DONE' });
    expect(actor.getSnapshot().value).toBe('complete');
    expect(actor.getSnapshot().context.failureReason).toBe('');
    actor.stop();
  });
});
