import React, { useEffect, useMemo, useState } from 'react';
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
  index_photos: {
    eyebrow: 'Photo library',
    label: 'Index photos',
    description: 'Refresh PhotoPrism’s photo library.',
  },
  cancel_media: {
    eyebrow: 'Photo library',
    label: 'Stop photo action',
    description: 'Safely stop the current Import or Index job.',
  },
  backup_app: {
    eyebrow: 'Recovery',
    label: 'Back up app',
    description: 'Save PhotoPrism settings, mappings, and safe app records.',
  },
  check_app: {
    eyebrow: 'Safety',
    label: 'Check app',
    description: 'Check PhotoPrism safety and app protection.',
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
    description: 'Update PhotoPrism after safety checks.',
  },
  repair_app: {
    eyebrow: 'Recovery',
    label: 'Repair',
    description: 'Fix PhotoPrism routing, health, or setup issues.',
  },
  remove_app: {
    eyebrow: 'Danger zone',
    label: 'Remove app',
    description: 'Remove PhotoPrism while preserving photos, backups, and evidence by default.',
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
  if (actionId === 'import_photos') return 'Importing...';
  if (actionId === 'index_photos') return 'Indexing...';
  if (actionId === 'cancel_media') return 'Stopping...';
  if (actionId === 'backup_app') return 'Backing up...';
  if (actionId === 'backup_to_storage') return 'Backing up...';
  if (actionId === 'check_app') return 'Checking...';
  if (actionId === 'preview_restore') return 'Preparing...';
  if (actionId === 'install_app') return 'Installing...';
  if (actionId === 'update_app') return 'Updating...';
  if (actionId === 'repair_app') return 'Repairing...';
  return 'Working...';
}


