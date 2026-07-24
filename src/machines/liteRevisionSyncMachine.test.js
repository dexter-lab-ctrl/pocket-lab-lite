import { describe, expect, it } from 'vitest';
import { createActor } from 'xstate';
import {
  liteRevisionSyncMachine,
  revisionFallbackInterval,
} from './liteRevisionSyncMachine.js';

describe('lite revision sync machine', () => {
  it('backs off failures and resets after an event', () => {
    const actor = createActor(liteRevisionSyncMachine).start();
    actor.send({ type: 'CONNECT' });
    actor.send({ type: 'ERROR' });
    expect(actor.getSnapshot().value).toBe('fallback');
    expect(actor.getSnapshot().context.retryAfterMs).toBe(30_000);

    actor.send({ type: 'RETRY' });
    actor.send({ type: 'ERROR' });
    expect(actor.getSnapshot().context.retryAfterMs).toBe(60_000);

    actor.send({ type: 'EVENT', lastEventId: 42 });
    expect(actor.getSnapshot().context.failureCount).toBe(0);
    expect(actor.getSnapshot().context.lastEventId).toBe(42);
    actor.stop();
  });

  it('restores a bounded Dexie cursor and uses long fallback windows', () => {
    const actor = createActor(liteRevisionSyncMachine).start();
    actor.send({ type: 'RESTORE', failureCount: 4, lastEventId: 71 });
    const snapshot = actor.getSnapshot();
    expect(snapshot.context.lastEventId).toBe(71);
    expect(snapshot.context.retryAfterMs).toBe(240_000);
    expect(revisionFallbackInterval({
      value: 'fallback', context: snapshot.context, visible: true, isLeader: true,
    })).toBe(240_000);
    expect(revisionFallbackInterval({
      value: 'open', context: snapshot.context, visible: true, isLeader: true,
    })).toBe(false);
    actor.stop();
  });
});
