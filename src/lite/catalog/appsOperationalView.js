// Presentation-only selectors. Backend media-backup readiness is the sole truth.
// No transfer percentages, connection inference or destination URLs are synthesized.
const normalize = (value) => String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
const active = new Set(['queued','planning','waiting','waiting_for_credentials','starting','transferring','cancelling']);
const completed = new Set(['completed','succeeded','success']);
const attention = new Set(['failed','error','partial','partial_storage_limit','interrupted','blocked']);

export function selectPhotoBackupFacts(devices = [], saved = false) {
  const rows = Array.isArray(devices) ? devices.filter((item) => item && typeof item === 'object') : [];
  const latestOwner = rows.filter((item) => item.latest_backup).sort((a,b) =>
    String(b.latest_backup?.updated_at || b.latest_backup?.completed_at || '').localeCompare(
      String(a.latest_backup?.updated_at || a.latest_backup?.completed_at || '')))[0] || null;
  const latest = latestOwner?.latest_backup || null;
  const device = latestOwner || rows.find((item) => item.ready === true) || rows[0] || null;
  const status = normalize(latest?.status);
  const sourceState = typeof device?.photo_storage_access === 'boolean'
    ? device.photo_storage_access ? 'Ready' : 'Not ready'
    : 'Not reported';
  const destinationState = typeof device?.destination_ready === 'boolean'
    ? device.destination_ready ? 'Ready' : 'Not ready'
    : 'Not reported';
  const transferState = !latest ? 'Not reported'
    : active.has(status) ? 'Running / waiting'
    : completed.has(status) ? 'Completed'
    : attention.has(status) ? 'Needs review'
    : status === 'cancelled' ? 'Stopped' : 'Unknown';
  const requiresAttention = Boolean(!saved && (attention.has(status) || device?.ready === false || destinationState === 'Not ready'));
  const statusLabel = saved ? 'Saved / offline'
    : active.has(status) ? 'Running'
    : attention.has(status) ? 'Needs review'
    : rows.some((item) => item.ready === true) ? 'Ready'
    : requiresAttention ? 'Attention'
    : rows.length ? 'Unknown' : 'Unavailable';
  return {
    statusLabel,
    tone: saved ? 'saved' : requiresAttention ? 'review' : active.has(status) ? 'working' : statusLabel === 'Ready' ? 'ready' : 'neutral',
    source: { title: device?.node_label || device?.device_label || 'Source device not reported', state: sourceState },
    transfer: { title: 'Protected transfer', state: transferState },
    destination: { title: 'Protected WebDAV destination · PhotoPrism', state: destinationState },
    latestTransfer: latest?.items_transferred != null && Number.isFinite(Number(latest.items_transferred))
      ? Number(latest.items_transferred).toLocaleString() + ' items' : 'Not reported',
    lastUpdate: latest?.completed_at || latest?.updated_at || device?.updated_at || null,
    reason: saved ? 'Showing saved information. Reconnect before starting a photo backup.'
      : device?.ready === false ? device?.summary || 'Device readiness is not confirmed.'
      : attention.has(status) ? latest?.summary || 'The latest transfer needs review.'
      : !rows.length ? 'No device photo-backup readiness has been reported.'
      : destinationState === 'Not reported' ? 'Destination readiness was not reported.'
      : latest?.summary || device?.summary || 'No transfer outcome has been reported.',
    nextStep: requiresAttention || !rows.length ? 'Review readiness in Devices.' : active.has(status)
      ? 'Review current transfer in Devices.' : 'Manage photo backups in Devices.',
    requiresAttention,
  };
}

// Notices are supplemental; avoid repeating the currently visible action row.
// A blocked action is never inferred from another app's readiness or static examples.
export function selectSupplementalActionNotices(entries = [], activeActionIds = []) {
  const activeIds = new Set(activeActionIds);
  const seen = new Set();
  return (Array.isArray(entries) ? entries : []).flatMap((entry) => {
    const action = entry?.action;
    const id = entry?.actionId;
    if (!id || !action || action.enabled !== false || activeIds.has(id)) return [];
    const state = normalize(action.status);
    if (['completed','success','succeeded','ready','installed','imported','connected','verified'].includes(state)) return [];
    const reason = String(action.disabled_reason || action.reason || '').trim();
    if (!reason || reason === 'Action not ready yet.') return [];
    const identity = id + ':' + normalize(reason);
    if (seen.has(identity)) return [];
    seen.add(identity);
    return [{ id, label: action.label || entry.label || id.replace(/_/g,' '),
      status: ['failed','error','blocked'].includes(state) ? 'Unavailable' : 'Not ready',
      reason, next: action.next_step || '' }];
  });
}
