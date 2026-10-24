/**
 * Azure Horizon Devices display-only vocabulary.
 * Backend fleet projections and canonicalDevicePresentation remain authoritative.
 * Never turn a saved/unknown heartbeat or a running process into "Connected".
 */
export function deviceHorizonConnection(device, { presentation, linkState, saved = false } = {}) {
  const role = String(device?.role || '').toLowerCase();
  const server = role === 'server_host' || device?.protected_server_host || device?.is_current || device?.isCurrent || linkState === 'server';
  if (server) return { kind: 'server', label: 'Protected server host', description: 'The protected workspace host', needsAttention: false };
  const identity = String(device?.identity?.status || device?.identity_status || '').toLowerCase();
  if (identity === 'join_blocked' || device?.identity?.repair_required || identity === 'mismatch') {
    return { kind: 'blocked', label: 'Identity check blocked', description: 'Explicit repair or rejoin is required', needsAttention: true };
  }
  const staleness = String(device?.staleness_state || device?.last_seen_state?.staleness_state || '').toLowerCase();
  if (saved || ['stale', 'expired'].includes(staleness)) {
    return { kind: 'stale', label: 'Last-known status', description: 'Waiting for current connection evidence', needsAttention: true };
  }
  const status = String(presentation?.state || '').toLowerCase();
  const state = String(device?.connection_truth?.state || device?.connection || '').toLowerCase();
  if (status === 'repairing' || linkState === 'repairing') {
    return { kind: 'repairing', label: 'Repairing', description: 'Recovery is in progress', needsAttention: true };
  }
  if (status === 'joining' || state === 'joining') {
    return { kind: 'joining', label: 'Joining', description: 'Waiting for the device to finish joining', needsAttention: true };
  }
  if (status === 'waiting' || state === 'waiting') {
    return { kind: 'waiting', label: 'Waiting', description: 'A fresh device connection has not been confirmed', needsAttention: true };
  }
  if (status === 'agent_stopped' || state === 'stopped') {
    return { kind: 'stopped', label: 'Agent stopped', description: 'Review supervisor recovery', needsAttention: true };
  }
  if (status === 'online' && linkState === 'joined' && (state === 'online' || !state)) {
    return { kind: 'connected', label: 'Connected', description: 'Current device connection reported', needsAttention: false };
  }
  if (status === 'offline' || state === 'offline') {
    return { kind: 'disconnected', label: 'Disconnected', description: 'Current connection is unavailable', needsAttention: true };
  }
  return { kind: 'unknown', label: 'Not confirmed', description: 'Current connection evidence is unavailable', needsAttention: true };
}

export function deviceHorizonFleetSummary(devices = [], { saved = false, presentationFor, linkStateFor } = {}) {
  const statuses = (Array.isArray(devices) ? devices : []).map((device) =>
    deviceHorizonConnection(device, {
      saved,
      presentation: presentationFor?.(device),
      linkState: linkStateFor?.(device),
    }));
  return {
    total: statuses.length,
    connected: saved ? 0 : statuses.filter((entry) => entry.kind === 'connected').length,
    attention: saved ? null : statuses.filter((entry) => entry.needsAttention).length,
    remaining: statuses.filter((entry) => entry.kind !== 'server').length,
    states: statuses,
  };
}
