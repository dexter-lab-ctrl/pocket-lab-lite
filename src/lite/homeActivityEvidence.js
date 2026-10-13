/** Bounded, sanitized presentation of server-prepared activity; never resolves backend incidents. */
const DOMAINS = { devices: 'Devices', apps: 'Apps', recovery: 'Recovery', security: 'Safety' };
const STATUS = {
  queued: 'Queued', published: 'Queued', received: 'Queued', accepted: 'Waiting',
  stale: 'Not confirmed running',
  running: 'Running', working: 'Running', in_progress: 'Running',
  succeeded: 'Completed', completed: 'Completed', failed: 'Failed',
  timed_out: 'Timed out', undeliverable: 'Could not deliver',
  error: 'Failed', blocked: 'Blocked', cancelled: 'Cancelled',
  degraded: 'Needs review', recovered: 'Recovered', historical: 'Historical issues',
};
const LABELS = new Set(['Device restart','Backup','Media backup repair','Repair','App safety check',
  'Device command','App operation','Recovery operation','Safety check',
  'Device commands encountered problems','Backup operations encountered problems',
  'Media backup repairs encountered problems','Repair operations encountered problems',
  'App safety checks encountered problems']);
const readCount = (value) => Number.isSafeInteger(value) && value >= 0 ? value : null;
const readTime = (value) => Number.isSafeInteger(value) && value > 0 && value <= 8640000000000000 ? value : null;
export const formatActivityCount = (value) => readCount(value) === null ? 'Not available' : new Intl.NumberFormat().format(value);
function selectEvent(raw) {
  if (!DOMAINS[raw?.domain]) return null;
  const at = readTime(raw.occurred_at_epoch_ms);
  if (at === null) return null;
  const rawStatus = String(raw.status || 'unknown').slice(0, 32);
  const status = ['running', 'working', 'in_progress'].includes(rawStatus) && raw.is_fresh_running !== true
    ? 'stale' : rawStatus;
  return {
    domain: raw.domain, at, status,
    needsAttention: raw.needs_attention === true,
    statusLabel: STATUS[status] || 'Status not available',
    label: LABELS.has(raw.label) ? raw.label : (raw.domain === 'security' ? 'Safety check' : raw.domain === 'devices' ? 'Device command' : raw.domain === 'apps' ? 'App operation' : 'Recovery operation'),
  };
}
export function selectHomeActivityEvidence(payload) {
  if (!payload || typeof payload !== 'object' || payload.history_available === false) return null;
  const available = payload.counts_available !== false && payload.read_degraded !== true;
  const events = (Array.isArray(payload.recent_events) ? payload.recent_events : []).slice(0, 24)
    .map(selectEvent).filter(Boolean);
  const grouped = (Array.isArray(payload.grouped_events) ? payload.grouped_events : []).slice(0, 8)
    .filter((e) => LABELS.has(e?.label) && DOMAINS[e?.domain] && readCount(e.count) !== null && e.count > 1)
    .map((e) => ({
      domain: e.domain, label: e.label, count: e.count, at: readTime(e.occurred_at_epoch_ms),
      summary: e.count + ' related operations reported problems within an hour.',
    })).filter((e) => e.at !== null);
  const safe = (value) => available ? readCount(value) : null;
  const lastActivityAt = readTime(payload.last_activity_at_epoch_ms) || events[0]?.at || null;
  return {
    summary: String(payload.summary || 'Activity summary available.').slice(0, 180),
    active: safe(payload.active_operations), queued: safe(payload.queued_operations),
    stale: safe(payload.stale_operations), completed: safe(payload.recent_completed),
    attention: safe(payload.attention_required), historicalFailures: safe(payload.historical_failures),
    attentionScope: payload.attention_scope || 'unknown',
    runningWindowMinutes: payload.running_window_minutes === 30 ? 30 : null,
    historyWindowDays: payload.history_window_days === 7 ? 7 : null,
    events, grouped, latestEvent: events[0] || null, lastActivityAt,
    saved: Boolean(payload.read_degraded || payload.__liteSnapshot?.cached),
  };
}
