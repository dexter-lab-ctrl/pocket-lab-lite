import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  CheckCircle2,
  FileCheck,
  HeartPulse,
  Camera,
  ExternalLink,
  FolderOpen,
  FolderPlus,
  HardDrive,
  Image as ImageIcon,
  RefreshCw,
  Search,
  X,
  Server,
  ShieldCheck,
  ShieldAlert,
  Smartphone,
  Trash2,
} from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { GlassCard, StatusBadge, StateSurface, PageHeader, LiteButton, LoadingCard, resolveSafeAppOpenPath, backendBadgeStatus, backendLabel } from './LiteUi.jsx';
import LiteActionProgress from './LiteActionProgress.jsx';

const KNOWN_APP_NAMES = ['PhotoPrism'];

const APP_FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'installed', label: 'Installed' },
  { id: 'available', label: 'Available' },
  { id: 'attention', label: 'Needs attention' },
];

const PHOTO_PRISM_ACTION_COPY = {
  connect_photos: {
    eyebrow: 'Photo source',
    label: 'Connect photos',
    description: 'Choose where PhotoPrism should look for pictures.',
  },
  import_photos: {
    eyebrow: 'Photo library',
    label: 'Import photos',
    description: 'Bring connected photos into PhotoPrism.',
  },
  backup_app: {
    eyebrow: 'Recovery',
    label: 'Back up app',
    description: 'Save PhotoPrism settings, mappings, and safe app records.',
  },
  check_app: {
    eyebrow: 'Safety',
    label: 'Check app',
    description: 'Check PhotoPrism health, route, storage, and safety record.',
  },
  preview_restore: {
    eyebrow: 'Recovery',
    label: 'Preview restore',
    description: 'Review what would be restored before making changes.',
  },
  backup_to_storage: {
    eyebrow: 'Recovery',
    label: 'Back up to storage device',
    description: 'Save the app backup to another joined storage device.',
  },
  install_app: {
    eyebrow: 'App setup',
    label: 'Install',
    description: 'Set up PhotoPrism.',
  },
  update_app: {
    eyebrow: 'App setup',
    label: 'Update',
    description: 'Check whether PhotoPrism is ready for a safe update.'
  },
  repair_app: {
    eyebrow: 'Recovery',
    label: 'Repair',
    description: 'Fix PhotoPrism route, health, and storage connection safely.',
  },
  remove_app: {
    eyebrow: 'Danger zone',
    label: 'Remove app',
    description: 'Remove PhotoPrism while preserving photos, backups, and backend records by default.',
  },
};

const PHOTO_PRISM_STORAGE_COPY = {
  phone_storage: {
    eyebrow: 'This phone',
    label: 'Use phone photos',
    description: 'Use photos from this phone.',
    busyLabel: 'Connecting...',
  },
  storage_device: {
    eyebrow: 'Joined device',
    label: 'Use storage device',
    description: 'Use photos from another joined storage device.',
    busyLabel: 'Connecting...',
  },
};

const PHONE_STORAGE_CONNECTED_FOLDERS = [
  'Android shared storage',
  'Camera photos',
  'Pictures',
  'Videos',
  'Downloads',
  'Music',
];


function actionCopy(actionId) {
  return PHOTO_PRISM_ACTION_COPY[actionId] || {
    eyebrow: 'Action',
    label: actionId.replace(/_/g, ' '),
    description: 'Pocket Lab will run this safely through the backend.',
  };
}

function isActionBusy(app, actionId, busyKey) {
  return busyKey === `${app?.id}:${actionId}`;
}

function busyActionLabel(actionId) {
  if (actionId === 'import_photos') return 'Working';
  if (actionId === 'backup_app') return 'Working';
  if (actionId === 'backup_to_storage') return 'Working';
  if (actionId === 'check_app') return 'Working';
  if (actionId === 'preview_restore') return 'Working';
  if (actionId === 'install_app') return 'Working';
  if (actionId === 'update_app') return 'Working';
  if (actionId === 'repair_app') return 'Working';
  return 'Working';
}

const APP_ACTION_CATEGORY_ORDER = ['media', 'safety', 'recovery', 'setup', 'danger'];

const APP_ACTION_CATEGORY_COPY = {
  media: { label: 'Photos', summary: 'Connect and import photos through backend-owned actions.' },
  safety: { label: 'Safety', summary: 'Check app health and protected records.' },
  recovery: { label: 'Recovery', summary: 'Back up, preview restore, and repair safely.' },
  setup: { label: 'App setup', summary: 'Install or check update readiness.' },
  danger: { label: 'Remove', summary: 'Advanced actions require explicit confirmation.' },
};

function normalizeActionStatus(rawStatus, enabled, busy = false, hasProgress = false) {
  if (busy || hasProgress) return 'running';
  const value = String(rawStatus || '').toLowerCase().replace(/[\s-]+/g, '_');
  if (['queued', 'pending'].includes(value)) return 'queued';
  if (['running', 'working', 'executing'].includes(value)) return 'running';
  if (['succeeded', 'success', 'done', 'completed', 'verified'].includes(value)) return 'done';
  if (['review', 'degraded', 'warning', 'needs_attention'].includes(value)) return 'review';
  if (['failed', 'failure', 'error'].includes(value)) return 'failed';
  if (['blocked', 'disabled', 'paused'].includes(value)) return 'blocked';
  if (['not_supported', 'unsupported'].includes(value)) return 'not_supported';
  if (['not_ready', 'unavailable'].includes(value)) return 'not_ready';
  if (['connected', 'imported'].includes(value)) return value;
  return enabled ? 'ready' : 'not_ready';
}

function getActionDisplayState(status, enabled = true) {
  const normalized = normalizeActionStatus(status, enabled);
  if (normalized === 'ready') return { status: 'healthy', label: 'Ready' };
  if (normalized === 'connected') return { status: 'healthy', label: 'Connected' };
  if (normalized === 'imported') return { status: 'healthy', label: 'Imported' };
  if (normalized === 'queued') return { status: 'degraded', label: 'Getting ready' };
  if (normalized === 'running') return { status: 'degraded', label: 'Working' };
  if (normalized === 'done') return { status: 'healthy', label: 'Done' };
  if (['review', 'failed'].includes(normalized)) return { status: 'degraded', label: 'Needs attention' };
  if (normalized === 'blocked') return { status: 'degraded', label: 'Paused for safety' };
  if (normalized === 'not_supported') return { status: 'unknown', label: 'Not available' };
  if (normalized === 'not_ready') return { status: 'unknown', label: enabled ? 'Waiting' : 'Not ready' };
  return { status: 'unknown', label: 'Unknown' };
}

function appActionCategory(actionId, action = {}) {
  if (action?.category === 'app_setup') return 'setup';
  if (action?.category) return String(action.category).replace('app_setup', 'setup');
  if (['open', 'open_full_screen', 'install_to_phone'].includes(actionId)) return 'access';
  if (['connect_photos', 'import_photos'].includes(actionId)) return 'media';
  if (actionId === 'check_app') return 'safety';
  if (['backup_app', 'preview_restore', 'backup_to_storage', 'repair_app'].includes(actionId)) return 'recovery';
  if (['install_app', 'update_app'].includes(actionId)) return 'setup';
  if (actionId === 'remove_app') return 'danger';
  return 'setup';
}

function actionDisabledReason(action = {}) {
  return action?.disabled_reason || action?.reason || '';
}

