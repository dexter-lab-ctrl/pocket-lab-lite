// Read-only Recovery presentation. Never infer operation completion or restore authority.
const ACTIVE = new Set(['accepted', 'pending', 'queued', 'running', 'working', 'in_progress', 'restoring']);
const FAILED = new Set(['failed', 'failure', 'error', 'blocked', 'cancelled', 'canceled', 'rolled_back', 'rollback_failed']);
const BLOCKED = new Set(['blocked', 'unavailable', 'not_available', 'read_only']);
const COMPLETE = new Set(['succeeded', 'completed', 'complete', 'success', 'done']);
const string = (value) => typeof value === 'string' ? value : '';
const norm = (value) => string(value).trim().toLowerCase();
const record = (value) => value && typeof value === 'object' && !Array.isArray(value) ? value : {};
export function isRecoveryLocationReady(location) {
  const item = record(location);
  // Unknown, missing and merely "available" destinations are not recovery-ready.
  // Only a backend-reported ready destination can support an eligible restore.
  return norm(item.status) === 'ready'
    && item.available !== false
    && item.ready !== false;
};
const validTime = (value) => {
  if (typeof value !== 'string' || !value || !Number.isFinite(Date.parse(value))) return '';
  return value;
};
const result = (label, state) => ({ label, state });
export function recoveryPremiumHero({ data = {}, backup = null, preview = null, repository = {}, database = {}, busy = '', saved = false, stale = false, reachable = true, blocked = false } = {}) {
  const unavailable = saved || stale || reachable === false;
  const b = record(backup), p = record(preview), db = record(database), repo = record(repository);
  const hasBackup = Boolean(b.backup_id);
  const verified = hasBackup && norm(b.verification_status) === 'verified';
  const matchingPreview = verified && Boolean(p.preview_id) && p.backup_id === b.backup_id && norm(p.status) === 'ready' && p.restore_allowed !== false;
  const repoUnavailable = repo.ready === false || ['unavailable', 'missing', 'error'].includes(norm(repo.status));
  const dbBlocked = blocked || db.restore_guard?.unresolved === true || db.maintenance?.active === true;
  const operation = record(data?.current_operation || data?.latest_operation || data?.operation || data?.action_progress || data?.active_operation);
  const activeRestore = norm(data?.last_restore?.status || data?.last_restore?.state || data?.last_restore?.phase);
  const active = Boolean(busy) || data?.live === true || ACTIVE.has(activeRestore) || ACTIVE.has(norm(operation.status || operation.state || operation.phase));
  const restoreState = norm(data?.last_restore?.status);
  let headline = 'Create your first protected backup';
  let summary = 'No verified recovery point has been reported.';
  if (hasBackup) { headline = verified ? 'A verified recovery point is available' : 'Your backup needs verification'; summary = verified ? 'Preview the selected backup before any restore.' : 'A saved backup is not yet proof that a restore is safe.'; }
  if (matchingPreview) { headline = 'Restore preview ready for review'; summary = 'A matching preview is available. Restoring still requires confirmation and backend safety checks.'; }
  if (FAILED.has(restoreState)) { headline = 'Restore needs attention'; summary = string(data.last_restore.summary) || 'The last restore did not report a successful result.'; }
  if (repoUnavailable) { headline = 'Backup location unavailable'; summary = 'Pocket Lab cannot currently confirm the backup repository is usable.'; }
  if (dbBlocked) { headline = 'Recovery actions are protected'; summary = 'A database safety guard or active maintenance is blocking recovery changes.'; }
  if (active) { headline = 'Recovery operation in progress'; summary = 'Pocket Lab is processing a requested recovery operation. Completion has not been confirmed.'; }
  if (unavailable) { headline = saved ? 'Showing saved recovery information' : 'Current recovery state unavailable'; summary = 'Live protection and restore readiness must be confirmed before making changes.'; }
  const backupIndicator = unavailable ? result('Not confirmed', 'unknown') : verified ? result('Verified', 'completed') : hasBackup ? result('Verification needed', 'needs_action') : result('Not created', 'not_started');
  const restoreIndicator = unavailable ? result('Not confirmed', 'unknown') : matchingPreview ? result('Preview ready', 'available') : verified ? result('Preview required', 'needs_action') : result('Not ready', 'blocked');
  const databaseBackup = record(db.latest_backup);
  const dbVerified = norm(databaseBackup.verification_status) === 'verified';
  const safetyIndicator = unavailable ? result('Not confirmed', 'unknown') : dbBlocked ? result('Guard active', 'blocked') : dbVerified ? result('Database verified', 'completed') : databaseBackup.backup_id ? result('Database backed up', 'available') : result('Not confirmed', 'unknown');
  const state = unavailable ? 'unknown' : dbBlocked || repoUnavailable ? 'blocked' : active ? 'in_progress' : FAILED.has(restoreState) ? 'failed' : verified ? 'available' : 'needs_action';
  const statusLabel = {
    unknown: 'Not confirmed',
    blocked: repoUnavailable && !dbBlocked ? 'Needs attention' : 'Protected',
    in_progress: 'In progress',
    failed: 'Needs attention',
    available: 'Verified backup',
    needs_action: 'Review recommended',
  }[state];
  return {
    headline, summary, time: validTime(b.created_at), backup: backupIndicator, restore: restoreIndicator, safety: safetyIndicator,
    state, statusLabel,
    disabled: unavailable || dbBlocked || repoUnavailable || active,
    verified, previewReady: matchingPreview,
  };
}
export const RECOVERY_JOURNEY_STAGES = [
  { id: 'backup', label: 'Back Up', description: 'Create a protected copy of your workspace. A saved recovery point must still be verified.' },
  { id: 'verify', label: 'Verify', description: 'Check the integrity of a saved backup. Creation by itself does not establish verification.' },
  { id: 'preview', label: 'Preview', description: 'Review what a restore would change. A preview never applies those changes.' },
  { id: 'restore', label: 'Restore', description: 'A confirmed restore is executed by Pocket Lab with backend safety checks, a pre-restore checkpoint and post-restore health review.' },
];
export function recoveryJourneyStatus({ backup = {}, preview = {}, restore = {}, busy = '', saved = false } = {}) {
  const b = record(backup), p = record(preview), r = record(restore);
  if (saved) return Object.fromEntries(RECOVERY_JOURNEY_STAGES.map((s) => [s.id, 'unknown']));
  const hasBackup = Boolean(b.backup_id);
  const verified = hasBackup && norm(b.verification_status) === 'verified';
  const matching = verified && Boolean(p.preview_id) && p.backup_id === b.backup_id && norm(p.status) === 'ready' && p.restore_allowed !== false;
  const rStatus = norm(r.status);
  const backupStatus = norm(b.status || b.state);
  const verificationStatus = norm(b.verification_status || b.verification_state);
  const previewStatus = norm(p.status || p.state || p.phase);
  const statuses = {
    backup: ACTIVE.has(backupStatus) || b.pending === true ? 'in_progress' : BLOCKED.has(backupStatus) ? 'blocked' : FAILED.has(backupStatus) ? 'failed' : hasBackup ? 'completed' : 'not_started',
    verify: ACTIVE.has(verificationStatus) || ['verifying', 'checking'].includes(backupStatus) ? 'in_progress' : verified ? 'completed' : BLOCKED.has(verificationStatus) ? 'blocked' : FAILED.has(verificationStatus) ? 'failed' : hasBackup ? 'needs_action' : 'blocked',
    preview: ACTIVE.has(previewStatus) ? 'in_progress' : matching ? 'completed' : BLOCKED.has(previewStatus) ? 'blocked' : FAILED.has(previewStatus) ? 'failed' : verified ? 'needs_action' : 'blocked',
    restore: r.restore_id && ACTIVE.has(rStatus) ? 'in_progress' : r.restore_id && COMPLETE.has(rStatus) ? 'completed' : r.restore_id && BLOCKED.has(rStatus) ? 'blocked' : r.restore_id && FAILED.has(rStatus) ? 'failed' : matching ? 'available' : 'blocked',
  };
  if (busy && Object.hasOwn(statuses, busy)) statuses[busy] = 'in_progress';
  return statuses;
}
const ACTIVITY_KINDS = {
  backup: ['Backup recorded', 'Backup record'],
  verify: ['Backup verification', 'Verification record'],
  verification: ['Backup verification', 'Verification record'],
  preview: ['Restore preview', 'Preview record'],
  restore: ['Restore operation', 'Restore record'],
  checkpoint: ['Recovery checkpoint', 'Checkpoint record'],
};
export function recoveryPremiumActivity({ activity = [], backup = null, restore = null, unavailable = false } = {}) {
  if (unavailable) return [];
  const supplied = Array.isArray(activity) ? activity : [];
  const mapped = supplied.map((entry) => {
    const item = record(entry);
    const kind = norm(item.kind), id = string(item.id);
    if (!id || !Object.hasOwn(ACTIVITY_KINDS, kind)) return null;
    const state = norm(item.status);
    return { id: kind + ':' + id, kind, title: ACTIVITY_KINDS[kind][0], summary: string(item.summary) || 'Outcome not reported', time: validTime(item.occurred_at), state: COMPLETE.has(state) ? 'completed' : FAILED.has(state) ? 'failed' : ACTIVE.has(state) ? 'in_progress' : 'unknown', origin: 'event' };
  }).filter(Boolean);
  // Fallbacks are clearly marked current records, never synthetic history events.
  if (!mapped.length) {
    const b = record(backup), r = record(restore);
    if (b.backup_id) mapped.push({ id: 'backup:' + b.backup_id, kind: 'backup', title: 'Latest backup record', summary: b.verification_status === 'verified' ? 'The current backup record is marked verified.' : 'Verification has not been confirmed.', time: validTime(b.created_at), state: b.verification_status === 'verified' ? 'completed' : 'unknown', origin: 'snapshot' });
    if (r.restore_id) mapped.push({ id: 'restore:' + r.restore_id, kind: 'restore', title: 'Latest restore record', summary: string(r.summary) || 'Review the backend restore outcome.', time: validTime(r.completed_at), state: COMPLETE.has(norm(r.status)) ? 'completed' : FAILED.has(norm(r.status)) ? 'failed' : 'unknown', origin: 'snapshot' });
  }
  const seen = new Set();
  return mapped.filter((item) => { if (seen.has(item.id)) return false; seen.add(item.id); return true; }).sort((a, b) => {
    if (!a.time && !b.time) return 0;
    if (!a.time) return 1;
    if (!b.time) return -1;
    return Date.parse(b.time) - Date.parse(a.time);
  }).slice(0, 3);
}
export function recoveryRestoreImpact({ backup = {}, preview = {}, location = null } = {}) {
  const b = record(backup), p = record(preview), l = record(location || record(backup).location);
  const matched = Boolean(b.backup_id && p.preview_id && p.backup_id === b.backup_id);
  const verified = norm(b.verification_status) === 'verified';
  const readyLocation = isRecoveryLocationReady(l);
  return {
    backupId: string(b.backup_id), createdAt: validTime(b.created_at), verified,
    previewId: matched ? string(p.preview_id) : '',
    ready: matched && verified && norm(p.status) === 'ready' && p.restore_allowed !== false && readyLocation,
    count: matched && Number.isInteger(p.change_count) && p.change_count >= 0 ? p.change_count : null,
    included: matched && Array.isArray(p.included_components) ? p.included_components.filter((x) => typeof x === 'string').slice(0, 12) : [],
    excluded: matched && Array.isArray(p.excluded_components) ? p.excluded_components.filter((x) => typeof x === 'string').slice(0, 12) : [],
    location: string(l.display_name) || string(b.location?.display_name) || '',
    locationReady: readyLocation,
  };
}


