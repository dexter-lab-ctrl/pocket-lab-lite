import { describe, expect, it } from 'vitest';
import {
  acquireLiteRevisionLeadership,
  applyLiteRevisionEnvelope,
  applyLiteRevisionSnapshot,
  createLiteRevisionState,
  releaseLiteRevisionLeadership,
  validateLiteRevisionEnvelope,
} from './liteRevisionSync.js';

function queryClientSpy() {
  const calls = [];
  return {
    calls,
    invalidateQueries(options) {
      calls.push(options);
      return Promise.resolve();
    },
  };
}

function event(overrides = {}) {
  return {
    type: 'lite.revision.changed',
    event_id: 1,
    domain: 'apps',
    revision: 1,
    database_instance: 'database-a',
    changed_ids: ['photoprism'],
    reason: 'apps_state_changed',
    projection_version: 2,
    occurred_at: '2026-07-22T14:00:00Z',
    sanitized: true,
    ...overrides,
  };
}

describe('Lite revision-driven synchronization', () => {
  it('validates the allowlisted bounded event schema', () => {
    expect(validateLiteRevisionEnvelope(event())).toMatchObject({ domain: 'apps', revision: 1 });
    expect(validateLiteRevisionEnvelope(event({ domain: 'unknown' }))).toBeNull();
    expect(validateLiteRevisionEnvelope(event({ reason: 'raw_payload_changed' }))).toBeNull();
    expect(validateLiteRevisionEnvelope(event({ changed_ids: Array.from({ length: 33 }, (_, index) => `app-${index}`) }))).toBeNull();
    expect(validateLiteRevisionEnvelope(event({ projection_version: 99 }))).toBeNull();
  });

  it('invalidates only focused app queries and changed app details', () => {
    const client = queryClientSpy();
    const state = createLiteRevisionState();
    const result = applyLiteRevisionEnvelope(client, state, event());
    expect(result.accepted).toBe(true);
    expect(client.calls.map((call) => call.queryKey)).toEqual(expect.arrayContaining([
      ['lite', 'apps'],
      ['lite', 'app'],
      ['lite', 'catalog'],
      ['lite', 'app', 'photoprism', 'actions'],
    ]));
    expect(client.calls.some((call) => call.queryKey[1] === 'fleet')).toBe(false);
    expect(client.calls.some((call) => call.queryKey[1] === 'recovery')).toBe(false);
  });

  it('deduplicates repeated and out-of-order events', () => {
    const client = queryClientSpy();
    const state = createLiteRevisionState();
    expect(applyLiteRevisionEnvelope(client, state, event()).accepted).toBe(true);
    const count = client.calls.length;
    expect(applyLiteRevisionEnvelope(client, state, event()).reason).toBe('duplicate_or_out_of_order');
    expect(applyLiteRevisionEnvelope(client, state, event({ event_id: 2, revision: 1 })).reason).toBe('revision_not_newer');
    expect(client.calls).toHaveLength(count);
  });

  it('treats database-instance replacement as a full cache fence', () => {
    const client = queryClientSpy();
    const state = createLiteRevisionState({ databaseInstance: 'database-a', revisions: { fleet: 4 } });
    const result = applyLiteRevisionSnapshot(client, state, {
      database_instance: 'database-b',
      revisions: { fleet: 1, apps: 1, recovery: 0, commands: 0, storage: 0, audit: 0, security: 0 },
      event_cursor: { latest_event_id: 0 },
    });
    expect(result.databaseInstanceChanged).toBe(true);
    expect(state.databaseInstance).toBe('database-b');
    expect(state.revisions.fleet).toBe(1);
    expect(client.calls).toEqual(expect.arrayContaining([
      expect.objectContaining({ queryKey: ['lite'], exact: false }),
    ]));
  });


  it('uses one renewable cross-tab stream leader lease', () => {
    const values = new Map();
    const storage = {
      getItem: (key) => values.get(key) || null,
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    };
    expect(acquireLiteRevisionLeadership(storage, 'tab-a', { now: 1_000, ttlMs: 20_000 })).toBe(true);
    expect(acquireLiteRevisionLeadership(storage, 'tab-b', { now: 2_000, ttlMs: 20_000 })).toBe(false);
    expect(acquireLiteRevisionLeadership(storage, 'tab-a', { now: 8_000, ttlMs: 20_000 })).toBe(true);
    expect(releaseLiteRevisionLeadership(storage, 'tab-b')).toBe(false);
    expect(releaseLiteRevisionLeadership(storage, 'tab-a')).toBe(true);
    expect(acquireLiteRevisionLeadership(storage, 'tab-b', { now: 9_000, ttlMs: 20_000 })).toBe(true);
  });

  it('uses freshness snapshots to invalidate only newer domains', () => {
    const client = queryClientSpy();
    const state = createLiteRevisionState({
      databaseInstance: 'database-a',
      revisions: { fleet: 3, apps: 2, recovery: 5 },
    });
    const result = applyLiteRevisionSnapshot(client, state, {
      database_instance: 'database-a',
      revisions: { fleet: 3, apps: 3, recovery: 5, commands: 0, storage: 0, audit: 0, security: 0 },
      event_cursor: { latest_event_id: 7 },
    });
    expect(result.changedDomains).toEqual(['apps']);
    expect(client.calls.some((call) => call.queryKey[1] === 'apps')).toBe(true);
    expect(client.calls.some((call) => call.queryKey[1] === 'fleet')).toBe(false);
    expect(state.lastEventId).toBe(7);
  });
});
