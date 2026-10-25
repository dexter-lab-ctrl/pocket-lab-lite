import { describe, expect, it } from 'vitest';
import { deviceHorizonConnection, deviceHorizonFleetSummary } from './deviceHorizonPresentation.js';

// SOURCE-DEFINED ONLY: these tests were authored without executing Vitest.
const device = (id, connection, status = connection) =>
  ({ id, name: id, role: 'compute', connection, status });

describe('Azure Horizon Devices evidence-safe connection vocabulary', () => {
  it.each([
    ['online', 'joined', 'connected', 'Connected'],
    ['repairing', 'repairing', 'repairing', 'Repairing'],
    ['joining', 'disconnected', 'joining', 'Joining'],
    ['waiting', 'disconnected', 'waiting', 'Waiting'],
    ['offline', 'disconnected', 'disconnected', 'Offline'],
    ['agent_stopped', 'disconnected', 'stopped', 'Agent stopped'],
    ['unknown', 'disconnected', 'unknown', 'Not confirmed'],
  ])('%s is not confused with other states', (status, linkState, kind, label) => {
    const view = deviceHorizonConnection(device('test', status), {
      presentation: { state: status }, linkState,
    });
    expect(view).toMatchObject({ kind, label });
  });

  it('never reports a saved or stale online device as connected', () => {
    const online = device('phone', 'online');
    expect(deviceHorizonConnection(online, {
      saved: true, presentation: { state: 'online' }, linkState: 'joined',
    }).kind).toBe('stale');
    expect(deviceHorizonConnection({ ...online, staleness_state: 'expired' }, {
      presentation: { state: 'online' }, linkState: 'joined',
    }).kind).toBe('stale');
  });

  it.each(['join_blocked', 'identity_mismatch', 'identity_blocked', 'blocked'])(
    'identity %s fails closed before connection readiness', (identity) => {
      const view = deviceHorizonConnection({ ...device('phone', 'online'), identity_status: identity }, {
        presentation: { state: 'online' }, linkState: 'joined',
      });
      expect(view).toMatchObject({ kind: 'blocked', needsAttention: true });
    },
  );

  it('does not infer connection from a running process', () => {
    const view = deviceHorizonConnection({
      id: 'phone', agent_process_status: 'online', supervisor_status: 'online',
      connection_truth: { state: 'offline' },
    }, { presentation: { state: 'offline' }, linkState: 'disconnected' });
    expect(view.kind).toBe('disconnected');
  });

  it('never allows a mismatched device invite to appear as connected', () => {
    const view = deviceHorizonConnection({
      ...device('phone', 'online'), identity: { repair_required: true },
    }, { presentation: { state: 'online' }, linkState: 'joined' });
    expect(view.kind).toBe('blocked');
  });

  it('marks protected server host separately without repair/removal attention', () => {
    const view = deviceHorizonConnection({ id: 'host', role: 'server_host' }, { linkState: 'server' });
    expect(view).toMatchObject({ kind: 'server', needsAttention: false });
  });

  it('provides backend-derived counts without promoting unknown or saved data', () => {
    const devices = [
      { id: 'host', role: 'server_host' },
      device('online', 'online'),
      device('offline', 'offline'),
      device('joining', 'joining'),
    ];
    const projection = (saved) => deviceHorizonFleetSummary(devices, {
      saved,
      presentationFor: (item) => ({ state: item.status }),
      linkStateFor: (item) => item.role === 'server_host' ? 'server' : item.connection === 'online' ? 'joined' : 'disconnected',
    });
    expect(projection(false)).toMatchObject({ total: 4, connected: 1, attention: 2, remaining: 3 });
    expect(projection(true)).toMatchObject({ total: 4, connected: 0, attention: null, remaining: 3 });
  });

  it('handles empty and malformed fleet members without fabricating connectivity', () => {
    const view = deviceHorizonFleetSummary([{}, null, undefined], {
      presentationFor: () => ({ state: 'unknown' }),
      linkStateFor: () => 'disconnected',
    });
    expect(view.connected).toBe(0);
    expect(view.attention).toBe(3);
  });
});