function normalizedActionValue(value) {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function actionHasRunEvidence(action = {}, result = null, progress = null) {
  const mergedResult = result || action?.result || {};
  const mergedProgress = progress || action?.progress || {};
  const resultStatus = normalizedActionValue(mergedResult?.status);
  const phase = normalizedActionValue(mergedProgress?.phase);
  return Boolean(
    action?.first_ran_at
    || action?.last_ran_at
    || action?.last_result
    || action?.evidence_ref
    || action?.receipt_id
    || action?.latest_backup_id
    || action?.troubleshooting?.available
    || ['completed', 'complete', 'done', 'succeeded', 'success', 'verified'].includes(phase)
    || (['succeeded', 'success', 'done', 'completed', 'verified'].includes(resultStatus) && mergedResult?.summary)
  );
}

function normalizeAppActionsPayload(payload = {}) {
  const actions = {};
  if (payload?.actions && typeof payload.actions === 'object') {
    Object.entries(payload.actions).forEach(([actionId, action]) => {
      if (action && typeof action === 'object') actions[actionId] = { id: actionId, ...action };
    });
  }
  if (Array.isArray(payload?.action_list)) {
    payload.action_list.forEach((action) => {
      const actionId = action?.id || action?.action_id;
      if (actionId) actions[actionId] = { ...(actions[actionId] || {}), ...action, id: actionId };
    });
  }
  const latestResults = payload?.latest_results && typeof payload.latest_results === 'object' ? payload.latest_results : {};
  const latestTroubleshooting = payload?.latest_troubleshooting_records && typeof payload.latest_troubleshooting_records === 'object'
    ? payload.latest_troubleshooting_records
    : {};
  Object.entries(latestResults).forEach(([actionId, latestResult]) => {
    if (!actions[actionId]) actions[actionId] = { id: actionId };
    actions[actionId] = {
      ...actions[actionId],
      result: { ...(actions[actionId].result || {}), ...(latestResult || {}) },
      latest_result: latestResult || null,
    };
  });
  Object.entries(latestTroubleshooting).forEach(([actionId, record]) => {
    if (!actions[actionId]) actions[actionId] = { id: actionId };
    actions[actionId] = {
      ...actions[actionId],
      troubleshooting: record || actions[actionId].troubleshooting,
    };
  });
  return {
    actions,
    updated_at: payload?.updated_at || null,
  };
}

function appSnapshotKey(app) {
  return String(app?.id || 'photoprism').toLowerCase();
}

function actionFromSnapshot(snapshot, actionId, fallback = {}) {
  const fresh = snapshot?.actions?.[actionId] || null;
  if (!fresh) return fallback || {};
  const merged = {
    ...(fallback || {}),
    ...fresh,
    result: {
      ...((fallback || {}).result || {}),
      ...(fresh.result || {}),
    },
    progress: {
      ...((fallback || {}).progress || {}),
      ...(fresh.progress || {}),
    },
    details: fresh.details || (fallback || {}).details,
    troubleshooting: fresh.troubleshooting || (fallback || {}).troubleshooting,
  };
  return merged;
}

function bestResultForAction(actionId, action = {}, result = null) {
  if (result?.action_id === actionId || (actionId === 'connect_photos' && ['duplicate_mapping', 'already_connected', 'created', 'queued'].includes(String(result?.status || '').toLowerCase()))) {
    return result;
  }
  if (actionHasRunEvidence(action, action?.result, action?.progress)) {
    return {
      action_id: actionId,
      status: action?.result?.status || action?.status || 'ready',
      summary: action?.last_result || action?.result?.summary || action?.summary || 'Action completed.',
      receipt_id: action?.receipt_id || action?.result?.receipt_id || null,
      backend_only: action?.result?.backend_only !== false,
    };
  }
  return null;
}

function actionRunTimestamp(action = {}, result = null, key = 'last') {
  const values = key === 'first'
    ? [action?.first_ran_at, action?.first_run_at, action?.started_at, result?.first_ran_at, result?.started_at]
    : [action?.last_ran_at, action?.last_run_at, action?.completed_at, action?.updated_at, result?.last_ran_at, result?.completed_at, result?.updated_at];
  return values.find(Boolean) || '';
}

function normalizeAppAction(entry) {
  const action = entry?.action || {};
  const actionId = entry?.actionId || action?.id || '';
  const copy = actionCopy(actionId);
  const busy = Boolean(entry?.busy);
  const connected = Boolean(entry?.connected);
  const progress = entry?.progress || action?.progress || null;
  const hasProgress = Boolean(progress?.running || ['queued', 'running'].includes(String(progress?.phase || '').toLowerCase()));
  const enabled = action?.enabled !== false && !entry?.disabled;
  const status = normalizeActionStatus(action?.status, enabled, busy, hasProgress);
  const category = appActionCategory(actionId, action);
  let display = getActionDisplayState(status, enabled);
  if (actionId === 'connect_photos') {
    if (connected) {
      display = { status: 'healthy', label: 'Connected' };
    } else if (busy) {
      display = { status: 'degraded', label: 'Connecting' };
    } else {
      display = { status: 'unknown', label: 'Not connected' };
    }
  }
  if (actionId === 'import_photos' && String(action?.status || '').toLowerCase() === 'imported') {
    display = { status: 'healthy', label: 'Imported' };
  }
  return {
    ...entry,
    id: actionId,
    actionId,
    action,
    copy,
    category,
    categoryLabel: APP_ACTION_CATEGORY_COPY[category]?.label || category,
    connected,
    enabled,
    status,
    display,
    progress,
    disabledReason: !enabled ? actionDisabledReason(action) || entry?.title || 'Action is not ready yet.' : '',
    risk: action?.risk || (category === 'danger' ? 'destructive' : category === 'recovery' || category === 'setup' ? 'review' : 'low'),
    detailsAvailable: actionId !== 'connect_photos',
    summary: action?.summary || copy.description,
  };
}

function groupAppActions(entries) {
  const grouped = new Map();
  entries.map(normalizeAppAction).forEach((entry) => {
    if (!entry?.actionId) return;
    const category = entry.category || 'setup';
    if (category === 'access') return;
    if (!grouped.has(category)) {
      grouped.set(category, {
        id: category,
        label: APP_ACTION_CATEGORY_COPY[category]?.label || category,
        summary: APP_ACTION_CATEGORY_COPY[category]?.summary || 'App actions.',
        actions: [],
      });
    }
    grouped.get(category).actions.push(entry);
  });
  return APP_ACTION_CATEGORY_ORDER.map((category) => grouped.get(category)).filter(Boolean);
}

function actionResultCopy(actionId, payload = {}, action = {}) {
  const status = String(payload?.status || action?.result?.status || '').toLowerCase();
  const summary = payload?.summary || action?.result?.summary || action?.last_result || '';
  if (actionId === 'backup_app') {
    return { title: status === 'queued' ? 'App backup queued' : 'App backup saved', summary: summary || 'Settings, mappings, route records, and safe app records were saved.', badges: ['Media excluded', 'Secrets hidden'] };
  }
  if (actionId === 'preview_restore') {
    return { title: status === 'queued' ? 'Restore preview queued' : 'Restore preview ready', summary: summary || 'No files were restored. No database was changed.', badges: ['Preview only', 'Media preserved'] };
  }
  if (actionId === 'update_app') {
    return { title: status === 'queued' ? 'Update readiness queued' : 'Update readiness checked', summary: summary || 'No update was applied.', badges: ['No update was applied', 'Rollback checked'] };
  }
  if (actionId === 'check_app') {
    return { title: status === 'queued' ? 'Check app queued' : status === 'failed' ? 'Something changed' : 'Protected app', summary: summary || 'Route, health, storage, and redaction checks passed.', badges: ['Saved for troubleshooting'] };
  }
  if (actionId === 'repair_app') {
    return { title: status === 'queued' ? 'Repair queued' : 'Repair completed', summary: summary || 'Route and health are ready.', badges: ['Non-destructive', 'Saved for troubleshooting'] };
  }
  if (actionId === 'import_photos') {
    return { title: status === 'queued' ? 'Import photos queued' : 'Import photos completed', summary: summary || 'PhotoPrism owns indexing and media details.', badges: ['Media flow', 'Saved for troubleshooting'] };
  }
  if (actionId === 'connect_photos') {
    return { title: 'Photos connected', summary: summary || 'PhotoPrism can now look there. Run Import photos to update your library.', badges: ['Read-only', 'Paths hidden'] };
  }
  if (actionId === 'backup_to_storage') {
    return { title: status === 'queued' ? 'Storage backup queued' : 'Storage target checked', summary: summary || 'Join a storage device to save app backups elsewhere.', badges: ['Readiness only'] };
  }
  return { title: status === 'queued' ? 'Getting ready' : 'Action updated', summary: summary || 'Pocket Lab updated this app action.', badges: [] };
}

function tileResultForAction(actionId, action = {}, result = null) {
  return bestResultForAction(actionId, action, result);
}

function AppActionDetailsButton({ available, onClick, expanded = false }) {
  if (!available) return null;
  return (
    <button
      type="button"
      className={`lite-app-action-details-button ${expanded ? 'is-expanded' : ''}`}
      onClick={onClick}
      aria-expanded={expanded}
    >
      <FileCheck className="h-4 w-4" />
      <span>{expanded ? 'Hide details' : 'Details'}</span>
    </button>
  );
}

function AppActionDisabledReason({ reason }) {
  if (!reason) return null;
  return <p className="lite-app-action-disabled-reason">{reason}</p>;
}

function AppActionResultCard({ actionId, action, result, onViewDetails, detailsExpanded = false }) {
  const payload = result || null;
  if (!payload) return null;
  const copy = actionResultCopy(actionId, payload, action);
  const detailsAvailable = true;
  return (
    <div className="lite-app-action-result-card" role="status" aria-live="polite">
      <div>
        <strong>{copy.title}</strong>
        <p>{copy.summary}</p>
      </div>
      {copy.badges?.length ? <div className="lite-app-action-result-badges">{copy.badges.map((badge) => <span key={badge}>{badge}</span>)}</div> : null}
      <AppActionDetailsButton available={detailsAvailable} onClick={onViewDetails} expanded={detailsExpanded} />
    </div>
  );
}

function AppActionGroup({ group, children }) {
  return (
    <section className={`lite-app-action-group is-${group.id}`} aria-label={`${group.label} actions`}>
      <div className="lite-app-action-group-head">
        <div>
          <span>{group.label}</span>
          <p>{group.summary}</p>
        </div>
      </div>
      <div className="lite-app-action-group-grid">
        {children}
      </div>
    </section>
  );
}


function actionProgressFromLifecycle(lifecycle, actionId, busy = false) {
  if (actionId === 'import_photos') {
    const media = lifecycle?.media || {};
    const operation = media?.last_import || null;
    const operationStatus = String(operation?.status || '').toLowerCase();
    const isRunning = Boolean(busy || ['queued', 'running'].includes(operationStatus));
    if (!isRunning) return null;
    const progress = operation?.progress || {};
    const rawPercent = Number(progress?.percent);
    let percent = Number.isFinite(rawPercent) ? rawPercent : 18;
    if (percent < 10) percent = 10;
    if (percent >= 100) percent = 88;
    percent = Math.min(92, Math.max(10, percent));
    return {
      running: isRunning,
      percent,
      indeterminate: Boolean(progress?.indeterminate || progress?.phase === 'executing' || operationStatus === 'running'),
      phase: progress?.phase || operation?.phase || operationStatus || (busy ? 'queued' : 'idle'),
      step: progress?.step || operation?.summary || (busy ? 'Importing photos' : 'Importing photos'),
      steps: progress?.steps || [],
    };
  }

  if (actionId === 'update_app') {
    const update = lifecycle?.update || {};
    const action = lifecycle?.actions?.update_app || {};
    const pending = update?.pending_check || null;
    const latest = update?.latest_check || action?.latest_check || null;
    const progress = pending?.progress || latest?.progress || action?.progress || {};
    const rawStatus = String(pending?.status || action?.status || '').toLowerCase();
    const isRunning = Boolean(busy || update?.operation_running || ['queued', 'running'].includes(rawStatus));
    if (!isRunning) return null;
    const rawPercent = Number(progress?.percent);
    const percent = Number.isFinite(rawPercent) ? Math.min(92, Math.max(10, rawPercent)) : 24;
    return {
      running: true,
      percent,
      indeterminate: progress?.indeterminate !== false,
      phase: progress?.phase || rawStatus || 'queued',
      step: progress?.step || 'Checking update readiness',
      steps: Array.isArray(progress?.steps) && progress.steps.length ? progress.steps : [
        { id: 'ready', label: 'Getting ready', status: 'active' },
        { id: 'working', label: 'Checking readiness', status: 'waiting' },
        { id: 'evidence', label: 'Evidence saved', status: 'waiting' },
      ],
    };
  }

  if (['backup_app', 'preview_restore', 'backup_to_storage'].includes(actionId)) {
    if (!busy) return null;
    const step = actionId === 'backup_app'
      ? 'Saving app settings'
      : actionId === 'preview_restore'
        ? 'Preparing restore preview. No changes made.'
        : 'Checking storage-device readiness.';
    return {
      running: true,
      percent: actionId === 'preview_restore' ? 28 : 20,
      indeterminate: true,
      phase: 'queued',
      step,
      steps: [
        { id: 'ready', label: 'Getting ready', status: 'completed' },
        { id: 'working', label: 'Working', status: 'active' },
        { id: 'evidence', label: 'Evidence saved', status: 'waiting' },
      ],
    };
  }

  if (!['check_app', 'repair_app'].includes(actionId)) return null;
  const operationAction = lifecycle?.operations?.actions?.[actionId] || lifecycle?.actions?.[actionId] || {};
  const currentAction = lifecycle?.current_action || lifecycle?.operations?.current_action || null;
  const currentMatches = currentAction?.action_id === actionId;
  const rawStatus = String((currentMatches ? currentAction?.status : operationAction?.status) || '').toLowerCase();
  const isRunning = Boolean(busy || ['queued', 'running'].includes(rawStatus));
  if (!isRunning) return null;
  const progress = (currentMatches ? currentAction?.progress : operationAction?.progress) || {};
  const rawPercent = Number(progress?.percent);
  const percent = Number.isFinite(rawPercent) ? Math.min(92, Math.max(10, rawPercent)) : 22;
  return {
    running: true,
    percent,
    indeterminate: progress?.indeterminate !== false,
    phase: progress?.phase || rawStatus || 'queued',
    step: progress?.step || (actionId === 'check_app' ? 'Checking safely' : 'Checking repair'),
    steps: Array.isArray(progress?.steps) ? progress.steps : [],
  };
}

function hasRunningPhotoPrismMedia(apps) {
  return (Array.isArray(apps) ? apps : []).some((app) => (
    isPhotoPrismApp(app)
    && Boolean(lifecycleProfile(app)?.media?.operation_running)
  ));
}

function PhotoPrismActionIcon({ actionId }) {
  if (actionId === 'connect_photos') return <FolderPlus className="h-4 w-4" />;
  if (actionId === 'import_photos') return <RefreshCw className="h-4 w-4" />;
  if (actionId === 'backup_app' || actionId === 'backup_to_storage' || actionId === 'preview_restore') return <FileCheck className="h-4 w-4" />;
  if (actionId === 'check_app') return <ShieldCheck className="h-4 w-4" />;
  if (actionId === 'install_app') return <Smartphone className="h-4 w-4" />;
  if (actionId === 'update_app' || actionId === 'repair_app') return <HeartPulse className="h-4 w-4" />;
  if (actionId === 'remove_app') return <Trash2 className="h-4 w-4" />;
  return <CheckCircle2 className="h-4 w-4" />;
}

function PhotoPrismStorageIcon({ preset }) {
  if (preset === 'phone_storage') return <Camera className="h-4 w-4" />;
  if (preset === 'storage_device') return <HardDrive className="h-4 w-4" />;
  return <FolderPlus className="h-4 w-4" />;
}

function catalogActionReference(result) {
  return result?.operation_id || result?.command_id || result?.job_id || result?.backup_id || result?.run_id || result?.mapping_id || '';
}

function catalogActionNotice(result, error) {
  if (error) {
    return {
      key: `error:${error}`,
      tone: 'danger',
      title: 'Needs attention',
      message: error,
      persistent: true,
    };
  }

  if (!result) return null;

  const status = String(result?.status || '').toLowerCase();
  const actionId = String(result?.action_id || result?.operation || '').toLowerCase();
  const reference = catalogActionReference(result);
  const base = {
    key: `${status || 'result'}:${actionId || reference || result?.summary || result?.message || Date.now()}`,
    tone: 'success',
    title: 'Request sent safely',
    message: result?.summary || result?.message || 'Pocket Lab accepted the request.',
    reference,
    timeoutMs: 5000,
    persistent: false,
  };

  if (status === 'already_connected' || status === 'duplicate_mapping') {
    return {
      ...base,
      tone: 'review',
      title: 'Already connected',
      message: result?.summary || 'This media folder is already connected to PhotoPrism.',
      timeoutMs: 8000,
    };
  }

  if (actionId === 'import_photos') {
    return {
      ...base,
      title: 'Import started',
      message: 'Pocket Lab is bringing connected photos into PhotoPrism.',
    };
  }

  if (actionId === 'check_app') {
    return {
      ...base,
      tone: 'review',
      title: 'Checking safely',
      message: 'Pocket Lab is checking PhotoPrism safely.',
      persistent: true,
    };
  }

  if (actionId === 'update_app') {
    return {
      ...base,
      tone: 'review',
      title: 'Checking update readiness',
      message: 'Pocket Lab is checking whether this app is ready. No update will be applied.',
      persistent: true,
    };
  }

  if (actionId === 'repair_app') {
    return {
      ...base,
      tone: 'review',
      title: 'Checking repair',
      message: 'Pocket Lab is checking route, health, and storage setup safely.',
      persistent: true,
    };
  }

  if (actionId === 'backup_app' || String(reference).startsWith('app-backup-photoprism')) {
    return {
      ...base,
      title: 'Backup started',
      message: 'Pocket Lab is saving PhotoPrism settings and safe app records.',
    };
  }

  if (actionId === 'preview_restore') {
    return {
      ...base,
      tone: 'review',
      title: 'Restore preview started',
      message: 'Pocket Lab is preparing a preview-only restore plan. Restore apply stays disabled.',
      persistent: true,
    };
  }

  const summary = String(result?.summary || result?.message || '').toLowerCase();
  if (summary.includes('media folder connected') || summary.includes('phone photos connected') || summary.includes('storage connected')) {
    return {
      ...base,
      title: 'Phone photos connected',
      message: 'PhotoPrism can now look there. Run Import photos to update your library.',
    };
  }

  if (result?.accepted || status === 'queued') {
    return {
      ...base,
      message: 'Pocket Lab accepted this safely.',
    };
  }

  return base;
}

function AppCatalogResultNotice({ result, error, onDismiss }) {
  const [noticeDetailsOpen, setNoticeDetailsOpen] = useState(false);
  const notice = catalogActionNotice(result, error);
  if (!notice) return null;

  const toneClass = notice.tone === 'danger'
    ? 'is-danger'
    : notice.tone === 'review'
      ? 'is-review'
      : 'is-success';

  return (
    <div className={`lite-catalog-action-notice ${toneClass}`} role={notice.tone === 'danger' ? 'alert' : 'status'} aria-live={notice.tone === 'danger' ? 'assertive' : 'polite'}>
      <div className="lite-catalog-action-notice-main">
        <span className="lite-catalog-action-notice-dot" aria-hidden="true" />
        <div>
          <strong>{notice.title}</strong>
          <p>{notice.message}</p>
        </div>
      </div>
      <div className="lite-catalog-action-notice-actions">
        {notice.reference ? (
          <button type="button" className="lite-catalog-action-notice-detail" onClick={() => setNoticeDetailsOpen((open) => !open)}>
            {noticeDetailsOpen ? 'Hide details' : 'Details'}
          </button>
        ) : null}
        <button type="button" className="lite-catalog-action-notice-close" onClick={onDismiss} aria-label="Dismiss App Catalog message">
          <X className="h-4 w-4" />
        </button>
      </div>
      {noticeDetailsOpen && notice.reference ? (
        <div className="lite-catalog-action-notice-reference">
          <span>Action reference</span>
          <code>{notice.reference}</code>
        </div>
      ) : null}
    </div>
  );
}

function PhotoPrismActionTile({
  app,
  actionId,
  action,
  busyKey,
  progress,
  result,
  tone = 'secondary',
  onClick,
  onViewDetails,
  detailsExpanded = false,
  disabled = false,
  title,
}) {
  const busy = isActionBusy(app, actionId, busyKey) || (actionId === 'connect_photos' && busyKey === `${app?.id}:phone_storage`);
  const normalized = normalizeAppAction({ app, actionId, action, busy, disabled, progress, result, title });
  const copy = normalized.copy;
  const progressState = normalized.progress || null;
  const reason = normalized.disabledReason;
  const isConnectPhotos = actionId === 'connect_photos';
  const isImportedPhotos = actionId === 'import_photos' && String(action?.status || '').toLowerCase() === 'imported';
  const isSimpleMediaShortcut = isConnectPhotos || isImportedPhotos;
  const progressDisablesAction = progressState?.running && !isSimpleMediaShortcut;
  const isDisabled = Boolean(disabled || action?.enabled === false || busy || progressDisablesAction);
  const showProgress = Boolean(!isSimpleMediaShortcut && progressState?.running && ['import_photos', 'check_app', 'repair_app', 'backup_app', 'preview_restore', 'backup_to_storage', 'update_app'].includes(actionId));
  const progressLabel = progressState?.running ? progressState.step || busyActionLabel(actionId) : '';
  const tileResult = isSimpleMediaShortcut ? null : tileResultForAction(actionId, action, result);
  const detailsAvailable = !isSimpleMediaShortcut;
  return (
    <div className={`lite-catalog-action-tile lite-app-action-tile ${isDisabled ? 'is-disabled' : ''} ${showProgress ? 'has-progress' : ''} ${progressState?.running ? 'is-running' : ''} ${actionId === 'remove_app' ? 'is-danger' : ''} ${isConnectPhotos && normalized.connected ? 'is-connected' : ''} ${isImportedPhotos ? 'is-imported' : ''}`} data-action-id={actionId}>
      <div className="lite-catalog-action-tile-copy">
        <span className="lite-catalog-action-tile-icon"><PhotoPrismActionIcon actionId={actionId} /></span>
        <div>
          <span>{copy.eyebrow || normalized.categoryLabel}</span>
          <strong>{copy.label}</strong>
          <p>{progressLabel || reason || normalized.summary || copy.description}</p>
        </div>
      </div>
      <div className="lite-app-action-state-row">
        <StatusBadge status={normalized.display.status}>{normalized.display.label}</StatusBadge>
      </div>
      <LiteButton
        tone={tone}
        onClick={onClick}
        disabled={isDisabled}
        title={title || reason || copy.description}
      >
        {busy || progressState?.running ? 'Working' : copy.label}
      </LiteButton>
      <AppActionDisabledReason reason={!showProgress && !isSimpleMediaShortcut ? reason : ''} />
      {!isSimpleMediaShortcut ? (
        <LiteActionProgress
          actionId={actionId}
          status={normalized.status}
          enabled={!(action?.enabled === false || (disabled && !busy && !progressState?.running))}
          disabledReason={(action?.enabled === false || (disabled && !busy && !progressState?.running)) && !showProgress ? reason : ''}
          progress={progressState || action?.progress}
          result={tileResult || action?.result}
          detailsAvailable={detailsAvailable}
          lastResult={action?.last_result || tileResult?.summary || ''}
          firstRanAt={actionRunTimestamp(action, tileResult, 'first')}
          lastRanAt={actionRunTimestamp(action, tileResult, 'last')}
          runCount={action?.run_count || 0}
          troubleshooting={action?.troubleshooting}
          evidenceRef={action?.evidence_ref || ''}
          receiptId={action?.receipt_id || action?.result?.receipt_id || tileResult?.receipt_id || ''}
          executionOwner={action?.execution_owner || ''}
        />
      ) : null}
      {!isSimpleMediaShortcut ? <AppActionResultCard actionId={actionId} action={action} result={tileResult} onViewDetails={onViewDetails} detailsExpanded={detailsExpanded} /> : null}
      {!isSimpleMediaShortcut && !tileResult ? <AppActionDetailsButton available={detailsAvailable} onClick={onViewDetails} expanded={detailsExpanded} /> : null}
    </div>
  );
}

function PhoneStorageConnectedFolders() {
  return (
    <div className="lite-catalog-connected-folders" role="status" aria-live="polite">
      <p>Connected folders from Phone Storage</p>
      <div className="lite-catalog-connected-folder-list">
        {storageConnectedFolderLabels().map((folder) => (
          <span key={folder}>{folder}</span>
        ))}
      </div>
    </div>
  );
}

function PhotoPrismStorageTile({ app, preset, busyKey, disabled, onClick }) {
  const copy = PHOTO_PRISM_STORAGE_COPY[preset];
  const busy = busyKey === `${app?.id}:${preset}`;
  return (
    <div className={`lite-catalog-storage-tile ${disabled ? 'is-disabled' : ''}`}>
      <div className="lite-catalog-storage-tile-copy">
        <span className="lite-catalog-storage-tile-icon"><PhotoPrismStorageIcon preset={preset} /></span>
        <div>
          <span>{copy.eyebrow}</span>
          <strong>{copy.label}</strong>
          <p>{copy.description}</p>
        </div>
      </div>
      <LiteButton tone={preset === 'storage_device' ? 'ghost' : 'secondary'} onClick={onClick} disabled={disabled}>
        {busy ? copy.busyLabel : copy.label}
      </LiteButton>
    </div>
  );
}

function previewStatusText(preview) {
  const status = String(preview?.status || '').toLowerCase();
  if (status === 'ready') return 'Ready';
  if (status === 'not_ready') return 'Storage not ready';
  return 'Checking';
}

function PhotoPrismStoragePreviewSheet({
  preview,
  loading,
  error,
  connecting,
  notice,
  onClose,
  onConfirm,
  onRetry,
  onDismissNotice,
}) {
  const ready = String(preview?.status || '').toLowerCase() === 'ready' && preview?.connect_payload;
  const notReady = String(preview?.status || '').toLowerCase() === 'not_ready';
  const folders = Array.isArray(preview?.subfolders) ? preview.subfolders : [];

  return (
      <section
        className="lite-catalog-storage-preview-sheet"
        role="region"
        aria-labelledby="lite-catalog-storage-preview-title"
      >
        <div className="lite-catalog-storage-preview-head">
          <div>
            <span>Connect photos</span>
            <h2 id="lite-catalog-storage-preview-title">Choose where PhotoPrism should look for pictures.</h2>
            <p>PhotoPrism will look for pictures in this phone’s storage.</p>
          </div>
          <button type="button" className="lite-catalog-storage-preview-close" onClick={onClose} aria-label="Cancel Connect photos">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="lite-catalog-storage-preview-root" aria-label="Phone storage mapping">
          <div>
            <span>Phone storage</span>
            <strong>{preview?.root || '~/storage'}</strong>
          </div>
          <span>{previewStatusText(preview)}</span>
          <span>Read-only</span>
        </div>

        <div className="lite-catalog-storage-preview-note">
          <strong>Photos are not moved by this step.</strong>
          <p>PhotoPrism will look in ~/storage. Run Import photos after connecting storage. PhotoPrism handles indexing inside the app.</p>
        </div>

        <div className="lite-catalog-storage-preview-list-head">
          <div>
            <span>Visible folders</span>
            <strong>Included with phone storage</strong>
          </div>
          <p>These folders are shown for clarity. Pocket Lab connects the whole phone storage folder.</p>
        </div>

        {loading ? (
          <div className="lite-catalog-storage-preview-list" aria-label="Loading visible folders">
            {[0, 1, 2, 3].map((item) => (
              <div key={item} className="lite-catalog-storage-preview-row is-skeleton">
                <span />
                <span />
                <span />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="lite-catalog-storage-preview-empty is-error" role="alert">
            <strong>Storage preview needs a moment</strong>
            <p>{error}</p>
            <LiteButton type="button" tone="secondary" onClick={onRetry}>Try again</LiteButton>
          </div>
        ) : notReady ? (
          <div className="lite-catalog-storage-preview-empty" role="status">
            <strong>Phone storage is not ready yet.</strong>
            <p>{preview?.reason || 'Run termux-setup-storage in Termux and allow storage access.'}</p>
          </div>
        ) : folders.length ? (
          <div className="lite-catalog-storage-preview-list" aria-label="Visible folders included with phone storage">
            {folders.map((folder) => (
              <div key={folder.path_summary || folder.name} className="lite-catalog-storage-preview-row">
                <span>{folder.name}</span>
                <span>{folder.kind || 'Folder'}</span>
                <strong>Included</strong>
              </div>
            ))}
          </div>
        ) : (
          <div className="lite-catalog-storage-preview-empty" role="status">
            <strong>No visible folders yet.</strong>
            <p>Pocket Lab can still connect the whole phone storage folder if Android storage access is ready.</p>
          </div>
        )}

        <div className="lite-catalog-storage-preview-actions">
          <LiteButton tone="primary" onClick={onConfirm} disabled={!ready || loading || connecting}>
            {connecting ? 'Connecting...' : 'Use phone storage'}
          </LiteButton>
          <LiteButton tone="secondary" onClick={onClose} disabled={connecting}>Cancel</LiteButton>
        </div>
        {notice ? (
          <div className={`lite-catalog-storage-preview-inline-notice is-${notice.tone || 'review'}`} role={notice.tone === 'danger' ? 'alert' : 'status'} aria-live={notice.tone === 'danger' ? 'assertive' : 'polite'}>
            <span className="lite-catalog-storage-preview-inline-dot" aria-hidden="true" />
            <div>
              <strong>{notice.title || 'Storage update'}</strong>
              <p>{notice.message || 'Pocket Lab recorded the storage update.'}</p>
            </div>
            <button type="button" onClick={onDismissNotice} aria-label="Dismiss storage message">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ) : null}
      </section>
  );
}

function PhotoPrismMediaFlowCard({ lifecycle, busyKey = '' }) {
  const flow = photoPrismMediaFlowState(lifecycle, busyKey);
  const steps = [
    { id: 'phone', label: 'Phone photos', icon: <Smartphone className="h-4 w-4" /> },
    { id: 'worker', label: 'Pocket Lab', icon: <RefreshCw className="h-4 w-4" /> },
    { id: 'prism', label: 'PhotoPrism', icon: <ImageIcon className="h-4 w-4" /> },
    { id: 'backup', label: 'Storage', icon: <HardDrive className="h-4 w-4" /> },
  ];

  return (
    <div className={`lite-catalog-media-flow-card is-${flow.state} motion-${flow.motion}`} aria-label={flow.ariaLabel}>
      <div className="lite-catalog-media-flow-copy">
        <span>{flow.eyebrow}</span>
        <strong>{flow.title}</strong>
        <p>{flow.summary}</p>
      </div>
      <div className="lite-catalog-media-flow-stage">
        <div className="lite-catalog-media-flow-visual" aria-hidden="true">
          {steps.map((step, index) => (
            <React.Fragment key={step.id}>
              {index > 0 ? <span className={`lite-catalog-media-flow-line is-${step.id}`}><i /></span> : null}
              <span className={`lite-catalog-media-flow-node is-${step.id} ${flow.activeNodes.includes(step.id) ? 'is-active' : ''} ${flow.doneNodes.includes(step.id) ? 'is-done' : ''}`}>
                {step.icon}
                <small>{step.label}</small>
              </span>
            </React.Fragment>
          ))}
        </div>
      </div>
      <span className="lite-catalog-media-flow-badge">{flow.badge}</span>
    </div>
  );
}

function photoPrismMediaFlowState(lifecycle, busyKey = '') {
  const media = lifecycle?.media || {};
  const backup = lifecycle?.backup || {};
  const backupTargets = lifecycle?.backup_targets || {};
  const mappingCount = Number(media?.mapping_count || lifecycle?.storage?.mapping_count || 0);
  const storageConnected = mappingCount > 0 || lifecycle?.storage?.status === 'connected';
  const lastImport = media?.last_import || {};
  const importStatus = String(lastImport?.status || '').toLowerCase();
  const actionBusy = String(busyKey || '').includes('import_photos');
  const operationRunning = Boolean(media?.operation_running || actionBusy);
  const importing = operationRunning && ['queued', 'running'].includes(importStatus);
  const failed = ['failed', 'timed_out'].includes(importStatus) || media?.status === 'review';
  const succeeded = ['succeeded'].includes(importStatus) || media?.evidence?.status === 'saved';
  const backupTargetReady = Boolean(backup?.target_ready || backupTargets?.ready_count > 0);
  const backupMissing = storageConnected && !backupTargetReady;

  if (!storageConnected) {
    return {
      state: 'idle',
      eyebrow: 'PhotoPrism flow',
      title: 'Connect photos to start',
      summary: 'Choose phone photos or a storage device before importing.',
      badge: 'Connect photos',
      ariaLabel: 'PhotoPrism media flow idle. Connect photos to start.',
      motion: 'calm',
      activeNodes: [],
      doneNodes: [],
    };
  }

  if (importing) {
    return {
      state: 'importing',
      eyebrow: 'PhotoPrism flow',
      title: 'Importing photos',
      summary: 'Pocket Lab is bringing connected photos into PhotoPrism.',
      badge: 'Working',
      ariaLabel: 'PhotoPrism media flow importing photos through Pocket Lab.',
      motion: 'active',
      activeNodes: ['phone', 'worker', 'prism'],
      doneNodes: ['phone'],
    };
  }

  if (failed) {
    return {
      state: 'review',
      eyebrow: 'PhotoPrism flow',
      title: 'Photo action needs review',
      summary: 'Check the latest media action before running it again.',
      badge: 'Needs review',
      ariaLabel: 'PhotoPrism media flow needs review.',
      motion: 'attention',
      activeNodes: [],
      doneNodes: ['phone'],
    };
  }

  if (backupMissing) {
    return {
      state: succeeded ? 'succeeded' : 'connected',
      eyebrow: 'PhotoPrism flow',
      title: succeeded ? 'Photo library updated' : 'Phone photos connected',
      summary: 'Add a storage device when you are ready to save app backups elsewhere.',
      badge: succeeded ? 'Done' : 'Connected',
      ariaLabel: 'PhotoPrism media flow connected. Backup target is not ready yet.',
      motion: succeeded ? 'calm' : 'ready',
      activeNodes: [],
      doneNodes: succeeded ? ['phone', 'worker', 'prism'] : ['phone'],
    };
  }

  return {
    state: succeeded ? 'succeeded' : 'connected',
    eyebrow: 'PhotoPrism flow',
    title: succeeded ? 'Photo library updated' : 'Phone photos connected',
    summary: succeeded ? 'PhotoPrism is ready with a saved troubleshooting record.' : 'PhotoPrism is ready to import connected media.',
    badge: succeeded ? 'Done' : 'Connected',
    ariaLabel: 'PhotoPrism media flow ready.',
    motion: succeeded ? 'calm' : 'ready',
    activeNodes: [],
    doneNodes: succeeded ? ['phone', 'worker', 'prism', ...(backupTargetReady ? ['backup'] : [])] : ['phone'],
  };
}



function safeDetailList(items, fallback = []) {
  const values = Array.isArray(items) ? items : fallback;
  return values.filter(Boolean).map((item) => String(item)).slice(0, 6);
}

function fallbackActionDetails(actionId, action = {}, result = null) {
  const copy = actionCopy(actionId);
  const summary = result?.summary || action?.summary || copy.description || 'Action details are available.';
  const browserOnly = ['open', 'open_full_screen', 'install_to_phone'].includes(actionId);
  const disabled = action?.enabled === false;
  return {
    title: action?.label || copy.label,
    status: action?.status || (disabled ? 'not_ready' : 'ready'),
    summary,
    what_happened: disabled
      ? [`This action is paused because ${String(action?.disabled_reason || action?.reason || 'it is not ready yet.').replace(/^./, (char) => char.toLowerCase())}`]
      : [summary],
    what_changed: [browserOnly || disabled ? 'Nothing changed.' : 'Pocket Lab will update this action after the backend finishes.'],
    what_did_not_happen: browserOnly
      ? ['No worker command was queued.', 'No app files were changed.', 'No photos were changed.']
      : ['No unsafe action was started from the browser.'],
    saved_for_troubleshooting: {
      saved: Boolean(result?.summary && !browserOnly),
      backend_only: true,
      summary: result?.summary && !browserOnly
        ? 'A backend record was saved for troubleshooting.'
        : 'No backend record was saved because this action did not run.',
    },
    technical_details: [
      `Execution owner: ${String(action?.execution_owner || (browserOnly ? 'browser navigation' : 'backend worker')).replace(/_/g, ' ')}`,
      `Action: ${actionId}`,
      `Status: ${action?.status || 'ready'}`,
      'Backend troubleshooting records stay backend-only.',
    ],
  };
}


function formatRunHistoryValue(value, hasEvidence) {
  if (value) return formatLiteTime(value);
  return hasEvidence ? 'Recorded' : 'Not run yet';
}

function detailsForAction(actionId, action = {}, result = null) {
  const details = result?.details && typeof result.details === 'object'
    ? result.details
    : action?.result?.details && typeof action.result.details === 'object'
      ? action.result.details
      : action?.details && typeof action.details === 'object'
        ? action.details
        : fallbackActionDetails(actionId, action, result);
  const summary = result?.summary || action?.last_result || action?.result?.summary || details.summary;
  const hasEvidence = actionHasRunEvidence(action, result, action?.progress);
  const firstRanAt = actionRunTimestamp(action, result, 'first') || details.first_ran_at || '';
  const lastRanAt = actionRunTimestamp(action, result, 'last') || details.last_ran_at || firstRanAt || '';
  return {
    ...details,
    summary,
    last_result: action?.last_result || result?.summary || action?.result?.summary || details.last_result || summary,
    first_ran_at: firstRanAt,
    last_ran_at: lastRanAt,
    run_count: Number(action?.run_count || details.run_count || (hasEvidence ? 1 : 0)),
    has_run_evidence: hasEvidence,
    saved_for_troubleshooting: details.saved_for_troubleshooting || {
      saved: hasEvidence,
      backend_only: true,
      summary: hasEvidence
        ? 'A backend record was saved for troubleshooting.'
        : 'No backend record was saved because this action did not run.',
    },
  };
}

function AppActionDetailsPanel({ details, onClose }) {
  if (!details) return null;
  const happened = safeDetailList(details.what_happened, [details.summary || 'Action details are available.']);
  const changed = safeDetailList(details.what_changed, ['Nothing changed.']);
  const didNotHappen = safeDetailList(details.what_did_not_happen, ['No unsafe action was started.']);
  const wouldHappen = safeDetailList(details.what_would_happen_after_confirmation);
  const willNotHappen = safeDetailList(details.what_will_not_happen_by_default);
  const technical = safeDetailList(details.technical_details);
  const saved = details.saved_for_troubleshooting && typeof details.saved_for_troubleshooting === 'object'
    ? details.saved_for_troubleshooting
    : { saved: false, backend_only: true, summary: 'No backend record was saved because this action did not run.' };

  return (
    <section className="lite-app-action-details-panel" role="region" aria-label={`${details.title || 'Action'} details`}>
      <div className="lite-app-action-details-head">
        <div>
          <span>Details</span>
          <h3>{details.title || 'Action details'}</h3>
          <p>{details.summary || 'Action details are available.'}</p>
        </div>
        <button type="button" className="lite-app-action-details-close" onClick={onClose} aria-label="Close action details">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="lite-app-action-details-status">
        <span>Last result</span>
        <strong>{details.last_result || getActionDisplayState(details.status || 'ready').label}</strong>
      </div>

      <div className="lite-app-action-details-grid">
        <div className="lite-app-action-detail-section lite-app-action-detail-section--run-history">
          <strong>Run history</strong>
          <p>First run: {formatRunHistoryValue(details.first_ran_at, Boolean(details.has_run_evidence || saved.saved))}</p>
          <p>Last run: {formatRunHistoryValue(details.last_ran_at, Boolean(details.has_run_evidence || saved.saved))}</p>
          {details.run_count ? <p>Run count: {details.run_count}</p> : null}
        </div>
        <div className="lite-app-action-detail-section">
          <strong>What happened</strong>
          {happened.map((item) => <p key={item}>{item}</p>)}
        </div>
        <div className="lite-app-action-detail-section">
          <strong>What changed</strong>
          {changed.map((item) => <p key={item}>{item}</p>)}
        </div>
        <div className="lite-app-action-detail-section">
          <strong>What did not happen</strong>
          {didNotHappen.map((item) => <p key={item}>{item}</p>)}
        </div>
        {wouldHappen.length ? (
          <div className="lite-app-action-detail-section">
            <strong>What would happen after confirmation</strong>
            {wouldHappen.map((item) => <p key={item}>{item}</p>)}
          </div>
        ) : null}
        {willNotHappen.length ? (
          <div className="lite-app-action-detail-section">
            <strong>What will not happen by default</strong>
            {willNotHappen.map((item) => <p key={item}>{item}</p>)}
          </div>
        ) : null}
        <div className="lite-app-action-detail-section lite-app-action-detail-section--saved">
          <strong>Saved for troubleshooting</strong>
          <p>{saved.summary || (saved.saved ? 'A backend record was saved for troubleshooting.' : 'No backend record was saved because this action did not run.')}</p>
        </div>
      </div>

      {technical.length ? (
        <details className="lite-app-action-technical-details">
          <summary>Technical details</summary>
          <div>
            {technical.map((item) => <p key={item}>{item}</p>)}
          </div>
        </details>
      ) : null}
    </section>
  );
}


function isStandalonePwa() {
  try {
    return window.matchMedia?.('(display-mode: standalone)')?.matches || window.navigator?.standalone === true;
  } catch {
    return false;
  }
}

function safeHaptic(duration = 8) {
  try {
    if (!isStandalonePwa()) return;
    navigator.vibrate?.(duration);
  } catch {
    // Optional PWA-only browser feedback.
  }
}

function handleCatalogPointerDown(event) {
  const target = event.target?.closest?.('button, a, [role="button"]');
  if (!target || target.getAttribute?.('aria-disabled') === 'true' || target.disabled) return;
  safeHaptic(6);
}


function appTone(status) {
  const value = String(status || '').toLowerCase();
  if (['ready', 'installed', 'healthy'].includes(value)) return 'healthy';
  if (['installing', 'queued', 'running'].includes(value)) return 'working';
  if (['needs_attention', 'unavailable', 'failed'].includes(value)) return 'degraded';
  return 'ready';
}

function appLabel(app) {
  const value = String(app?.status || '').toLowerCase();
  if (value === 'ready' && app?.actions?.open) return 'Ready';
  if (value === 'ready' || app?.installed) return 'Ready';
  if (value === 'installing') return 'Installing';
  if (value === 'needs_attention') return 'Needs attention';
  if (value === 'unavailable') return 'Unavailable';
  return 'Available';
}


function appFilterState(app) {
  const value = String(app?.status || '').toLowerCase();
  if (['needs_attention', 'unavailable', 'failed'].includes(value)) return 'attention';
  if (value === 'ready' || app?.installed) return 'installed';
  return 'available';
}

function lastOperationText(app) {
  const op = app?.last_operation;
  if (!op) return 'No install has run yet.';
  const when = op.updated_at ? ` · ${formatLiteTime(op.updated_at)}` : '';
  return `${op.message || 'Latest install status is available.'}${when}`;
}

function resolveAppOpenUrl(item) {
  return resolveSafeAppOpenPath(item);
}

function isAppInstalled(app) {
  const status = String(app?.status || '').toLowerCase();
  return Boolean(app?.installed || status === 'ready' || status === 'installed');
}

function isPhotoPrismApp(app) {
  return String(app?.id || '').toLowerCase() === 'photoprism' || String(app?.name || '').toLowerCase() === 'photoprism';
}

function canInstallAppToPhone(app) {
  return Boolean(isPhotoPrismApp(app) && isAppInstalled(app) && resolveAppOpenUrl(app));
}

function storageMappings(app) {
  const mappings = app?.storage?.mappings;
  return Array.isArray(mappings) ? mappings : [];
}

function isPhoneStorageMapping(mapping = {}) {
  const text = [
    mapping.mapping_id,
    mapping.id,
    mapping.label,
    mapping.source_label,
    mapping.source_type,
    mapping.preset,
    mapping.kind,
  ].map((value) => String(value || '').toLowerCase()).join(' ');
  return Boolean(
    text.includes('phone')
    || text.includes('android')
    || text.includes('shared storage')
    || text.includes('phone_storage')
  );
}

function phoneStorageConnected(app, lifecycle = null, actionSnapshot = null) {
  const mediaSources = [
    actionSnapshot?.media,
    lifecycle?.media,
    app?.lifecycle?.media,
    app?.media,
    app?.storage,
  ].filter(Boolean);
  for (const media of mediaSources) {
    const labels = Array.isArray(media?.labels) ? media.labels : [];
    const labelText = labels.map((label) => String(label || '').toLowerCase()).join(' ');
    const mappingCount = Number(media?.mapping_count || media?.connected_count || media?.count || 0);
    const statusText = String(media?.status || media?.summary || '').toLowerCase();
    if (labelText.includes('phone storage') || labelText.includes('phone') || labelText.includes('android shared storage')) return true;
    if (mappingCount > 0 && (statusText.includes('ready') || statusText.includes('connected') || statusText.includes('import'))) return true;
  }
  const mappings = storageMappings(app);
  if (!mappings.length) return false;
  return mappings.some(isPhoneStorageMapping) || mappings.length === 1;
}

function photosAlreadyImported(lifecycle = null, actionSnapshot = null, app = null) {
  const mediaSources = [
    actionSnapshot?.media,
    lifecycle?.media,
    app?.lifecycle?.media,
    app?.media,
  ].filter(Boolean);
  return mediaSources.some((media) => {
    const lastImport = media?.last_import && typeof media.last_import === 'object' ? media.last_import : null;
    const status = String(lastImport?.status || media?.last_import_status || '').toLowerCase();
    const evidenceStatus = String(lastImport?.evidence_status || media?.evidence?.status || '').toLowerCase();
    return Boolean(
      media?.last_imported_at
      || lastImport?.completed_at
      || ['succeeded', 'success', 'completed', 'done'].includes(status)
      || evidenceStatus === 'saved'
    );
  });
}

function storageConnectedFolderLabels() {
  return PHONE_STORAGE_CONNECTED_FOLDERS;
}

function storageMediaSummary(app) {
  const mappings = storageMappings(app);
  if (!mappings.length) return 'Not connected';
  return mappings
    .map((mapping) => `${mapping.label || mapping.source_label || 'Media folder'} · ${mapping.mode_label || 'Read-only'}`)
    .slice(0, 2)
    .join(', ');
}


function lifecycleProfile(app) {
  return app?.lifecycle || null;
}

function lifecycleAction(lifecycle, key) {
  return lifecycle?.actions && typeof lifecycle.actions === 'object' ? lifecycle.actions[key] || {} : {};
}

function lifecycleStorageLabel(lifecycle, app) {
  const storage = lifecycle?.storage || {};
  if (storage.mapping_count > 0) return storage.summary || 'Media connected';
  if (storageMappings(app).length) return app?.storage?.summary || 'Media connected';
  return 'Media not connected';
}

function lifecycleSecurityLabel(lifecycle, app) {
  const status = String(lifecycle?.security?.status || app?.security_profile?.status || '').toLowerCase();
  if (status === 'protected' || status === 'ready') return 'Protected app';
  return lifecycle?.security?.summary || app?.security_profile?.label || 'Check app';
}

function lifecycleBackupLabel(lifecycle, app) {
  const backup = lifecycle?.backup || {};
  if (backup.status === 'ready') return 'Backup ready';
  if (backup.target_available === false) return 'Backup target not ready';
  return backup.summary || app?.backup_profile?.label || 'Backup ready';
}

function lifecycleAttentionItems(lifecycle) {
  const items = lifecycle?.attention;
  return Array.isArray(items) ? items.slice(0, 3) : [];
}

function lifecycleMediaSummary(lifecycle) {
  const media = lifecycle?.media || {};
  if (media?.operation_running) return 'Importing photos';
  if (media?.last_imported_at) return `Last import ${formatLiteTime(media.last_imported_at)}`;
  if (Number(media?.mapping_count || 0) > 0) return media.summary || 'Import ready';
  return 'Connect a photo folder first';
}

function lifecycleActionReason(action) {
  return action?.enabled === false ? action.reason || 'Action not ready yet.' : '';
}

function storageDeviceCount(app) {
  const value = app?.device_relationships?.storage_devices_available
    ?? app?.available_device_capabilities?.media_storage
    ?? 0;
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function firstStorageDevice(app) {
  const devices = Array.isArray(app?.storage_devices) ? app.storage_devices : [];
  return devices.find((device) => device?.ready) || devices[0] || null;
}

function attentionReason(app, canOpen) {
  const status = String(app?.status || app?.health || '').toLowerCase();
  const health = String(app?.runtime?.health || '').toLowerCase();
  const access = app?.access || {};

  if (access.https_ready === false) return 'Remote access is not ready. Use the server device or check remote access health.';
  if (!isAppInstalled(app) && !canOpen) return 'Install this app to make Open available.';
  if (!canOpen || access.route_ready === false || app?.actions?.open === false) return 'Open is not ready yet. Pocket Lab is still checking the app route.';
  if (['needs_attention', 'unavailable', 'failed', 'error', 'blocked'].includes(status) || ['unhealthy', 'failed', 'error'].includes(health)) {
    return 'App needs attention. The app has not reported a healthy status yet.';
  }
  if (['installing', 'queued', 'running'].includes(status)) return 'Setting up. Pocket Lab is preparing this app.';
  return '';
}

function AppIcon({ app }) {
  const [failed, setFailed] = useState(false);

  if (isPhotoPrismApp(app) && !failed) {
    return (
      <img
        src="/assets/apps/photoprism.svg"
        className="lite-catalog-app-icon-img"
        alt=""
        aria-hidden="true"
        onError={() => setFailed(true)}
      />
    );
  }

  return <ImageIcon className="h-6 w-6" />;
}

function CatalogSkeletons() {
  return (
    <div className="lite-catalog-grid lite-catalog-skeleton-grid" aria-label="Loading App Catalog">
      {[0, 1, 2].map((item) => (
        <GlassCard key={item} className="lite-catalog-card lite-catalog-app-card lite-catalog-skeleton-card">
          <div className="lite-catalog-skeleton-icon" />
          <div className="lite-catalog-skeleton-line is-title" />
          <div className="lite-catalog-skeleton-line" />
          <div className="lite-catalog-skeleton-line is-short" />
          <div className="lite-catalog-skeleton-button" />
        </GlassCard>
      ))}
    </div>
  );
}


export default function CatalogScreen({ onOpenWorkspace }) {
  const { data, loading, error, refresh } = useLiteResource(liteApi.catalog, []);
  const [query, setQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('all');
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [openingId, setOpeningId] = useState(null);
  const [storageBusy, setStorageBusy] = useState('');
  const [actionBusyKey, setActionBusyKey] = useState('');
  const [removeConfirmApp, setRemoveConfirmApp] = useState(null);
  const [storagePreviewApp, setStoragePreviewApp] = useState(null);
  const [storagePreview, setStoragePreview] = useState(null);
  const [storagePreviewLoading, setStoragePreviewLoading] = useState(false);
  const [storagePreviewError, setStoragePreviewError] = useState(null);
  const [storagePreviewNotice, setStoragePreviewNotice] = useState(null);
  const [detailsActionId, setDetailsActionId] = useState(null);
  const [actionSnapshots, setActionSnapshots] = useState({});

  const apps = data?.apps || data?.items || [];
  const access = data?.access || {};
  const featuredApp = apps.find((app) => KNOWN_APP_NAMES.includes(app?.name) || String(app?.id || '').toLowerCase() === 'photoprism') || apps[0];

  const filteredApps = useMemo(() => {
    const value = query.trim().toLowerCase();
    return apps.filter((app) => {
      const matchesQuery = !value || `${app.name || ''} ${app.summary || ''} ${app.category || ''}`.toLowerCase().includes(value);
      const matchesFilter = activeFilter === 'all' || appFilterState(app) === activeFilter;
      return matchesQuery && matchesFilter;
    });
  }, [apps, activeFilter, query]);


  const refreshAppActions = useCallback(async (appId = 'photoprism') => {
    try {
      const payload = await liteApi.appActions(appId || 'photoprism');
      const snapshot = normalizeAppActionsPayload(payload || {});
      setActionSnapshots((current) => ({
        ...current,
        [String(appId || 'photoprism').toLowerCase()]: snapshot,
      }));
      return snapshot;
    } catch (_error) {
      return null;
    }
  }, []);


  useEffect(() => {
    const notice = catalogActionNotice(result, actionError);
    if (!notice || notice.persistent) return undefined;
    const timer = window.setTimeout(() => {
      setResult(null);
      setActionError(null);
    }, notice.timeoutMs || 5000);
    return () => window.clearTimeout(timer);
  }, [result, actionError]);

  useEffect(() => {
    if (!storagePreviewNotice) return undefined;
    const timer = window.setTimeout(() => setStoragePreviewNotice(null), storagePreviewNotice.timeoutMs || 6200);
    return () => window.clearTimeout(timer);
  }, [storagePreviewNotice]);

  useEffect(() => {
    const busyAppAction = /:(import_photos|check_app|repair_app)$/.test(actionBusyKey || '');
    const runningCatalogAction = apps.some((app) => {
      const current = lifecycleProfile(app)?.current_action || lifecycleProfile(app)?.operations?.current_action;
      return ['check_app', 'repair_app'].includes(String(current?.action_id || '')) && ['queued', 'running'].includes(String(current?.status || '').toLowerCase());
    });
    if (!busyAppAction && !runningCatalogAction && !hasRunningPhotoPrismMedia(apps)) return undefined;
    const timer = window.setInterval(() => {
      refresh();
      refreshAppActions('photoprism');
    }, 4000);
    return () => window.clearInterval(timer);
  }, [actionBusyKey, apps, refresh, refreshAppActions]);


  function openActionDetails(actionId, appId = 'photoprism') {
    setDetailsActionId((current) => {
      const next = current === actionId ? null : actionId;
      if (next) refreshAppActions(appId || 'photoprism');
      return next;
    });
  }

  function closeActionDetails() {
    setDetailsActionId(null);
  }


  function dismissActionNotice() {
    setResult(null);
    setActionError(null);
  }


  async function install(app, event) {
    event?.stopPropagation?.();
    if (!app) return;
    setBusyId(app.id);
    setResult({ status: 'queued', message: `${app.name || 'App'} install started.` });
    setActionError(null);
    try {
      const targetNodeId = app?.target?.default_node_id || 'pocket-lab-lite-server';
      setResult(await liteApi.installApp(app.id, { target_node_id: targetNodeId }));
      refresh();
      window.setTimeout(refresh, 700);
      window.setTimeout(refresh, 1800);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  function openApp(app, event) {
    event?.stopPropagation?.();
    const target = resolveAppOpenUrl(app);
    if (!target) return;
    setOpeningId(app.id);
    window.setTimeout(() => {
      setOpeningId(null);
      if (typeof onOpenWorkspace === 'function') {
        onOpenWorkspace(app, target);
        return;
      }
      window.location.assign(target);
    }, 120);
  }

  function openAppFullScreen(app, event) {
    event?.stopPropagation?.();
    const target = resolveAppOpenUrl(app);
    if (!target) return;
    window.location.assign(target);
  }

  function installAppToPhone(app, event) {
    event?.stopPropagation?.();
    const target = resolveAppOpenUrl(app);
    if (!canInstallAppToPhone(app) || !target) return;
    setResult({
      accepted: true,
      summary: `Opening ${app?.name || 'this app'} full screen. Use your browser menu to install it on this phone.`,
    });
    window.setTimeout(() => window.location.assign(target), 160);
  }


  async function refreshPhotoPrismState() {
    await Promise.allSettled([
      liteApi.photoprismStorageMappings(),
      liteApi.appLifecycleProfile('photoprism'),
      refreshAppActions('photoprism'),
    ]);
    await refresh();
  }

  async function loadStoragePreview() {
    setStoragePreviewLoading(true);
    setStoragePreviewError(null);
    setStoragePreviewNotice(null);
    try {
      setStoragePreview(await liteApi.photoprismStoragePreview());
    } catch (err) {
      setStoragePreviewError(err.message || 'Pocket Lab could not check phone storage.');
    } finally {
      setStoragePreviewLoading(false);
    }
  }

  async function openPhoneStoragePreview(app, event) {
    event?.stopPropagation?.();
    if (!isPhotoPrismApp(app)) return;
    setStoragePreviewApp(app);
    setStoragePreview(null);
    setStoragePreviewNotice(null);
    await loadStoragePreview();
  }

  function closeStoragePreview(force = false) {
    if (storageBusy && !force) return;
    setStoragePreviewApp(null);
    setStoragePreview(null);
    setStoragePreviewError(null);
    setStoragePreviewLoading(false);
    setStoragePreviewNotice(null);
  }

  async function connectPhoneStorageFromPreview() {
    const app = storagePreviewApp;
    if (!isPhotoPrismApp(app) || !storagePreview?.connect_payload) return;
    setStorageBusy(`${app.id}:phone_storage`);
    setActionError(null);
    setStoragePreviewNotice(null);
    setResult({ status: 'queued', summary: 'Connecting phone storage...' });
    try {
      const response = await liteApi.connectPhotoPrismStorage(storagePreview.connect_payload);
      setResult({ action_id: 'connect_photos', ...response, summary: 'Phone storage connected. PhotoPrism can now look there. Run Import photos to update your library.' });
      closeStoragePreview(true);
      await refreshPhotoPrismState();
      window.setTimeout(refresh, 700);
      window.setTimeout(refresh, 1800);
    } catch (err) {
      const detail = err?.payload?.detail;
      if (detail?.status === 'duplicate_mapping') {
        setResult(null);
        setStoragePreviewNotice({
          tone: 'review',
          title: 'Already connected',
          message: detail.summary || 'Phone storage is already connected to PhotoPrism.',
          timeoutMs: 6500,
        });
        await refreshPhotoPrismState();
      } else {
        setStoragePreviewNotice({
          tone: 'danger',
          title: 'Could not connect storage',
          message: detail?.summary || err.message || 'Pocket Lab could not connect phone storage.',
          timeoutMs: 8500,
        });
        setActionError(null);
      }
    } finally {
      setStorageBusy('');
    }
  }

  async function connectStorage(app, preset, event) {
    event?.stopPropagation?.();
    if (!isPhotoPrismApp(app)) return;
    if (preset === 'phone_storage') {
      await openPhoneStoragePreview(app, event);
      return;
    }
    const storageDevice = firstStorageDevice(app);
    const presets = {
      storage_device: {
        label: storageDevice?.name || 'Storage device',
        source_type: 'storage_device',
        source_path: '~/.pocket_lab/lite/media',
        target: 'import',
        mode: 'read_only',
        device_id: storageDevice?.id,
        device_name: storageDevice?.name,
      },
    };
    if (preset === 'storage_device' && !storageDevice) {
      setActionError('Join a storage device first, then connect it here.');
      return;
    }
    const payload = presets[preset];
    if (!payload) return;
    setStorageBusy(`${app.id}:${preset}`);
    setActionError(null);
    setResult({ status: 'queued', summary: 'Connecting media folder...' });
    try {
      const response = await liteApi.connectPhotoPrismStorage(payload);
      setResult({ action_id: 'connect_photos', ...response });
      await refreshPhotoPrismState();
      window.setTimeout(refresh, 700);
    } catch (err) {
      const detail = err?.payload?.detail;
      if (detail?.status === 'duplicate_mapping') {
        setResult({ action_id: 'connect_photos', status: 'already_connected', summary: detail.summary || 'This media folder is already connected to PhotoPrism.' });
      } else {
        setActionError(err.message);
      }
    } finally {
      setStorageBusy('');
    }
  }


  async function runLifecycleAction(app, actionId, event, extraPayload = {}) {
    event?.stopPropagation?.();
    if (!isPhotoPrismApp(app) || !actionId) return;
    const busyKey = `${app.id}:${actionId}`;
    setActionBusyKey(busyKey);
    setActionError(null);
    setResult({ status: 'queued', action_id: actionId, summary: 'Sending app action to Pocket Lab...' });
    try {
      const appId = app.id || 'photoprism';
      const response = await liteApi.runAppAction(appId, actionId, { reason: `manual ${actionId.replace(/_/g, ' ')}`, ...extraPayload });
      setResult({ action_id: actionId, ...response });
      await refreshAppActions(appId);
      refresh();
      window.setTimeout(() => { refresh(); refreshAppActions(appId); }, 700);
      window.setTimeout(() => { refresh(); refreshAppActions(appId); }, 1800);
    } catch (err) {
      const detail = err?.payload?.detail;
      setActionError(detail?.summary || err.message);
    } finally {
      setActionBusyKey('');
    }
  }


  async function confirmRemoveApp(app, event) {
    event?.stopPropagation?.();
    if (!app) return;
    await runLifecycleAction(app, 'remove_app', event, {
      confirm: true,
      reason: 'user confirmed app removal from App Catalog',
      preserve_media: true,
      preserve_backups: true,
      preserve_backend_records: true,
      preserve_storage_mappings: true,
    });
    setRemoveConfirmApp(null);
  }

  function renderAppCard(app, featured = false) {
    const status = String(app.status || 'not_installed').toLowerCase();
    const installing = status === 'installing' || busyId === app.id;
    const opening = openingId === app.id;
    const canInstall = Boolean(app?.actions?.install) && !installing;
    const canOpen = Boolean(app?.actions?.open && resolveAppOpenUrl(app));
    const installed = isAppInstalled(app);
    const canInstallPhone = Boolean(canOpen && canInstallAppToPhone(app));
    const targetName = app?.target?.eligible_devices?.[0]?.name || 'Server Host';
    const reason = attentionReason(app, canOpen);
    const progress = app?.progress;
    const percent = Math.min(100, Math.max(0, ((progress?.current || 1) / (progress?.total || 7)) * 100));
    const cardClassName = `lite-catalog-card lite-catalog-app-card ${featured ? 'is-featured' : ''} ${installing ? 'is-installing' : ''}`;
    const actionsClassName = `lite-catalog-actions ${canInstallPhone ? 'has-phone-install' : ''}`;
    const lifecycle = lifecycleProfile(app);
    const actionSnapshot = actionSnapshots[appSnapshotKey(app)] || null;
    const actionState = (actionId) => actionFromSnapshot(actionSnapshot, actionId, lifecycleAction(lifecycle, actionId));
    const lifecycleAttention = lifecycleAttentionItems(lifecycle);
    const openAction = actionState('open');
    const connectPhotosAction = actionState('connect_photos');
    const isPhoneStorageConnected = phoneStorageConnected(app, lifecycle, actionSnapshot);
    const checkAppAction = actionState('check_app');
    const backupAppAction = actionState('backup_app');
    const importPhotosAction = actionState('import_photos');
    const importProgress = actionProgressFromLifecycle(lifecycle, 'import_photos', actionBusyKey === `${app.id}:import_photos`);
    const checkAppProgress = actionProgressFromLifecycle(lifecycle, 'check_app', actionBusyKey === `${app.id}:check_app`);
    const repairAppProgress = actionProgressFromLifecycle(lifecycle, 'repair_app', actionBusyKey === `${app.id}:repair_app`);
    const backupAppProgress = actionProgressFromLifecycle(lifecycle, 'backup_app', actionBusyKey === `${app.id}:backup_app`);
    const previewRestoreProgress = actionProgressFromLifecycle(lifecycle, 'preview_restore', actionBusyKey === `${app.id}:preview_restore`);
    const backupToStorageProgress = actionProgressFromLifecycle(lifecycle, 'backup_to_storage', actionBusyKey === `${app.id}:backup_to_storage`);
    const updateAppProgress = actionProgressFromLifecycle(lifecycle, 'update_app', actionBusyKey === `${app.id}:update_app`);
    const previewRestoreAction = actionState('preview_restore');
    const backupToStorageAction = actionState('backup_to_storage');
    const installAppAction = actionState('install_app');
    const updateAppAction = actionState('update_app');
    const repairAppAction = actionState('repair_app');
    const removeAppAction = actionState('remove_app');
    const mediaSummary = lifecycleMediaSummary(lifecycle);
    const isPhotosImported = photosAlreadyImported(lifecycle, actionSnapshot, app);
    const appActionEntries = [
      {
        actionId: 'open',
        action: openAction,
        tone: 'primary',
        onClick: (event) => openApp(app, event),
        disabled: !canOpen || openAction.enabled === false,
        title: lifecycleActionReason(openAction) || app?.access?.message || 'Open PhotoPrism.',
        result,
      },
      {
        actionId: 'connect_photos',
        action: {
          ...connectPhotosAction,
          status: isPhoneStorageConnected ? 'connected' : connectPhotosAction.status,
          summary: isPhoneStorageConnected ? 'Phone storage is connected.' : connectPhotosAction.summary,
        },
        busyKey: storageBusy || actionBusyKey,
        tone: 'secondary',
        connected: isPhoneStorageConnected,
        onClick: (event) => {
          if (isPhoneStorageConnected) return;
          openPhoneStoragePreview(app, event);
        },
        disabled: isPhoneStorageConnected || connectPhotosAction.enabled === false || Boolean(storageBusy),
        title: isPhoneStorageConnected ? 'Phone storage is already connected.' : lifecycleActionReason(connectPhotosAction),
        result: isPhoneStorageConnected ? null : result,
      },
      {
        actionId: 'import_photos',
        action: {
          ...importPhotosAction,
          status: isPhotosImported ? 'imported' : importPhotosAction.status,
          summary: isPhotosImported ? 'Photos are imported. PhotoPrism will handle new photos.' : importPhotosAction.summary,
          disabled_reason: isPhotosImported ? 'Photos are already imported. PhotoPrism will handle new photos.' : importPhotosAction.disabled_reason,
          reason: isPhotosImported ? 'Photos are already imported. PhotoPrism will handle new photos.' : importPhotosAction.reason,
          enabled: isPhotosImported ? false : importPhotosAction.enabled,
        },
        busyKey: actionBusyKey,
        progress: isPhotosImported ? null : importProgress,
        tone: 'secondary',
        onClick: (event) => {
          if (isPhotosImported) return;
          runLifecycleAction(app, 'import_photos', event);
        },
        disabled: isPhotosImported || importPhotosAction.enabled === false || actionBusyKey === `${app.id}:import_photos`,
        title: isPhotosImported ? 'Photos are already imported. PhotoPrism will handle new photos.' : lifecycleActionReason(importPhotosAction),
        result: isPhotosImported ? null : result,
      },
      {
        actionId: 'check_app',
        action: checkAppAction,
        busyKey: actionBusyKey,
        progress: checkAppProgress,
        tone: 'ghost',
        onClick: (event) => runLifecycleAction(app, 'check_app', event),
        disabled: checkAppAction.enabled === false || actionBusyKey === `${app.id}:check_app`,
        title: lifecycleActionReason(checkAppAction),
        result,
      },
      {
        actionId: 'backup_app',
        action: backupAppAction,
        busyKey: actionBusyKey,
        progress: backupAppProgress,
        tone: 'ghost',
        onClick: (event) => runLifecycleAction(app, 'backup_app', event),
        disabled: backupAppAction.enabled === false || actionBusyKey === `${app.id}:backup_app`,
        title: lifecycleActionReason(backupAppAction),
        result,
      },
      {
        actionId: 'preview_restore',
        action: previewRestoreAction,
        busyKey: actionBusyKey,
        progress: previewRestoreProgress,
        tone: 'ghost',
        onClick: (event) => runLifecycleAction(app, 'preview_restore', event),
        disabled: previewRestoreAction.enabled === false || actionBusyKey === `${app.id}:preview_restore`,
        title: lifecycleActionReason(previewRestoreAction),
        result,
      },
      {
        actionId: 'backup_to_storage',
        action: backupToStorageAction,
        busyKey: actionBusyKey,
        progress: backupToStorageProgress,
        tone: 'ghost',
        onClick: (event) => runLifecycleAction(app, 'backup_to_storage', event, { target_device_id: lifecycle?.backup?.target_device_id || lifecycle?.backup?.target_id }),
        disabled: backupToStorageAction.enabled === false || actionBusyKey === `${app.id}:backup_to_storage`,
        title: lifecycleActionReason(backupToStorageAction),
        result,
      },
      {
        actionId: 'repair_app',
        action: repairAppAction,
        busyKey: actionBusyKey,
        progress: repairAppProgress,
        tone: 'ghost',
        onClick: (event) => runLifecycleAction(app, 'repair_app', event),
        disabled: repairAppAction.enabled === false || actionBusyKey === `${app.id}:repair_app`,
        title: lifecycleActionReason(repairAppAction),
        result,
      },
      {
        actionId: 'install_app',
        action: installAppAction,
        busyKey: actionBusyKey,
        tone: 'ghost',
        onClick: (event) => runLifecycleAction(app, 'install_app', event),
        disabled: installAppAction.enabled === false || actionBusyKey === `${app.id}:install_app`,
        title: lifecycleActionReason(installAppAction),
        result,
      },
      {
        actionId: 'update_app',
        action: updateAppAction,
        busyKey: actionBusyKey,
        progress: updateAppProgress,
        tone: 'ghost',
        onClick: (event) => runLifecycleAction(app, 'update_app', event),
        disabled: updateAppAction.enabled === false || actionBusyKey === `${app.id}:update_app`,
        title: lifecycleActionReason(updateAppAction),
        result,
      },
      {
        actionId: 'remove_app',
        action: removeAppAction,
        busyKey: actionBusyKey,
        tone: 'danger',
        onClick: (event) => { event?.stopPropagation?.(); setRemoveConfirmApp(app); },
        disabled: removeAppAction.enabled === false,
        title: lifecycleActionReason(removeAppAction),
        result,
      },
    ];
    const appActionGroups = groupAppActions(appActionEntries);

    return (
      <GlassCard
        key={app.id}
        className={cardClassName}
      >
        <div className="lite-catalog-card-top">
          <div className="lite-catalog-icon"><AppIcon app={app} /></div>
          <StatusBadge status={appTone(status)} className="lite-catalog-status-badge">{appLabel(app)}</StatusBadge>
        </div>
        <div className="lite-catalog-card-title-row">
          <div>
            <p className="lite-catalog-category">{featured ? 'Featured local app' : app.category || 'Local app'}</p>
            <h2>{app.name}</h2>
          </div>
        </div>
        <p>{app.summary}</p>
        {installed ? (
          <div className="lite-catalog-trust-marker" aria-label="Self-hosted app">
            <ShieldCheck className="h-4 w-4" />
            <span>Self-hosted app</span>
          </div>
        ) : null}
        {installed ? (
          <div className="lite-catalog-profile-markers" aria-label="App protection and backup readiness">
            <span><ShieldCheck className="h-4 w-4" />{app?.security_profile?.label || 'Protected app'}</span>
            <span><FileCheck className="h-4 w-4" />{app?.backup_profile?.media || 'Media excluded'}</span>
          </div>
        ) : null}
        {installed && lifecycle ? (
          <div className="lite-catalog-lifecycle-panel" aria-label="Unified App Lifecycle status">
            <div className="lite-catalog-lifecycle-head">
              <div>
                <span>Unified App Lifecycle</span>
                <strong>{lifecycle.status === 'ready' ? 'Ready' : lifecycle.status === 'review' ? 'Needs attention' : lifecycle.summary || 'Checking'}</strong>
              </div>
              <StatusBadge status={backendBadgeStatus(lifecycle.status)}>
                {backendLabel(lifecycle.status, { ready: 'Ready', review: 'Needs attention', danger: 'Needs attention', checking: 'Checking' })}
              </StatusBadge>
            </div>
            <div className="lite-catalog-lifecycle-chips">
              <span><Server className="h-4 w-4" />{lifecycle?.host_device?.label || 'Runs on Server Phone'}</span>
              <span><FolderOpen className="h-4 w-4" />{lifecycleStorageLabel(lifecycle, app)}</span>
              <span><ShieldCheck className="h-4 w-4" />{lifecycleSecurityLabel(lifecycle, app)}</span>
              <span><FileCheck className="h-4 w-4" />{lifecycleBackupLabel(lifecycle, app)}</span>
            </div>
            {lifecycleAttention.length ? (
              <div className="lite-catalog-lifecycle-attention">
                {lifecycleAttention.map((item) => (
                  <span key={item.id || item.title}><strong>{item.title || 'Needs attention'}</strong>{item.summary || 'Check again.'}</span>
                ))}
              </div>
            ) : null}
            <div className="lite-catalog-action-center" aria-label="Action Center">
              <div className="lite-catalog-action-center-head">
                <div>
                  <span>Action Center</span>
                  <strong>{mediaSummary}</strong>
                </div>
                <PhotoPrismMediaFlowCard lifecycle={lifecycle} busyKey={actionBusyKey} />
              </div>
              <div className="lite-catalog-action-groups">
                {appActionGroups.map((group) => (
                  <AppActionGroup key={group.id} group={group}>
                    {group.actions.map((entry) => (
                      <React.Fragment key={entry.actionId}>
                        <PhotoPrismActionTile
                          app={app}
                          actionId={entry.actionId}
                          action={entry.action}
                          busyKey={entry.busyKey || actionBusyKey}
                          progress={entry.progress}
                          result={entry.result}
                          tone={entry.tone}
                          onClick={entry.onClick}
                          onViewDetails={() => openActionDetails(entry.actionId, app.id || 'photoprism')}
                          detailsExpanded={detailsActionId === entry.actionId}
                          disabled={entry.disabled}
                          title={entry.title}
                        />
                        {entry.actionId === 'connect_photos' && isPhoneStorageConnected ? (
                          <PhoneStorageConnectedFolders />
                        ) : null}
                        {entry.actionId === 'connect_photos' && !isPhoneStorageConnected && storagePreviewApp?.id === app.id ? (
                          <div className="lite-catalog-storage-preview-anchor">
                            <PhotoPrismStoragePreviewSheet
                              preview={storagePreview}
                              loading={storagePreviewLoading}
                              error={storagePreviewError}
                              connecting={Boolean(storageBusy)}
                              notice={storagePreviewNotice}
                              onClose={closeStoragePreview}
                              onConfirm={connectPhoneStorageFromPreview}
                              onRetry={loadStoragePreview}
                              onDismissNotice={() => setStoragePreviewNotice(null)}
                            />
                          </div>
                        ) : null}
                        {entry.actionId === 'import_photos' && isPhotosImported ? (
                          <p className="lite-catalog-media-note">Photos imported. PhotoPrism will handle new photos.</p>
                        ) : null}
                        {entry.actionId !== 'connect_photos' && detailsActionId === entry.actionId ? (
                          <div className="lite-catalog-action-details-anchor">
                            <AppActionDetailsPanel
                              details={detailsForAction(entry.actionId, entry.action, tileResultForAction(entry.actionId, entry.action, entry.result))}
                              onClose={closeActionDetails}
                            />
                          </div>
                        ) : null}
                      </React.Fragment>
                    ))}
                  </AppActionGroup>
                ))}
              </div>
              <div className="lite-catalog-action-reasons">
                {importPhotosAction.enabled === false ? <span>Import photos: {lifecycleActionReason(importPhotosAction)}</span> : null}
                {previewRestoreAction.enabled === false ? <span>Preview restore: {lifecycleActionReason(previewRestoreAction)}</span> : null}
                {backupToStorageAction.enabled === false ? <span>Back up to storage device: {lifecycleActionReason(backupToStorageAction)}</span> : null}
                {updateAppAction.enabled === false ? <span>Update: {lifecycleActionReason(updateAppAction)}</span> : null}
                {repairAppAction.enabled === false ? <span>Repair: {lifecycleActionReason(repairAppAction)}</span> : null}
              </div>
            </div>
          </div>
        ) : null}
        <div className="lite-catalog-meta lite-catalog-meta-grid">
          <span><Server className="h-4 w-4" /> {targetName}</span>
          <span><CheckCircle2 className="h-4 w-4" /> {canOpen ? 'Ready' : app?.access?.message || 'Available after install'}</span>
          <span><HeartPulse className="h-4 w-4" /> {app?.runtime?.health ? `Health: ${app.runtime.health}` : 'Health: not installed'}</span>
        </div>
        {reason ? (
          <div className="lite-catalog-attention-reason">
            <strong>{installed ? (canOpen ? 'Status note' : 'Attention') : 'Setup'}</strong>
            <p>{reason}</p>
          </div>
        ) : null}
        {progress ? (
          <div className="lite-catalog-progress" aria-label="Install progress">
            <div><strong>{progress.step || 'Working'}</strong><span>{progress.current || 1}/{progress.total || 7}</span></div>
            <p>{progress.message || 'Preparing the app.'}</p>
            <div className="lite-catalog-progress-bar"><span style={{ width: `${percent}%` }} /></div>
          </div>
        ) : null}
        {isPhotoPrismApp(app) ? (
          <div className="lite-catalog-storage-panel">
            <div className="lite-catalog-storage-head">
              <div>
                <span>Media folders</span>
                <strong>{storageMappings(app).length ? storageMediaSummary(app) : 'No folders connected'}</strong>
              </div>
              <FolderOpen className="h-5 w-5" />
            </div>
            <div className="lite-catalog-storage-facts">
              <span><Server className="h-4 w-4" /> Runs on {app?.host_device_name || targetName}</span>
              <span><FolderPlus className="h-4 w-4" /> Media from: {storageMappings(app).length ? app?.storage?.summary || storageMediaSummary(app) : 'Not connected'}</span>
              <span><HardDrive className="h-4 w-4" /> Storage devices: {storageDeviceCount(app)} available</span>
            </div>
            {storageMappings(app).length ? (
              <div className="lite-catalog-storage-chips">
                {storageMappings(app).map((mapping) => (
                  <span key={mapping.mapping_id || mapping.label}>
                    {mapping.label || 'Media folder'} · {mapping.mode_label || 'Read-only'}
                  </span>
                ))}
              </div>
            ) : (
              <p className="lite-catalog-storage-empty">No media folders connected yet. Connect a photo folder to start using PhotoPrism.</p>
            )}
            <div className="lite-catalog-storage-actions">
              <PhotoPrismStorageTile
                app={app}
                preset="phone_storage"
                busyKey={storageBusy}
                disabled={Boolean(storageBusy)}
                onClick={(event) => connectStorage(app, 'phone_storage', event)}
              />
              <PhotoPrismStorageTile
                app={app}
                preset="storage_device"
                busyKey={storageBusy}
                disabled={Boolean(storageBusy) || storageDeviceCount(app) < 1}
                onClick={(event) => connectStorage(app, 'storage_device', event)}
              />
            </div>
            {storageDeviceCount(app) < 1 ? (
              <p className="lite-catalog-storage-hint">Join a storage device to use remote media folders.</p>
            ) : null}
          </div>
        ) : null}
        <div className="lite-catalog-last-op"><strong>Latest status</strong><p>{lastOperationText(app)}</p></div>
        <div className={actionsClassName}>
          <LiteButton onClick={(event) => install(app, event)} disabled={!canInstall} tone={canInstall ? 'primary' : 'secondary'}>{installing ? 'Installing...' : app?.actions?.retry ? 'Retry' : status === 'ready' ? 'Installed' : 'Install'}</LiteButton>
          <LiteButton onClick={(event) => openApp(app, event)} disabled={!canOpen} tone={canOpen ? 'primary' : 'ghost'}><ExternalLink className="h-4 w-4" />{opening ? 'Opening...' : 'Open'}</LiteButton>
          <LiteButton onClick={(event) => openAppFullScreen(app, event)} disabled={!canOpen} tone="secondary"><ExternalLink className="h-4 w-4" />Open full screen</LiteButton>
          {canInstallPhone ? (
            <LiteButton onClick={(event) => installAppToPhone(app, event)} tone="secondary"><Smartphone className="h-4 w-4" />Install to phone</LiteButton>
          ) : null}
        </div>
      </GlassCard>
    );
  }

  const insecureAppCount = apps.filter((app) => {
    const accessState = app?.access || {};
    const appStatus = String(app?.status || app?.health || '').toLowerCase();

    return (
      accessState.https_ready === false ||
      accessState.route_ready === false ||
      accessState.open === false ||
      appStatus === 'unhealthy' ||
      appStatus === 'error' ||
      appStatus === 'blocked'
    );
  }).length;

  const isCatalogSecure = Boolean(access?.https_ready) && insecureAppCount === 0;

  return (
    <div className="lite-catalog-screen" onPointerDown={handleCatalogPointerDown}>
      <PageHeader
        eyebrow="Apps"
        title="App Catalog"
        description="Install and open local apps from your Pocket Lab. App setup is handled by the Server Host."
        actions={(
          <div className="lite-catalog-hero-actions">
            <div className={isCatalogSecure ? 'lite-home-pill lite-catalog-hero-pill is-secure' : 'lite-home-pill lite-catalog-hero-pill is-not-secure'}>
              {isCatalogSecure ? <ShieldCheck className="h-4 w-4" /> : <ShieldAlert className="h-4 w-4" />}
              {isCatalogSecure ? 'Secure Access' : 'Not Secure'}
            </div>
            <LiteButton onClick={refresh} tone="secondary"><RefreshCw className="h-4 w-4" />Refresh</LiteButton>
          </div>
        )}
      />

      <div className="lite-catalog-toolbar">
        <div className="lite-catalog-search-wrap"><Search className="h-5 w-5" /><input className="lite-catalog-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search apps" aria-label="Search apps" /></div>
        <div className="lite-catalog-filter-pills" role="tablist" aria-label="Filter apps" data-access-contract="Secure access ready">
          {APP_FILTERS.map((filter) => (
            <button key={filter.id} type="button" className={activeFilter === filter.id ? 'is-active' : ''} onClick={() => setActiveFilter(filter.id)}>{filter.label}</button>
          ))}
        </div>
        <p>{filteredApps.length} shown</p>
      </div>



      {featuredApp ? (
        <section className="lite-catalog-featured" aria-label="Featured app">
          {renderAppCard(featuredApp, true)}
        </section>
      ) : null}





      {error ? <StateSurface tone="degraded" title="Catalog needs a moment" description={error} className="mb-5" /> : null}
      {loading ? <CatalogSkeletons /> : null}
      {loading ? <LoadingCard label="Loading apps..." /> : null}

      <div className="lite-catalog-grid">
        {filteredApps.filter((app) => app.id !== featuredApp?.id).map((app) => renderAppCard(app))}
      </div>

      {!loading && filteredApps.length === 0 ? (
        <GlassCard className="lite-catalog-empty-state">
          <div className="lite-catalog-empty-icon"><ImageIcon className="h-5 w-5" /></div>
          <div>
            <h2>{query ? 'No matching apps' : apps.length ? 'No apps in this view' : 'No apps installed yet'}</h2>
            <p>{query ? 'Try another search or clear the filter.' : apps.length ? 'Choose another filter to see more apps.' : 'Install your first local app to start using this self-hosted workspace.'}</p>
          </div>
          <LiteButton onClick={refresh} tone="secondary"><RefreshCw className="h-4 w-4" />Check again</LiteButton>
        </GlassCard>
      ) : null}
      {removeConfirmApp ? (
        <GlassCard className="lite-catalog-remove-confirm" role="dialog" aria-label="Confirm remove">
          <div>
            <span>Confirm remove</span>
            <h2>Remove PhotoPrism?</h2>
            <p>This removes the app runtime and Pocket Lab route when removal support is enabled. Your photo files and backups will not be deleted by default. Backend records preserved.</p>
          </div>
          <div className="lite-catalog-remove-confirm-grid">
            <span><strong>What will happen</strong>Remove app runtime and route after backend support is enabled.</span>
            <span><strong>What will not happen</strong>Your photo files and backups will not be deleted by default.</span>
          </div>
          <div className="lite-catalog-remove-confirm-actions">
            <LiteButton tone="danger" onClick={(event) => confirmRemoveApp(removeConfirmApp, event)}>Confirm remove</LiteButton>
            <LiteButton tone="secondary" onClick={() => setRemoveConfirmApp(null)}>Cancel</LiteButton>
          </div>
        </GlassCard>
      ) : null}

      <AppCatalogResultNotice result={result} error={actionError} onDismiss={dismissActionNotice} />

    </div>
  );
}
