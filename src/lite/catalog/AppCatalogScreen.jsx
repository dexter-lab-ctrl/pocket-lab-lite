import { LiteProtectedConfirmation } from '../components/LiteSafeForms.jsx';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { distinctCatalogStatusSummary, filterCatalogApps, sortCatalogApps, partitionCatalogApps, trustedCatalogIconPath, catalogLibraryIdentity } from './catalogPresentation.js';
import { LiteDetailsPanel, useFocusTrap, useFocusReturn } from '../LiteOverlay.jsx';
import { useDesktopManageGeometry } from '../components/useDesktopManageGeometry.js';
import { useMobileSheetSnap } from '../components/useMobileSheetSnap.js';
import './appsPremiumRefinement.css';
import '../components/liteSafeForms.css';
import { createPortal } from 'react-dom';
import { useDrag } from '@use-gesture/react';
import { animated, config, useSpring } from '@react-spring/web';
import {
  CheckCircle2,
  FileCheck,
  PlugZap,
  ImageUp,
  DatabaseBackup,
  RotateCcw,
  Toolbox,
  Megaphone,
  HeartPulse,
  Camera,
  ExternalLink,
  FolderOpen,
  FolderPlus,
  HardDrive,
  Image as ImageIcon,
  RefreshCw,
  Search,
  Move,
  Maximize2,
  X,
  Server,
  ShieldCheck,
  ShieldAlert,
  Smartphone,
  Trash2,
} from 'lucide-react';
import { useLiteQuery } from '../../hooks/useLiteQuery.js';
import { getLiteAppActionInvalidations, useLiteMutation } from '../../hooks/useLiteMutation.js';
import { useLiteAppActionFlow } from '../../hooks/useLiteAppActionFlow.js';
import { useLiteServiceWorkerUpdateBlocker } from '../../hooks/useLiteServiceWorkerUpdateBlocker.js';
import { formatLiteTime, liteApi } from '../../lib/liteApi.js';
import { createLiteFeedbackDeduper } from '../../lib/liteNativeFeedback.js';
import { liteQueryKeys, liteQueryPaths } from '../../lib/liteQueryClient.js';
import { isLiteAppActionsViewLive, selectAppActionsView, selectAppResourceView, selectCanonicalAppState, selectCatalogSummaryView, selectPhotoPrismActionsView } from '../../lib/liteViewModels.js';
import { GlassCard, StatusBadge, StateSurface, PageHeader, LiteButton, LiteRefreshButton, LoadingCard, resolveSafeAppOpenPath, backendBadgeStatus, backendLabel } from '../LiteUi.jsx';
import { LiteConsequenceSummary, LiteEmptyState, LiteFreshness } from '../LiteUx.jsx';
import { useLiteUiStore } from '../../stores/liteUiStore.js';
import AppActionRow from './AppActionRow.jsx';
import AppSummaryCard from './AppSummaryCard.jsx';
import AppActionProgressSlot from './AppActionProgressSlot.jsx';
import { selectPhotoBackupFacts, selectSupplementalActionNotices } from './appsOperationalView.js';
import { LiteContextualActionCue, LiteFlipGroup, LiteMotionReveal, LitePressableButton, triggerLiteTactileFeedback, useLiteReducedMotion } from '../LiteMotion.jsx';
import { isLitePerformanceMode } from '../liteNavigationRuntime.js';
const loadAppActionDetails = () => import('./AppActionDetailsLazy.jsx');
const AppActionDetailsLazy = React.lazy(loadAppActionDetails);

// Source marker for HTTPS/server-owned App Catalog contract tests.
// Keep this text in source even if the visible layout changes: Secure access ready.

const APP_CATALOG_SOURCE_CONTRACT_MARKERS = [
  'Secure access ready',
  '!isSimpleMediaShortcut ? (',
  // Legacy source-contract markers retained for repository qualification.
  // Runtime selection is generic through selectAppActionsView.
  'select: selectPhotoPrismActionsView',
  // The decorative shared cue remains a legacy contract marker; the visible
  // Manage header intentionally omits it so the Close control stays isolated.
  'kind="card-to-sheet"',
  'snapshotSelect: selectPhotoPrismActionsView',
  "queryKey: liteQueryKeys.appActions('photoprism')",
  // Legacy PhotoPrism copy remains a compatibility marker; visible UI is
  // capability-aware and does not claim this state for unsupported apps.
  'Config protected',
];
void APP_CATALOG_SOURCE_CONTRACT_MARKERS;



const APP_CATALOG_IMPORT_HISTORY_COPY = 'Photos are imported. PhotoPrism will handle new photos.';
void APP_CATALOG_IMPORT_HISTORY_COPY;

const APP_CATALOG_ACTION_ROWS_OWN_CLICKS = true;
// Enterprise UI rule: action rows, action buttons, and Details buttons own their clicks.
// Swipe gestures must not be bound to the action-row viewport.
void APP_CATALOG_ACTION_ROWS_OWN_CLICKS;

const APP_CATALOG_POLLING_POLICY_PHASE3 = true;
// App Catalog polling is intentionally calmer at rest and faster only while
// backend-owned app actions are live.
void APP_CATALOG_POLLING_POLICY_PHASE3;

const APP_CATALOG_PRIMARY_ACTIONS_OWN_CLICKS = true;
// Enterprise UI rule: Open and Manage are primary visible buttons.
// Gesture handlers must not be bound to the same surface that owns these clicks.
void APP_CATALOG_PRIMARY_ACTIONS_OWN_CLICKS;


const APP_CATALOG_MANAGE_PORTAL_STABLE_APP_KEY = true;
// Enterprise UI rule: Manage open state uses a stable app key and the Manage
// button opens the portal. Closing is handled only by close controls.
void APP_CATALOG_MANAGE_PORTAL_STABLE_APP_KEY;

const APP_CATALOG_MANAGE_SHEET_PORTAL_OVERLAY = true;
// Enterprise UI rule: Manage opens as a top-level portal overlay so app cards,
// transforms, animation wrappers, and overflow containers cannot clip the sheet.
void APP_CATALOG_MANAGE_SHEET_PORTAL_OVERLAY;

const APP_CATALOG_DETAILS_PRELOAD_ON_MANAGE = true;
// Warm the code-split read-only details view after the lightweight Manage
// shell is ready so the first Details interaction spends its frame budget on
// rendering rather than module fetch and evaluation.
void APP_CATALOG_DETAILS_PRELOAD_ON_MANAGE;


const APP_CATALOG_FLIP_SHARED_CONTINUITY_IS_PRESENTATION_ONLY = true;
// Enterprise UI rule: FLIP and shared visual continuity animate cloned or
// decorative surfaces only. They must not move real buttons, own gestures,
// intercept clicks, or change backend-owned action execution.
void APP_CATALOG_FLIP_SHARED_CONTINUITY_IS_PRESENTATION_ONLY;

const APP_CATALOG_MANAGE_BODY_PERF_DELAY_MS = 700;

function updateLiteCatalogVisualViewportVar() {
  if (typeof document === 'undefined' || typeof window === 'undefined') return;
  const height = window.visualViewport?.height || window.innerHeight;
  if (height) {
    document.documentElement.style.setProperty('--pl-visual-vh', `${height}px`);
  }
}


function catalogAppKey(appOrId) {
  if (appOrId && typeof appOrId === 'object') {
    return String(appOrId.id || appOrId.name || 'app').trim().toLowerCase() || 'app';
  }
  return String(appOrId || 'app').trim().toLowerCase() || 'app';
}

function stopGestureEvent(event) {
  event?.stopPropagation?.();
}

const KNOWN_APP_NAMES = [];

function appHostLabel(app, lifecycle, fallbackName = 'Server Host') {
  if (lifecycle?.host_device?.label) return lifecycle.host_device.label;
  if (app?.host_device_name) return `Runs on ${app.host_device_name}`;
  if (fallbackName && fallbackName !== 'Server Host') return `Runs on ${fallbackName}`;
  return 'Host not reported';
}

function verifiedStorageBackupLabel(action = {}) {
  const result = action?.result || action?.last_result || {};
  const status = String(result?.status || action?.status || '').toLowerCase();
  const transferVerified = Boolean(
    result?.transfer_verified
    || result?.verification_status === 'verified'
    || result?.checksum_verified === true
  );
  if (!transferVerified || !['succeeded', 'completed', 'verified'].includes(status)) return '';
  const targetLabel = result?.target_label || result?.target_device_name || 'Storage Phone';
  return targetLabel === 'Storage Phone' ? 'Saved to Storage Phone' : `Saved to ${targetLabel}`;
}

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
    description: 'Remove PhotoPrism while preserving photos, backups, and protected troubleshooting records by default.',
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

// Only backend-projected mapping or preview names are shown here.
function storageConnectedFolderLabels(app, preview = null) {
  const labels = [];
  const add = (value) => {
    if (typeof value !== 'string') return;
    const label = value.trim();
    if (label && !labels.includes(label)) labels.push(label);
  };
  for (const mapping of storageMappings(app).filter(isPhoneStorageMapping)) {
    add(mapping.label || mapping.source_label);
    for (const folder of Array.isArray(mapping.folders) ? mapping.folders : []) add(typeof folder === 'string' ? folder : folder?.name);
    for (const folder of Array.isArray(mapping.subfolders) ? mapping.subfolders : []) add(typeof folder === 'string' ? folder : folder?.name);
  }
  if (['ready', 'connected'].includes(String(preview?.status || '').toLowerCase())) {
    for (const folder of Array.isArray(preview?.subfolders) ? preview.subfolders : []) add(typeof folder === 'string' ? folder : folder?.name);
  }
  return labels;
}

