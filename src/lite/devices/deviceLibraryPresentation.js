/**
 * Display-only inventory projection. FastAPI's prepared fleet remains the authority.
 * Saved, stale, unknown and partial signals never prove live connectivity.
 */
import { deviceHorizonConnection } from './deviceHorizonPresentation.js';

export const DEVICE_LIBRARY_FILTERS = Object.freeze([
  { id: 'all', label: 'All devices' },
  { id: 'connected', label: 'Connected' },
  { id: 'attention', label: 'Needs attention' },
]);

export function deviceLibraryEntry(device, { saved = false, presentation, linkState } = {}) {
  const connection = deviceHorizonConnection(device, { saved, presentation, linkState });
  const health = device?.proactive_health || {};
  const healthStatus = String(health.status || '').toLowerCase();
  const healthAttention = !saved && health.attention_current !== false
    && (Number(health.attention_count || 0) > 0 || ['needs_attention', 'degraded', 'unreachable', 'watch'].includes(healthStatus));
  const needsAttention = connection.needsAttention || healthAttention;
  return { device, connection, needsAttention, healthAttention };
}

export function deviceLibrarySummary(entries = [], { confirmed = false } = {}) {
  const list = Array.isArray(entries) ? entries : [];
  return {
    total: confirmed ? list.length : null,
    connected: confirmed ? list.filter((item) => item.connection.kind === 'connected').length : null,
    attention: confirmed ? list.filter((item) => item.needsAttention).length : null,
  };
}

export function filterDeviceLibrary(entries = [], { filter = 'all', query = '' } = {}) {
  const needle = String(query || '').trim().toLocaleLowerCase();
  return (Array.isArray(entries) ? entries : []).filter(({ device, connection, needsAttention }) => {
    if (filter === 'connected' && connection.kind !== 'connected') return false;
    if (filter === 'attention' && !needsAttention) return false;
    if (!needle) return true;
    return [device?.name, device?.hostname, device?.system_profile?.display_model, device?.role,
      ...(Array.isArray(device?.roles) ? device.roles : [])]
      .some((value) => String(value || '').toLocaleLowerCase().includes(needle));
  }).map(({ device }) => device);
}
