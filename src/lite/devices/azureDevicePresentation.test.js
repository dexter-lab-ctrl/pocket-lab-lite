import { describe, expect, it } from 'vitest';
import { deviceRelationshipPresentation, remoteAccessPresentation, remoteAccessSummaryRows } from '../LiteDevices.jsx';

describe('Azure Horizon backend-truthful Devices presentation', () => {
  it.each([
    [{ status: 'joining' }, 'Joining'],
    [{ status: 'waiting' }, 'Waiting'],
    [{ status: 'agent_stopped' }, 'Agent stopped'],
    [{ status: 'identity_mismatch' }, 'Identity check blocked'],
    [{ status: 'offline' }, 'Offline'],
    [{ status: 'repairing' }, 'Repairing'],
  ])('preserves explicit state %#', (device, label) => {
    expect(deviceRelationshipPresentation(device).label).toBe(label);
  });
  it('never presents a saved connection as currently connected', () => {
    expect(deviceRelationshipPresentation({ status: 'online' }, true).state).toBe('unknown');
  });
  it('does not claim network readiness from saved state', () => {
    expect(remoteAccessPresentation({ status: 'healthy' }, true).ready).toBe(false);
  });
  it('does not surface a Tailnet address in saved-state summaries', () => {
    const rows = remoteAccessSummaryRows({ ip: '100.101.102.103', running: true }, { ready: true }, true);
    expect(rows.some((row) => String(row.value).includes('100.101.102.103'))).toBe(false);
  });
});