// Azure Horizon overview facts are read-only presentation. A verified backup
// never grants restore authority, and a destination marked "available" is not
// automatically writable or ready.
export function recoveryOverviewFacts({
  backup = null, preview = null, locations = {}, saved = false, stale = false,
  reachable = true,
} = {}) {
  const unconfirmed = saved || stale || reachable === false;
  const b = record(backup);
  const p = record(preview);
  const locationList = Array.isArray(locations?.locations) ? locations.locations : [];
  const destination = record(locations?.selected_location || locationList.find((item) => item.is_selected) || b.location);
  const destinationState = norm(destination.status);
  const verified = b.backup_id && norm(b.verification_status) === 'verified';
  const matched = Boolean(b.backup_id && p.preview_id && p.backup_id === b.backup_id);
  const previewReady = matched && verified && norm(p.status) === 'ready' && p.restore_allowed !== false;
  const fact = (id, title, label, detail, state) => ({ id, title, label, detail, state });
  if (unconfirmed) {
    return [
      fact('backup', 'Latest backup', 'Not confirmed', b.created_at ? 'Saved record · live verification unavailable' : 'Live backup status unavailable', 'unknown'),
      fact('destination', 'Destination', 'Not confirmed', destination.display_name || 'Live storage readiness unavailable', 'unknown'),
      fact('preview', 'Restore preview', 'Not confirmed', 'A current matching preview is required', 'unknown'),
    ];
  }
  const backupFact = fact(
    'backup', 'Latest backup',
    verified ? 'Verified' : b.backup_id ? 'Needs verification' : 'No backup',
    b.created_at || (b.backup_id ? 'Time not reported' : 'Create a backup to begin'),
    verified ? 'completed' : 'needs_action',
  );
  const destinationLabel = destinationState === 'ready' && destination.available !== false && destination.ready !== false
    ? 'Ready'
    : ({ available: 'Available', low_space: 'Low space', read_only: 'Read-only', missing: 'Missing',
      unavailable: 'Unavailable', permission_required: 'Unavailable', repository_invalid: 'Unavailable',
      repository_missing: 'Missing' })[destinationState] || 'Unknown';
  const destinationFact = fact(
    'destination', 'Selected destination', destinationLabel,
    destination.display_name || 'No confirmed selected location',
    destinationLabel === 'Ready' ? 'completed' : ['Missing', 'Unavailable', 'Read-only', 'Low space'].includes(destinationLabel) ? 'blocked' : 'unknown',
  );
  const previewFact = fact(
    'preview', 'Restore preview',
    previewReady ? 'Preview ready' : matched && norm(p.status) === 'expired' ? 'Preview expired' : p.preview_id && !matched ? 'Different backup' : 'Preview required',
    previewReady ? 'Matches the latest verified backup · confirmation still required'
      : 'Verify and preview the selected backup before restoring',
    previewReady ? 'available' : 'needs_action',
  );
  return [backupFact, destinationFact, previewFact];
}