function actionProgressFromLifecycle(lifecycle, actionId, busy = false) {
  const media = lifecycle?.media || {};
  const operation = actionId === 'index_photos'
    ? media?.last_index
    : actionId === 'import_photos'
      ? media?.last_import
      : actionId === 'cancel_media'
        ? (media?.last_import?.status === 'running' || media?.last_import?.status === 'queued' ? media?.last_import : media?.last_index)
        : null;
  const operationStatus = String(operation?.status || '').toLowerCase();
  const isRunning = Boolean(
    busy
    || (actionId === 'cancel_media' && media?.operation_running)
    || ['queued', 'running'].includes(operationStatus)
  );
  if (!isRunning && !operation?.progress) return null;
  const progress = operation?.progress || {};
  const rawPercent = Number(progress?.percent);
  let percent = Number.isFinite(rawPercent) ? rawPercent : isRunning ? 12 : 0;
  if (isRunning && percent < 8) percent = 8;
  percent = Math.min(100, Math.max(0, percent));
  return {
    running: isRunning,
    percent,
    phase: progress?.phase || operation?.phase || operationStatus || (busy ? 'queued' : 'idle'),
    step: progress?.step || operation?.summary || (busy ? busyActionLabel(actionId) : ''),
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
  if (actionId === 'import_photos' || actionId === 'index_photos') return <RefreshCw className="h-4 w-4" />;
  if (actionId === 'cancel_media') return <X className="h-4 w-4" />;
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
  return result?.command_id || result?.job_id || result?.backup_id || result?.run_id || result?.mapping_id || '';
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

  if (actionId === 'index_photos') {
    return {
      ...base,
      title: 'Library update started',
      message: 'Pocket Lab is refreshing PhotoPrism’s library.',
    };
  }

  if (actionId === 'cancel_media') {
    return {
      ...base,
      tone: status === 'idle' ? 'review' : 'success',
      title: status === 'idle' ? 'Nothing running' : 'Photo action stopped',
      message: result?.summary || 'Pocket Lab safely stopped the current PhotoPrism media action.',
      timeoutMs: 8000,
    };
  }

  if (actionId === 'backup_app' || String(reference).startsWith('app-backup-photoprism')) {
    return {
      ...base,
      title: 'Backup started',
      message: 'Pocket Lab is saving PhotoPrism settings and safe app records.',
    };
  }

  const summary = String(result?.summary || result?.message || '').toLowerCase();
  if (summary.includes('media folder connected') || summary.includes('phone photos connected') || summary.includes('storage connected')) {
    return {
      ...base,
      title: 'Phone photos connected',
      message: 'PhotoPrism can now look there. Run Import photos or Index photos to update your library.',
    };
  }

  if (result?.accepted || status === 'queued') {
    return {
      ...base,
      message: 'Pocket Lab queued this through the control plane.',
    };
  }

  return base;
}

function AppCatalogResultNotice({ result, error, onDismiss }) {
  const [receiptOpen, setReceiptOpen] = useState(false);
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
          <button type="button" className="lite-catalog-action-notice-detail" onClick={() => setReceiptOpen((open) => !open)}>
            {receiptOpen ? 'Hide receipt' : 'Receipt'}
          </button>
        ) : null}
        <button type="button" className="lite-catalog-action-notice-close" onClick={onDismiss} aria-label="Dismiss App Catalog message">
          <X className="h-4 w-4" />
        </button>
      </div>
      {receiptOpen && notice.reference ? (
        <div className="lite-catalog-action-notice-reference">
          <span>Reference</span>
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
  tone = 'secondary',
  onClick,
  disabled = false,
  title,
}) {
  const copy = actionCopy(actionId);
  const busy = isActionBusy(app, actionId, busyKey) || (actionId === 'connect_photos' && busyKey === `${app?.id}:phone_storage`);
  const progressState = progress || null;
  const reason = action?.enabled === false ? lifecycleActionReason(action) : '';
  const progressDisablesAction = progressState?.running && actionId !== 'cancel_media';
  const isDisabled = Boolean(disabled || action?.enabled === false || busy || progressDisablesAction);
  const showProgress = Boolean(progressState && ['import_photos', 'index_photos'].includes(actionId));
  const progressLabel = progressState?.running ? progressState.step || busyActionLabel(actionId) : '';
  return (
    <div className={`lite-catalog-action-tile ${isDisabled ? 'is-disabled' : ''} ${showProgress ? 'has-progress' : ''} ${progressState?.running ? 'is-running' : ''} ${actionId === 'remove_app' ? 'is-danger' : ''}`}>
      <div className="lite-catalog-action-tile-copy">
        <span className="lite-catalog-action-tile-icon"><PhotoPrismActionIcon actionId={actionId} /></span>
        <div>
          <span>{copy.eyebrow}</span>
          <strong>{copy.label}</strong>
          <p>{progressLabel || reason || copy.description}</p>
        </div>
      </div>
      <LiteButton
        tone={tone}
        onClick={onClick}
        disabled={isDisabled}
        title={title || reason || copy.description}
      >
        {busy || (progressState?.running && actionId !== 'cancel_media') ? busyActionLabel(actionId) : copy.label}
      </LiteButton>
      {showProgress ? (
        <div className="lite-catalog-action-progress" role="progressbar" aria-label={`${copy.label} progress`} aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progressState.percent || 0)}>
          <span style={{ width: `${Math.min(100, Math.max(0, progressState.percent || 0))}%` }} />
        </div>
      ) : null}
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
  onClose,
  onConfirm,
  onRetry,
}) {
  const ready = String(preview?.status || '').toLowerCase() === 'ready' && preview?.connect_payload;
  const notReady = String(preview?.status || '').toLowerCase() === 'not_ready';
  const folders = Array.isArray(preview?.subfolders) ? preview.subfolders : [];

  return (
    <div className="lite-catalog-storage-preview-backdrop" role="presentation" onClick={onClose}>
      <section
        className="lite-catalog-storage-preview-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="lite-catalog-storage-preview-title"
        onClick={(event) => event.stopPropagation()}
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
          <p>PhotoPrism will look in ~/storage. You can run Import photos or Index photos after connecting storage.</p>
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
      </section>
    </div>
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
  const lastIndex = media?.last_index || {};
  const importStatus = String(lastImport?.status || '').toLowerCase();
  const indexStatus = String(lastIndex?.status || '').toLowerCase();
  const actionBusy = String(busyKey || '').includes('import_photos') || String(busyKey || '').includes('index_photos');
  const operationRunning = Boolean(media?.operation_running || actionBusy);
  const importing = operationRunning && ['queued', 'running'].includes(importStatus);
  const indexing = operationRunning && ['queued', 'running'].includes(indexStatus);
  const failed = ['failed', 'timed_out'].includes(importStatus) || ['failed', 'timed_out'].includes(indexStatus) || media?.status === 'review';
  const succeeded = ['succeeded'].includes(importStatus) || ['succeeded'].includes(indexStatus) || media?.evidence?.status === 'saved';
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

  if (indexing || actionBusy) {
    return {
      state: 'indexing',
      eyebrow: 'PhotoPrism flow',
      title: 'Updating library',
      summary: 'Pocket Lab is refreshing PhotoPrism with connected media.',
      badge: 'Indexing',
      ariaLabel: 'PhotoPrism media flow updating the PhotoPrism library.',
      motion: 'active',
      activeNodes: ['worker', 'prism'],
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
    summary: succeeded ? 'PhotoPrism is ready with saved media evidence.' : 'PhotoPrism is ready to import or index connected media.',
    badge: succeeded ? 'Done' : 'Connected',
    ariaLabel: 'PhotoPrism media flow ready.',
    motion: succeeded ? 'calm' : 'ready',
    activeNodes: [],
    doneNodes: succeeded ? ['phone', 'worker', 'prism', ...(backupTargetReady ? ['backup'] : [])] : ['phone'],
  };
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
  if (media?.operation_running) return 'Indexing';
  if (media?.last_indexed_at) return `Last indexed ${formatLiteTime(media.last_indexed_at)}`;
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
    if (!hasRunningPhotoPrismMedia(apps)) return undefined;
    const timer = window.setInterval(() => {
      refresh();
    }, 2500);
    return () => window.clearInterval(timer);
  }, [apps, refresh]);

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
      liteApi.appActions('photoprism'),
    ]);
    await refresh();
  }

  async function loadStoragePreview() {
    setStoragePreviewLoading(true);
    setStoragePreviewError(null);
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
    await loadStoragePreview();
  }

  function closeStoragePreview(force = false) {
    if (storageBusy && !force) return;
    setStoragePreviewApp(null);
    setStoragePreview(null);
    setStoragePreviewError(null);
    setStoragePreviewLoading(false);
  }

  async function connectPhoneStorageFromPreview() {
    const app = storagePreviewApp;
    if (!isPhotoPrismApp(app) || !storagePreview?.connect_payload) return;
    setStorageBusy(`${app.id}:phone_storage`);
    setActionError(null);
    setResult({ status: 'queued', summary: 'Connecting phone storage...' });
    try {
      const response = await liteApi.connectPhotoPrismStorage(storagePreview.connect_payload);
      setResult({ ...response, summary: 'Phone storage connected. PhotoPrism can now look in ~/storage. Run Import photos or Index photos to update your library.' });
      closeStoragePreview(true);
      await refreshPhotoPrismState();
      window.setTimeout(refresh, 700);
      window.setTimeout(refresh, 1800);
    } catch (err) {
      const detail = err?.payload?.detail;
      if (detail?.status === 'duplicate_mapping') {
        setResult({ status: 'already_connected', summary: detail.summary || 'Phone storage is already connected to PhotoPrism.' });
        closeStoragePreview(true);
        await refreshPhotoPrismState();
      } else {
        setActionError(detail?.summary || err.message);
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
      setResult(response);
      await refreshPhotoPrismState();
      window.setTimeout(refresh, 700);
    } catch (err) {
      const detail = err?.payload?.detail;
      if (detail?.status === 'duplicate_mapping') {
        setResult({ status: 'already_connected', summary: detail.summary || 'This media folder is already connected to PhotoPrism.' });
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
      const response = await liteApi.runAppAction(app.id || 'photoprism', actionId, { reason: `manual ${actionId.replace(/_/g, ' ')}`, ...extraPayload });
      setResult({ action_id: actionId, ...response });
      refresh();
      window.setTimeout(refresh, 700);
      window.setTimeout(refresh, 1800);
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
      preserve_evidence: true,
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
    const lifecycleAttention = lifecycleAttentionItems(lifecycle);
    const connectPhotosAction = lifecycleAction(lifecycle, 'connect_photos');
    const checkAppAction = lifecycleAction(lifecycle, 'check_app');
    const backupAppAction = lifecycleAction(lifecycle, 'backup_app');
    const importPhotosAction = lifecycleAction(lifecycle, 'import_photos');
    const indexPhotosAction = lifecycleAction(lifecycle, 'index_photos');
    const cancelMediaAction = lifecycleAction(lifecycle, 'cancel_media');
    const importProgress = actionProgressFromLifecycle(lifecycle, 'import_photos', actionBusyKey === `${app.id}:import_photos`);
    const indexProgress = actionProgressFromLifecycle(lifecycle, 'index_photos', actionBusyKey === `${app.id}:index_photos`);
    const cancelProgress = actionProgressFromLifecycle(lifecycle, 'cancel_media', actionBusyKey === `${app.id}:cancel_media`);
    const previewRestoreAction = lifecycleAction(lifecycle, 'preview_restore');
    const backupToStorageAction = lifecycleAction(lifecycle, 'backup_to_storage');
    const installAppAction = lifecycleAction(lifecycle, 'install_app');
    const updateAppAction = lifecycleAction(lifecycle, 'update_app');
    const repairAppAction = lifecycleAction(lifecycle, 'repair_app');
    const removeAppAction = lifecycleAction(lifecycle, 'remove_app');
    const mediaSummary = lifecycleMediaSummary(lifecycle);

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
              <div className="lite-catalog-action-buttons">
                <PhotoPrismActionTile
                  app={app}
                  actionId="connect_photos"
                  action={connectPhotosAction}
                  busyKey={storageBusy || actionBusyKey}
                  tone="secondary"
                  onClick={(event) => openPhoneStoragePreview(app, event)}
                  disabled={connectPhotosAction.enabled === false || Boolean(storageBusy)}
                  title={lifecycleActionReason(connectPhotosAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="import_photos"
                  action={importPhotosAction}
                  busyKey={actionBusyKey}
                  progress={importProgress}
                  tone="secondary"
                  onClick={(event) => runLifecycleAction(app, 'import_photos', event)}
                  disabled={importPhotosAction.enabled === false || actionBusyKey === `${app.id}:import_photos`}
                  title={lifecycleActionReason(importPhotosAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="index_photos"
                  action={indexPhotosAction}
                  busyKey={actionBusyKey}
                  progress={indexProgress}
                  tone="secondary"
                  onClick={(event) => runLifecycleAction(app, 'index_photos', event)}
                  disabled={indexPhotosAction.enabled === false || actionBusyKey === `${app.id}:index_photos`}
                  title={lifecycleActionReason(indexPhotosAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="cancel_media"
                  action={cancelMediaAction}
                  busyKey={actionBusyKey}
                  progress={cancelProgress}
                  tone="secondary"
                  onClick={(event) => runLifecycleAction(app, 'cancel_media', event)}
                  disabled={cancelMediaAction.enabled === false || actionBusyKey === `${app.id}:cancel_media`}
                  title={lifecycleActionReason(cancelMediaAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="backup_app"
                  action={backupAppAction}
                  busyKey={actionBusyKey}
                  tone="ghost"
                  onClick={(event) => runLifecycleAction(app, 'backup_app', event)}
                  disabled={backupAppAction.enabled === false || actionBusyKey === `${app.id}:backup_app`}
                  title={lifecycleActionReason(backupAppAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="check_app"
                  action={checkAppAction}
                  busyKey={actionBusyKey}
                  tone="ghost"
                  onClick={(event) => runLifecycleAction(app, 'check_app', event)}
                  disabled={checkAppAction.enabled === false || actionBusyKey === `${app.id}:check_app`}
                  title={lifecycleActionReason(checkAppAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="preview_restore"
                  action={previewRestoreAction}
                  busyKey={actionBusyKey}
                  tone="ghost"
                  onClick={(event) => runLifecycleAction(app, 'preview_restore', event)}
                  disabled={previewRestoreAction.enabled === false || actionBusyKey === `${app.id}:preview_restore`}
                  title={lifecycleActionReason(previewRestoreAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="backup_to_storage"
                  action={backupToStorageAction}
                  busyKey={actionBusyKey}
                  tone="ghost"
                  onClick={(event) => runLifecycleAction(app, 'backup_to_storage', event, { target_device_id: lifecycle?.backup?.target_device_id || lifecycle?.backup?.target_id })}
                  disabled={backupToStorageAction.enabled === false || actionBusyKey === `${app.id}:backup_to_storage`}
                  title={lifecycleActionReason(backupToStorageAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="install_app"
                  action={installAppAction}
                  busyKey={actionBusyKey}
                  tone="ghost"
                  onClick={(event) => runLifecycleAction(app, 'install_app', event)}
                  disabled={installAppAction.enabled === false || actionBusyKey === `${app.id}:install_app`}
                  title={lifecycleActionReason(installAppAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="update_app"
                  action={updateAppAction}
                  busyKey={actionBusyKey}
                  tone="ghost"
                  onClick={(event) => runLifecycleAction(app, 'update_app', event)}
                  disabled={updateAppAction.enabled === false || actionBusyKey === `${app.id}:update_app`}
                  title={lifecycleActionReason(updateAppAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="repair_app"
                  action={repairAppAction}
                  busyKey={actionBusyKey}
                  tone="ghost"
                  onClick={(event) => runLifecycleAction(app, 'repair_app', event)}
                  disabled={repairAppAction.enabled === false || actionBusyKey === `${app.id}:repair_app`}
                  title={lifecycleActionReason(repairAppAction)}
                />
                <PhotoPrismActionTile
                  app={app}
                  actionId="remove_app"
                  action={removeAppAction}
                  busyKey={actionBusyKey}
                  tone="danger"
                  onClick={(event) => { event?.stopPropagation?.(); setRemoveConfirmApp(app); }}
                  disabled={removeAppAction.enabled === false}
                  title={lifecycleActionReason(removeAppAction)}
                />
              </div>
              <div className="lite-catalog-action-reasons">
                {importPhotosAction.enabled === false ? <span>Import photos: {lifecycleActionReason(importPhotosAction)}</span> : null}
                {indexPhotosAction.enabled === false ? <span>Index photos: {lifecycleActionReason(indexPhotosAction)}</span> : null}
                {cancelMediaAction.enabled === false && lifecycle?.media?.operation_running ? <span>Stop photo action: {lifecycleActionReason(cancelMediaAction)}</span> : null}
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
            <p>This removes the app runtime and Pocket Lab route when removal support is enabled. Your photo files and backups will not be deleted by default. Evidence saved.</p>
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

      {storagePreviewApp ? (
        <PhotoPrismStoragePreviewSheet
          preview={storagePreview}
          loading={storagePreviewLoading}
          error={storagePreviewError}
          connecting={Boolean(storageBusy)}
          onClose={closeStoragePreview}
          onConfirm={connectPhoneStorageFromPreview}
          onRetry={loadStoragePreview}
        />
      ) : null}

      <AppCatalogResultNotice result={result} error={actionError} onDismiss={dismissActionNotice} />

    </div>
  );
}