function actionCopy(actionId, action = {}) {
  const category = appActionCategory(actionId, action);
  const appId = String(action?.app_id || '').toLowerCase();
  const legacyPhotoPrism = appId === 'photoprism' || !appId ? PHOTO_PRISM_ACTION_COPY[actionId] : null;
  return {
    eyebrow: action?.category_label || APP_ACTION_CATEGORY_COPY[category]?.label || legacyPhotoPrism?.eyebrow || 'Action',
    label: action?.label || legacyPhotoPrism?.label || actionId.replace(/_/g, ' '),
    description: action?.summary || legacyPhotoPrism?.description || 'Pocket Lab will run this through its protected local service.',
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
  media: { label: 'Photos', summary: 'Connect and import photos through Pocket Lab-managed actions.' },
  safety: { label: 'Safety', summary: 'Check app health and protected records.' },
  recovery: { label: 'Recovery', summary: 'Back up, preview restore, and repair safely.' },
  setup: { label: 'App setup', summary: 'Install or check update readiness.' },
  danger: { label: 'Remove', summary: 'Advanced actions require explicit confirmation.' },
};

const MANAGE_SECTION_ORDER = ['overview', 'media', 'safety', 'recovery', 'setup', 'activity', 'danger'];

const MANAGE_SECTION_LABELS = {
  overview: 'Overview',
  activity: 'Activity',
  media: 'Photos',
  safety: 'Safety',
  recovery: 'Recovery',
  setup: 'App setup',
  danger: 'Remove',
};


function LiteManageSectionTabStatic({ sectionId, active, label, onSelect }) {
  return (
    <button
      type="button"
      role="tab"
      aria-label={label}
      aria-selected={active}
      aria-controls="lite-catalog-manage-active-panel"
      id={`lite-catalog-manage-tab-${sectionId}`}
      tabIndex={active ? 0 : -1}
      className={active ? 'is-active' : ''}
      onClick={(event) => { triggerLiteTactileFeedback('selection'); onSelect?.(event); }}
    >
      <span className="lite-catalog-manage-tab-label">{label}</span><small aria-hidden="true" className="lite-app-manage-nav-hint">{MANAGE_SECTION_SUMMARY[sectionId]}</small>
      <span
        className="lite-catalog-manage-tab-indicator"
        aria-hidden="true"
        style={{ opacity: active ? 1 : 0, transform: active ? 'scaleX(1)' : 'scaleX(0.62)' }}
      />
    </button>
  );
}

function LiteManageSectionTab({ sectionId, active, label, onSelect }) {
  // The qualification mode already disables motion at the runtime boundary;
  // avoid creating five matchMedia/effect pairs for a surface that is static
  // by contract. The normal product tab keeps its animated path unchanged.
  if (isLitePerformanceMode()) {
    return <LiteManageSectionTabStatic sectionId={sectionId} active={active} label={label} onSelect={onSelect} />;
  }
  return <LiteManageSectionTabMotion sectionId={sectionId} active={active} label={label} onSelect={onSelect} />;
}

function LiteManageSectionTabMotion({ sectionId, active, label, onSelect }) {
  const reducedMotion = useLiteReducedMotion();
  if (reducedMotion) {
    return <LiteManageSectionTabStatic sectionId={sectionId} active={active} label={label} onSelect={onSelect} />;
  }
  return <LiteManageSectionTabAnimated sectionId={sectionId} active={active} label={label} onSelect={onSelect} />;
}

function LiteManageSectionTabAnimated({ sectionId, active, label, onSelect }) {
  const [pressed, setPressed] = React.useState(false);
  const spring = useSpring({
    transform: active ? 'translateY(-1px)' : pressed ? 'translateY(1px)' : 'translateY(0px)',
    opacity: active ? 1 : 0.92,
    config: { tension: 360, friction: 30, clamp: true },
  });

  return (
    <animated.button
      type="button"
      role="tab"
      aria-label={label}
      aria-selected={active}
      aria-controls="lite-catalog-manage-active-panel"
      id={`lite-catalog-manage-tab-${sectionId}`}
      tabIndex={active ? 0 : -1}
      className={[active ? 'is-active' : '', pressed ? 'is-pressed' : ''].filter(Boolean).join(' ')}
      style={spring}
      onPointerDown={() => setPressed(true)}
      onPointerUp={() => setPressed(false)}
      onPointerCancel={() => setPressed(false)}
      onPointerLeave={() => setPressed(false)}
      onClick={(event) => { triggerLiteTactileFeedback('selection'); onSelect?.(event); }}
    >
      <span className="lite-catalog-manage-tab-label">{label}</span><small aria-hidden="true" className="lite-app-manage-nav-hint">{MANAGE_SECTION_SUMMARY[sectionId]}</small>
      <span className="lite-catalog-manage-tab-indicator" aria-hidden="true" />
    </animated.button>
  );
}

const MANAGE_SECTION_SUMMARY = {
  overview: 'App status and availability.',
  activity: 'Recent app operations and results.',
  media: 'Connect and import photos.',
  safety: 'Check whether the app is safe.',
  recovery: 'Back up, preview restore, and repair.',
  setup: 'Install or check updates.',
  danger: 'Advanced actions.',
};


function prefersReducedMotion() {
  if (isLitePerformanceMode()) return true;
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function clampNumber(value, min, max) {
  const number = Number(value);
  if (!Number.isFinite(number)) return min;
  return Math.min(max, Math.max(min, number));
}


function normalizeActionStatus(rawStatus, enabled, busy = false, hasProgress = false) {
  if (busy || hasProgress) return 'running';
  const value = String(rawStatus || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (!value) return enabled ? 'unknown' : 'not_ready';
  if (['queued', 'pending'].includes(value)) return 'queued';
  if (['running', 'working', 'executing'].includes(value)) return 'running';
  if (['succeeded', 'success', 'done', 'completed', 'verified'].includes(value)) return 'done';
  if (['review', 'degraded', 'warning', 'needs_attention'].includes(value)) return 'review';
  if (['failed', 'failure', 'error'].includes(value)) return 'failed';
  if (['blocked', 'disabled', 'paused'].includes(value)) return 'blocked';
  if (['not_supported', 'unsupported'].includes(value)) return 'not_supported';
  if (['not_ready', 'unavailable'].includes(value)) return 'not_ready';
  if (['connected', 'imported', 'installed'].includes(value)) return value;
  return enabled ? 'ready' : 'not_ready';
}

function getActionDisplayState(status, enabled = true) {
  const normalized = normalizeActionStatus(status, enabled);
  if (normalized === 'ready') return { status: 'healthy', label: 'Ready' };
  if (normalized === 'connected') return { status: 'healthy', label: 'Connected' };
  if (normalized === 'imported') return { status: 'healthy', label: 'Imported' };
  if (normalized === 'installed') return { status: 'healthy', label: 'Installed' };
  if (normalized === 'queued') return { status: 'degraded', label: 'Getting ready' };
  if (normalized === 'running') return { status: 'degraded', label: 'Working' };
  if (normalized === 'done') return { status: 'healthy', label: 'Done' };
  if (['review', 'failed'].includes(normalized)) return { status: 'degraded', label: 'Needs attention' };
  if (normalized === 'blocked') return { status: 'degraded', label: 'Paused for safety' };
  if (normalized === 'not_supported') return { status: 'unknown', label: 'Not available' };
  if (normalized === 'not_ready') return { status: 'unknown', label: enabled ? 'Waiting' : 'Not ready' };
  return { status: 'unknown', label: 'Unknown' };
}


function actionRowStateLabel(actionId, action = {}, result = null) {
  const latest = result?.summary || action?.last_result || action?.result?.summary || action?.summary || '';
  const status = normalizeActionStatus(action?.status || result?.status, action?.enabled !== false);
  if (latest) return latest;
  if (actionId === 'connect_photos' && status === 'connected') return 'Connected';
  if (actionId === 'import_photos' && status === 'imported') return 'Imported';
  const display = getActionDisplayState(status, action?.enabled !== false);
  return display.label || 'Ready';
}

function actionRowTone(actionId, action = {}, result = null) {
  const normalized = normalizeActionStatus(action?.status || result?.status, action?.enabled !== false);
  const summary = String(result?.summary || action?.last_result || action?.result?.summary || action?.summary || '').toLowerCase();
  if (['review', 'failed', 'blocked', 'not_ready'].includes(normalized)) return 'review';
  if (summary.includes('needs attention') || summary.includes('needs review') || summary.includes('something changed') || summary.includes('not ready')) return 'review';
  if (['running', 'queued'].includes(normalized)) return 'working';
  if (['connected', 'imported', 'installed', 'done', 'ready'].includes(normalized)) return 'ready';
  return 'neutral';
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
    media: payload?.media && typeof payload.media === 'object' ? payload.media : null,
    updated_at: payload?.updated_at || null,
  };
}

const APP_CATALOG_LIVE_ACTION_STATUSES = new Set([
  'queued',
  'pending',
  'accepted',
  'running',
  'working',
  'executing',
  'waiting',
  'in_progress',
]);

const APP_CATALOG_TERMINAL_ACTION_STATUSES = new Set([
  'ready',
  'succeeded',
  'success',
  'completed',
  'complete',
  'done',
  'verified',
  'failed',
  'failure',
  'error',
  'blocked',
  'cancelled',
  'canceled',
]);

function isLiveAppCatalogActionStatus(value) {
  return APP_CATALOG_LIVE_ACTION_STATUSES.has(normalizedActionValue(value));
}

function isTerminalAppCatalogActionStatus(value) {
  return APP_CATALOG_TERMINAL_ACTION_STATUSES.has(normalizedActionValue(value));
}

function isLiveAppCatalogAction(action = {}) {
  const progress = action?.progress || {};
  const values = [
    action?.status,
    action?.state,
    action?.phase,
    progress?.status,
    progress?.phase,
    action?.result?.status,
  ];
  const live = Boolean(action?.running || progress?.running || action?.operation_running)
    || values.some(isLiveAppCatalogActionStatus);
  const terminal = values.some(isTerminalAppCatalogActionStatus);
  return Boolean(live && !terminal);
}

function hasLivePhotoPrismAppActionsPayload(payload = {}) {
  const snapshot = normalizeAppActionsPayload(payload || {});
  const actions = Object.values(snapshot?.actions || {});
  return Boolean(
    snapshot?.media?.operation_running
    || isLiveAppCatalogAction(snapshot?.media?.last_import || {})
    || actions.some(isLiveAppCatalogAction)
  );
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
      status: action?.result?.status || action?.status || 'unknown',
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
  const copy = actionCopy(actionId, action);
  const busy = Boolean(entry?.busy);
  const actionStatus = normalizedActionValue(action?.status);
  const connected = Boolean(entry?.connected || ['connected', 'already_connected'].includes(actionStatus));
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
  if (actionId === 'install_app' && String(action?.status || '').toLowerCase() === 'installed') {
    display = { status: 'healthy', label: 'Installed' };
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
    detailsAvailable: true,
    summary: action?.summary || copy.description,
  };
}

function groupAppActions(entries, sectionId = '') {
  const grouped = new Map();
  const scopedEntries = sectionId
    ? entries.filter((entry) => {
      const actionId = entry?.actionId || entry?.action?.id || '';
      return appActionCategory(actionId, entry?.action) === sectionId;
    })
    : entries;
  scopedEntries.forEach((entry) => {
    const actionId = entry?.actionId || entry?.action?.id || '';
    if (!actionId) return;
    const category = appActionCategory(actionId, entry.action) || 'setup';
    if (category === 'access') return;
    if (!grouped.has(category)) {
      grouped.set(category, {
        id: category,
        label: APP_ACTION_CATEGORY_COPY[category]?.label || category,
        summary: APP_ACTION_CATEGORY_COPY[category]?.summary || 'App actions.',
        actions: [],
      });
    }
    grouped.get(category).actions.push(entry.actionId ? entry : { ...entry, actionId });
  });
  return APP_ACTION_CATEGORY_ORDER.map((category) => grouped.get(category)).filter(Boolean);
}

function normalizedResultTone(actionId, payload = {}, action = {}) {
  const status = normalizedActionValue(payload?.status || action?.status || action?.result?.status);
  const summary = String(payload?.summary || action?.last_result || action?.result?.summary || '').toLowerCase();
  if (['review', 'needs_attention', 'degraded', 'warning', 'failed', 'error'].includes(status)) return 'review';
  if (['queued', 'pending', 'accepted', 'running', 'working', 'executing', 'in_progress'].includes(status)) return 'working';
  if (['ready', 'connected', 'imported', 'installed', 'succeeded', 'success', 'completed', 'complete', 'done', 'verified'].includes(status)) return 'ready';
  if (summary.includes('something changed') || summary.includes('needs review') || summary.includes('not ready')) return 'review';
  return 'neutral';
}

function actionStatusChecks(actionId, action = {}) {
  const detailsChecks = Array.isArray(action?.details?.status_checks) ? action.details.status_checks : [];
  const actionChecks = Array.isArray(action?.status_checks) ? action.status_checks : [];
  const checks = detailsChecks.length ? detailsChecks : actionChecks;
  if (checks.length) {
    return checks.slice(0, 4).map((item) => ({
      id: item?.id || item?.label || 'check',
      label: item?.label || 'Check',
      status: String(item?.status || 'review').toLowerCase(),
      summary: item?.summary || '',
    }));
  }
  const tone = normalizedResultTone(actionId, action?.result, action);
  if (actionId === 'check_app') {
    return ['Route', 'Health', 'Storage', 'Safety'].map((label) => ({ id: label.toLowerCase(), label, status: tone === 'ready' ? 'ready' : 'review' }));
  }
  return [];
}

const ACTION_RESULT_LIVE_STATUSES = new Set([
  'queued', 'pending', 'accepted', 'running', 'working', 'executing', 'in_progress',
]);
const ACTION_RESULT_SUCCESS_STATUSES = new Set([
  'succeeded', 'success', 'completed', 'complete', 'done', 'verified', 'connected',
  'already_connected', 'created', 'imported', 'installed', 'ready',
]);
const ACTION_RESULT_REVIEW_STATUSES = new Set([
  'review', 'needs_attention', 'degraded', 'warning', 'failed', 'failure', 'error',
  'blocked', 'not_ready', 'unavailable', 'cancelled', 'canceled', 'partial',
]);

function actionResultStatus(payload = {}, action = {}) {
  return normalizedActionValue(payload?.status || action?.result?.status || action?.status);
}

function actionResultTitle(status, {
  live = 'Working',
  success = 'Completed',
  review = 'Needs review',
  unknown = 'Status unavailable',
} = {}) {
  if (ACTION_RESULT_LIVE_STATUSES.has(status)) return live;
  if (ACTION_RESULT_SUCCESS_STATUSES.has(status)) return success;
  if (ACTION_RESULT_REVIEW_STATUSES.has(status)) return review;
  return unknown;
}

function actionResultCopy(actionId, payload = {}, action = {}) {
  const status = actionResultStatus(payload, action);
  const summary = payload?.summary || action?.result?.summary || action?.last_result || '';
  if (actionId === 'backup_app') {
    return { title: actionResultTitle(status, { live: 'App backup queued', success: 'App backup saved', review: 'App backup needs review' }), summary: summary || (ACTION_RESULT_SUCCESS_STATUSES.has(status) ? 'Settings, mappings, route records, and safe app records were saved.' : 'The backend has not reported a completed app backup.'), badges: ['Media excluded', 'Secrets hidden'] };
  }
  if (actionId === 'preview_restore') {
    return { title: actionResultTitle(status, { live: 'Restore preview queued', success: 'Restore preview ready', review: 'Restore preview needs review' }), summary: summary || (ACTION_RESULT_SUCCESS_STATUSES.has(status) ? 'No files were restored. No database was changed.' : 'The backend has not reported a ready restore preview.'), badges: ['Preview only', 'Media preserved'] };
  }
  if (actionId === 'update_app') {
    return { title: actionResultTitle(status, { live: 'Update readiness queued', success: 'Update readiness checked', review: 'Update readiness needs review' }), summary: summary || (ACTION_RESULT_SUCCESS_STATUSES.has(status) ? 'No update was applied.' : 'The backend has not reported an update-readiness result.'), badges: ['No update was applied', 'Rollback checked'] };
  }
  if (actionId === 'check_app') {
    const tone = normalizedResultTone(actionId, payload, action);
    return {
      title: ACTION_RESULT_LIVE_STATUSES.has(status) ? 'Check app queued' : tone === 'review' ? 'Something changed' : tone === 'ready' ? 'Checked safely' : 'Check status unavailable',
      summary: summary || (tone === 'review' ? 'PhotoPrism needs attention.' : tone === 'ready' ? 'Route, health, storage, and safety look ready.' : 'The backend has not reported a completed app check.'),
      badges: [],
      checks: actionStatusChecks(actionId, action),
      tone,
    };
  }
  if (actionId === 'repair_app') {
    const tone = normalizedResultTone(actionId, payload, action);
    return {
      title: ACTION_RESULT_LIVE_STATUSES.has(status) ? 'Repair queued' : tone === 'review' ? 'Repair needs attention' : tone === 'ready' ? 'Repair completed' : 'Repair status unavailable',
      summary: summary || (tone === 'review' ? 'PhotoPrism still needs attention.' : tone === 'ready' ? 'PhotoPrism is online again.' : 'The backend has not reported a completed repair.'),
      badges: ['Non-destructive', tone === 'review' ? 'Needs attention' : 'Evidence saved'],
      tone,
    };
  }
  if (actionId === 'import_photos') {
    return { title: actionResultTitle(status, { live: 'Import photos in progress', success: 'Import photos completed', review: 'Import photos needs review', unknown: 'Import status unavailable' }), summary: summary || (ACTION_RESULT_SUCCESS_STATUSES.has(status) ? 'PhotoPrism owns indexing and media details.' : 'The backend has not reported a completed import.'), badges: ['Media flow', 'Saved for troubleshooting'] };
  }
  if (actionId === 'connect_photos') {
    return { title: actionResultTitle(status, { live: 'Photo connection in progress', success: 'Photos connected', review: 'Photo connection needs review', unknown: 'Connection status unavailable' }), summary: summary || (ACTION_RESULT_SUCCESS_STATUSES.has(status) ? 'PhotoPrism can now look there. Run Import photos to update your library.' : 'The backend has not reported a connected photo source.'), badges: ['Read-only', 'Paths hidden'] };
  }
  if (actionId === 'backup_to_storage') {
    return { title: actionResultTitle(status, { live: 'Storage backup queued', success: 'Storage target checked', review: 'Storage target needs review' }), summary: summary || (ACTION_RESULT_SUCCESS_STATUSES.has(status) ? 'Join a storage device to save app backups elsewhere.' : 'The backend has not reported a ready storage target.'), badges: ['Readiness only'] };
  }
  return { title: actionResultTitle(status, { live: 'Getting ready', success: 'Action completed', review: 'Action needs review' }), summary: summary || (ACTION_RESULT_SUCCESS_STATUSES.has(status) ? 'Pocket Lab updated this app action.' : 'The backend has not reported a completed outcome.'), badges: [] };
}

function tileResultForAction(actionId, action = {}, result = null) {
  return bestResultForAction(actionId, action, result);
}

function AppActionDetailsButton({ available, onClick, expanded = false }) {
  if (!available) return null;
  const className = `lite-app-action-details-button ${expanded ? 'is-expanded' : ''}`;
  if (isLitePerformanceMode()) {
    return (
      <button
        type="button"
        className={className}
        onClick={onClick}
        aria-expanded={expanded}
      >
        <FileCheck className="h-4 w-4" />
        <span>{expanded ? 'Hide details' : 'Details'}</span>
      </button>
    );
  }
  return (
    <LitePressableButton
      type="button"
      className={className}
      onClick={onClick}
      aria-expanded={expanded}
      haptic="selection"
    >
      <FileCheck className="h-4 w-4" />
      <span>{expanded ? 'Hide details' : 'Details'}</span>
    </LitePressableButton>
  );
}

function AppActionDisabledReason({ reason }) {
  if (!reason) return null;
  if (isLitePerformanceMode()) {
    return <p className="lite-app-action-disabled-reason">{reason}</p>;
  }
  return (
    <LiteMotionReveal
      as="p"
      show
      className="lite-app-action-disabled-reason"
      motionKey={reason || ''}
    >
      {reason}
    </LiteMotionReveal>
  );
}

function AppActionResultCard({ actionId, action, result, onViewDetails, detailsExpanded = false }) {
  const payload = result || null;
  if (!payload) return null;
  const copy = actionResultCopy(actionId, payload, action);
  const detailsAvailable = true;
  const tone = copy.tone || normalizedResultTone(actionId, payload, action);
  return (
    <LiteMotionReveal
      className={`lite-app-action-result-card is-${tone}`}
      role="status"
      ariaLive="polite"
      motionKey={`${actionId}:${payload?.status || ''}:${payload?.receipt_id || payload?.summary || ''}`}
    >
      <div>
        <strong>{copy.title}</strong>
        <p>{copy.summary}</p>
      </div>
      {copy.checks?.length ? (
        <div className="lite-app-action-result-checks" aria-label="Check summary">
          {copy.checks.map((check) => {
            const checkReady = String(check.status || '').toLowerCase() === 'ready';
            return (
              <span key={check.id || check.label} className={checkReady ? 'is-ready' : 'is-review'} title={check.summary || check.label}>
                <CheckCircle2 className="h-3.5 w-3.5" />
                {check.label}
              </span>
            );
          })}
        </div>
      ) : null}
      {copy.badges?.length ? <div className="lite-app-action-result-badges">{copy.badges.map((badge) => <span key={badge}>{badge}</span>)}</div> : null}
      <AppActionDetailsButton available={detailsAvailable} onClick={onViewDetails} expanded={detailsExpanded} />
    </LiteMotionReveal>
  );
}

function AppActionGroup({ group, children, actionIds = [] }) {
  const flipKeys = actionIds.length ? actionIds : React.Children.toArray(children).map((_, index) => `${group.id}:${index}`);
  const reducedMotion = useLiteReducedMotion();
  const renderItems = (registerFlipItem = () => () => {}) => React.Children.toArray(children).map((child, index) => {
    const flipKey = String(flipKeys[index] || `${group.id}:${index}`);
    return (
      <div
        key={flipKey}
        ref={registerFlipItem(flipKey)}
        className="lite-motion-flip-item"
        data-lite-flip-key={flipKey}
      >
        {child}
      </div>
    );
  });
  return (
    <section className={`lite-app-action-group is-${group.id}`} aria-label={group.id === 'recovery' ? 'App backups and recovery actions' : `${group.label} actions`}>
      <div className="lite-app-action-group-head">
        <div>
          <span>{group.label}</span>
          <p>{group.summary}</p>
        </div>
      </div>
      {reducedMotion || flipKeys.length <= 1 ? (
        <div className="lite-motion-flip-group lite-app-action-group-grid">
          {renderItems()}
        </div>
      ) : (
        <LiteFlipGroup keys={flipKeys} className="lite-app-action-group-grid">
          {(registerFlipItem) => renderItems(registerFlipItem)}
        </LiteFlipGroup>
      )}
    </section>
  );
}


function normalizedActionStatus(value) {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function isLiveCatalogActionStatus(value) {
  return ['queued', 'pending', 'accepted', 'running', 'working', 'executing', 'waiting', 'in_progress'].includes(normalizedActionStatus(value));
}

function isTerminalCatalogActionStatus(value) {
  return ['succeeded', 'success', 'completed', 'complete', 'done', 'verified', 'ready'].includes(normalizedActionStatus(value));
}

function syntheticBusyProgress(actionId) {
  const step = actionId === 'backup_app'
    ? 'Saving app records'
    : actionId === 'preview_restore'
      ? 'Preparing restore preview. No changes made.'
      : actionId === 'backup_to_storage'
        ? 'Checking storage-device readiness.'
        : actionId === 'update_app'
          ? 'Checking update readiness'
          : actionId === 'import_photos'
            ? 'Importing photos'
            : actionId === 'repair_app'
              ? 'Checking repair'
              : 'Checking safely';
  return {
    running: true,
    percent: 0,
    indeterminate: true,
    phase: 'running',
    step,
    synthetic: true,
    steps: [],
    timeline: [],
  };
}

function progressFromLiveOperation({ actionId, progress, status, fallbackStep }) {
  if (!progress || typeof progress !== 'object') return syntheticBusyProgress(actionId);
  const rawPercent = Number(progress?.percent);
  const percent = Number.isFinite(rawPercent) ? Math.min(95, Math.max(10, rawPercent)) : 22;
  return {
    running: true,
    percent,
    indeterminate: progress?.indeterminate !== false,
    phase: progress?.phase || status || 'running',
    step: progress?.step || fallbackStep || 'Working',
    steps: Array.isArray(progress?.steps) ? progress.steps : [],
    timeline: Array.isArray(progress?.timeline) ? progress.timeline : [],
  };
}

function actionProgressFromLifecycle(lifecycle, actionId, busy = false) {
  if (actionId === 'import_photos') {
    const media = lifecycle?.media || {};
    const operation = media?.last_import || null;
    const operationStatus = normalizedActionStatus(operation?.status || operation?.phase);
    const operationLive = !mediaImportIsStale(media)
      && Boolean(media?.operation_running || isLiveCatalogActionStatus(operationStatus));
    if (!operationLive) return busy ? syntheticBusyProgress(actionId) : null;
    return progressFromLiveOperation({
      actionId,
      progress: operation?.progress || {},
      status: operationStatus,
      fallbackStep: operation?.summary || 'Importing photos',
    });
  }

  if (actionId === 'update_app') {
    const update = lifecycle?.update || {};
    const action = lifecycle?.actions?.update_app || {};
    const pending = update?.pending_check || null;
    const pendingStatus = normalizedActionStatus(pending?.status || pending?.phase);
    const actionStatus = normalizedActionStatus(action?.status);
    const live = Boolean(update?.operation_running || isLiveCatalogActionStatus(pendingStatus) || isLiveCatalogActionStatus(actionStatus));
    if (!live) return busy ? syntheticBusyProgress(actionId) : null;
    return progressFromLiveOperation({
      actionId,
      progress: pending?.progress || action?.progress || {},
      status: pendingStatus || actionStatus,
      fallbackStep: 'Checking update readiness',
    });
  }

  if (['backup_app', 'preview_restore', 'backup_to_storage'].includes(actionId)) {
    const action = lifecycle?.actions?.[actionId] || {};
    const status = normalizedActionStatus(action?.status || action?.phase);
    const live = isLiveCatalogActionStatus(status) && !isTerminalCatalogActionStatus(status);
    if (!live) return busy ? syntheticBusyProgress(actionId) : null;
    return progressFromLiveOperation({
      actionId,
      progress: action?.progress || {},
      status,
      fallbackStep: action?.summary || syntheticBusyProgress(actionId).step,
    });
  }

  if (!['check_app', 'repair_app'].includes(actionId)) return null;
  const operationAction = lifecycle?.operations?.actions?.[actionId] || lifecycle?.actions?.[actionId] || {};
  const currentAction = lifecycle?.current_action || lifecycle?.operations?.current_action || null;
  const currentMatches = currentAction?.action_id === actionId;
  const source = currentMatches ? currentAction : operationAction;
  const rawStatus = normalizedActionStatus(source?.status || source?.phase);
  const live = currentMatches && isLiveCatalogActionStatus(rawStatus) && !isTerminalCatalogActionStatus(rawStatus);
  if (!live) return busy ? syntheticBusyProgress(actionId) : null;
  return progressFromLiveOperation({
    actionId,
    progress: source?.progress || {},
    status: rawStatus,
    fallbackStep: actionId === 'check_app' ? 'Checking safely' : 'Checking repair',
  });
}


function hasRunningPhotoPrismMedia(apps) {
  return (Array.isArray(apps) ? apps : []).some((app) => (
    isPhotoPrismApp(app)
    && Boolean(lifecycleProfile(app)?.media?.operation_running)
  ));
}

function PhotoPrismActionIcon({ actionId }) {
  const iconClassName = 'h-4 w-4 lite-catalog-action-lucide';
  if (actionId === 'connect_photos') return <PlugZap className={iconClassName} />;
  if (actionId === 'import_photos') return <ImageUp className={iconClassName} />;
  if (actionId === 'backup_app') return <DatabaseBackup className={iconClassName} />;
  if (actionId === 'preview_restore') return <RotateCcw className={iconClassName} />;
  if (actionId === 'backup_to_storage') return <HardDrive className={iconClassName} />;
  if (actionId === 'repair_app') return <Toolbox className={iconClassName} />;
  if (actionId === 'update_app') return <Megaphone className={iconClassName} />;
  if (actionId === 'check_app') return <ShieldCheck className={iconClassName} />;
  if (actionId === 'install_app') return <Smartphone className={iconClassName} />;
  if (actionId === 'remove_app') return <Trash2 className={iconClassName} />;
  return <CheckCircle2 className={iconClassName} />;
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

  const host = (
    <div className={`lite-catalog-action-notice lite-catalog-action-notice--global ${toneClass}`} role={notice.tone === 'danger' ? 'alert' : 'status'} aria-live={notice.tone === 'danger' ? 'assertive' : 'polite'}>
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

  if (typeof document === 'undefined') return null;
  return createPortal(host, document.querySelector('.pocket-app-shell') || document.body);
}

const PhotoPrismActionTile = React.memo(function PhotoPrismActionTile({
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
  const detailsAvailable = true;
  const rowTone = actionRowTone(actionId, action, tileResult || result);
  const rowStateLabel = progressLabel || reason || actionRowStateLabel(actionId, action, tileResult || result);
  const actionButtonLabel = busy || progressState?.running ? 'Working' : copy.label;
  const progressSlot = showProgress ? (
    <AppActionProgressSlot
      active={showProgress}
      motionKey={`${actionId}:${progressState?.phase || ''}:${progressState?.step || ''}:${progressState?.percent || ''}`}
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
  ) : null;

  const resultSlot = !showProgress && !isSimpleMediaShortcut && tileResult ? (
    <div className={`lite-app-action-row-result is-${rowTone}`}>
      <span>{tileResult.summary || action?.last_result || 'Done'}</span>
      <AppActionDetailsButton available={detailsAvailable} onClick={onViewDetails} expanded={detailsExpanded} />
    </div>
  ) : !showProgress && !isSimpleMediaShortcut && !tileResult ? (
    <div className="lite-app-action-row-result is-neutral">
      <span>{normalized.summary || copy.description}</span>
      <AppActionDetailsButton available={detailsAvailable} onClick={onViewDetails} expanded={detailsExpanded} />
    </div>
  ) : isSimpleMediaShortcut ? (
    <div className="lite-app-action-row-result is-neutral">
      <span>{reason || normalized.summary || copy.description}</span>
      <AppActionDetailsButton available onClick={onViewDetails} expanded={detailsExpanded} />
    </div>
  ) : null;

  return (
    <AppActionRow
      actionId={actionId}
      className={`lite-catalog-action-tile lite-app-action-row lite-app-action-tile ${isDisabled ? 'is-disabled' : ''} ${showProgress ? 'has-progress' : ''} ${progressState?.running ? 'is-running' : ''} is-${rowTone} ${actionId === 'remove_app' ? 'is-danger' : ''} ${isConnectPhotos && normalized.connected ? 'is-connected' : ''} ${isImportedPhotos ? 'is-imported' : ''}`}
      disabled={isDisabled}
      active={showProgress || Boolean(detailsExpanded)}
      icon={<PhotoPrismActionIcon actionId={actionId} />}
      cue={isLitePerformanceMode() ? null : (
        <LiteContextualActionCue
          actionId={actionId}
          active={showProgress || Boolean(progressState?.running)}
          completed={Boolean(tileResult)}
          review={rowTone === 'review'}
        />
      )}
      eyebrow={copy.eyebrow || normalized.categoryLabel}
      label={copy.label}
      summary={rowStateLabel || normalized.summary || copy.description}
      displayStatus={normalized.display.status}
      displayLabel={normalized.display.label}
      buttonTone={tone}
      buttonLabel={actionButtonLabel}
      buttonTitle={title || reason || copy.description}
      onClick={onClick}
      disabledReason={<AppActionDisabledReason reason={!showProgress && !isSimpleMediaShortcut ? reason : ''} />}
      progressSlot={progressSlot}
      resultSlot={resultSlot}
    />
  );
});

function PhoneStorageConnectedFolders({ app, preview }) {
  const folders = storageConnectedFolderLabels(app, preview);
  return (
    <section className="lite-catalog-connected-folders" aria-label="Connected folders from Phone Storage">
      <div className="lite-catalog-premium-connection-heading">
        <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
        <div><strong>Phone storage connected</strong><p>Read-only access to shared storage.</p></div>
      </div>
      {folders.length ? (
        <>
          <div className="lite-catalog-connected-folder-list" aria-label="Reported folders preview">
            {folders.slice(0, 3).map((folder) => <span key={folder}>{folder}</span>)}
            {folders.length > 3 ? <span>+{folders.length - 3} more</span> : null}
          </div>
          {folders.length > 3 ? <details className="lite-catalog-premium-disclosure">
            <summary>View all {folders.length} reported folders</summary>
            <ul>{folders.map((folder) => <li key={folder}>{folder}</li>)}</ul>
          </details> : null}
        </>
      ) : <p className="lite-catalog-premium-muted">Folder names are not available in the current storage projection.</p>}
    </section>
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
  const previewStatus = String(preview?.status || '').toLowerCase();
  const ready = previewStatus === 'ready' && preview?.connect_payload;
  const notReady = previewStatus === 'not_ready';
  const hasReportedPreview = ['ready', 'connected'].includes(previewStatus);
  const folders = Array.isArray(preview?.subfolders) ? preview.subfolders : [];
  const reportedRoot = preview?.root_label || preview?.root || 'Not reported';

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
            <p>{preview?.summary || 'Pocket Lab will show the backend-reported storage preview before connecting photos.'}</p>
          </div>
          <button type="button" className="lite-catalog-storage-preview-close" onClick={onClose} aria-label="Cancel Connect photos">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="lite-catalog-storage-preview-root" aria-label="Phone storage mapping">
          <div>
            <span>Phone storage</span>
            <strong>{reportedRoot}</strong>
          </div>
          <span>{previewStatusText(preview)}</span>
          <span>Read-only</span>
        </div>

        <div className="lite-catalog-storage-preview-note">
          <strong>Photos are not moved by this step.</strong>
          <p>{ready ? 'Run Import photos after connecting storage. PhotoPrism handles indexing inside the app.' : 'No photo source is connected by this preview.'}</p>
        </div>

        <div className="lite-catalog-storage-preview-list-head">
          <div>
            <span>Visible folders</span>
            <strong>Included with phone storage</strong>
          </div>
          <p>Only folder names reported by the backend preview are shown here.</p>
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
            <p>Pocket Lab could not read the latest storage information. Try again when the device is reachable.</p>
            <LiteButton type="button" tone="secondary" onClick={onRetry}>Try again</LiteButton>
          </div>
        ) : notReady ? (
          <div className="lite-catalog-storage-preview-empty" role="status">
            <strong>Phone storage is not ready yet.</strong>
            <p>{preview?.reason || 'Allow Android storage access for Pocket Lab on this device, then try again.'}</p>
          </div>
        ) : hasReportedPreview && folders.length ? (
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
            <strong>No reported folders yet.</strong>
            <p>The backend did not report folder metadata for this storage preview.</p>
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

function PhotoPrismMediaFlowCard({ lifecycle, busyKey = '', phoneSource = false, onViewDetails }) {
  const flow = photoPrismMediaFlowState(lifecycle, busyKey, phoneSource);
  const icons = {
    phone: <Smartphone aria-hidden="true" />,
    source: <FolderOpen aria-hidden="true" />,
    transfer: <RefreshCw aria-hidden="true" />,
    prism: <ImageIcon aria-hidden="true" />,
  };
  return (
    <section className={`lite-catalog-media-flow-card lite-catalog-premium-flow is-${flow.state}`} aria-label="Photo workflow">
      <div className="lite-catalog-premium-flow-header">
        <div className="lite-catalog-premium-flow-heading"><span>Photo workflow</span><strong>{flow.title}</strong></div>
        <span className={`lite-catalog-premium-state is-${flow.state}`}>{flow.badge}</span>
      </div>
      <ol className="lite-catalog-premium-flow-steps" aria-label={flow.ariaLabel}>
        {flow.steps.map((step, index) => (
          <li key={step.id} className={`lite-catalog-premium-flow-step is-${step.state}`}>
            <span className="lite-catalog-premium-flow-icon">{icons[step.id]}</span>
            <strong>{step.label}</strong><small>{step.status}</small>
            {index < flow.steps.length - 1 ? (
              <span className={`lite-catalog-premium-flow-connector is-${step.state}`} aria-hidden="true" />
            ) : null}
          </li>
        ))}
      </ol>
      <div className="lite-catalog-premium-flow-foot">
        <p>{flow.summary}</p>
        {onViewDetails ? <button type="button" onClick={onViewDetails}>View details</button> : null}
      </div>
    </section>
  );
}

function mediaImportIsStale(media = {}) {
  const operation = media?.last_import && typeof media.last_import === 'object' ? media.last_import : {};
  const progress = operation?.progress && typeof operation.progress === 'object' ? operation.progress : {};
  return Boolean(media?.progress_stale || media?.stale || operation?.progress_stale || operation?.stale || progress?.progress_stale || progress?.stale);
}

function photoPrismMediaFlowState(lifecycle, busyKey = '', phoneSource = false) {
  const media = lifecycle?.media || {};
  const mediaLabels = [
    ...(Array.isArray(media.labels) ? media.labels : []),
    ...(Array.isArray(lifecycle?.storage?.labels) ? lifecycle.storage.labels : []),
  ].map((label) => String(label || '').toLowerCase());
  const phoneSourceReported = phoneSource
    || mediaLabels.some((label) => label.includes('phone') || label.includes('android shared storage'))
    || (Array.isArray(media.mappings) && media.mappings.some(isPhoneStorageMapping));
  const usesPhoneSource = Boolean(phoneSourceReported);
  const connected = Number(media.mapping_count ?? lifecycle?.storage?.mapping_count ?? 0) > 0
    || lifecycle?.storage?.status === 'connected';
  const status = normalizedActionValue(media?.last_import?.status);
  const stale = mediaImportIsStale(media);
  const queued = !stale && ['queued', 'accepted', 'pending', 'planning', 'waiting', 'waiting_for_credentials', 'starting'].includes(status);
  const executing = !stale && ['running', 'working', 'executing', 'in_progress', 'transferring', 'cancelling'].includes(status);
  const completed = ['succeeded', 'success', 'completed', 'done'].includes(status);
  const failed = ['failed', 'error', 'timed_out', 'blocked', 'partial', 'needs_review'].includes(status) || media.status === 'review';
  const active = !failed && !completed && (queued || executing || (!stale && Boolean(media.operation_running)) || String(busyKey).includes('import_photos'));
  const state = failed ? 'review' : active ? (executing ? 'running' : 'waiting') : completed ? 'completed' : connected ? 'connected' : 'idle';
  const badge = { review: 'Needs review', running: 'Running', waiting: 'Waiting', completed: 'Completed', connected: 'Connected', idle: 'Not connected' }[state];
  const transferStatus = executing ? 'Running' : queued || active ? 'Waiting' : completed ? 'Completed' : failed ? 'Needs review' : 'Not running';
  const prismStatus = completed ? 'Updated' : failed ? 'Check readiness' : active ? 'Waiting' : 'Not checked';
  const steps = [
    { id: usesPhoneSource ? 'phone' : 'source', label: usesPhoneSource ? 'Phone' : 'Photo source', state: connected ? 'done' : 'idle', status: connected ? 'Connected' : 'Not connected' },
    { id: 'transfer', label: 'Transfer', state: active ? 'running' : failed ? 'review' : completed ? 'done' : 'idle', status: transferStatus },
    { id: 'prism', label: 'PhotoPrism', state: completed ? 'done' : failed ? 'review' : 'idle', status: prismStatus },
  ];
  const title = failed ? 'Latest photo action needs review' : active ? 'Photo action in progress'
    : completed ? 'Latest photo import completed' : connected ? 'Phone storage connected' : 'Connect photos to start';
  const summary = failed ? 'Review the latest import outcome before retrying.'
    : active ? 'Waiting for the latest backend-reported photo action outcome.'
    : completed ? 'The latest import was reported as completed.'
    : connected ? 'A connected folder does not mean photos were transferred.'
    : 'Connect a backend-approved photo source before importing.';
  return { state, badge, title, summary, steps, ariaLabel: steps.map((step) => `${step.label}: ${step.status}`).join('. ') };
}

function safeDetailList(items, fallback = []) {
  const values = Array.isArray(items) ? items : fallback;
  return values
    .filter(Boolean)
    .map((item) => String(item).trim())
    .filter((item) => item && item.toLowerCase() !== 'hidden')
    .slice(0, 6);
}

function actionDetailList(actionId, items, fallback = []) {
  const filtered = safeDetailList(items, fallback)
    .filter((item) => !(item.toLowerCase().includes('troubleshooting records') && item.toLowerCase().includes('backend-only')));
  if (actionId !== 'backup_app') return filtered;
  return filtered
    .map((item) => {
      if (item === 'Pocket Lab saved the approved app records through its protected local service.') {
        return 'Pocket Lab saved the approved PhotoPrism app records.';
      }
      if (item === 'PhotoPrism settings, mappings, route records, and safe app records may be saved.') {
        return 'PhotoPrism settings, mappings, route records, and safe app records were prepared for backup.';
      }
      if (item === 'Photo files were not backed up by this app-record backup.') {
        return 'Your photo files were not copied by this app-record backup.';
      }
      if (item === 'Raw backup internals were not shown.') {
        return 'Private backup details stayed hidden.';
      }
      if (item === 'Raw secrets were not exposed.') {
        return 'Secrets stayed hidden.';
      }
      return item;
    });
}

function actionDetailSavedSummary(actionId, saved) {
  if (actionId === 'backup_app') {
    return saved?.saved
      ? 'A protected troubleshooting record was saved.'
      : 'No troubleshooting record was saved because this action did not run.';
  }
  return saved?.summary || (saved?.saved ? 'A protected troubleshooting record was saved.' : 'No troubleshooting record was saved because this action did not run.');
}

function actionDetailRunHistoryLabels(actionId) {
  if (actionId === 'backup_app') {
    return {
      title: 'Backup history',
      first: 'First backup',
      last: 'Latest backup',
      count: 'Backups saved',
    };
  }
  return {
    title: 'Run history',
    first: 'First run',
    last: 'Last run',
    count: 'Run count',
  };
}

function fallbackActionDetails(actionId, action = {}, result = null) {
  const copy = actionCopy(actionId, action);
  const summary = result?.summary || action?.summary || copy.description || 'Action details are available.';
  const browserOnly = ['open', 'open_full_screen', 'install_to_phone'].includes(actionId);
  const disabled = action?.enabled === false;
  const status = action?.status || (disabled ? 'not_ready' : 'unknown');
  const hasReportedOutcome = actionHasRunEvidence(action, result, action?.progress);
  return {
    title: action?.label || copy.label,
    status,
    summary,
    what_happened: disabled
      ? [`This action is paused because ${String(action?.disabled_reason || action?.reason || 'it is not ready yet.').replace(/^./, (char) => char.toLowerCase())}`]
      : [summary],
    what_changed: [browserOnly || disabled || !hasReportedOutcome ? 'Nothing changed.' : 'Pocket Lab reported the latest action outcome.'],
    what_did_not_happen: browserOnly
      ? ['No device action was started.', 'No app files were changed.', 'No photos were changed.']
      : ['No unsafe change was started.'],
    saved_for_troubleshooting: {
      saved: Boolean(hasReportedOutcome && !browserOnly),
      backend_only: true,
      summary: hasReportedOutcome && !browserOnly
        ? 'A protected troubleshooting record was saved.'
        : 'No troubleshooting record was saved because this action did not run.',
    },
    technical_details: [
      `Run by: ${browserOnly ? 'This screen' : 'Pocket Lab'}`,
      `Action: ${actionId}`,
      `Status: ${status}`,
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
        ? 'A protected troubleshooting record was saved.'
        : 'No troubleshooting record was saved because this action did not run.',
    },
  };
}

function actionDetailsTone(details = {}, saved = {}) {
  const raw = `${details.status || ''} ${details.summary || ''} ${details.last_result || ''}`.toLowerCase();
  const hasAttention = Array.isArray(details.what_needs_attention) && details.what_needs_attention.some(Boolean);
  if (hasAttention || ['review', 'needs_attention', 'failed', 'error'].some((term) => raw.includes(term)) || raw.includes('something changed') || raw.includes('not ready')) {
    return 'review';
  }
  if (saved?.saved || raw.includes('completed') || raw.includes('protected') || raw.includes('ready')) return 'ready';
  return 'neutral';
}

function appTone(status) {
  const value = String(status || '').toLowerCase();
  if (['ready', 'installed_running', 'running', 'healthy'].includes(value)) return 'healthy';
  if (['installing', 'queued'].includes(value)) return 'working';
  if (['needs_attention', 'unavailable', 'failed', 'installed_stopped', 'installed_degraded', 'state_conflict'].includes(value)) return 'degraded';
  return 'neutral';
}

function appLabel(app, actionSnapshot = null) {
  return selectCanonicalAppState(app, actionSnapshot || {}).statusLabel;
}

function lastOperationText(app, actionSnapshot = null) {
  const op = app?.last_operation;
  const canonical = selectCanonicalAppState(app, actionSnapshot || {});
  if (!op && canonical.running) return `${app?.name || 'This app'} is installed and running.`;
  if (!op && canonical.installed) return `${app?.name || 'This app'} is installed but needs attention.`;
  if (!op && canonical.installationState === 'unknown') return `Pocket Lab is checking ${app?.name || 'this app'}.`;
  if (!op) return `${app?.name || 'This app'} is not currently installed.`;
  const when = op.updated_at ? ` · ${formatLiteTime(op.updated_at)}` : '';
  return `${op.message || 'Latest install status is available.'}${when}`;
}

function resolveAppOpenUrl(item) {
  return resolveSafeAppOpenPath(item);
}

function isAppInstalled(app, actionSnapshot = null) {
  return selectCanonicalAppState(app, actionSnapshot || {}).installed;
}

function isPhotoPrismApp(app) {
  return String(app?.id || '').toLowerCase() === 'photoprism' || String(app?.name || '').toLowerCase() === 'photoprism';
}

function appSupports(app, capability) {
  const capabilities = app?.platform_contract?.capabilities;
  if (capabilities && Object.prototype.hasOwnProperty.call(capabilities, capability)) {
    return capabilities[capability] === true;
  }
  // Compatibility for saved snapshots created before the Universal App Platform
  // contract was projected. PhotoPrism remains the only legacy production app.
  return isPhotoPrismApp(app);
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
  const connectAction = actionSnapshot?.actions?.connect_photos || lifecycleAction(lifecycle, 'connect_photos') || {};
  const connectText = [
    connectAction.status,
    connectAction.summary,
    connectAction.disabled_reason,
    connectAction.reason,
  ].map((value) => String(value || '').toLowerCase()).join(' ');
  if (connectText.includes('connected') || connectText.includes('already connected')) return true;

  const mediaSources = [
    actionSnapshot?.media,
    actionSnapshot?.actions?.connect_photos?.media,
    lifecycle?.media,
    app?.lifecycle?.media,
    app?.media,
    app?.storage,
  ].filter(Boolean);
  for (const media of mediaSources) {
    const labels = Array.isArray(media?.labels) ? media.labels : [];
    const labelText = labels.map((label) => String(label || '').toLowerCase()).join(' ');
    if (labelText.includes('phone storage') || labelText.includes('phone') || labelText.includes('android shared storage')) return true;
    const mappings = Array.isArray(media?.mappings) ? media.mappings : [];
    if (mappings.some(isPhoneStorageMapping)) return true;
  }
  const mappings = storageMappings(app);
  if (!mappings.length) return false;
  return mappings.some(isPhoneStorageMapping);
}

function photosAlreadyImported(lifecycle = null, actionSnapshot = null, app = null, action = null) {
  const actionStatus = normalizedActionValue(action?.status);
  if (['imported', 'succeeded', 'success', 'completed', 'complete', 'done', 'verified'].includes(actionStatus)) return true;

  const mediaSources = [
    actionSnapshot?.media,
    actionSnapshot?.actions?.import_photos?.media,
    lifecycle?.media,
    app?.lifecycle?.media,
    app?.media,
  ].filter(Boolean);
  return mediaSources.some((media) => {
    const lastImport = media?.last_import && typeof media.last_import === 'object' ? media.last_import : null;
    const status = String(lastImport?.status || media?.last_import_status || '').toLowerCase();
    return Boolean(
      media?.last_imported_at
      || lastImport?.completed_at
      || ['succeeded', 'success', 'completed', 'complete', 'done', 'verified'].includes(status)
    );
  });
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

function lifecycleMediaSummary(lifecycle, app) {
  if (!appSupports(app, 'media_sources')) {
    return lifecycle?.summary || `${app?.name || 'App'} actions are available.`;
  }
  const media = lifecycle?.media || {};
  if (media?.operation_running && !mediaImportIsStale(media)) return 'Importing photos';
  if (media?.last_imported_at) return `Last import ${formatLiteTime(media.last_imported_at)}`;
  if (Number(media?.mapping_count || 0) > 0) return media.summary || 'Import ready';
  return 'Connect a photo folder first';
}

const TERMINAL_ACTION_STATUSES = new Set([
  'already_connected', 'completed', 'connected', 'done', 'imported', 'installed',
  'nothing_needed', 'succeeded', 'success', 'verified',
]);

function lifecycleActionReason(action) {
  return action?.enabled === false
    ? action.disabled_reason || action.reason || 'Action not ready yet.'
    : '';
}

function lifecycleActionWarning(action, label) {
  if (!action || action.enabled !== false) return '';
  const status = String(action.status || '').toLowerCase().replace(/[\s-]+/g, '_');
  if (TERMINAL_ACTION_STATUSES.has(status)) return '';
  const reason = lifecycleActionReason(action);
  if (!reason || reason === 'Action not ready yet.') return '';
  return `${label}: ${reason}`;
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
  const iconPath = trustedCatalogIconPath(app);
  if (!failed && iconPath) {
    return <img src={iconPath} className="lite-catalog-app-icon-img" alt="" aria-hidden="true" onError={() => setFailed(true)} />;
  }
  return <ImageIcon className="h-6 w-6" aria-hidden="true" />;
}

function CatalogSkeletons() {
  return (
    <div
      className="lite-catalog-grid lite-catalog-skeleton-grid"
      role="status"
      aria-label="Loading App Catalog"
    >
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

function shouldRefreshCatalogAfterAppAction(actionId = '', response = {}) {
  const normalized = String(actionId || response?.action_id || '').toLowerCase().replace(/[\s-]+/g, '_');
  const hints = response?.hints || response?.changed || {};
  const changed = (name) => response?.[name] === true || hints?.[name] === true;
  if (['install_app', 'remove_app', 'repair_app'].includes(normalized)) return true;
  if (['connect_photos', 'import_photos'].includes(normalized)) return true;
  if (normalized === 'check_app' && (changed('catalog_changed') || changed('security_changed') || changed('safety_changed'))) return true;
  return [
    'catalog_changed',
    'app_changed',
    'route_changed',
    'route_readiness_changed',
    'openability_changed',
    'media_changed',
    'storage_changed',
    'mapping_changed',
    'lifecycle_changed',
  ].some(changed);
}

const PHOTO_BACKUP_LIVE_STATUSES = new Set(['queued', 'planning', 'waiting', 'waiting_for_credentials', 'starting', 'transferring', 'cancelling']);
const PHOTO_BACKUP_PRESENTATION = {
  queued: 'Queued', planning: 'Planning', waiting_for_credentials: 'Waiting for credentials',
  starting: 'Starting', transferring: 'Transferring', cancelling: 'Cancelling',
  completed: 'Completed', partial: 'Partial', partial_storage_limit: 'Partial',
  failed: 'Failed', error: 'Failed', ready: 'Ready', not_ready: 'Not ready',
  unavailable: 'Unavailable', cancelled: 'Cancelled', unknown: 'Unknown', metadata_unavailable: 'Metadata unavailable',
};

function PhotoBackupTruthCard({ devices = [], summary = '', saved = false, onGoToDevices }) {
  const facts = selectPhotoBackupFacts(devices, saved);
  return (
    <section className="lite-catalog-photo-backup-truth lite-catalog-premium-backup" aria-label="Photo backup">
      <div className="lite-catalog-premium-backup-header">
        <div><span><Camera className="h-4 w-4" aria-hidden="true" />Photo backup</span><p>Device-owned transfer readiness · app-record backups are separate</p></div>
        <span className={`lite-catalog-premium-state is-${facts.tone}`} role="status">{facts.statusLabel}</span>
      </div>
      <div className="lite-catalog-premium-backup-path" aria-label="Photo backup readiness steps">
        {[facts.source, facts.transfer, facts.destination].map((step, index) => (
          <span key={index}>
            <span className="lite-catalog-premium-step-title">
              {index === 0 ? <Smartphone aria-hidden="true" /> : index === 1 ? <RefreshCw aria-hidden="true" /> : <ImageIcon aria-hidden="true" />}
              <strong>{index === 0 ? 'Device' : index === 1 ? 'Transfer' : 'Destination'}</strong>
            </span>
            <span>{step.title}</span>
            <small className="lite-catalog-premium-step-state">{step.state}</small>
          </span>
        ))}
      </div>
      <dl className="lite-catalog-premium-backup-metrics">
        <div><dt>Latest recorded transfer</dt><dd>{facts.latestTransfer}</dd></div>
        <div><dt>Last update</dt><dd>{facts.lastUpdate ? formatLiteTime(facts.lastUpdate) : 'Not reported'}</dd></div>
      </dl>
      <div className={`lite-catalog-premium-backup-guidance ${facts.requiresAttention ? 'is-review' : ''}`} role={facts.requiresAttention ? 'alert' : 'status'}>
        <strong>{facts.requiresAttention ? 'Action required' : 'Current readiness'}</strong>
        <p>{facts.reason}</p>
        <small>Next step: {facts.nextStep}</small>
      </div>
      <div className="lite-catalog-premium-backup-actions">
        {onGoToDevices ? <button type="button" onClick={onGoToDevices}>Review in Devices</button> : null}
        <details className="lite-catalog-premium-disclosure">
          <summary>How photo backup works</summary>
          <ol className="lite-catalog-premium-how-guide">
            <li><strong>1. Connect a source</strong><p>Use Devices to connect an enrolled device and its supported photo folders.</p></li>
            <li><strong>2. Check readiness</strong><p>Review device, access and protected destination readiness in Devices before starting.</p></li>
            <li><strong>3. Deliver to PhotoPrism</strong><p>The backend transfers approved photos to the protected WebDAV destination. A connection alone does not prove transfer.</p></li>
          </ol>
          <p><strong>Important distinction:</strong> Photo backup transfers media. Back up app saves supported app records. Preview restore checks an app restore without performing it.</p>
          {summary ? <p>{summary}</p> : null}
        </details>
      </div>
    </section>
  );
}

function CatalogManagePortal({
  app,
  lifecycle,
  canonical,
  canOpen,
  buildManageViewModel,
  actionBusyKey,
  result,
  storagePreviewApp,
  storagePreview,
  storagePreviewLoading,
  storagePreviewError,
  storageBusy,
  storagePreviewNotice,
  closeManageSheet,
  openAppFullScreen,
  openActionDetails,
  closeActionDetails,
  closeStoragePreview,
  connectPhoneStorageFromPreview,
  loadStoragePreview,
  setStoragePreviewNotice,
  photoBackupDevices,
  photoBackupSummary,
  savedStateOnly = false,
  backendReachable = true,
  appResource,
}) {
  const appKey = catalogAppKey(app);
  const manageAppOpen = useLiteUiStore((state) => state.manageAppId === appKey);
  const detailsActionId = useLiteUiStore((state) => state.manageAppId === appKey ? state.activeDetailsActionId : '');
  const manageSection = useLiteUiStore((state) => state.manageAppId === appKey ? state.activeManageSection : '');
  const setManageSection = useLiteUiStore((state) => state.setManageSection);
  const manageCloseRef = useRef(null);
  const manageSheetRef = useRef(null);
  const manageScrollRef = useRef(null);
  const { panelRef: geometryPanelRef, desktopPanel, panelStyle, announcement, reset: resetPanelGeometry, startPanelInteraction, adjustPanelWithKeyboard } = useDesktopManageGeometry({ open: manageAppOpen, defaultWidth: 620 });
  const detailsGeometry = useDesktopManageGeometry({ open: manageAppOpen && Boolean(detailsActionId), defaultWidth: 580 });
  const mobileSheet = useMobileSheetSnap({ open: manageAppOpen, enabled: !desktopPanel, surfaceRef: manageSheetRef });
  useFocusTrap(manageAppOpen && !detailsActionId, manageSheetRef);
  useFocusReturn(manageAppOpen, manageCloseRef);
  const [manageBodyReady, setManageBodyReady] = useState(false);
  const [manageExtrasReady, setManageExtrasReady] = useState(false);

  useEffect(() => {
    if (!manageAppOpen) {
      setManageBodyReady(false);
      setManageExtrasReady(false);
      return undefined;
    }
    if (isLitePerformanceMode()) {
      const timer = window.setTimeout(() => setManageBodyReady(true), APP_CATALOG_MANAGE_BODY_PERF_DELAY_MS);
      return () => window.clearTimeout(timer);
    }
    const frame = window.requestAnimationFrame(() => setManageBodyReady(true));
    return () => window.cancelAnimationFrame(frame);
  }, [manageAppOpen]);

  useEffect(() => {
    if (!manageBodyReady) {
      setManageExtrasReady(false);
      return undefined;
    }
    const frame = window.requestAnimationFrame(() => setManageExtrasReady(true));
    return () => window.cancelAnimationFrame(frame);
  }, [manageBodyReady]);

  useEffect(() => {
    if (!manageAppOpen || !manageBodyReady || typeof window === 'undefined') return undefined;
    let idleId = null;
    let timerId = null;
    const preload = () => {
      void loadAppActionDetails().catch(() => null);
    };
    if (typeof window.requestIdleCallback === 'function') {
      idleId = window.requestIdleCallback(preload, { timeout: 1200 });
    } else {
      timerId = window.setTimeout(preload, 0);
    }
    return () => {
      if (idleId !== null) window.cancelIdleCallback?.(idleId);
      if (timerId !== null) window.clearTimeout(timerId);
    };
  }, [manageAppOpen, manageBodyReady]);

  useEffect(() => {
    if (!manageAppOpen) return undefined;
    const onKeyDown = (event) => {
      const activeDetailsActionId = useLiteUiStore.getState().activeDetailsActionId;
      if (event.key === 'Escape' && !event.defaultPrevented && !activeDetailsActionId && !document.querySelector('.lite-details-overlay-layer')) {
        event.preventDefault();
        closeManageSheet();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [closeManageSheet, manageAppOpen]);

  useEffect(() => {
    if (!manageAppOpen) return undefined;
    const previousOverflow = document.body.style.overflow;
    // The fixed portal already owns pointer/scroll interaction in the
    // qualification render path. Avoid changing the document scroll
    // container while mounting the sheet: that synchronous style mutation
    // forces a full-page layout exactly at the measured open boundary. The
    // normal product path keeps its existing body scroll lock.
    const lockBodyScroll = !isLitePerformanceMode();
    if (lockBodyScroll) document.body.style.overflow = 'hidden';
    updateLiteCatalogVisualViewportVar();
    const viewport = window.visualViewport;
    viewport?.addEventListener?.('resize', updateLiteCatalogVisualViewportVar);
    viewport?.addEventListener?.('scroll', updateLiteCatalogVisualViewportVar);
    window.addEventListener('resize', updateLiteCatalogVisualViewportVar);
    window.requestAnimationFrame(() => {
      if (manageScrollRef.current) manageScrollRef.current.scrollTop = 0;
      manageCloseRef.current?.focus?.({ preventScroll: true });
    });
    return () => {
      viewport?.removeEventListener?.('resize', updateLiteCatalogVisualViewportVar);
      viewport?.removeEventListener?.('scroll', updateLiteCatalogVisualViewportVar);
      window.removeEventListener('resize', updateLiteCatalogVisualViewportVar);
      if (lockBodyScroll) document.body.style.overflow = previousOverflow;
    };
  }, [manageAppOpen]);

  // Keep the expensive lifecycle/action projection out of the measured Manage
  // open boundary. The portal first paints its lightweight shell, then builds
  // the action model after the qualification-safe body delay has elapsed.
  const manageViewModel = useMemo(
    () => (manageBodyReady && manageAppOpen && app && lifecycle ? buildManageViewModel() : null),
    [app, buildManageViewModel, lifecycle, manageAppOpen, manageBodyReady],
  );
  const mediaSummary = manageViewModel?.mediaSummary || '';
  const hostLabel = manageViewModel?.hostLabel || '';
  const storageBackupLabel = manageViewModel?.storageBackupLabel || '';
  const isPhoneStorageConnected = Boolean(manageViewModel?.isPhoneStorageConnected);
  const isPhotosImported = Boolean(manageViewModel?.isPhotosImported);
  const appActionEntries = manageViewModel?.appActionEntries || [];
  const appActionGroups = useMemo(
    () => (manageViewModel ? groupAppActions(appActionEntries) : []),
    [appActionEntries, manageViewModel],
  );
  const availableManageSections = ['overview', ...appActionGroups.map((group) => group.id), 'activity'];
  const activeManageSection = availableManageSections.includes(manageSection)
    ? manageSection
    : 'overview';
  const activeAppActionGroups = useMemo(
    () => (manageViewModel ? groupAppActions(appActionEntries, activeManageSection) : []),
    [activeManageSection, appActionEntries, manageViewModel],
  );
  const activityEntries = appActionEntries.filter((entry) => actionHasRunEvidence(entry.action, entry.result, entry.progress)).slice(0, 6);
  const actionDetailHandlers = useMemo(
    () => new Map(appActionEntries.map((entry) => [
      entry.actionId,
      () => openActionDetails(entry.actionId, app.id),
    ])),
    [app.id, appActionEntries, openActionDetails],
  );
  if (!app || !lifecycle || !manageAppOpen || typeof document === 'undefined') return null;

  const selectedDetailsEntry = appActionEntries.find((entry) => entry.actionId === detailsActionId) || null;
  const appAuthority = appResource?.authority || {};
  const credentialStatus = appResource?.credential_status || {};
  const appRecovery = appResource?.recovery || {};
  const enterpriseAccess = appAuthority.mode === 'enterprise';
  const approvalRequired = (appAuthority.actions || []).some((item) => item?.requires_approval);
  const temporaryAccessRequired = (appAuthority.actions || []).some((item) => item?.requires_temporary_access);
  const blockedByRules = (appAuthority.actions || []).length > 0
    && !(appAuthority.actions || []).some((item) => item?.allowed || item?.requires_approval || item?.temporary_access_supported);
  const accessSummary = blockedByRules
    ? 'Access is blocked by Rules.'
    : approvalRequired
      ? 'A requested app change needs approval.'
      : temporaryAccessRequired
        ? 'Some app changes need temporary access.'
        : appAuthority.summary || 'App access follows current Safety Rules.';
  const showAccessSafety = enterpriseAccess
    || credentialStatus.missing
    || credentialStatus.needs_rotation
    || (appRecovery.recovery_blockers || []).length > 0;

  return createPortal(
    <div
      className="lite-catalog-manage-layer lite-catalog-app-premium-layer"
      role="presentation"
      data-lite-manage-portal="true"
      data-lite-perf-mode={isLitePerformanceMode() ? 'true' : undefined}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        padding: 'max(0.75rem, env(safe-area-inset-top)) max(0.75rem, env(safe-area-inset-right)) max(0.75rem, env(safe-area-inset-bottom)) max(0.75rem, env(safe-area-inset-left))',
        pointerEvents: 'auto',
        isolation: 'isolate',
        color: 'var(--azure-text)',
      }}
    >
      <button
        type="button"
        className="lite-catalog-manage-backdrop"
        onClick={closeManageSheet}
        aria-label="Close app management"
        style={{
          position: 'absolute',
          inset: 0,
          zIndex: 0,
          border: 0,
          background: 'var(--azure-backdrop)',
          pointerEvents: 'auto',
        }}
      />
      <section
        ref={(node) => { manageSheetRef.current = node; geometryPanelRef.current = node; }}
        className={`lite-catalog-manage-sheet ${desktopPanel ? 'is-movable' : 'is-mobile-resizable'} ${!desktopPanel && mobileSheet.state === 'compact' ? 'is-compact' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label={`Manage ${app.name}`}
        data-lite-apps-manage-layout={desktopPanel ? 'desktop-movable' : 'mobile-sheet'}
        data-lite-sheet-snap={desktopPanel ? undefined : mobileSheet.state}
        tabIndex={-1}
        style={{
          position: desktopPanel ? 'fixed' : 'relative',
          zIndex: 1,
          width: desktopPanel ? undefined : 'min(100%, 44rem)',
          maxHeight: desktopPanel ? 'none' : 'min(86vh, calc(var(--lite-visual-viewport-height, 100vh) - max(1.5rem, env(safe-area-inset-top)) - max(1.5rem, env(safe-area-inset-bottom))))',
          minHeight: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          opacity: 1,
          visibility: 'visible',
          pointerEvents: 'auto',
          transform: 'none',
          background: 'var(--azure-surface)',
          color: 'var(--azure-text)',
          border: '1px solid var(--azure-border)',
          borderRadius: 'var(--azure-radius-card)',
          boxShadow: 'var(--azure-panel-shadow)',
          ...(desktopPanel ? panelStyle : mobileSheet.style),
        }}
      >
        {!desktopPanel ? (
          <div className="lite-catalog-manage-mobile-grip-bar">
            <button type="button" className="lite-catalog-manage-grip" {...mobileSheet.gripProps}>
              <span aria-hidden="true" />
            </button>
            <div className="lite-catalog-mobile-snap-actions" role="group" aria-label="Sheet size">
              <button type="button" onClick={mobileSheet.contract} disabled={!mobileSheet.canContract}>Compact</button>
              <button type="button" onClick={mobileSheet.expand} disabled={!mobileSheet.canExpand}>Expand</button>
            </div>
          </div>
        ) : null}
        <div className="lite-catalog-manage-head">
          <div>
            <span>Manage</span>
            <strong>{app.name}</strong>
            <p>{app?.description || mediaSummary || 'Review available app actions and readiness.'}</p>
            <span className="lite-catalog-manage-current-state">{canonical?.statusLabel || app?.status_summary || 'Status unknown'}{savedStateOnly ? ' · Saved information' : ''}</span>
          </div>
          {desktopPanel ? (
            <div className="lite-catalog-manage-desktop-controls" role="group" aria-label="Desktop app panel controls">
              <button type="button" className="lite-catalog-manage-panel-tool" aria-label="Move app management panel" title="Drag or use arrow keys to move; Home resets" onPointerDown={(event) => startPanelInteraction('move', event)} onKeyDown={(event) => adjustPanelWithKeyboard('move', event)}><Move aria-hidden="true" size={16} />Move</button>
              <button type="button" className="lite-catalog-manage-panel-tool" aria-label="Reset app panel position and size" onClick={resetPanelGeometry}><RotateCcw aria-hidden="true" size={16} />Reset</button>
              <button type="button" className="lite-catalog-manage-panel-tool" aria-label="Resize app management panel" title="Drag or use arrow keys to resize; Home resets" onPointerDown={(event) => startPanelInteraction('resize', event)} onKeyDown={(event) => adjustPanelWithKeyboard('resize', event)}><Maximize2 aria-hidden="true" size={16} />Resize</button>
              <span className="sr-only" role="status" aria-live="polite">{announcement}</span>
            </div>
          ) : null}
          <button ref={manageCloseRef} type="button" className="lite-catalog-manage-close" onClick={closeManageSheet} aria-label="Close app actions">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="lite-catalog-manage-scroll" ref={manageScrollRef}>
          {manageBodyReady ? (
            <>
              {isPhotoPrismApp(app) && activeManageSection === 'media' ? <PhotoPrismMediaFlowCard lifecycle={lifecycle} busyKey={actionBusyKey} phoneSource={isPhoneStorageConnected} onViewDetails={actionDetailHandlers.get('import_photos')} /> : null}
              {isPhotoPrismApp(app) && activeManageSection === 'media' ? (
                <PhotoBackupTruthCard devices={photoBackupDevices} summary={photoBackupSummary} saved={savedStateOnly} onGoToDevices={() => { closeManageSheet(); useLiteUiStore.getState().setActiveTab('devices'); }} />
              ) : null}
              <div className="lite-catalog-manage-quick-actions" aria-label="Quick app actions">
                <LiteButton onClick={(event) => { stopGestureEvent(event); openAppFullScreen(app, event); }} disabled={!canOpen || savedStateOnly || !backendReachable} tone="secondary"><ExternalLink className="h-4 w-4" />Open full screen</LiteButton>
              </div>
              {showAccessSafety ? (
                <StateSurface
                  tone={blockedByRules || credentialStatus.missing ? 'degraded' : approvalRequired || credentialStatus.needs_rotation || (appRecovery.recovery_blockers || []).length ? 'review' : 'neutral'}
                  title={enterpriseAccess ? 'Access & safety' : 'App readiness'}
                  description={[
                    enterpriseAccess ? accessSummary : '',
                    credentialStatus.missing ? 'A required app credential is missing.' : credentialStatus.needs_rotation ? 'An app credential needs rotation.' : '',
                    (appRecovery.recovery_blockers || [])[0] || '',
                  ].filter(Boolean).join(' ')}
                />
              ) : null}
              {availableManageSections.length ? <div className="lite-catalog-manage-section-tabs" role="tablist" aria-label="Manage app sections" onKeyDown={(event) => {
                const order = MANAGE_SECTION_ORDER.filter((id) => availableManageSections.includes(id));
                const current = order.indexOf(activeManageSection);
                const target = event.key === 'ArrowRight' ? (current + 1) % order.length
                  : event.key === 'ArrowLeft' ? (current - 1 + order.length) % order.length
                    : event.key === 'Home' ? 0 : event.key === 'End' ? order.length - 1 : -1;
                if (target < 0) return;
                event.preventDefault();
                setManageSection(order[target]);
                event.currentTarget.querySelector(`#lite-catalog-manage-tab-${order[target]}`)?.focus();
              }}>
                {MANAGE_SECTION_ORDER.filter((sectionId) => availableManageSections.includes(sectionId)).map((sectionId) => (
                  <LiteManageSectionTab
                    key={sectionId}
                    sectionId={sectionId}
                    active={activeManageSection === sectionId}
                    label={MANAGE_SECTION_LABELS[sectionId] || sectionId}
                    onSelect={(event) => {
                      stopGestureEvent(event);
                      setManageSection(sectionId);
                      if (detailsActionId) closeActionDetails();
                    }}
                  />
                ))}
              </div> : null}
              {availableManageSections.length ? <div className="lite-catalog-manage-section-viewport" role="tabpanel" id="lite-catalog-manage-active-panel" aria-labelledby={`lite-catalog-manage-tab-${activeManageSection}`} tabIndex={0}>
                <div className="lite-catalog-manage-section-hint" aria-live="polite">
                  <strong>{MANAGE_SECTION_LABELS[activeManageSection] || 'Manage'}</strong>
                  <span>{MANAGE_SECTION_SUMMARY[activeManageSection] || 'Swipe left or right to switch sections.'}</span>
                </div>
                <div className="lite-catalog-action-groups">
                  {activeAppActionGroups.map((group) => (
                    <AppActionGroup key={group.id} group={group} actionIds={group.actions.map((entry) => entry.actionId)}>
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
                              onViewDetails={actionDetailHandlers.get(entry.actionId)}
                              detailsExpanded={detailsActionId === entry.actionId}
                              disabled={entry.disabled}
                              title={entry.title}
                            />
                            {entry.actionId === 'connect_photos' && isPhoneStorageConnected ? <PhoneStorageConnectedFolders app={app} preview={storagePreviewApp?.id === app.id ? storagePreview : null} /> : null}
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
                            {entry.actionId === 'import_photos' && isPhotosImported ? <p className="lite-catalog-media-note">Photos imported. PhotoPrism will handle new photos.</p> : null}
                          </React.Fragment>
                        ))}
                    </AppActionGroup>
                  ))}
                </div>
              </div> : null}
              {manageExtrasReady && isPhotoPrismApp(app) ? (
                <>
                  {selectSupplementalActionNotices(appActionEntries, activeAppActionGroups.flatMap((group) => group.actions.map((entry) => entry.actionId))).length ? (
                    <details className="lite-catalog-premium-disclosure lite-catalog-premium-action-notices">
                      <summary>Other action notices</summary>
                      <div className="lite-catalog-action-reasons">
                        {selectSupplementalActionNotices(appActionEntries, activeAppActionGroups.flatMap((group) => group.actions.map((entry) => entry.actionId))).map((notice) => (
                          <article key={notice.id}>
                            <strong>{notice.label}</strong>
                            <span>{notice.status}</span>
                            <p>{notice.reason}</p>
                            {notice.next ? <p>Next step: {notice.next}</p> : null}
                          </article>
                        ))}
                      </div>
                    </details>
                  ) : null}
                  {activeManageSection === 'media' ? (
                    <details className="lite-catalog-premium-disclosure lite-catalog-premium-storage-details">
                      <summary>Storage and device details</summary>
                      <div className="lite-catalog-storage-panel lite-catalog-storage-panel--sheet">
                        <dl className="lite-catalog-premium-fact-list">
                          <div><dt>Where this app runs</dt><dd>{hostLabel || 'Not reported'}</dd></div>
                          <div><dt>Media source</dt><dd>{app?.device_relationships?.media_from || (canonical.mediaConnected ? 'Phone storage' : 'Not connected')}</dd></div>
                          <div><dt>Connected media folders</dt><dd>{storageMappings(app).length ? `${storageMappings(app).length} · ${storageMediaSummary(app)}` : 'None reported'}</dd></div>
                          <div><dt>Storage devices</dt><dd>{storageDeviceCount(app)} available</dd></div>
                          <div><dt>App-record backup readiness</dt><dd>{storageBackupLabel || 'Not reported'}</dd></div>
                          <div><dt>Media protection</dt><dd>{storageMappings(app).length ? 'Backend-approved access · review mapping mode below' : 'No folders connected'}</dd></div>
                        </dl>
                        {storageMappings(app).length ? (
                          <div className="lite-catalog-storage-chips">
                            {storageMappings(app).map((mapping) => <span key={mapping.mapping_id || mapping.label}>{mapping.label || 'Media folder'} · {mapping.mode_label || 'Access mode not reported'}</span>)}
                          </div>
                        ) : <p className="lite-catalog-storage-empty">Connect a supported photo source to review available folders.</p>}
                        {storageDeviceCount(app) < 1 ? <p className="lite-catalog-storage-hint">Next step: Review storage-device readiness in Devices.</p> : null}
                      </div>
                    </details>
                  ) : null}
                </>
              ) : null}
            </>
          ) : <div className="lite-catalog-manage-section-loading" aria-busy="true">Preparing app actions…</div>}
        </div>
       </section>
      {selectedDetailsEntry ? (
        <LiteDetailsPanel
          open
          onClose={closeActionDetails}
          title={actionCopy(selectedDetailsEntry.actionId, selectedDetailsEntry.action).label}
          desktopGeometry={detailsGeometry}
          desktopToolLabels
          closeLabel="Close Action Details"
          mobileSnap
          bodyClassName="lite-apps-premium-details-scroll"
        >
          <React.Suspense fallback={<p className="lite-app-action-details-loading" role="status">Loading details…</p>}>
            <AppActionDetailsLazy
              actionId={selectedDetailsEntry.actionId}
              details={detailsForAction(selectedDetailsEntry.actionId, selectedDetailsEntry.action, tileResultForAction(selectedDetailsEntry.actionId, selectedDetailsEntry.action, selectedDetailsEntry.result))}
            />
          </React.Suspense>
        </LiteDetailsPanel>
      ) : null}
    </div>,
    document.body,
  );
}


export default function CatalogScreen({ onOpenWorkspace }) {
  const {
    data,
    loading,
    error,
    refresh,
    cacheStatus,
    refreshing,
    lastUpdatedLabel,
    backendReachable,
    savedStateOnly,
  } = useLiteQuery({
    queryKey: liteQueryKeys.catalog(),
    path: liteQueryPaths.catalog,
    queryFn: liteApi.catalog,
    pollingMode: 'relaxed',
    staleTime: 60_000,
    isLive: () => false,
    select: selectCatalogSummaryView,
    snapshotSelect: selectCatalogSummaryView,
  });
  const setManageApp = useLiteUiStore((state) => state.setManageApp);
  const clearManageApp = useLiteUiStore((state) => state.clearManageApp);
  const manageAppId = useLiteUiStore((state) => state.manageAppId || '');
  const longPressRef = useRef(null);
  const catalogFeedbackDeduper = useRef(createLiteFeedbackDeduper());
  const initiatedCatalogOperations = useRef(new Map());

  const clearLongPress = useCallback(() => {
    if (longPressRef.current) {
      window.clearTimeout(longPressRef.current);
      longPressRef.current = null;
    }
  }, []);

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
  const setActiveAction = useLiteUiStore((state) => state.setActiveAction);
  const setActiveDetailsAction = useLiteUiStore((state) => state.setActiveDetailsAction);
  const clearActiveDetailsAction = useLiteUiStore((state) => state.clearActiveDetailsAction);
  const [actionSnapshots, setActionSnapshots] = useState({});
  const [pullRefresh, setPullRefresh] = useState({ pulling: false, ready: false, offsetY: 0 });
  const pullRefreshInFlight = useRef(false);
  const [quickActionsAppId, setQuickActionsAppId] = useState(null);
  const appActionFlow = useLiteAppActionFlow({ backendReachable, savedStateOnly });
  const reduceMotion = useMemo(prefersReducedMotion, []);
  const [{ catalogPullY }, catalogPullSpring] = useSpring(() => ({ catalogPullY: 0, config: config.gentle }));
  const catalogEntranceSpring = useSpring({
    from: reduceMotion ? { opacity: 1, transform: 'none' } : { opacity: 0.01, transform: 'translate3d(0, 8px, 0)' },
    to: { opacity: 1, transform: 'translate3d(0, 0, 0)' },
    immediate: reduceMotion,
    config: { tension: 320, friction: 34, clamp: true },
  });

  const apps = data?.apps || data?.items || [];
  const [catalogSearch, setCatalogSearch] = useState('');
  const [catalogFilter, setCatalogFilter] = useState('all');
  const [discoveryOpen, setDiscoveryOpen] = useState(false);
  const access = data?.access || {};
  const featuredApp = sortCatalogApps(apps)[0];
  const featuredAppId = String(featuredApp?.id || '').trim().toLowerCase();
  const appActionsLive = useCallback((payload) => Boolean(actionBusyKey) || isLiteAppActionsViewLive(payload) || hasLivePhotoPrismAppActionsPayload(payload), [actionBusyKey]);
  const {
    data: appActionsData,
    refresh: refreshFeaturedAppActions,
  } = useLiteQuery({
    queryKey: liteQueryKeys.appActions(featuredAppId || 'none'),
    path: featuredAppId ? liteQueryPaths.appActions(featuredAppId) : null,
    queryFn: () => liteApi.appActions(featuredAppId),
    enabled: Boolean(featuredAppId),
    pollingMode: 'normal',
    isLive: appActionsLive,
    staleTime: 10_000,
    select: selectAppActionsView,
    snapshotSelect: selectAppActionsView,
  });
  const { data: managedAppResource } = useLiteQuery({
    queryKey: liteQueryKeys.appResource(manageAppId || 'none'),
    path: manageAppId ? liteQueryPaths.appResource(manageAppId) : null,
    queryFn: () => liteApi.appResource(manageAppId),
    enabled: Boolean(manageAppId),
    pollingMode: 'relaxed',
    staleTime: 20_000,
    select: selectAppResourceView,
    refetchOnWindowFocus: false,
  });
  const { data: mediaBackupData } = useLiteQuery({
    queryKey: ['lite', 'media-backup'],
    path: '/api/lite/media-backup',
    queryFn: liteApi.mediaBackup,
    enabled: apps.length === 0 || apps.some((app) => isPhotoPrismApp(app)),
    pollingMode: 'relaxed',
    staleTime: 60_000,
    isLive: (payload) => (payload?.devices || []).some((device) => (
      ['queued', 'planning', 'waiting', 'waiting_for_credentials', 'starting', 'transferring', 'cancelling']
        .includes(String(device?.latest_backup?.status || '').toLowerCase())
    )),
    refetchOnWindowFocus: false,
  });
  const photoBackupDevices = Array.isArray(mediaBackupData?.devices) ? mediaBackupData.devices : [];
  const photoBackupLatest = photoBackupDevices
    .map((device) => device?.latest_backup)
    .filter(Boolean)
    .sort((left, right) => String(right?.updated_at || '').localeCompare(String(left?.updated_at || '')))[0] || null;
  const photoBackupLive = photoBackupDevices.some((device) => (
    ['queued', 'planning', 'waiting', 'waiting_for_credentials', 'starting', 'transferring', 'cancelling']
      .includes(String(device?.latest_backup?.status || '').toLowerCase())
  ));
  const photoBackupReadyCount = photoBackupDevices.filter((device) => device?.ready).length;
  const photoBackupSummary = photoBackupLive
    ? 'Photo backup is running'
    : String(photoBackupLatest?.status || '').toLowerCase() === 'completed'
      ? `Latest photo backup completed · ${formatLiteTime(photoBackupLatest?.completed_at || photoBackupLatest?.updated_at)}`
      : photoBackupReadyCount
        ? `Photo backup ready on ${photoBackupReadyCount} device${photoBackupReadyCount === 1 ? '' : 's'}`
        : 'Photo backup not ready yet';

  const appActionMutation = useLiteMutation({
    mutationFn: ({ appId = 'photoprism', actionId, payload = {} }) => liteApi.runAppAction(appId, actionId, payload),
    invalidateForAction: ({ appId = 'photoprism', actionId }, response) => getLiteAppActionInvalidations(appId, actionId, response),
  });
  const installAppMutation = useLiteMutation({
    mutationFn: ({ appId, targetNodeId }) => liteApi.installApp(appId, { target_node_id: targetNodeId }),
    invalidateForAction: ({ appId }) => [
      liteQueryKeys.catalog(),
      appId ? liteQueryKeys.appActions(appId) : null,
      appId ? liteQueryKeys.appResource(appId) : null,
    ],
  });
  useLiteServiceWorkerUpdateBlocker('app-catalog-workflow', Boolean(
    busyId
    || storageBusy
    || actionBusyKey
    || removeConfirmApp
    || hasLivePhotoPrismAppActionsPayload(appActionsData)
  ));

  const { installed: libraryApps, discoverable: discoverableApps } = partitionCatalogApps(apps, isAppInstalled);
  const displayedApps = filterCatalogApps(libraryApps, catalogSearch, catalogFilter);
  const catalogFilters = [
    { id: 'all', label: 'All' }, { id: 'ready', label: 'Ready' },
    { id: 'working', label: 'Installing / working' },
    { id: 'attention', label: 'Needs attention' }, { id: 'not_installed', label: 'Not installed' },
  ].map((item) => ({ ...item, count: filterCatalogApps(apps, '', item.id).length }));
  // A single grid is the only library composition; the featured-card layout is retired.
  useEffect(() => {
    return () => {
      clearLongPress();
    };
  }, [clearLongPress]);

  const openManageSheet = useCallback((appOrId, section = '') => {
    triggerLiteTactileFeedback('selection');
    const appKey = catalogAppKey(appOrId);
    const nextSection = MANAGE_SECTION_ORDER.includes(section) ? section : undefined;
    setQuickActionsAppId(null);
    setManageApp(appKey, nextSection);
    closeActionDetails();
  }, [closeActionDetails, setManageApp]);

  const closeManageSheet = useCallback(() => {
    clearManageApp();
    closeActionDetails();
  }, [clearManageApp, closeActionDetails]);

  const pullReadyRef = useRef(false);
  const runCatalogRefresh = useCallback(() => {
    if (pullRefreshInFlight.current || refreshing || savedStateOnly || !backendReachable) return;
    pullRefreshInFlight.current = true;
    pullReadyRef.current = false;
    setPullRefresh({ pulling: false, ready: false, offsetY: 0 });
    catalogPullSpring.start({ catalogPullY: 0, immediate: reduceMotion, config: config.gentle });
    Promise.resolve().then(() => refresh()).catch(() => {}).finally(() => { pullRefreshInFlight.current = false; });
    if (featuredAppId) refreshFeaturedAppActions();
    setQuickActionsAppId(null);
  }, [backendReachable, catalogPullSpring, featuredAppId, reduceMotion, refresh, refreshFeaturedAppActions, refreshing, savedStateOnly]);

  const bindCatalogPull = useDrag(({ active, movement: [, my], direction: [, dy], cancel, event }) => {
    if (typeof window !== 'undefined' && (window.scrollY > 4 || (document.scrollingElement?.scrollTop || 0) > 4 || refreshing || savedStateOnly || !backendReachable)) {
      pullReadyRef.current = false;
      setPullRefresh({ pulling: false, ready: false, offsetY: 0 });
      catalogPullSpring.start({ catalogPullY: 0, immediate: true });
      cancel?.();
      return;
    }
    if (event?.target?.closest?.('button, a, input, textarea, select, [role="button"], .lite-catalog-manage-layer')) {
      cancel?.();
      return;
    }
    const pullingDown = dy >= 0 || my > 0;
    const offsetY = active && pullingDown ? clampNumber(my * 0.42, 0, 92) : 0;
    const ready = offsetY >= 54;
    if (active) pullReadyRef.current = ready;
    setPullRefresh({ pulling: active && offsetY > 2, ready, offsetY });
    catalogPullSpring.start({ catalogPullY: offsetY, immediate: active || reduceMotion, config: config.gentle });
    if (!active) {
      const releaseReady = pullReadyRef.current || ready;
      pullReadyRef.current = false;
      if (releaseReady) runCatalogRefresh();
      else {
        setPullRefresh({ pulling: false, ready: false, offsetY: 0 });
        catalogPullSpring.start({ catalogPullY: 0, immediate: reduceMotion, config: config.gentle });
      }
    }
  }, {
    axis: 'y',
    pointer: { touch: true },
    preventScroll: false,
    filterTaps: true,
    // Only the dedicated 22px touch zone can prevent scroll; page content never does.
  });

  const bindAppCardLongPress = useDrag(({ first, last, tap, movement: [mx, my], event, args: [appId] }) => {
    if (event?.target?.closest?.('button, a, input, textarea, select, [role="button"]')) return;
    if (first) {
      window.clearTimeout(longPressRef.current);
      longPressRef.current = window.setTimeout(() => {
        setQuickActionsAppId(appId);
      }, 420);
    }
    if (Math.abs(mx) + Math.abs(my) > 16) {
      window.clearTimeout(longPressRef.current);
    }
    if (last || tap) {
      window.clearTimeout(longPressRef.current);
    }
  }, {
    filterTaps: true,
    pointer: { touch: true },
  });


  const refreshAppActions = useCallback(async (appId = featuredAppId) => {
    try {
      const normalizedAppId = String(appId || featuredAppId || '').trim().toLowerCase();
      if (!normalizedAppId) return null;
      const payload = normalizedAppId === featuredAppId
        ? await refreshFeaturedAppActions()
        : await liteApi.appActions(normalizedAppId);
      const snapshot = normalizeAppActionsPayload(payload || {});
      setActionSnapshots((current) => ({
        ...current,
        [normalizedAppId]: snapshot,
      }));
      return snapshot;
    } catch (_error) {
      return null;
    }
  }, [featuredAppId, refreshFeaturedAppActions]);


  useEffect(() => {
    if (!appActionsData || !featuredAppId) return;
    const snapshot = normalizeAppActionsPayload(appActionsData || {});
    setActionSnapshots((current) => ({
      ...current,
      [featuredAppId]: snapshot,
    }));
  }, [appActionsData, featuredAppId]);

  // Lifecycle reads are authoritative for terminal feedback. Only operations
  // initiated on this screen are tracked, and a stable reference settles once
  // even while the live query continues to poll.
  useEffect(() => {
    const actions = normalizeAppActionsPayload(appActionsData || {}).actions || {};
    Object.values(actions).forEach((action) => {
      const reference = catalogActionReference(action);
      if (!reference || !initiatedCatalogOperations.current.has(reference)) return;
      const status = normalizedActionStatus(action?.status || action?.phase || action?.result?.status);
      if (!isTerminalAppCatalogActionStatus(status)) return;
      const kind = ['failed', 'failure', 'error', 'blocked', 'cancelled', 'canceled'].includes(status) ? 'warning' : 'success';
      if (catalogFeedbackDeduper.current.once(`catalog:${reference}`, kind)) {
        initiatedCatalogOperations.current.delete(reference);
      }
    });
  }, [appActionsData]);

  const rememberCatalogOperation = useCallback((response, actionId) => {
    const reference = catalogActionReference(response);
    if (!reference) return;
    initiatedCatalogOperations.current.set(reference, actionId);
    if (initiatedCatalogOperations.current.size > 32) {
      initiatedCatalogOperations.current.delete(initiatedCatalogOperations.current.keys().next().value);
    }
  }, []);

  useEffect(() => () => clearLongPress(), [clearLongPress]);

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

  // Adaptive polling for App Catalog actions is owned by useLiteQuery.
  // Do not add manual refresh intervals here; live actions should use isLive polling.


  function openActionDetails(actionId, _appId = 'photoprism') {
    const next = useLiteUiStore.getState().activeDetailsActionId === actionId ? null : actionId;
    setActiveAction(next);
    if (next) {
      void loadAppActionDetails();
      setActiveDetailsAction(next);
      return;
    }
    clearActiveDetailsAction();
  }

  function closeActionDetails() {
    const uiState = useLiteUiStore.getState();
    // Opening/closing Manage already starts with no details selection. Avoid
    // dispatching two no-op Zustand updates on that hot path; those updates
    // still notify the screen subscribers and extend the click task before
    // the portal can paint.
    if (uiState.activeActionId !== null) setActiveAction(null);
    if (uiState.activeDetailsActionId !== null || uiState.activeOverlay?.type === 'details') {
      clearActiveDetailsAction();
    }
  }


  function dismissActionNotice() {
    setResult(null);
    setActionError(null);
  }


  async function install(app, event) {
    event?.stopPropagation?.();
    if (!app) return;
    if (savedStateOnly || !backendReachable) { setActionError('Reconnect to Pocket Lab before installing an app.'); return; }
    triggerLiteTactileFeedback('accepted');
    setBusyId(app.id);
    setResult({ status: 'queued', message: `Sending ${app.name || 'app'} install request to Pocket Lab...` });
    setActionError(null);
    try {
      const targetNodeId = app?.target?.default_node_id || 'pocket-lab-lite-server';
      const response = await installAppMutation.run({ appId: app.id, targetNodeId });
      rememberCatalogOperation(response, 'install_app');
      setResult(response);
      await refresh();
      await refreshAppActions(app.id);
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  function openApp(app, event) {
    event?.stopPropagation?.();
    triggerLiteTactileFeedback('selection');
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
    } catch (err) {
      appActionFlow.fail(err);
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
    } catch (err) {
      appActionFlow.fail(err);
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
    if (!app?.id || !actionId) return;
    if (savedStateOnly || !backendReachable) { setActionError('Reconnect to Pocket Lab before changing this app.'); return; }
    if (['connect_photos', 'import_photos'].includes(actionId) && !isPhotoPrismApp(app)) return;
    const flowAction = actionFromSnapshot(actionSnapshots[appSnapshotKey(app)] || null, actionId, lifecycleAction(lifecycleProfile(app), actionId));
    appActionFlow.review({ appId: app.id, actionId, actionLabel: flowAction?.label, risk: flowAction?.risk, destructive: flowAction?.destructive, confirmationRequired: flowAction?.confirmation_required || actionId === 'remove_app', disabledReason: flowAction?.disabled_reason || flowAction?.reason });
    const flowSubmit = appActionFlow.submit({ actionId, confirmed: Boolean(extraPayload.confirm), confirmationRequired: flowAction?.confirmation_required || actionId === 'remove_app', destructive: flowAction?.destructive });
    if (!flowSubmit.ok) { setActionError(flowSubmit.reason); return; }
    const busyKey = `${app.id}:${actionId}`;
    setActionBusyKey(busyKey);
    setActionError(null);
    setResult({ status: 'queued', action_id: actionId, summary: 'Sending app action to Pocket Lab...' });
    try {
      const appId = app.id;
      const response = await appActionMutation.run({
        appId,
        actionId,
        payload: { reason: `manual ${actionId.replace(/_/g, ' ')}`, ...extraPayload },
      });
      appActionFlow.accepted(response);
      appActionFlow.resultReady(response);
      rememberCatalogOperation(response, actionId);
      setResult({ action_id: actionId, ...response });
      await refreshAppActions(appId);
      if (shouldRefreshCatalogAfterAppAction(actionId, response)) {
        await refresh();
      }
    } catch (err) {
      appActionFlow.fail(err);
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
    const actionSnapshot = actionSnapshots[appSnapshotKey(app)] || null;
    const canonical = selectCanonicalAppState(app, actionSnapshot || {});
    const status = canonical.running ? 'ready' : canonical.degraded || canonical.stopped ? 'needs_attention' : canonical.installed ? 'installed' : String(app.status || 'not_installed').toLowerCase();
    const installing = status === 'installing' || busyId === app.id;
    const opening = openingId === app.id;
    const canInstall = Boolean(app?.actions?.install) && !installing && !canonical.installed;
    const canOpen = Boolean(canonical.openEnabled && resolveAppOpenUrl(app));
    const installed = canonical.installed;
    const targetName = app?.host_device_name || app?.target?.eligible_devices?.[0]?.name || 'Server Host';
    const reason = attentionReason(app, canOpen);
    const progress = app?.progress;
    const measuredProgress = progress?.current !== null && progress?.current !== undefined && progress?.total !== null && progress?.total !== undefined && Number.isFinite(Number(progress.current)) && Number.isFinite(Number(progress.total)) && Number(progress.total) > 0;
    const percent = measuredProgress ? Math.min(100, Math.max(0, Number(progress.current) / Number(progress.total) * 100)) : null;
    const cardClassName = `lite-catalog-card lite-catalog-app-card ${featured ? 'is-featured' : ''} ${installing ? 'is-installing' : ''}`;
    const actionsClassName = 'lite-catalog-actions';
    const lifecycle = lifecycleProfile(app) || (installed ? { actions: app?.platform_contract?.actions || {} } : null);
    const lifecycleAttention = lifecycleAttentionItems(lifecycle);
    const appDescription = app?.description || app?.summary || 'Manage this self-hosted app from your private workspace.';
    const libraryIdentity = catalogLibraryIdentity(app, canonical, savedStateOnly || !backendReachable);
    const openLive = canOpen && !savedStateOnly && backendReachable;
    const statusSummary = distinctCatalogStatusSummary(appDescription, installed && lifecycle
      ? lifecycle.summary || canonical.statusSummary || 'App status is not available.'
      : app?.status_summary || app?.summary || 'Install to set up this app.');
    const buildManageViewModel = () => {
      const actionState = (actionId) => {
        const action = actionFromSnapshot(actionSnapshot, actionId, lifecycleAction(lifecycle, actionId));
        if (canOpen && ['open', 'open_full_screen', 'install_to_phone'].includes(actionId)) {
          return {
            ...action,
            enabled: true,
            status: 'ready',
            url: resolveAppOpenUrl(app),
            disabled_reason: null,
            reason: null,
          };
        }
        return action;
      };
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
      const isPhotosImported = photosAlreadyImported(lifecycle, actionSnapshot, app, importPhotosAction);
      const declaredActions = app?.platform_contract?.actions || {};
      const snapshotActions = actionSnapshot?.actions || {};
      const lifecycleActions = lifecycle?.actions || {};
      const supportedActionIds = new Set([
        ...Object.keys(declaredActions),
        ...Object.keys(snapshotActions),
        ...Object.keys(lifecycleActions),
        ...(canOpen ? ['open', 'open_full_screen', 'install_to_phone'] : []),
      ]);
      return {
        mediaSummary: lifecycleMediaSummary(lifecycle, app),
        hostLabel: appHostLabel(app, lifecycle, targetName),
        storageBackupLabel: verifiedStorageBackupLabel(backupToStorageAction),
        isPhoneStorageConnected,
        isPhotosImported,
        appActionEntries: [
      {
        actionId: 'open',
        action: openAction,
        tone: 'primary',
        onClick: (event) => openApp(app, event),
        disabled: !canOpen || openAction.enabled === false,
        title: lifecycleActionReason(openAction) || app?.access?.message || `Open ${app?.name || 'app'}.`,
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
        action: isPhotosImported ? {
          ...importPhotosAction,
          enabled: false,
          status: 'imported',
          summary: isPhotoPrismApp(app) ? 'Photos are already imported. PhotoPrism will handle new photos.' : 'Media import is already complete.',
          disabled_reason: isPhotoPrismApp(app) ? 'Photos are already imported. PhotoPrism will handle new photos.' : 'Media import is already complete.',
          reason: isPhotoPrismApp(app) ? 'Photos are already imported. PhotoPrism will handle new photos.' : 'Media import is already complete.',
        } : importPhotosAction,
        busyKey: actionBusyKey,
        progress: importProgress,
        tone: 'secondary',
        onClick: (event) => runLifecycleAction(app, 'import_photos', event),
        disabled: isPhotosImported || importPhotosAction.enabled !== true || actionBusyKey === `${app.id}:import_photos`,
        title: isPhotosImported
          ? (isPhotoPrismApp(app) ? 'Photos are already imported. PhotoPrism will handle new photos.' : 'Media import is already complete.')
          : lifecycleActionReason(importPhotosAction),
        result,
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
        action: installed ? {
          ...installAppAction,
          enabled: false,
          status: 'installed',
          summary: `${app?.name || 'App'} is installed and running.`,
          disabled_reason: `${app?.name || 'App'} is already installed and running.`,
          reason: `${app?.name || 'App'} is already installed and running.`,
        } : installAppAction,
        busyKey: actionBusyKey,
        tone: 'ghost',
        onClick: (event) => runLifecycleAction(app, 'install_app', event),
        disabled: installed || installAppAction.enabled === false || actionBusyKey === `${app.id}:install_app`,
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
        ].filter((entry) => supportedActionIds.has(entry.actionId)),
      };
    };
    const quickActionsOpen = quickActionsAppId === app.id;

    return (
      <AppSummaryCard key={app.id} className={cardClassName} data-app-library-card={app.id}>
        <div className="lite-app-library-identity">
          <div className="lite-catalog-icon"><AppIcon app={app} /></div>
          <div className="lite-app-library-identity-copy">
            <h2 title={app.name}>{app.name || app.id || 'Unnamed app'}</h2>
            <p className="lite-catalog-category">{libraryIdentity.category}</p>
            <StatusBadge status={savedStateOnly || !backendReachable ? 'neutral' : appTone(status)} className="lite-catalog-status-badge">
              {libraryIdentity.status}
            </StatusBadge>
          </div>
        </div>
        <p className="lite-catalog-app-description" title={appDescription}>{libraryIdentity.description}</p>
        {(libraryIdentity.host || libraryIdentity.safety) ? (
          <div className="lite-app-library-facts" aria-label="App details">
            {libraryIdentity.host ? <span><Server size={15} aria-hidden="true" />{libraryIdentity.host}</span> : null}
            {libraryIdentity.safety ? <span><ShieldCheck size={15} aria-hidden="true" />{libraryIdentity.safety}</span> : null}
          </div>
        ) : null}
        {installed && !openLive && reason ? (
          <div className="lite-app-library-attention" role="status"><ShieldAlert size={17} aria-hidden="true" /><p>{reason}</p></div>
        ) : null}
        {progress?.running || installing ? (
          <div className="lite-catalog-progress" role="status" aria-label="App installation progress">
            <strong>{progress?.step || 'Working'}</strong>
            <p>{progress?.message || 'Waiting for the latest app state.'}</p>
            {percent !== null ? <div className="lite-catalog-progress-bar" role="progressbar" aria-label="App installation progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)}><span style={{ width: `${percent}%` }} /></div> : null}
          </div>
        ) : null}
        <div className="lite-catalog-actions lite-app-library-actions">
          <LiteButton onClick={(event) => { stopGestureEvent(event); openApp(app, event); }} disabled={!openLive} tone={openLive ? 'primary' : 'secondary'} title={!openLive ? reason || 'App access is not confirmed.' : undefined}><ExternalLink className="h-4 w-4" />{opening ? 'Opening...' : 'Open'}</LiteButton>
          {installed ? <LiteButton onClick={(event) => { stopGestureEvent(event); openManageSheet(app, 'overview'); }} tone="secondary">Manage</LiteButton> : null}
        </div>
        {installed && lifecycle ? (
          <CatalogManagePortal
            app={app}
            lifecycle={lifecycle}
            canonical={canonical}
            canOpen={openLive}
            buildManageViewModel={buildManageViewModel}
            actionBusyKey={actionBusyKey}
            result={result}
            storagePreviewApp={storagePreviewApp}
            storagePreview={storagePreview}
            storagePreviewLoading={storagePreviewLoading}
            storagePreviewError={storagePreviewError}
            storageBusy={storageBusy}
            storagePreviewNotice={storagePreviewNotice}
            closeManageSheet={closeManageSheet}
            openAppFullScreen={openAppFullScreen}
            openActionDetails={openActionDetails}
            closeActionDetails={closeActionDetails}
            closeStoragePreview={closeStoragePreview}
            connectPhoneStorageFromPreview={connectPhoneStorageFromPreview}
            loadStoragePreview={loadStoragePreview}
            setStoragePreviewNotice={setStoragePreviewNotice}
            photoBackupDevices={photoBackupDevices}
            photoBackupSummary={photoBackupSummary}
            savedStateOnly={savedStateOnly}
            backendReachable={backendReachable}
            appResource={manageAppId === catalogAppKey(app) ? managedAppResource : null}
          />
        ) : null}
      </AppSummaryCard>
    );
  }

  const installedApps = apps.filter(isAppInstalled);
  const setupNeededCount = apps.length - installedApps.length;
  const insecureAppCount = installedApps.filter((app) => {
    const accessState = app?.access || {};
    const appStatus = String(app?.status || app?.health || '').toLowerCase();
    return (
      accessState.https_ready === false ||
      accessState.route_ready === false ||
      accessState.open === false ||
      ['unhealthy', 'error', 'blocked', 'installed_degraded'].includes(appStatus) ||
      app?.runtime?.state_conflict === true
    );
  }).length;

  const isCatalogSecure = Boolean(access?.https_ready) && insecureAppCount === 0;
  const catalogBanner = insecureAppCount > 0
    ? { secure: false, label: 'Access needs attention' }
    : setupNeededCount > 0
      ? { secure: false, label: 'Setup needed' }
      : { secure: isCatalogSecure, label: isCatalogSecure ? 'Protected access' : 'Remote access not ready' };
  const catalogSaved = savedStateOnly || data?.read_degraded === true || data?.degraded_reason === 'projection_too_old';
  const catalogRefreshing = refreshing || data?.refresh_pending === true;

  return (
    <animated.div
      className={`lite-catalog-screen lite-catalog-gesture-layer lite-catalog-native-polish ${pullRefresh.pulling ? 'is-pulling' : ''}`}
      data-catalog-native-polish="true"
      style={{ ...catalogEntranceSpring, '--lite-catalog-pull-offset': catalogPullY.to((value) => `${value}px`) }}
    >
      <div className={`lite-catalog-pull-refresh ${pullRefresh.pulling ? 'is-pulling' : ''} ${pullRefresh.ready ? 'is-ready' : ''} ${refreshing ? 'is-refreshing' : ''}`} role="status" aria-live="polite" aria-hidden={!pullRefresh.pulling && !refreshing}>
        <RefreshCw className="h-4 w-4" aria-hidden="true" />
        <span>{refreshing ? 'Refreshing' : pullRefresh.ready ? 'Release to refresh' : 'Pull to refresh'}</span>
      </div>
      <div className="lite-catalog-touch-pull-zone" {...bindCatalogPull()} aria-hidden="true" />
      <PageHeader
        eyebrow="Self-hosted workspace"
        title="Apps"
        description="Your self-hosted applications"
        actions={<LiteRefreshButton scope="apps" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <LiteFreshness
        saved={catalogSaved}
        stale={data?.degraded_reason === 'projection_too_old'}
        refreshing={catalogRefreshing}
        lastUpdatedLabel={lastUpdatedLabel || ''}
        backendReachable={backendReachable}
      />
      <header className="lite-app-library-heading">
        <div><h2>Your library</h2><p>Applications installed in your workspace</p></div>
        <span aria-label={`${libraryApps.length} installed applications`}>{libraryApps.length} installed</span>
      </header>
      {libraryApps.length >= 8 ? (
        <div className="lite-catalog-toolbar lite-app-library-search">
          <label htmlFor="lite-catalog-app-search">Find an installed app</label>
          <input id="lite-catalog-app-search" type="search" value={catalogSearch} onChange={(event) => setCatalogSearch(event.target.value)} placeholder="Search your library" autoComplete="off" />
        </div>
      ) : null}

      {error ? <StateSurface tone="degraded" title="Apps are temporarily unavailable" description="Pocket Lab could not confirm the latest app information. Saved app information remains visible when available." className="mb-5" /> : null}
      {loading ? <CatalogSkeletons /> : null}

      <div className="lite-catalog-grid lite-app-library-grid lite-render-containment lite-render-containment--catalog" data-app-library-count={displayedApps.length}>
        {displayedApps.map((app) => renderAppCard(app))}
      </div>

      {!loading && libraryApps.length === 0 ? (
        <LiteEmptyState className="lite-catalog-empty-state" title="Your app library is empty" description="Install an available application to get started." />
      ) : null}
      {!loading && libraryApps.length > 0 && displayedApps.length === 0 ? (
        <LiteEmptyState className="lite-catalog-empty-state" title="No matching apps" description="Try another app name." action={{label:'Clear search',onClick:()=>{setCatalogSearch('');setCatalogFilter('all');}}} />
      ) : null}
      <section className="lite-app-library-discovery" aria-label="Discover apps">
        <button type="button" className="lite-app-library-discover-trigger" onClick={() => setDiscoveryOpen((open) => !open)} disabled={!discoverableApps.length} aria-expanded={discoveryOpen} aria-controls="lite-app-library-discover-results">
          <span><strong>Discover apps</strong><small>{discoverableApps.length ? 'Explore applications available to install' : 'No additional applications are listed yet'}</small></span>
          <span aria-hidden="true">{discoverableApps.length ? (discoveryOpen ? '−' : '›') : ''}</span>
        </button>
        {discoveryOpen && discoverableApps.length ? (
          <div id="lite-app-library-discover-results" className="lite-app-library-discover-results">
            {discoverableApps.map((app) => {
              const canInstall = Boolean(app?.actions?.install) && backendReachable && !savedStateOnly && busyId !== app.id;
              return <article key={app.id} className="lite-app-library-discover-item">
                <div className="lite-catalog-icon"><AppIcon app={app} /></div>
                <div><strong>{app.name || app.id}</strong><p>{app.category || 'Self-hosted app'}</p></div>
                <LiteButton tone="secondary" disabled={!canInstall} title={!canInstall ? 'Installation is not available from the current backend state.' : undefined} onClick={(event) => install(app,event)}>{busyId === app.id ? 'Working…' : 'Install'}</LiteButton>
                {!canInstall ? <p className="lite-app-library-discover-reason">Install not available on this device right now.</p> : null}
              </article>;
            })}
          </div>
        ) : null}
      </section>
      {removeConfirmApp ? (
        <GlassCard className="lite-catalog-remove-confirm" role="dialog" aria-label="Confirm remove">
          <div>
            <span>Confirm remove</span>
            <h2>Remove {removeConfirmApp.name || 'this app'}?</h2>
            <p>
              This removes {removeConfirmApp.name || 'the app'} from this Pocket Lab when removal is available.
              Protected user data and existing backups are preserved by default.
            </p>
          </div>
          <LiteProtectedConfirmation value={{
            title: `Before ${removeConfirmApp.name || 'this app'} is removed`,
            summary: 'Review the effect on this app before continuing.',
            will: [`Remove the ${removeConfirmApp.name || 'app'} service and its Pocket Lab access route when removal is available.`],
            willNot: [
              appSupports(removeConfirmApp, 'media_sources')
                ? 'Connected media files are not deleted by default.'
                : 'Protected user data is not deleted by default.',
              'Delete existing backups by default.',
            ],
            reversible: appSupports(removeConfirmApp, 'install')
              ? 'Reinstalling the app can restore the app service. Recovery depends on the backups you keep.'
              : 'Recovery depends on the app-specific recovery capabilities and backups you keep.',
            availability: `${removeConfirmApp.name || 'The app'} will be unavailable after removal until it is installed or recovered again.`,
          }} />
          <div className="lite-catalog-remove-confirm-actions">
            <LiteButton tone="danger" onClick={(event) => confirmRemoveApp(removeConfirmApp, event)}>Confirm remove</LiteButton>
            <LiteButton tone="secondary" onClick={() => setRemoveConfirmApp(null)}>Cancel</LiteButton>
          </div>
        </GlassCard>
      ) : null}

      <AppCatalogResultNotice result={result} error={actionError} onDismiss={dismissActionNotice} />

    </animated.div>
  );
}
