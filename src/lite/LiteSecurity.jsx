import React, { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { animated, useSpring } from '@react-spring/web';
import { useQueryClient } from '@tanstack/react-query';
import {
  Activity,
  Copy,
  Database,
  Download,
  EyeOff,
  FileCheck,
  Fingerprint,
  LayoutGrid,
  Lock,
  Menu,
  Network,
  RefreshCw,
  Server,
  ShieldCheck,
  Trash2,
  WifiOff,
  X,
} from 'lucide-react';
import { useLiteResource } from '../hooks/useLiteStatus.js';
import { useLiteSecurityCheckFlow } from '../hooks/useLiteSecurityCheckFlow.js';
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
import { liteQueryKeys } from '../lib/liteQueryClient.js';
import { subscribeLiteSecurityScanCompleted } from '../lib/liteSafeSnapshots.js';
import {
  isLiteSecurityViewLive,
  selectSecurityPollingPolicyView,
  selectSecurityProfileView,
  selectSecurityScreenView,
} from '../lib/liteViewModels.js';
import { hasLiteLiveOperation, isLiteLiveStatus } from '../lib/litePollingPolicy.js';
import { LiteSheet } from './LiteOverlay.jsx';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  DEVICE_ROLE_OPTIONS,
  NAV_ITEMS,
  roleLabel,
  deviceConnectionLabel,
  canRestartDeviceAgent,
  canRemoveDevice,
  normalizeDeviceName,
  findDeviceNameConflict,
  deviceDuplicateMessage,
  deviceStatusLabel,
  copyTextToClipboard,
  serviceTone,
  normalizeBackendState,
  backendBadgeStatus,
  backendLabel,
  backendHeroTitle,
  securityFindingTone,
  securityFindingLabel,
  clampSecurityProgress,
  parseSecurityTimestamp,
  formatSecurityRemainingSeconds,
  liveSecurityProgress,
  securityProgressStage,
  scanInProgressValue,
  triggerHapticFeedback,
  shortRunId,
  formatSecurityDuration,
  securityTrendLabel,
  securityTrendView,
  securityDeltaTone,
  isSecurityTimeoutFinding,
  securityDeltaBadge,
  securityDeltaTitle,
  securityDeltaDescription,
  securityDeltaAction,
  securityDeltaSummary,
  securityExecutionStateTone,
  securityExecutionStepGlyph,
  securityToolStatusLabel,
  securityExecutionStateFromBackend,
  securityExecutionStepLabel,
  normalizeSecurityExecutionSteps,
  securityExecutionTimeline,
  PageHeader,
  LiteButton,
  ResultNotice,
  LoadingCard,
  LiteFlowStatusPanel,
  friendlyOverallLabel,
  deviceLinkState,
  restartProgressTitle,
  restartStepStateLabel,
  safeRestartSteps
} from './LiteUi.jsx';

const SECURITY_RENDER_REDUCTION_MILESTONE_1 = true;
const SECURITY_PROGRESSIVE_DETAILS_MILESTONE_2 = true;
const SecurityFindingDetailsLazy = React.lazy(() => import('./security/SecurityFindingDetailsLazy.jsx'));
const SecurityHistoryLazy = React.lazy(() => import('./security/SecurityHistoryLazy.jsx'));
const SecurityProgressiveDetailsLazy = React.lazy(() => import('./security/SecurityProgressiveDetailsLazy.jsx'));
void SECURITY_RENDER_REDUCTION_MILESTONE_1;
void SECURITY_PROGRESSIVE_DETAILS_MILESTONE_2;
const SECURITY_PHASE1_SOURCE_GUARDS = ['Execution timeline', 'Protection dashboard', 'lite-security-protection-dashboard-body', 'selectedFinding === issue ? ('];
const SECURITY_PHASE2_PROGRESSIVE_DETAILS_SOURCE_GUARDS = ['SecurityProgressiveDetailsLazy', 'data-security-phase2-progressive-details', 'Technical details stay collapsed'];
const SECURITY_PHASE3_RESPONSIVE_SHELL_SOURCE_GUARDS = ['LiteSheet', 'lite-security-phase3-details-shell', 'bottom sheet on mobile', 'side panel on desktop'];
const SECURITY_PHASE4_MOTION_POLISH_SOURCE_GUARDS = ['lite-security-phase4-motion', 'lite-security-phase4-score-settle', 'lite-security-phase4-delta-count', 'lite-security-phase4-evidence-stamp', 'lite-security-phase4-step-handoff', 'motion polish respects reduced motion'];
const SECURITY_REMEDIATION_DRAWER_CLASS_LEGACY_GUARD = 'lite-security-remediation-drawer';
const SECURITY_PHASE5_SAFETY_CENTER_MANAGE_UX = true;
const SECURITY_PATCH_E_FRESHNESS_RETENTION_SYNC = true;
void SECURITY_PATCH_E_FRESHNESS_RETENTION_SYNC;
const SECURITY_PHASE5_MANAGE_SOURCE_GUARDS = [
  'lite-security-safety-center-card',
  'lite-security-manage-shell',
  'lite-security-manage-panel',
  'lite-security-manage-tabs',
  'lite-security-manage-section',
  'overview',
  'changes',
  'issues',
  'check_path',
  'evidence',
  'history',
  'technical_details',
  'lite-security-phase1-layout',
  'lite-security-phase1-main',
  'lite-security-phase1-side',
  'lite-security-phase1-more',
  'lite-security-phase2-summary-only',
  "hidden={isSecurityCardCollapsed('moreSecurityDetails')}",
  "isSecurityCardCollapsed('securityHistory')",
  "isSecurityCardCollapsed('moreSecurityDetails')",
  "openSecurityDetails('checkPath'",
  "openSecurityDetails('changes'",
  "openSecurityDetails('attention'",
  'Show check path',
  'Open history',
  'More security details',
  'Open all review items',
  "activeSecurityDetails === 'legacyEvidenceNeverMounts'",
  'lite-security-phase1-shell',
  'lite-security-insight-grid',
  'lite-security-receipt-summary-card',
  'lite-security-scan-quality-card',
  'lite-security-scan-quality-body',
  'lite-security-history-body',
  'View evidence',
  '<SecurityHistoryLazy',
  'lite-security-execution-timeline-body',
  'lite-security-protection-dashboard-body',
  'lite-security-latest-evidence-body',
  'lite-security-last-known-good-body',
  'lite-security-posture-comparison-body',
  'Protected apps',
  'Protection dashboard',
  'Execution timeline',
  "{isSecurityCardCollapsed('securityHistory') ? (",
  "{isSecurityCardCollapsed('moreSecurityDetails') ? (",
];
void SECURITY_PHASE1_SOURCE_GUARDS;
void SECURITY_PHASE2_PROGRESSIVE_DETAILS_SOURCE_GUARDS;
void SECURITY_PHASE3_RESPONSIVE_SHELL_SOURCE_GUARDS;
void SECURITY_PHASE4_MOTION_POLISH_SOURCE_GUARDS;
void SECURITY_REMEDIATION_DRAWER_CLASS_LEGACY_GUARD;
void SECURITY_PHASE5_SAFETY_CENTER_MANAGE_UX;
void SECURITY_PHASE5_MANAGE_SOURCE_GUARDS;
const SECURITY_PREMIUM_POLISH_V2_SOURCE_GUARDS = [
  'lite-security-premium-v2-shell-depth',
  'lite-security-premium-v2-focus-ring',
  'lite-security-premium-v2-touch-targets',
  'lite-security-premium-v2-manage-tabs-motion',
  'lite-security-premium-v2-live-progress-motion',
  'lite-security-premium-v2-reduced-motion',
];
void SECURITY_PREMIUM_POLISH_V2_SOURCE_GUARDS;
const SECURITY_PROFILE1_QUICK_SAFETY_GUARDS = [
  'Quick safety check',
  'Checks Pocket Lab basics',
  'Skips photos, backups, and large caches',
  'Skipped by Quick Safety Check',
  'coverage_summary',
  'scan_profile',
];
const SECURITY_PROFILE2_FULL_LOCAL_CHECK_GUARDS = [
  'Full Local Check',
  'Checks this device more deeply',
  'Best while phone is charging',
  'Can take 10–30 minutes',
  'Still skips photos, backups, and large caches',
  'profile: full',
];
const SECURITY_PROFILE3_APP_CHECK_GUARDS = [
  'App Check',
  'Check PhotoPrism',
  'Checks PhotoPrism route, app files, settings, backup metadata, and action state',
  'Skips photos and media',
  'profile: app',
  'app_id: photoprism',
];
void SECURITY_PROFILE1_QUICK_SAFETY_GUARDS;
void SECURITY_PROFILE2_FULL_LOCAL_CHECK_GUARDS;
void SECURITY_PROFILE3_APP_CHECK_GUARDS;
const SECURITY_PROFILE_VIEW_POLISH_GUARDS = [
  'lite-security-profile-action-grid',
  'lite-security-profile-switcher',
  'lite-security-profile-rollup-trigger',
  'Quick Scan',
  'Full Scan',
  'App Scan',
  'data-security-profile-view="profile-linked"',
  'data-security-profile-run-actions="quick-full-app"',
  'data-security-profile-history-preserved',
  'data-security-scan-details-profile-bound',
];
void SECURITY_PROFILE_VIEW_POLISH_GUARDS;

const SECURITY_SCAN_PROFILES = [
  { id: 'quick', label: 'Quick Scan', chip: 'Quick', actionLabel: 'Quick Scan', summary: 'Fast check for Pocket Lab basics.', running: 'Quick scan running' },
  { id: 'full', label: 'Full Scan', chip: 'Full', actionLabel: 'Full Scan', summary: 'Deeper local check. Best while charging.', running: 'Full scan running' },
  { id: 'app', label: 'App Scan', chip: 'App', actionLabel: 'App Scan', summary: 'Checks PhotoPrism without scanning photos.', running: 'App scan running' },
];
const SECURITY_SCAN_PROFILE_IDS = SECURITY_SCAN_PROFILES.map((profile) => profile.id);

function normalizeSecurityProfileId(value = '') {
  const normalized = String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
  if (normalized === 'full_local' || normalized === 'full_local_check') return 'full';
  if (normalized === 'app_check' || normalized === 'photoprism') return 'app';
  return SECURITY_SCAN_PROFILE_IDS.includes(normalized) ? normalized : 'quick';
}

function securityProfileMeta(profile = 'quick') {
  return SECURITY_SCAN_PROFILES.find((item) => item.id === normalizeSecurityProfileId(profile)) || SECURITY_SCAN_PROFILES[0];
}

function securityProfileRunTime(run = {}) {
  const value = run?.completed_at || run?.started_at || run?.requested_at || '';
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function profileFallbackCoverage(profile = 'quick') {
  const id = normalizeSecurityProfileId(profile);
  if (id === 'app') return DEFAULT_APP_COVERAGE_SUMMARY;
  if (id === 'full') return DEFAULT_FULL_COVERAGE_SUMMARY;
  return DEFAULT_QUICK_COVERAGE_SUMMARY;
}

function buildSecurityProfileRuns({ data = {}, lastRun = null, evidenceRun = null, result = null, history = [], profileLatest = {} }) {
  const byProfile = {};
  const latestValues = profileLatest && typeof profileLatest === 'object' ? Object.values(profileLatest) : [];
  const candidates = [
    ...(Array.isArray(history) ? history : []),
    ...latestValues,
    lastRun,
    evidenceRun,
    result,
  ].filter(Boolean);
  candidates.forEach((run) => {
    const profile = normalizeSecurityProfileId(run?.scan_profile || run?.profile || (run?.app_id ? 'app' : 'quick'));
    const current = byProfile[profile];
    if (!current || securityProfileRunTime(run) >= securityProfileRunTime(current)) {
      byProfile[profile] = run;
    }
  });
  const topProfile = normalizeSecurityProfileId(data?.scan_profile || lastRun?.scan_profile || evidenceRun?.scan_profile || result?.scan_profile || 'quick');
  if (!byProfile[topProfile] && lastRun) byProfile[topProfile] = lastRun;
  return byProfile;
}

function profileEvidenceRefs(run = {}, fallback = []) {
  const refs = Array.isArray(run?.evidence_refs) ? run.evidence_refs : [];
  return Array.from(new Set([...refs, ...(Array.isArray(fallback) ? fallback : [])].filter(Boolean).map(String)));
}

function profileRunTimestampLabel(run = null) {
  const timestamp = run?.completed_at || run?.started_at || run?.requested_at || run?.updated_at || '';
  return timestamp ? `Last ${formatLiteTime(timestamp)}` : 'No saved check yet';
}

function securityToolChip(toolKey, toolLabel, toolResult = {}, context = {}) {
  const runStatus = String(context.runStatus || '').toLowerCase();
  const terminal = ['succeeded', 'success', 'healthy', 'degraded', 'partial', 'completed', 'done'].some((status) => runStatus.includes(status));
  const tools = Array.isArray(context.tools) ? context.tools.map((tool) => String(tool).toLowerCase()) : [];
  const stepText = (Array.isArray(context.executionSteps) ? context.executionSteps : [])
    .map((step) => `${step?.key || ''} ${step?.title || ''} ${step?.detail || ''} ${step?.state || ''}`.toLowerCase())
    .join(' ');
  const profile = normalizeSecurityProfileId(context.profile || 'quick');
  const toolWasExpected = tools.includes(toolKey) || stepText.includes(toolKey) || (profile !== 'app' && ['lynis', 'trivy'].includes(toolKey)) || (profile === 'app' && toolKey === 'trivy');
  if (securityToolCompleted(toolResult) || (terminal && toolWasExpected && !runStatus.includes('failed') && !runStatus.includes('error'))) {
    return { key: toolKey, label: `${toolLabel} checked`, tone: 'ready' };
  }
  if (terminal && !toolWasExpected) {
    return { key: toolKey, label: `${toolLabel} not used`, tone: 'neutral' };
  }
  const rawLabel = securityToolStatusLabel(toolResult);
  const normalized = String(rawLabel || '').trim().toLowerCase();
  const readableStatus = rawLabel && normalized !== 'pending'
    ? rawLabel.charAt(0).toUpperCase() + rawLabel.slice(1)
    : 'pending';
  return {
    key: toolKey,
    label: `${toolLabel} ${readableStatus}`,
    tone: securityToolPartial(toolResult) || securityToolMissing(toolResult) ? 'review' : 'checking',
  };
}

const SECURITY_SCORE_RING_GREEN_SPRING_GUARDS = [
  'lite-security-score-ring-green-fill',
  'data-security-score-fill="spring"',
  'Lynis checked',
  'Trivy checked',
  'lite-security-execution-ready',
];
void SECURITY_SCORE_RING_GREEN_SPRING_GUARDS;

const SECURITY_DETAIL_SHELL_META = {
  changes: {
    eyebrow: 'Safety Details',
    title: 'What changed',
    description: 'Review changes from the latest safety check without opening raw scanner output.',
  },
  attention: {
    eyebrow: 'Safety Details',
    title: 'Needs attention',
    description: 'Review current items one at a time with safe, plain-language guidance.',
  },
  coverage: {
    eyebrow: 'Coverage',
    title: 'Quick safety coverage',
    description: 'See what Quick Safety Check covered and what it skipped to stay fast.',
  },
  checkPath: {
    eyebrow: 'Check Path',
    title: 'Backend check path',
    description: 'See the FastAPI, worker, Lynis, Trivy, and evidence handoff summary.',
  },
  evidence: {
    eyebrow: 'Evidence',
    title: 'Safe evidence summary',
    description: 'Open sanitized evidence metadata while raw evidence remains backend-owned.',
  },
  history: {
    eyebrow: 'Safety History',
    title: 'Safety history',
    description: 'Open recent safety checks only when needed so the main page stays light.',
  },
  technical_details: {
    eyebrow: 'Technical Details',
    title: 'Safe technical details',
    description: 'Collapsed support metadata with raw evidence, logs, paths, and secrets hidden.',
  },
};

function securityDetailShellMeta(type) {
  return SECURITY_DETAIL_SHELL_META[type] || SECURITY_DETAIL_SHELL_META.evidence;
}

const SECURITY_MANAGE_SECTIONS = [
  { id: 'overview', label: 'Overview' },
  { id: 'changes', label: 'Changes' },
  { id: 'issues', label: 'Issues' },
  { id: 'coverage', label: 'Coverage' },
  { id: 'check_path', label: 'Check path' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'history', label: 'History' },
  { id: 'technical_details', label: 'Technical details' },
];

const SECURITY_MANAGE_SECTION_DESCRIPTIONS = {
  overview: 'Score, last checked state, saved evidence, and tool chips.',
  changes: 'New, resolved, and still-present safety changes.',
  issues: 'Compact review rows with focused finding details.',
  coverage: 'What the latest Security check covered, skipped, or marked partial.',
  check_path: 'Backend-truthful FastAPI, worker, Lynis, Trivy, and evidence steps.',
  evidence: 'Sanitized evidence summary. Raw scanner output stays backend-owned.',
  history: 'Recent safety trend summary with lazy details.',
  technical_details: 'Collapsed safe metadata for support and troubleshooting.',
};

const DEFAULT_APP_COVERAGE_SUMMARY = {
  profile: 'app',
  app_id: 'photoprism',
  app_label: 'PhotoPrism',
  checked_targets: [
    'PhotoPrism route',
    'PhotoPrism app files',
    'PhotoPrism settings',
    'PhotoPrism backup metadata',
    'PhotoPrism action state',
  ],
  skipped_targets: [
    'Photo library/media',
    'PhotoPrism originals/import folder',
    'PhotoPrism thumbnails/cache/sidecars',
    'PhotoPrism database',
    'Backup payloads',
    'Android shared storage',
    'Logs and large caches',
  ],
  excluded_groups: [
    'Photo library/media',
    'PhotoPrism originals/import folder',
    'PhotoPrism thumbnails, cache, sidecars, and database',
    'Backup payloads and restic repository contents',
    'Android shared storage',
    'Logs and large caches',
  ],
  partial_targets: [],
  timed_out_targets: [],
};


const SECURITY_COVERAGE_ROWS = [
  { component: 'Lite API', dependencies: true, secrets: true, config: true, runtime: true, evidence: true },
  { component: 'PWA bundle', dependencies: true, secrets: true, config: false, runtime: false, evidence: true },
  { component: 'Caddy', dependencies: false, secrets: true, config: true, runtime: true, evidence: true },
  { component: 'NATS', dependencies: false, secrets: true, config: true, runtime: true, evidence: true },
  { component: 'Worker', dependencies: true, secrets: true, config: true, runtime: true, evidence: true },
  { component: 'Bootstrap scripts', dependencies: false, secrets: true, config: true, runtime: false, evidence: true },
  { component: 'Recovery state', dependencies: false, secrets: true, config: true, runtime: true, evidence: true },
];

const SECURITY_PROTECTION_REASONS = [
  'Scans run locally through Pocket Lab',
  'Browser never runs shell commands',
  'Secrets are redacted before display',
  'Evidence is saved with sensitive values hidden',
  'SBOM is generated for dependency visibility',
];

const SECURITY_TRUST_BOUNDARY_STEPS = [
  { label: 'Browser', note: 'requests only' },
  { label: 'FastAPI', note: 'control API' },
  { label: 'Worker', note: 'runs tools' },
  { label: 'Lynis/Trivy', note: 'local checks' },
  { label: 'Evidence', note: 'sanitized before display' },
];


const DEFAULT_QUICK_COVERAGE_SUMMARY = {
  profile: 'quick',
  checked_targets: [
    'Termux host posture',
    'Pocket Lab Lite files',
    'Caddy route config',
    'NATS config posture',
    'Services summary',
    'Security evidence state',
  ],
  skipped_targets: [
    'Photo library/media',
    'Backup payloads',
    'PROot Ubuntu full filesystem',
    'Go/npm/cache folders',
    'Old PWA builds',
    'Large runtime histories',
  ],
  excluded_groups: [
    'Photo library/media',
    'Backup payloads and restore checkpoints',
    'PROot Ubuntu full filesystem',
    'Go/npm/cache folders',
    'Old PWA builds',
    'Large runtime histories',
  ],
  partial_targets: [],
  timed_out_targets: [],
};


const DEFAULT_FULL_COVERAGE_SUMMARY = {
  profile: 'full',
  checked_targets: [
    'Termux host',
    'Pocket Lab Lite',
    'Runtime config',
    'PROot Ubuntu',
    'PhotoPrism',
    'Backup metadata',
  ],
  skipped_targets: [
    'Photo library/media',
    'Android shared storage',
    'PhotoPrism originals/import/media/cache/sidecars',
    'Backup payloads',
    'Restic repository contents',
    'Service logs',
    'Go/npm/tool caches',
  ],
  excluded_groups: [
    'Photo library/media',
    'Android shared storage',
    'Backup payloads and restic repository contents',
    'Logs and generated runtime histories',
    'Go/npm/tool caches',
  ],
  partial_targets: [],
  timed_out_targets: [],
  missing_targets: [],
  target_statuses: [],
};

function quickCoverageList(values, fallback = []) {
  const items = Array.isArray(values) && values.length ? values : fallback;
  return items.map((value) => String(value || '').trim()).filter(Boolean).slice(0, 12);
}

function quickCoverageStatus(value, coverageSummary = {}) {
  const text = String(value || '').toLowerCase();
  const partial = quickCoverageList(coverageSummary.partial_targets).some((item) => text.includes(String(item).toLowerCase()) || String(item).toLowerCase().includes(text));
  const timedOut = quickCoverageList(coverageSummary.timed_out_targets).some((item) => text.includes(String(item).toLowerCase()) || String(item).toLowerCase().includes(text));
  if (timedOut) return { label: 'Timed out', tone: 'review' };
  if (partial) return { label: 'Partial', tone: 'review' };
  return { label: 'Checked', tone: 'ready' };
}

function QuickCoverageRows({ title, items, statusLabel, statusTone = 'ready' }) {
  return (
    <div className="lite-security-quick-coverage-group">
      <h4>{title}</h4>
      <div className="lite-security-quick-coverage-list" role="list">
        {items.map((item) => (
          <div key={`${title}-${item}`} className="lite-security-quick-coverage-row" role="listitem">
            <span>{item}</span>
            <span className={`lite-security-quick-coverage-pill lite-security-quick-coverage-${statusTone}`}>{statusLabel}</span>
          </div>
        ))}
      </div>
    </div>
  );
}


function SecurityTargetStatusRows({ targetStatuses = [] }) {
  const rows = Array.isArray(targetStatuses) ? targetStatuses.slice(0, 12) : [];
  if (!rows.length) return null;
  return (
    <div className="lite-security-quick-coverage-group lite-security-full-target-statuses">
      <h4>Target status</h4>
      <div className="lite-security-quick-coverage-list" role="list">
        {rows.map((item) => {
          const status = String(item?.status || 'unknown').toLowerCase();
          const tone = ['checked', 'completed'].includes(status) ? 'ready' : ['partial', 'timed_out', 'missing', 'review'].includes(status) ? 'review' : status === 'failed' ? 'danger' : 'neutral';
          const label = status === 'timed_out' ? 'Timed out' : status === 'missing' ? 'Missing' : status === 'partial' ? 'Partial' : status === 'checked' || status === 'completed' ? 'Checked' : status || 'Unknown';
          return (
            <div key={`${item?.target_id || item?.target_label}-${item?.tool || 'target'}`} className="lite-security-quick-coverage-row" role="listitem">
              <span>{item?.target_label || item?.target_id || 'Security target'}</span>
              <span className={`lite-security-quick-coverage-pill lite-security-quick-coverage-${tone}`}>{label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function securityStepState(steps, key) {
  return steps.find((step) => step.key === key)?.state || 'waiting';
}

function securityToolCompleted(toolResult = {}) {
  const status = String(toolResult?.status || '').toLowerCase();
  return ['completed', 'succeeded', 'success', 'done'].includes(status);
}

function securityToolPartial(toolResult = {}) {
  const status = String(toolResult?.status || '').toLowerCase();
  return ['partial', 'timed_out', 'timeout', 'review', 'degraded'].includes(status);
}

function securityToolMissing(toolResult = {}) {
  return String(toolResult?.status || '').toLowerCase() === 'missing_tool';
}

function deriveSecurityConfidence({ lastRun, runStatus, executionSteps, evidenceRefs, evidence, toolResults, sbomSaved, reviewItems }) {
  const status = String(lastRun?.status || runStatus || '').toLowerCase();
  const hasRun = Boolean(lastRun?.run_id || status);
  const evidenceSaved = Boolean(
    evidenceRefs.length ||
    evidence?.evidence_refs?.length ||
    securityStepState(executionSteps, 'evidence_saved') === 'done'
  );
  const lynisState = securityStepState(executionSteps, 'lynis_host_check');
  const trivyState = securityStepState(executionSteps, 'trivy_dependency_secret_check');
  const workerState = securityStepState(executionSteps, 'worker_picked_up');
  const lynisCompleted = lynisState === 'done' || securityToolCompleted(toolResults?.lynis);
  const trivyCompleted = trivyState === 'done' || securityToolCompleted(toolResults?.trivy);
  const workerCompleted = ['succeeded', 'completed', 'healthy', 'degraded'].includes(status) || workerState === 'done';
  const missingTool =
    securityToolMissing(toolResults?.lynis) ||
    securityToolMissing(toolResults?.trivy) ||
    reviewItems.some((item) => String(item?.category || item?.status || '').toLowerCase().includes('missing_tool'));
  const partialTool =
    Boolean(lastRun?.partial_results) ||
    ['partial', 'degraded', 'review'].includes(status) ||
    [lynisState, trivyState].includes('review') ||
    securityToolPartial(toolResults?.lynis) ||
    securityToolPartial(toolResults?.trivy);
  const failedCoreStep = executionSteps.some((step) => step.state === 'failed') || ['failed', 'failure', 'error'].includes(status);

  if (!hasRun) {
    return {
      level: 'Low',
      tone: 'danger',
      title: 'Confidence: Low',
      summary: 'Run Safety Check to create fresh evidence and SBOM visibility for this device.',
      chips: [
        { label: 'No recent check', tone: 'danger' },
        { label: 'Evidence unavailable', tone: 'danger' },
      ],
    };
  }

  if (failedCoreStep || missingTool || (!evidenceSaved && ['succeeded', 'completed', 'degraded', 'failed'].includes(status))) {
    const missingReason = missingTool ? 'A required security tool is missing.' : 'The worker did not finish with usable evidence.';
    return {
      level: 'Low',
      tone: 'danger',
      title: 'Confidence: Low',
      summary: `${missingReason} Recheck after fixing the tool or worker issue.`,
      chips: [
        { label: lynisCompleted ? 'Lynis completed' : missingTool ? 'Tool missing' : 'Lynis not complete', tone: lynisCompleted ? 'ready' : 'danger' },
        { label: trivyCompleted ? 'Trivy completed' : missingTool ? 'Tool missing' : 'Trivy not complete', tone: trivyCompleted ? 'ready' : 'danger' },
        { label: evidenceSaved ? 'Evidence saved' : 'Evidence unavailable', tone: evidenceSaved ? 'ready' : 'danger' },
      ],
    };
  }

  if (!partialTool && lynisCompleted && trivyCompleted && evidenceSaved && sbomSaved && workerCompleted) {
    return {
      level: 'High',
      tone: 'ready',
      title: 'Confidence: High',
      summary: 'Both Lynis and Trivy completed. Evidence and SBOM were saved.',
      chips: [
        { label: 'Lynis completed', tone: 'ready' },
        { label: 'Trivy completed', tone: 'ready' },
        { label: 'Evidence saved', tone: 'ready' },
        { label: 'SBOM saved', tone: 'ready' },
      ],
    };
  }

  const partialLabel = lynisState === 'review' || securityToolPartial(toolResults?.lynis)
    ? 'Lynis did not finish every host-readiness check.'
    : trivyState === 'review' || securityToolPartial(toolResults?.trivy)
      ? 'Trivy completed with partial review data.'
      : 'The latest check has partial quality signals.';

  return {
    level: 'Medium',
    tone: 'review',
    title: 'Confidence: Medium',
    summary: `${partialLabel} ${evidenceSaved ? 'Available evidence was saved.' : 'Evidence is not complete yet.'} Recheck recommended.`,
    chips: [
      { label: lynisCompleted ? 'Lynis completed' : lynisState === 'review' ? 'Lynis partial' : 'Lynis not complete', tone: lynisCompleted ? 'ready' : 'review' },
      { label: trivyCompleted ? 'Trivy completed' : trivyState === 'review' ? 'Trivy partial' : 'Trivy not complete', tone: trivyCompleted ? 'ready' : 'review' },
      { label: evidenceSaved ? 'Evidence saved' : 'Evidence pending', tone: evidenceSaved ? 'ready' : 'review' },
      { label: sbomSaved ? 'SBOM saved' : 'SBOM pending', tone: sbomSaved ? 'ready' : 'review' },
      { label: 'Recheck recommended', tone: 'review' },
    ],
  };
}

function SecurityConfidenceCard({ confidence }) {
  return (
    <section className={`lite-security-confidence-card lite-security-confidence-${confidence.tone}`} aria-labelledby="security-confidence-title">
      <div>
        <span className="lite-security-confidence-eyebrow">Security confidence</span>
        <h2 id="security-confidence-title">{confidence.title}</h2>
        <p>{confidence.summary}</p>
      </div>
      <div className="lite-security-confidence-chips" aria-label="Security confidence reasons">
        {confidence.chips.map((chip) => (
          <span key={`${chip.label}-${chip.tone}`} className={`lite-security-confidence-chip lite-security-confidence-chip-${chip.tone}`}>
            {chip.label}
          </span>
        ))}
      </div>
    </section>
  );
}

function SecurityProtectionReasonsCard() {
  return (
    <GlassCard className="lite-security-card lite-security-protection-card">
      <div className="lite-security-card-head">
        <div className="lite-security-icon">
          <Lock className="h-5 w-5" />
        </div>
        <span className="lite-security-soft-badge">Protected by design</span>
      </div>
      <h2>You are protected because...</h2>
      <div className="lite-security-protection-list" role="list">
        {SECURITY_PROTECTION_REASONS.map((reason) => (
          <div key={reason} role="listitem">
            <span aria-hidden="true">✓</span>
            <p>{reason}</p>
          </div>
        ))}
      </div>
      <p className="lite-security-card-note">This does not mean every compromise is impossible. It means Pocket Lab keeps checks local, browser-safe, and evidence-based.</p>
    </GlassCard>
  );
}

function SecurityTrustBoundaryCard() {
  return (
    <GlassCard className="lite-security-card lite-security-boundary-card">
      <div className="lite-security-card-head">
        <div className="lite-security-icon">
          <Network className="h-5 w-5" />
        </div>
        <span className="lite-security-soft-badge">Trust boundary</span>
      </div>
      <h2>Browser to evidence path</h2>
      <div className="lite-security-boundary-flow" aria-label="Browser to FastAPI to Worker to Lynis and Trivy to sanitized evidence">
        {SECURITY_TRUST_BOUNDARY_STEPS.map((step, index) => (
          <React.Fragment key={step.label}>
            <div className="lite-security-boundary-node">
              <strong>{step.label}</strong>
              <span>{step.note}</span>
            </div>
            {index < SECURITY_TRUST_BOUNDARY_STEPS.length - 1 ? <span className="lite-security-boundary-arrow" aria-hidden="true">→</span> : null}
          </React.Fragment>
        ))}
      </div>
      <p>The browser only requests checks and displays summaries. Security tools run on the device through Pocket Lab.</p>
    </GlassCard>
  );
}

function CoverageCell({ covered, label }) {
  return (
    <span
      className={`lite-security-coverage-mark ${covered ? 'lite-security-coverage-covered' : 'lite-security-coverage-not-covered'}`}
      aria-label={`${label}: ${covered ? 'covered' : 'not covered by this check'}`}
      title={`${label}: ${covered ? 'covered' : 'not covered by this check'}`}
    >
      {covered ? '✓' : '—'}
    </span>
  );
}

function SecurityCoverageMatrixCard({ expanded, onToggle }) {
  return (
    <GlassCard className="lite-security-card lite-security-coverage-card">
      <div className="lite-security-card-head">
        <div className="lite-security-icon">
          <LayoutGrid className="h-5 w-5" />
        </div>
        <span className="lite-security-soft-badge">Coverage</span>
      </div>
      <h2>Coverage: 7 protected areas</h2>
      <p>Dependencies, secrets, config, runtime, and evidence are checked across Pocket Lab Lite components where the backend can safely inspect them.</p>
      <button type="button" className="lite-security-coverage-toggle" onClick={onToggle} aria-expanded={expanded}>
        {expanded ? 'Hide details' : 'Details'}
      </button>
      {expanded ? (
        <div className="lite-security-coverage-scroll" role="region" aria-label="Security coverage matrix" tabIndex="0">
          <table className="lite-security-coverage-table">
            <caption>Coverage means Pocket Lab checks evidence and configuration paths it can safely inspect. It does not expose raw secrets.</caption>
            <thead>
              <tr>
                <th scope="col">Component</th>
                <th scope="col">Dependencies</th>
                <th scope="col">Secrets</th>
                <th scope="col">Config</th>
                <th scope="col">Runtime</th>
                <th scope="col">Evidence</th>
              </tr>
            </thead>
            <tbody>
              {SECURITY_COVERAGE_ROWS.map((row) => (
                <tr key={row.component}>
                  <th scope="row">{row.component}</th>
                  <td><CoverageCell covered={row.dependencies} label={`${row.component} dependencies`} /></td>
                  <td><CoverageCell covered={row.secrets} label={`${row.component} secrets`} /></td>
                  <td><CoverageCell covered={row.config} label={`${row.component} config`} /></td>
                  <td><CoverageCell covered={row.runtime} label={`${row.component} runtime`} /></td>
                  <td><CoverageCell covered={row.evidence} label={`${row.component} evidence`} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="lite-security-coverage-summary" aria-label="Coverage summary">
          <span>Dependencies</span>
          <span>Secrets</span>
          <span>Config</span>
          <span>Runtime</span>
          <span>Evidence</span>
        </div>
      )}
    </GlassCard>
  );
}


const SECURITY_ACTION_TONES = new Set(['safe', 'review', 'danger', 'neutral']);

function textIncludes(value, needles) {
  const text = String(value || '').toLowerCase();
  return needles.some((needle) => text.includes(needle));
}

function findingCategory(finding) {
  return String(finding?.category || finding?.type || finding?.source_type || '').toLowerCase();
}

function findingSeverity(finding) {
  return String(finding?.severity || finding?.level || '').toLowerCase();
}

function findingReviewText(finding) {
  return [
    finding?.id,
    finding?.category,
    finding?.type,
    finding?.source,
    finding?.summary,
    finding?.title,
    finding?.recommendation,
    finding?.status,
    finding?.detail,
  ].filter(Boolean).join(' ').toLowerCase();
}

export function classifyFindingAction(finding, context = {}) {
  const category = findingCategory(finding);
  const severity = findingSeverity(finding);
  const text = findingReviewText(finding);
  const status = String(finding?.status || context?.lastRun?.status || '').toLowerCase();
  const highRisk = ['critical', 'high'].includes(severity);
  const mediumRisk = severity === 'medium';
  const timeoutLike = isSecurityTimeoutFinding(finding)
    || textIncludes(text, ['timeout', 'timed out', 'partial', 'did not finish'])
    || ['timeout', 'timed_out', 'partial', 'review'].includes(status);

  if (category === 'protected_runtime_secret') {
    return {
      label: 'Expected',
      tone: 'safe',
      summary: 'Protected runtime secret is locked down server-side.',
    };
  }

  if (category === 'missing_tool') {
    return {
      label: 'Action needed',
      tone: 'danger',
      summary: 'A required safety tool is missing on this device.',
    };
  }

  if (highRisk || category === 'secret_exposure') {
    return {
      label: 'Action needed',
      tone: 'danger',
      summary: 'This item needs attention before confidence can be high.',
    };
  }

  if (category === 'dependency_vulnerability') {
    return mediumRisk
      ? { label: 'Action needed', tone: 'danger', summary: 'A dependency should be updated through the normal Pocket Lab flow.' }
      : { label: 'Review recommended', tone: 'review', summary: 'Review this dependency and update if appropriate.' };
  }

  if (category === 'misconfiguration') {
    return ['critical', 'high', 'medium'].includes(severity)
      ? { label: 'Action needed', tone: 'danger', summary: 'A local setting may need a safer configuration.' }
      : { label: 'Review recommended', tone: 'review', summary: 'Review this local setting when convenient.' };
  }

  if (category === 'host_hardening' && timeoutLike) {
    return {
      label: 'Recheck',
      tone: 'review',
      summary: 'Lynis timeout needs another run.',
    };
  }

  if (timeoutLike) {
    return {
      label: 'Recheck',
      tone: 'review',
      summary: 'The check was partial, so another run is recommended.',
    };
  }

  if (mediumRisk) {
    return {
      label: 'Action needed',
      tone: 'danger',
      summary: 'This item should be reviewed and fixed when possible.',
    };
  }

  return {
    label: 'Review recommended',
    tone: 'neutral',
    summary: 'Review this item and run another safety check after changes.',
  };
}

export function buildSecurityRemediation(finding, context = {}) {
  const category = findingCategory(finding);
  const action = classifyFindingAction(finding, context);
  const text = findingReviewText(finding);
  const timeoutLike = isSecurityTimeoutFinding(finding)
    || textIncludes(text, ['timeout', 'timed out', 'partial', 'did not finish']);

  if (category === 'protected_runtime_secret') {
    return {
      title: 'Protected runtime secret',
      action,
      happened: 'Pocket Lab found a backend runtime secret in a protected server-side file.',
      means: 'This can be expected when the file is locked down and never displayed in the browser.',
      recommended: 'Keep file permissions restricted. Do not copy this file into public repos or frontend assets.',
      risk: 'Expected if locked down server-side.',
    };
  }

  if (timeoutLike || (category === 'host_hardening' && action.label === 'Recheck')) {
    return {
      title: 'Partial host-readiness check',
      action,
      happened: 'The host-readiness check did not finish before the timeout.',
      means: 'This is usually caused by device speed, battery state, or Termux limits.',
      recommended: 'Run the check again while charging. If this happens often, increase the Lynis timeout.',
      risk: 'Recheck recommended. Not evidence of compromise.',
    };
  }

  if (category === 'missing_tool') {
    return {
      title: 'Safety tool missing',
      action,
      happened: 'A required safety tool was not available on this device.',
      means: 'Pocket Lab could not complete that part of the safety check.',
      recommended: 'Re-run the Lite bootstrap or install the missing tool through the backend-supported setup path.',
      risk: 'Action needed before confidence can be high.',
    };
  }

  if (category === 'dependency_vulnerability') {
    return {
      title: 'Dependency needs review',
      action,
      happened: 'Trivy found a dependency with a known vulnerability.',
      means: 'A package or dependency may need an update.',
      recommended: 'Update through Pocket Lab’s normal release/bootstrap workflow, then run another safety check.',
      risk: findingSeverity(finding) === 'low' ? 'Review recommended.' : 'Action needed, especially for high or critical severity.',
    };
  }

  if (category === 'secret_exposure') {
    return {
      title: 'Secret-like value found',
      action,
      happened: 'Trivy found a secret-like value in a scanned path.',
      means: 'A sensitive value may be stored somewhere it should not be.',
      recommended: 'Keep the value hidden, rotate it through the backend/Identity flow if needed, and verify it is not in frontend assets or public repos.',
      risk: 'Action needed.',
    };
  }

  if (category === 'misconfiguration' || category === 'host_hardening') {
    return {
      title: 'Configuration review',
      action,
      happened: 'Trivy or Lynis found a configuration concern.',
      means: 'A local setting may be weaker than recommended.',
      recommended: 'Review the specific item, apply a backend-supported fix if available, then re-run the check.',
      risk: ['critical', 'high', 'medium'].includes(findingSeverity(finding)) ? 'Action needed.' : 'Review recommended.',
    };
  }

  return {
    title: 'Review item',
    action,
    happened: 'Pocket Lab found an item that needs review.',
    means: 'The check needs operator review before it should be considered resolved.',
    recommended: 'Review the finding details and run another safety check after making changes.',
    risk: action.label === 'Action needed' ? 'Action needed.' : 'Review recommended.',
  };
}

function securityHasEvidence(data, evidenceRefs = []) {
  const refs = Array.isArray(evidenceRefs) ? evidenceRefs : [];
  return refs.length > 0
    || Number(data?.last_run?.evidence_count || data?.evidence_count || 0) > 0
    || Boolean(data?.last_run?.evidence_saved)
    || Boolean(data?.last_run?.sbom_saved)
    || Boolean(data?.evidence_saved);
}

export function deriveSecurityHealthBanner(securityData, confidence, findings = []) {
  const lastRun = securityData?.last_run || null;
  const runStatus = String(lastRun?.status || securityData?.scan_progress?.status || securityData?.status || '').toLowerCase();
  const evidenceRefs = Array.isArray(securityData?.evidence_refs) ? securityData.evidence_refs : [];
  const evidenceSaved = securityHasEvidence(securityData, evidenceRefs);
  const allFindings = Array.isArray(findings) ? findings : [];
  const criticalHighCount = Number(lastRun?.critical_count || 0) + Number(lastRun?.high_count || 0)
    + allFindings.filter((item) => ['critical', 'high'].includes(findingSeverity(item))).length;
  const actionNeeded = allFindings.some((item) => classifyFindingAction(item, { lastRun, securityData }).label === 'Action needed');
  const partial = Boolean(lastRun?.partial_results)
    || String(confidence?.label || '').toLowerCase().includes('medium')
    || runStatus.includes('partial')
    || allFindings.some((item) => classifyFindingAction(item, { lastRun, securityData }).label === 'Recheck');
  const terminal = ['succeeded', 'success', 'healthy', 'degraded', 'partial', 'failed', 'error'].some((status) => runStatus.includes(status));

  if (!lastRun) {
    return {
      tone: 'neutral',
      title: 'Run your first safety check',
      body: 'Pocket Lab will check this device locally and save sanitized evidence.',
    };
  }

  if (runStatus.includes('failed') || runStatus.includes('error') || (terminal && !evidenceSaved)) {
    return {
      tone: 'danger',
      title: 'Safety check did not finish',
      body: 'Pocket Lab could not complete the check. Run it again when the device is online and charging.',
    };
  }

  if (criticalHighCount > 0 || actionNeeded) {
    return {
      tone: 'danger',
      title: 'Review needed',
      body: 'Pocket Lab found items that need attention. Evidence was saved with sensitive values hidden.',
    };
  }

  if (partial) {
    return {
      tone: 'review',
      title: 'Mostly safe, recheck recommended',
      body: 'Available evidence was saved. Some host-readiness checks did not finish.',
    };
  }

  return {
    tone: 'safe',
    title: 'Your Pocket Lab looks safe',
    body: 'No critical or high-risk issues were found. Evidence was saved for review.',
  };
}


function useSecurityReducedMotion() {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return undefined;
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReducedMotion(Boolean(query.matches));
    update();
    query.addEventListener?.('change', update);
    return () => query.removeEventListener?.('change', update);
  }, []);

  return reducedMotion;
}

const SECURITY_SPRING_CONFIG = {
  calm: { tension: 260, friction: 30, mass: 0.9 },
  section: { tension: 320, friction: 34, mass: 0.85 },
  micro: { tension: 380, friction: 28, mass: 0.75 },
};

function SecurityActionIndicator({ action }) {
  const tone = SECURITY_ACTION_TONES.has(action?.tone) ? action.tone : 'neutral';
  return (
    <span className={`lite-security-action-indicator lite-security-action-${tone}`} aria-label={`Safe to ignore? ${action?.label || 'Review recommended'}. ${action?.summary || ''}`}>
      <span>Safe to ignore?</span>
      <strong>{action?.label || 'Review recommended'}</strong>
    </span>
  );
}

function SecurityHealthBanner({ banner }) {
  return (
    <section className={`lite-security-health-banner lite-security-health-${banner.tone}`} aria-label="Security Health banner">
      <div>
        <span className="lite-security-health-kicker">Security Health</span>
        <h2>{banner.title}</h2>
        <p>{banner.body}</p>
      </div>
    </section>
  );
}


function safeSecurityText(value, fallback = 'Not available') {
  const text = String(value || '').trim();
  if (!text) return fallback;
  return text.replace(/(token|password|secret|api[_-]?key|authorization|private[_-]?key)\s*[:=]\s*[^\s,;]+/gi, '$1=[hidden]');
}

function findingTitle(finding = {}) {
  const rawTitle = finding?.title || finding?.summary || finding?.name;
  if (rawTitle) return safeSecurityText(rawTitle, 'Security review item');
  const category = String(finding?.category || '').toLowerCase();
  if (category === 'protected_runtime_secret') return 'Protected backend runtime secret';
  if (category === 'missing_tool') return 'Security tool missing';
  if (category === 'dependency_vulnerability') return 'Dependency vulnerability';
  if (category === 'secret_exposure') return 'Secret-like value found';
  if (category === 'misconfiguration') return 'Configuration review';
  if (category === 'host_hardening') return isSecurityTimeoutFinding(finding) ? 'Host readiness check timed out' : 'Host readiness review';
  return 'Security review item';
}

function normalizeSecuritySeverityLabel(value) {
  const severity = String(value || 'unknown').toLowerCase();
  if (severity === 'critical') return 'Critical';
  if (severity === 'high') return 'High';
  if (severity === 'medium') return 'Medium';
  if (severity === 'low') return 'Low';
  if (severity === 'info' || severity === 'informational') return 'Info';
  if (severity === 'review') return 'Review';
  return 'Unknown';
}

function deriveFindingSource(finding = {}) {
  const raw = `${finding?.source || ''} ${finding?.tool || ''} ${finding?.scanner || ''} ${finding?.category || ''} ${finding?.evidence_ref || ''}`.toLowerCase();
  if (raw.includes('lynis') || raw.includes('host_hardening')) return 'Lynis';
  if (raw.includes('trivy') || raw.includes('dependency_vulnerability') || raw.includes('misconfiguration') || raw.includes('secret_exposure') || raw.includes('protected_runtime_secret')) return 'Trivy';
  if (raw.includes('pocket lab') || raw.includes('pocketlab') || raw.includes('review')) return 'Pocket Lab';
  return 'Unknown';
}

function safeFindingComponentLabel(finding = {}) {
  const category = String(finding?.category || '').toLowerCase();
  if (category === 'protected_runtime_secret') return 'Backend runtime file';
  if (category === 'dependency_vulnerability') return safeSecurityText(finding?.component || finding?.package || finding?.target || 'Local dependency', 'Local dependency');
  if (category === 'host_hardening') return 'Host readiness';
  if (category === 'misconfiguration') return safeSecurityText(finding?.resource || finding?.target || finding?.component || 'Configuration', 'Configuration');
  if (category === 'secret_exposure') return 'Scanned path';
  if (category === 'missing_tool') return safeSecurityText(finding?.tool || finding?.source || 'Security tool', 'Security tool');

  const raw = finding?.component || finding?.package || finding?.target || finding?.file || finding?.path || finding?.location || finding?.relative_path || finding?.resource;
  const text = String(raw || '').trim();
  if (!text) return 'Pocket Lab runtime';
  if (/(token|password|secret|api[_-]?key|authorization|private[_-]?key)/i.test(text)) return 'Pocket Lab runtime';
  if (text.length > 96) return 'Evidence item';
  return safeSecurityText(text, 'Pocket Lab runtime');
}

function evidenceReferenceLabel(finding = {}, evidenceRefs = [], lastRun = null) {
  const candidates = [
    finding?.evidence_ref,
    finding?.evidence,
    finding?.evidence_file,
    finding?.evidence_path,
    ...(Array.isArray(finding?.evidence_refs) ? finding.evidence_refs : []),
  ].filter(Boolean);
  const category = String(finding?.category || '').toLowerCase();
  const refs = Array.isArray(evidenceRefs) ? evidenceRefs : [];
  if (!candidates.length) {
    if (category === 'host_hardening') candidates.push(refs.find((ref) => String(ref).toLowerCase().includes('lynis')) || 'lynis-normalized.json');
    if (['dependency_vulnerability', 'misconfiguration', 'secret_exposure', 'protected_runtime_secret', 'missing_tool'].includes(category)) {
      candidates.push(refs.find((ref) => String(ref).toLowerCase().includes('trivy')) || 'trivy-normalized.json');
    }
    if (!candidates.length && refs.length) candidates.push(refs[0]);
    if (!candidates.length && lastRun?.run_id) candidates.push(`security/evidence/${shortRunId(lastRun.run_id)}/summary.json`);
  }
  const ref = String(candidates[0] || '').trim();
  if (!ref) return 'Saved evidence not available for this item.';
  const safeRef = ref.replace(/(token|password|secret|api[_-]?key|authorization|private[_-]?key)[^/\s]*/gi, '$1-hidden');
  return safeSecurityText(safeRef.split('/').slice(-2).join('/'), 'Saved evidence not available for this item.');
}

function SecurityFindingDetailModal({ finding, context, onClose }) {
  if (!finding) return null;
  const remediation = buildSecurityRemediation(finding, context);
  const action = remediation.action || classifyFindingAction(finding, context);
  const title = findingTitle(finding);
  const severity = normalizeSecuritySeverityLabel(finding?.severity || action?.label || 'review');
  const source = deriveFindingSource(finding);
  const component = safeFindingComponentLabel(finding);
  const evidenceRef = evidenceReferenceLabel(finding, context?.evidenceRefs || [], context?.lastRun);
  const descriptionId = 'lite-security-finding-detail-description';
  const titleId = 'lite-security-finding-detail-title';

  return (
    <section className="lite-finding-detail-modal lite-security-coverage-scroll" role="region" aria-labelledby={titleId} aria-describedby={descriptionId} tabIndex="0">
        <div className="lite-finding-detail-header">
          <div>
            <span className="lite-security-soft-badge">Finding</span>
            <h2 id={titleId}>{title}</h2>
          </div>
          <button type="button" className="lite-finding-detail-close" onClick={onClose} aria-label="Close finding details">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="lite-finding-detail-meta" id={descriptionId}>
          <span className={`lite-finding-detail-chip lite-security-action-${action.tone || 'neutral'}`}>Severity: {severity}</span>
          <span className="lite-finding-detail-chip">Source: {source}</span>
          <span className={`lite-finding-detail-chip lite-security-action-${action.tone || 'neutral'}`}>Status: {action.label || 'Review recommended'}</span>
        </div>

        <div className="lite-finding-detail-section">
          <h3>Affected component</h3>
          <p>{component}</p>
        </div>

        <div className="lite-finding-detail-section">
          <h3>Recommendation</h3>
          <p>{remediation.recommended}</p>
        </div>

        <div className="lite-finding-detail-section lite-finding-detail-evidence">
          <h3>Evidence reference</h3>
          <p>{evidenceRef}</p>
        </div>

        <div className="lite-finding-detail-section">
          <h3>What should I do?</h3>
          <p>{remediation.happened} {remediation.means} {remediation.risk}</p>
        </div>

        <div className="lite-finding-detail-actions">
          <button type="button" className="lite-finding-detail-trigger" onClick={onClose}>Close</button>
        </div>
      </section>
  );
}

function SecurityRemediationDrawer({ finding, context, onClose }) {
  const remediation = finding ? buildSecurityRemediation(finding, context) : null;
  const detail = finding?.recommendation || finding?.summary || finding?.title || 'Review this item and keep Pocket Lab protected.';
  return (
    <LiteSheet
      open={Boolean(finding)}
      onClose={onClose}
      eyebrow="What should I do?"
      title={remediation?.title || 'Remediation guidance'}
      description="Review safe guidance without running commands or changing this device."
      layerClassName="lite-security-phase3-layer lite-security-remediation-layer"
      className="lite-security-phase3-panel lite-security-remediation-panel lite-security-phase4-panel-motion"
      bodyClassName="lite-security-phase3-scroll lite-security-remediation-scroll"
      headerClassName="lite-security-phase3-head"
      closeClassName="lite-security-phase3-close"
      gripClassName="lite-security-phase3-grip"
      variant="security"
      motion="safe-grip"
      surfaceProps={{ 'data-security-phase3-responsive-shell': 'true', 'data-security-remediation-shell': 'true', 'data-security-safe-motion': 'gesture-spring', 'data-security-react-spring': 'remediation' }}
    >
      {finding && remediation ? (
        <div className="lite-security-remediation-content">
          <SecurityActionIndicator action={remediation.action} />
          <div className="lite-security-remediation-summary">
            <strong>{securityFindingLabel(finding)}</strong>
            <p>{detail}</p>
          </div>
          <div className="lite-security-remediation-sections">
            <section>
              <h3>What happened</h3>
              <p>{remediation.happened}</p>
            </section>
            <section>
              <h3>What it means</h3>
              <p>{remediation.means}</p>
            </section>
            <section>
              <h3>Recommended action</h3>
              <p>{remediation.recommended}</p>
            </section>
            <section>
              <h3>Risk</h3>
              <p>{remediation.risk}</p>
            </section>
          </div>
          <p className="lite-security-remediation-note">This guidance does not run commands or change your device. Any future fix action must stay backend-owned and evidence-backed.</p>
        </div>
      ) : null}
    </LiteSheet>
  );
}


function securityRunIsTerminal(status) {
  const value = String(status || '').toLowerCase();
  return ['succeeded', 'success', 'healthy', 'degraded', 'partial', 'failed', 'error'].some((item) => value.includes(item));
}

function securityRunIsGood(run, evidenceAvailable = false) {
  if (!run) return false;
  const status = String(run.status || '').toLowerCase();
  const criticalHigh = Number(run.critical_count || 0) + Number(run.high_count || 0);
  const evidenceSaved = evidenceAvailable
    || Number(run.evidence_count || 0) > 0
    || Boolean(run.evidence_saved)
    || Boolean(run.sbom_saved);
  return status.includes('succeeded') && criticalHigh === 0 && evidenceSaved && !run.partial_results;
}

function evidenceRefCount(data, fallbackRefs = []) {
  const refs = Array.isArray(fallbackRefs) ? fallbackRefs : [];
  return refs.length || Number(data?.last_run?.evidence_count || data?.evidence_count || 0) || 0;
}

function formatSecurityToolsLabel(tools = []) {
  const normalized = (Array.isArray(tools) ? tools : [])
    .filter(Boolean)
    .map((tool) => String(tool).trim())
    .filter(Boolean);
  if (!normalized.length) return 'Not recorded';
  return normalized.map((tool) => tool.charAt(0).toUpperCase() + tool.slice(1)).join(' + ');
}

export function deriveLatestEvidenceReceipt(securityData, evidenceState = {}) {
  const lastRun = securityData?.last_run || null;
  const runStatus = String(lastRun?.status || securityData?.scan_progress?.status || '').toLowerCase();
  const currentRunInProgress = ['queued', 'running'].includes(runStatus);
  const refs = Array.isArray(securityData?.evidence_refs) ? securityData.evidence_refs : [];
  const evidenceRefs = Array.isArray(evidenceState?.evidence?.evidence_refs) && evidenceState.evidence.evidence_refs.length
    ? evidenceState.evidence.evidence_refs
    : refs;
  const history = Array.isArray(securityData?.history) ? securityData.history : [];
  const latestHistoryWithEvidence = history.find((item) => Number(item?.evidence_count || 0) > 0 && item?.run_id);
  const sourceRun = currentRunInProgress && latestHistoryWithEvidence ? latestHistoryWithEvidence : (lastRun || latestHistoryWithEvidence);
  const available = Boolean(sourceRun?.run_id) && (securityHasEvidence(securityData, evidenceRefs) || Number(sourceRun?.evidence_count || 0) > 0);

  if (!available) {
    return {
      available: false,
      status: 'empty',
      title: 'Latest evidence',
      summary: 'Run a safety check to create a sanitized receipt.',
      runLabel: 'No saved evidence yet.',
      fileCountLabel: 'No saved evidence yet.',
      sbomLabel: 'Not saved',
      secretsLabel: 'Hidden after a check',
    };
  }

  const tools = Array.isArray(sourceRun?.tools) && sourceRun.tools.length
    ? sourceRun.tools
    : (Array.isArray(lastRun?.tools) && lastRun.tools.length ? lastRun.tools : ['lynis', 'trivy']);
  const fileCount = evidenceRefs.length || Number(sourceRun?.evidence_count || 0);
  const sbomSaved = Boolean(sourceRun?.sbom_saved)
    || evidenceRefs.some((ref) => String(ref).toLowerCase().includes('sbom'))
    || Boolean(evidenceState?.sbomSaved);

  return {
    available: true,
    status: currentRunInProgress ? 'saved_previous' : 'ready',
    title: currentRunInProgress ? 'Latest saved evidence' : 'Latest evidence',
    runId: sourceRun.run_id,
    shortRunId: shortRunId(sourceRun.run_id),
    toolsLabel: formatSecurityToolsLabel(tools),
    fileCountLabel: `${fileCount} sanitized evidence file${fileCount === 1 ? '' : 's'}`,
    sbomLabel: sbomSaved ? 'Saved' : 'Not saved',
    secretsLabel: 'Hidden',
    summary: currentRunInProgress
      ? 'Current check is running. Showing the latest saved sanitized receipt.'
      : 'Sanitized evidence is ready for review.',
  };
}

export function deriveLastKnownGood(securityData, findings = []) {
  const lastRun = securityData?.last_run || null;
  const refs = Array.isArray(securityData?.evidence_refs) ? securityData.evidence_refs : [];
  const history = Array.isArray(securityData?.history) ? securityData.history : [];
  const currentPartial = Boolean(lastRun?.partial_results) || String(lastRun?.status || '').toLowerCase().includes('partial');
  const currentHighRisk = Number(lastRun?.critical_count || 0) + Number(lastRun?.high_count || 0)
    + (Array.isArray(findings) ? findings.filter((item) => ['critical', 'high'].includes(findingSeverity(item))).length : 0);

  const knownGood = history.find((run) => securityRunIsGood(run, false))
    || (securityRunIsGood(lastRun, securityHasEvidence(securityData, refs)) ? lastRun : null);

  if (!knownGood) {
    return {
      available: false,
      title: 'Last known good',
      summary: 'Run a successful safety check to establish a baseline.',
      completedAtLabel: 'Not available yet',
      currentPartialNote: null,
      historicalWarning: currentHighRisk > 0 ? 'Current review still needs attention.' : null,
    };
  }

  return {
    available: true,
    title: 'Last known good',
    runId: knownGood.run_id,
    shortRunId: shortRunId(knownGood.run_id),
    completedAt: knownGood.completed_at,
    completedAtLabel: knownGood.completed_at ? formatLiteTime(knownGood.completed_at) : 'Saved baseline',
    score: knownGood.score,
    summary: `Score ${knownGood.score ?? '—'} · No urgent issues · Evidence saved`,
    currentPartialNote: currentPartial ? 'Current check is partial. Last known good state is still available.' : null,
    historicalWarning: currentHighRisk > 0 ? 'Last known good is historical. Current review still needs attention.' : null,
  };
}

function friendlyDeltaItemLabel(items = [], fallback = 'review item') {
  const list = Array.isArray(items) ? items : [];
  if (!list.length) return '0';
  const actionCount = list.filter((item) => classifyFindingAction(item).label === 'Action needed').length;
  const recheckCount = list.filter((item) => classifyFindingAction(item).label === 'Recheck').length;
  const expectedCount = list.filter((item) => classifyFindingAction(item).label === 'Expected').length;
  const count = list.length;
  if (actionCount) return `${count} action-needed item${count === 1 ? '' : 's'}`;
  if (recheckCount) return `${count} recheck item${count === 1 ? '' : 's'}`;
  if (expectedCount) return `${count} expected backend item${count === 1 ? '' : 's'}`;
  return `${count} ${fallback}${count === 1 ? '' : 's'}`;
}

export function deriveSecurityPostureComparison(securityData) {
  const history = Array.isArray(securityData?.history) ? securityData.history : [];
  const latest = history[0] || securityData?.last_run || null;
  const previous = history.find((item) => item?.run_id && item.run_id !== latest?.run_id) || null;
  const delta = securityData?.finding_delta && typeof securityData.finding_delta === 'object' ? securityData.finding_delta : {};
  const newItems = Array.isArray(delta.new) ? delta.new : [];
  const resolvedItems = Array.isArray(delta.resolved) ? delta.resolved : [];
  const stillItems = Array.isArray(delta.still_present) ? delta.still_present : (Array.isArray(delta.unchanged) ? delta.unchanged : []);
  const hasDelta = Boolean(delta.summary) || newItems.length || resolvedItems.length || stillItems.length;
  const hasScores = latest && previous && latest.score !== undefined && previous.score !== undefined;

  if (!hasDelta && !hasScores) {
    return {
      available: false,
      title: 'Compared with last check',
      summary: 'Run another safety check to compare posture over time.',
    };
  }

  const scoreDelta = hasScores ? Number(latest.score || 0) - Number(previous.score || 0) : 0;
  const scoreLabel = !hasScores
    ? 'Not enough history'
    : scoreDelta > 0
      ? `Up ${scoreDelta} pts`
      : scoreDelta < 0
        ? `Down ${Math.abs(scoreDelta)} pts`
        : 'No change';
  const newLabel = newItems.length ? friendlyDeltaItemLabel(newItems) : `${Number(delta.new_count || 0)} review items`;
  const resolvedLabel = resolvedItems.length ? String(resolvedItems.length) : String(Number(delta.resolved_count || 0));
  const stillPresentCount = stillItems.length || Number(delta.still_present_count || delta.unchanged_count || 0);
  const stillPresentLabel = stillItems.length ? friendlyDeltaItemLabel(stillItems) : `${stillPresentCount} review items`;
  const tone = newItems.some((item) => classifyFindingAction(item).label === 'Action needed') || scoreDelta < 0 ? 'review' : 'safe';

  return {
    available: true,
    title: 'Compared with last check',
    scoreDirection: scoreDelta > 0 ? 'up' : scoreDelta < 0 ? 'down' : 'same',
    scoreDelta: Math.abs(scoreDelta),
    scoreLabel,
    newLabel,
    resolvedLabel,
    stillPresentLabel,
    tone,
    summary: delta.summary || 'Posture comparison is based on saved Security history and finding changes.',
  };
}

export function deriveScanQuality(securityData, evidenceReceipt, executionSteps = []) {
  const lastRun = securityData?.last_run || null;
  const runStatus = String(lastRun?.status || securityData?.scan_progress?.status || securityData?.status || '').toLowerCase();
  const refs = Array.isArray(securityData?.evidence_refs) ? securityData.evidence_refs : [];
  const evidenceSaved = Boolean(evidenceReceipt?.available) || securityHasEvidence(securityData, refs);
  const stepText = (Array.isArray(executionSteps) ? executionSteps : [])
    .map((step) => `${step?.key || ''} ${step?.title || ''} ${step?.detail || ''} ${step?.state || ''}`.toLowerCase())
    .join(' ');
  const lynisCompleted = stepText.includes('lynis') && (stepText.includes('lynis completed') || stepText.includes('host readiness checks completed') || stepText.includes('done'))
    || String(lastRun?.tool_results?.lynis?.status || '').toLowerCase() === 'completed'
    || (Array.isArray(lastRun?.tools) && lastRun.tools.includes('lynis') && !runStatus.includes('failed'));
  const trivyCompleted = stepText.includes('trivy') && (stepText.includes('trivy completed') || stepText.includes('dependency') || stepText.includes('done'))
    || String(lastRun?.tool_results?.trivy?.status || '').toLowerCase() === 'completed'
    || (Array.isArray(lastRun?.tools) && lastRun.tools.includes('trivy') && !runStatus.includes('failed'));
  const sbomSaved = Boolean(lastRun?.sbom_saved)
    || refs.some((ref) => String(ref).toLowerCase().includes('sbom'))
    || evidenceReceipt?.sbomLabel === 'Saved';
  const timeoutOrPartial = Boolean(lastRun?.partial_results)
    || runStatus.includes('partial')
    || stepText.includes('timed out')
    || stepText.includes('timeout')
    || stepText.includes('review');
  const failedOrMissing = runStatus.includes('failed')
    || runStatus.includes('error')
    || stepText.includes('missing')
    || stepText.includes('failed')
    || !evidenceSaved;

  if (!lastRun) {
    return {
      status: 'not_checked',
      title: 'Not checked yet',
      detail: 'Run a safety check to measure scan quality.',
      chips: [{ label: 'Run Safety Check', tone: 'neutral' }],
    };
  }

  if (failedOrMissing) {
    return {
      status: 'failed',
      title: 'Incomplete scan',
      detail: evidenceSaved ? 'A required tool or worker step did not complete.' : 'Evidence is missing for the last terminal run.',
      chips: [
        { label: evidenceSaved ? 'Evidence saved' : 'Evidence missing', tone: evidenceSaved ? 'safe' : 'danger' },
        { label: stepText.includes('missing') ? 'Tool missing' : 'Recheck recommended', tone: 'danger' },
      ],
    };
  }

  if (timeoutOrPartial || !lynisCompleted || !trivyCompleted) {
    return {
      status: 'partial',
      title: 'Partial scan',
      detail: `${lynisCompleted ? 'Lynis completed' : 'Lynis timed out'} · ${trivyCompleted ? 'Trivy completed' : 'Trivy needs recheck'} · Evidence saved`,
      chips: [
        { label: lynisCompleted ? 'Lynis completed' : 'Lynis timed out', tone: lynisCompleted ? 'safe' : 'review' },
        { label: trivyCompleted ? 'Trivy completed' : 'Trivy needs recheck', tone: trivyCompleted ? 'safe' : 'review' },
        { label: 'Evidence saved', tone: 'safe' },
        { label: 'Recheck recommended', tone: 'review' },
      ],
    };
  }

  return {
    status: 'complete',
    title: 'Complete scan',
    detail: `Lynis completed · Trivy completed · ${sbomSaved ? 'SBOM saved' : 'Evidence saved'}`,
    chips: [
      { label: 'Lynis completed', tone: 'safe' },
      { label: 'Trivy completed', tone: 'safe' },
      { label: sbomSaved ? 'SBOM saved' : 'Evidence saved', tone: 'safe' },
      { label: 'Evidence saved', tone: 'safe' },
    ],
  };
}


function SecurityCollapseToggle({ label, collapsed, onToggle, controls }) {
  return (
    <button
      type="button"
      className="lite-security-collapse-toggle"
      aria-expanded={!collapsed}
      aria-controls={controls}
      onClick={onToggle}
    >
      <span>{collapsed ? 'Show' : 'Collapse'}</span>
      <span aria-hidden="true">{collapsed ? '+' : '−'}</span>
      <span className="sr-only"> {label}</span>
    </button>
  );
}

function SecurityEvidenceReceiptSummary({ receipt, onOpen, collapsed = false, onToggle }) {
  const bodyId = 'lite-security-latest-evidence-body';
  return (
    <GlassCard className={`lite-security-card lite-security-receipt-summary-card lite-security-receipt-${receipt.status} ${collapsed ? 'lite-security-card-collapsed' : ''}`}>
      <div className="lite-security-card-head lite-security-card-head-collapsible">
        <div className="lite-security-icon"><FileCheck className="h-5 w-5" /></div>
        <span className="lite-security-soft-badge">{receipt.title}</span>
        <SecurityCollapseToggle label="Latest evidence" collapsed={collapsed} onToggle={onToggle} controls={bodyId} />
      </div>
      <div id={bodyId} className="lite-security-collapsible-body" hidden={collapsed}>
        <h2>Latest evidence</h2>
        <p>{receipt.summary}</p>
        <div className="lite-security-receipt-summary-grid" aria-label="Latest evidence receipt summary">
          <div><span>Run ID</span><strong>{receipt.available ? receipt.shortRunId : receipt.runLabel}</strong></div>
          <div><span>Tools</span><strong>{receipt.available ? receipt.toolsLabel : 'Not recorded'}</strong></div>
          <div><span>Files</span><strong>{receipt.fileCountLabel}</strong></div>
          <div><span>SBOM</span><strong>{receipt.sbomLabel}</strong></div>
          <div aria-label="Secrets: Hidden"><span>Secrets</span><strong>Secrets: {receipt.secretsLabel}</strong></div>
        </div>
        <LiteButton tone="secondary" onClick={onOpen}>{receipt.available ? 'View Evidence Receipt' : 'Run Safety Check first'}</LiteButton>
      </div>
    </GlassCard>
  );
}

function SecurityLastKnownGoodCard({ marker, collapsed = false, onToggle }) {
  const bodyId = 'lite-security-last-known-good-body';
  return (
    <GlassCard className={`lite-security-card lite-security-known-good-card ${collapsed ? 'lite-security-card-collapsed' : ''}`}>
      <div className="lite-security-card-head lite-security-card-head-collapsible">
        <div className="lite-security-icon"><ShieldCheck className="h-5 w-5" /></div>
        <span className="lite-security-soft-badge">Last known good</span>
        <SecurityCollapseToggle label="Last known good" collapsed={collapsed} onToggle={onToggle} controls={bodyId} />
      </div>
      <div id={bodyId} className="lite-security-collapsible-body" hidden={collapsed}>
        <h2>{marker.completedAtLabel}</h2>
        <p>{marker.available ? marker.summary : 'Run a successful safety check to establish a baseline.'}</p>
        {marker.currentPartialNote ? <div className="lite-security-quality-note lite-security-quality-review">{marker.currentPartialNote}</div> : null}
        {marker.historicalWarning ? <div className="lite-security-quality-note lite-security-quality-danger">{marker.historicalWarning}</div> : null}
      </div>
    </GlassCard>
  );
}

function SecurityPostureComparisonCard({ comparison, collapsed = false, onToggle }) {
  const bodyId = 'lite-security-posture-comparison-body';
  return (
    <GlassCard className={`lite-security-card lite-security-comparison-card lite-security-comparison-${comparison.tone || 'neutral'} ${collapsed ? 'lite-security-card-collapsed' : ''}`}>
      <div className="lite-security-card-head lite-security-card-head-collapsible">
        <div className="lite-security-icon"><RefreshCw className="h-5 w-5" /></div>
        <span className="lite-security-soft-badge">Compared with last check</span>
        <SecurityCollapseToggle label="Compared with last check" collapsed={collapsed} onToggle={onToggle} controls={bodyId} />
      </div>
      <div id={bodyId} className="lite-security-collapsible-body" hidden={collapsed}>
        <h2>{comparison.available ? 'Posture comparison' : 'Compared with last check'}</h2>
        <p>{comparison.summary}</p>
        {comparison.available ? (
          <div className="lite-security-comparison-grid" aria-label="Security posture comparison">
            <div><span>Score:</span><strong>{comparison.scoreLabel}</strong></div>
            <div><span>New</span><strong>{comparison.newLabel}</strong></div>
            <div><span>Resolved</span><strong>{comparison.resolvedLabel}</strong></div>
            <div><span>Still present</span><strong>{comparison.stillPresentLabel}</strong></div>
          </div>
        ) : null}
      </div>
    </GlassCard>
  );
}

function SecurityScanQualityCard({ quality, collapsed = false, onToggle }) {
  const bodyId = 'lite-security-scan-quality-body';
  return (
    <GlassCard className={`lite-security-card lite-security-scan-quality-card lite-security-scan-quality-${quality.status} ${collapsed ? 'lite-security-card-collapsed' : ''}`}>
      <div className="lite-security-card-head lite-security-card-head-collapsible">
        <div className="lite-security-icon"><Activity className="h-5 w-5" /></div>
        <span className="lite-security-soft-badge">Scan quality</span>
        <SecurityCollapseToggle label="Scan quality" collapsed={collapsed} onToggle={onToggle} controls={bodyId} />
      </div>
      <div id={bodyId} className="lite-security-collapsible-body" hidden={collapsed}>
        <h2>{quality.title}</h2>
        <p>{quality.detail}</p>
        <div className="lite-security-quality-chips" aria-label="Scan quality reasons">
          {quality.chips.map((chip) => (
            <span key={chip.label} className={`lite-security-quality-chip lite-security-quality-${chip.tone || 'neutral'}`}>{chip.label}</span>
          ))}
        </div>
      </div>
    </GlassCard>
  );
}


export const SECURITY_POLLING_POLICY_PHASE5 = 'SECURITY_POLLING_POLICY_PHASE5';

const SECURITY_PROGRESSIVE_DETAILS_PATCH_D_GUARDS = [
  'SECURITY_PROGRESSIVE_DETAILS_PATCH_D',
  'securityDetailNeedsHeavyModel',
  'details panels hydrate only after user opens them',
  'data-security-progressive-details-hydrated',
  'lite-security-execution-${securityExecutionStateTone(step.state)}',
];
void SECURITY_PROGRESSIVE_DETAILS_PATCH_D_GUARDS;

const SECURITY_PROGRESSIVE_DETAIL_TYPES = new Set(['changes', 'attention', 'coverage', 'checkPath', 'evidence', 'history', 'technical_details']);

function securityDetailNeedsHeavyModel(type, group) {
  const detailType = String(type || '').trim();
  if (!SECURITY_PROGRESSIVE_DETAIL_TYPES.has(detailType)) return false;
  if (!group) return true;
  if (group === 'coverage') return detailType === 'coverage';
  if (group === 'timeline') return detailType === 'checkPath' || detailType === 'technical_details';
  if (group === 'evidence') return detailType === 'evidence' || detailType === 'technical_details';
  if (group === 'history') return detailType === 'history';
  if (group === 'findings') return detailType === 'changes' || detailType === 'attention';
  return true;
}

export function hasLiveSecurityOperation(payload) {
  if (!payload || typeof payload !== 'object') return false;
  const scanProgress = payload.scan_progress || payload.progress || {};
  const lastRun = payload.last_run || payload.current_run || payload.latest_run || {};
  const operation = payload.current_operation || payload.latest_operation || payload.operation || {};
  const statuses = [
    payload.status,
    payload.state,
    payload.phase,
    scanProgress.status,
    scanProgress.state,
    scanProgress.phase,
    lastRun.status,
    lastRun.state,
    lastRun.phase,
    operation.status,
    operation.state,
    operation.phase,
  ];

  if (statuses.some(isLiteLiveStatus)) return true;
  if (scanProgress.running === true || scanProgress.operation_running === true || scanProgress.in_progress === true) return true;
  if (hasLiteLiveOperation(payload.execution_timeline || lastRun.execution_timeline || operation.timeline)) return true;
  return false;
}

export default function SecurityScreen() {
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [activeSecurityDetails, setActiveSecurityDetails] = useState(null);
  const [securityManageOpen, setSecurityManageOpen] = useState(false);
  const [securityManageSection, setSecurityManageSection] = useState('overview');
  const queryClient = useQueryClient();
  const [selectedScanProfile, setSelectedScanProfile] = useState(null);
  const securityPollingProfile = normalizeSecurityProfileId(selectedScanProfile || result?.scan_profile || 'quick');
  const securityPollingPolicy = useCallback((payload) => (
    selectSecurityPollingPolicyView(payload || {}, securityPollingProfile, result)
  ), [result, securityPollingProfile]);
  const securityPollingIsLive = useCallback((payload) => {
    const policy = securityPollingPolicy(payload);
    return Boolean(busy) || policy.live || isLiteSecurityViewLive(payload) || hasLiveSecurityOperation(result);
  }, [busy, result, securityPollingPolicy]);
  const shouldLoadSecurityDetails = securityManageOpen || Boolean(activeSecurityDetails);
  const {
    data: securitySummaryData,
    loading,
    error,
    refresh,
    refreshing: summaryRefreshing,
    backendReachable,
    savedStateOnly,
    cacheStatus,
  } = useLiteResource(liteApi.securitySummary || liteApi.security, [], {
    pollingMode: 'slow',
    isLive: securityPollingIsLive,
    staleTime: 120_000,
    refetchOnWindowFocus: (query) => securityPollingIsLive(query?.state?.data),
    refetchOnMount: (query) => {
      const current = query?.state?.data;
      if (!current) return true;
      if (current?.__liteSnapshot) return true;
      return securityPollingIsLive(current);
    },
    placeholderData: (previousData) => previousData,
    select: selectSecurityScreenView,
    snapshotSelect: selectSecurityScreenView,
  });
  const {
    data: securityDetailsData,
    refreshing: detailsRefreshing,
    refresh: refreshSecurityDetails,
  } = useLiteResource(liteApi.securityDetails || liteApi.security, [], {
    enabled: shouldLoadSecurityDetails,
    pollingMode: 'relaxed',
    isLive: securityPollingIsLive,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    refetchOnMount: (query) => {
      if (!shouldLoadSecurityDetails) return false;
      const current = query?.state?.data;
      if (!current) return true;
      return securityPollingIsLive(current);
    },
    placeholderData: (previousData) => previousData,
    select: selectSecurityScreenView,
    snapshotSelect: selectSecurityScreenView,
  });
  const data = securityDetailsData || securitySummaryData;
  const refreshing = summaryRefreshing || (shouldLoadSecurityDetails && detailsRefreshing);

  useEffect(() => subscribeLiteSecurityScanCompleted((event = {}) => {
    if (event?.type && event.type !== 'security:scan-completed') return;
    const profile = normalizeSecurityProfileId(event.profile || 'quick');
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.security() });
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityProfile(profile) });
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.securityHistory() });
  }), [queryClient]);
  const [evidence, setEvidence] = useState(null);
  const [evidenceError, setEvidenceError] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [receiptCopied, setReceiptCopied] = useState(false);
  const [coverageExpanded, setCoverageExpanded] = useState(false);
  const [collapsedSecurityCards, setCollapsedSecurityCards] = useState({
    executionTimeline: true,
    latestEvidence: true,
    lastKnownGood: true,
    postureComparison: true,
    scanQuality: true,
    securityHistory: true,
    moreSecurityDetails: true,
  });

  const isSecurityCardCollapsed = (key) => Boolean(collapsedSecurityCards[key]);

  const toggleSecurityCard = (key) => {
    setCollapsedSecurityCards((current) => ({
      ...current,
      [key]: !current[key],
    }));
  };
  const [progressNow, setProgressNow] = useState(() => Date.now());
  const [remediationFinding, setRemediationFinding] = useState(null);
  const [selectedFinding, setSelectedFinding] = useState(null);
  const [fullLocalConfirmOpen, setFullLocalConfirmOpen] = useState(false);
  const [appCheckConfirmOpen, setAppCheckConfirmOpen] = useState(false);
  const [appCheckTarget, setAppCheckTarget] = useState({ app_id: 'photoprism', app_label: 'PhotoPrism' });
  const findingDetailTriggerRef = useRef(null);
  const securityDetailsTriggerRef = useRef(null);
  const remediationTriggerRef = useRef(null);
  const securityMotionReduced = useSecurityReducedMotion();

  const lastRun = data?.last_run || null;
  const securityHistory = Array.isArray(data?.history) ? data.history : [];
  const latestScanProfile = normalizeSecurityProfileId(data?.scan_profile || lastRun?.scan_profile || result?.scan_profile || 'quick');
  const scanProfile = normalizeSecurityProfileId(selectedScanProfile || latestScanProfile);
  const profileRunsById = useMemo(() => buildSecurityProfileRuns({ data, lastRun, evidenceRun: evidence?.run || null, result, history: securityHistory, profileLatest: data?.profile_latest || {} }), [data, lastRun, evidence, result, securityHistory]);
  const activeProfileView = useMemo(() => (data?.security_profiles?.[scanProfile] || selectSecurityProfileView(data || {}, scanProfile)), [data, scanProfile]);
  const profileFreshness = data?.profile_freshness || {};
  const activeProfileFreshness = activeProfileView?.freshness || profileFreshness?.[scanProfile] || null;
  const activeProfileRun = activeProfileView?.latest_run || profileRunsById[scanProfile] || null;
  const activeProfileHasRun = Boolean(activeProfileRun?.run_id || activeProfileRun?.status);
  const activeProfileIsLatest = Boolean(activeProfileRun && lastRun && activeProfileRun.run_id && activeProfileRun.run_id === lastRun.run_id) || scanProfile === latestScanProfile;
  const activeProfileMeta = securityProfileMeta(scanProfile);
  const findings = Number(activeProfileView?.items_to_review ?? activeProfileView?.findings_count ?? activeProfileRun?.items_to_review ?? 0);
  const checks = Number(activeProfileRun?.checks_reviewed ?? activeProfileRun?.checks_count ?? data?.checks_reviewed ?? data?.checks_count ?? 0);
  const criticalIssues = Array.isArray(activeProfileView?.critical_issues) ? activeProfileView.critical_issues : [];
  const reviewItems = Array.isArray(activeProfileView?.findings) ? activeProfileView.findings : [];
  const evidenceRefs = profileEvidenceRefs(activeProfileRun, activeProfileView?.evidence_refs || []);
  const componentPosture = Array.isArray(data?.component_posture) ? data.component_posture : [];
  const healthyComponents = componentPosture.filter((item) => normalizeBackendState(item?.status) === 'ready').length;
  const guidance = Array.isArray(data?.guidance) && data.guidance.length ? data.guidance : [

  ];
  const evidenceFindings = Array.isArray(evidence?.findings) ? evidence.findings : [];
  const allReviewFindings = [...criticalIssues, ...reviewItems];
  const evidenceRun = evidence?.run || null;
  const toolResults = (activeProfileIsLatest ? evidenceRun?.tool_results : null) || activeProfileView?.tool_results || activeProfileRun?.tool_results || {};
  const coverageFallback = profileFallbackCoverage(scanProfile);
  const coverageSummary = activeProfileView?.coverage_summary || activeProfileRun?.coverage_summary || (activeProfileIsLatest ? data?.coverage_summary || evidence?.coverage_summary : null) || coverageFallback;
  const checkedCoverageTargets = quickCoverageList(coverageSummary.checked_targets, coverageFallback.checked_targets);
  const skippedCoverageTargets = quickCoverageList(coverageSummary.skipped_targets, coverageFallback.skipped_targets);
  const partialCoverageTargets = quickCoverageList(coverageSummary.partial_targets);
  const timedOutCoverageTargets = quickCoverageList(coverageSummary.timed_out_targets);
  const missingCoverageTargets = quickCoverageList(coverageSummary.missing_targets);
  const targetCoverageStatuses = Array.isArray(coverageSummary.target_statuses) ? coverageSummary.target_statuses : [];
  const currentEvidenceRefs = Array.from(new Set([
    ...evidenceRefs,
    ...(Array.isArray(evidence?.evidence_refs) ? evidence.evidence_refs : []),
    ...(Array.isArray(evidenceRun?.evidence_refs) ? evidenceRun.evidence_refs : []),
  ]));
  const protectedFileNames = new Set([
    ...reviewItems.map((item) => item?.file).filter(Boolean),
    ...evidenceFindings.map((item) => item?.file).filter(Boolean),
  ]);
  const protectedFileCount = protectedFileNames.size;
  const toolNames = Array.isArray(activeProfileRun?.tools) && activeProfileRun.tools.length ? activeProfileRun.tools : (scanProfile === 'app' ? ['trivy'] : ['lynis', 'trivy']);
  const sbomSaved = currentEvidenceRefs.some((ref) => String(ref).includes('sbom.cdx.json')) || Boolean(toolResults?.trivy?.sbom_saved || activeProfileRun?.sbom_saved || (activeProfileIsLatest ? data?.sbom_saved : false));
  const evidenceFileCount = currentEvidenceRefs.length;
  const postureDashboard = [
    { label: 'Tools active', value: toolNames.length, detail: toolNames.join(' + ') },
    { label: 'Protected files', value: protectedFileCount || '—', detail: protectedFileCount ? 'with sanitized findings' : 'no file findings' },
    { label: 'Evidence files', value: evidenceFileCount, detail: sbomSaved ? 'SBOM saved' : 'saved after check' },
    { label: 'Protected areas', value: healthyComponents || componentPosture.length || 0, detail: 'components watched' },
  ];
  const findingDelta = activeProfileView?.finding_delta && typeof activeProfileView.finding_delta === 'object' ? activeProfileView.finding_delta : {};
  const profileHistory = Array.isArray(activeProfileView?.history) && activeProfileView.history.length
    ? activeProfileView.history
    : securityHistory.filter((item) => normalizeSecurityProfileId(item?.scan_profile || (item?.app_id ? 'app' : 'quick')) === scanProfile);
  const latestHistory = activeProfileRun || profileHistory[0] || null;
  const previousHistory = profileHistory.find((item) => item?.run_id && item.run_id !== latestHistory?.run_id) || null;
  const scoreTrend = latestHistory && previousHistory ? Number(latestHistory.score || 0) - Number(previousHistory.score || 0) : 0;
  const scoreTrendView = securityTrendView(latestHistory, previousHistory);
  const deltaStats = [
    { key: 'new', label: 'New review', value: Number(findingDelta.new_count || 0), tone: 'warning' },
    { key: 'resolved', label: 'Resolved', value: Number(findingDelta.resolved_count || 0), tone: 'safe' },
    { key: 'unchanged', label: 'Ongoing', value: Number(findingDelta.unchanged_count || 0), tone: 'neutral' },
  ];
  const deltaPreview = [
    ...(Array.isArray(findingDelta.new) ? findingDelta.new.slice(0, 2).map((item) => ({ ...item, delta_type: 'new' })) : []),
    ...(Array.isArray(findingDelta.resolved) ? findingDelta.resolved.slice(0, 2).map((item) => ({ ...item, delta_type: 'resolved' })) : []),
    ...(Array.isArray(findingDelta.unchanged) ? findingDelta.unchanged.slice(0, 2).map((item) => ({ ...item, delta_type: 'unchanged' })) : []),
  ].slice(0, 4);
  const deltaSummary = securityDeltaSummary(findingDelta, deltaPreview);
  const timeoutDeltaCount = deltaPreview.filter(isSecurityTimeoutFinding).length;
  const displayRunStatus = String(activeProfileRun?.status || (activeProfileIsLatest ? data?.status : '') || '').toLowerCase();
  const currentRunStatus = String(lastRun?.status || result?.status || '').toLowerCase();
  const runStatus = activeProfileIsLatest ? currentRunStatus : displayRunStatus;
  const scanProgress = activeProfileIsLatest ? data?.scan_progress || result?.scan_progress || null : null;
  const scanInProgress = activeProfileIsLatest && (busy || ['queued', 'running'].includes(currentRunStatus));
  const liveProgress = liveSecurityProgress(scanProgress, runStatus, busy, progressNow);
  const scanProgressPercent = liveProgress.percent;
  const scanProgressEta = liveProgress.eta;
  const scanProgressLabel = securityProgressStage(scanProgress, runStatus);
  const scanProgressStep = Number(scanProgress?.step || (runStatus === 'queued' ? 1 : 2));
  const scanProgressStepsTotal = Number(scanProgress?.steps_total || 3);
  const executionSteps = securityExecutionTimeline({
    executionTimeline: (activeProfileIsLatest ? data?.execution_timeline || evidenceRun?.execution_timeline : null) || activeProfileRun?.execution_timeline,
    currentRunId: activeProfileRun?.run_id || (activeProfileIsLatest ? result?.run_id : null),
    runStatus,
    scanProgress,
    evidenceRun,
    toolResults,
    evidenceRefs: currentEvidenceRefs,
    sbomSaved,
  });
  const executionResolved = executionSteps.length > 0 && executionSteps.every((step) => ['done', 'review', 'failed'].includes(step.state));
  const executionActiveStep = executionSteps.find((step) => step.state === 'active') || null;
  const executionProgressUnitsAligned = executionSteps.reduce((total, step) => {
    if (['done', 'review', 'failed'].includes(step.state)) return total + 1;
    if (step.state === 'active') return total + 0.5;
    return total;
  }, 0);
  const executionProgressAligned = executionResolved
    ? 100
    : Math.max(0, Math.min(100, Math.round((executionProgressUnitsAligned / Math.max(1, executionSteps.length)) * 100)));
  const executionTimelineLive = !executionResolved && (scanInProgress || Boolean(executionActiveStep));
  const executionLiveLabelAligned = executionTimelineLive
    ? `${executionActiveStep?.title || scanProgressLabel} · ${executionProgressAligned}%`
    : activeProfileRun?.completed_at
      ? `Completed ${formatLiteTime(activeProfileRun.completed_at)}`
      : 'Ready for the next safety check';
  const securityConfidence = useMemo(() => deriveSecurityConfidence({
    lastRun: activeProfileRun,
    runStatus,
    executionSteps,
    evidenceRefs: currentEvidenceRefs,
    evidence,
    toolResults,
    sbomSaved,
    reviewItems,
  }), [lastRun, runStatus, executionSteps, currentEvidenceRefs, evidence, toolResults, sbomSaved, reviewItems]);
  const evidenceReceipt = evidence ? {
    run_id: evidenceRun?.run_id || activeProfileRun?.run_id,
    status: evidenceRun?.status || activeProfileRun?.status || data?.status || 'unknown',
    score: evidence?.score ?? activeProfileRun?.score ?? data?.score ?? 0,
    findings: evidenceFindings.length,
    completed_at: evidenceRun?.completed_at || activeProfileRun?.completed_at,
    duration_seconds: evidenceRun?.duration_seconds || (typeof latestHistory !== 'undefined' ? latestHistory?.duration_seconds : undefined),
    tools: Object.keys(toolResults).length ? Object.keys(toolResults) : toolNames,
    evidence_files: currentEvidenceRefs,
    sbom_saved: Boolean(toolResults?.trivy?.sbom_saved || sbomSaved),
    sanitized: true,
  } : null;
  const safetyStatus = activeProfileHasRun ? (activeProfileRun?.status || data?.status || (findings === 0 ? 'healthy' : 'degraded')) : 'unknown';
  const safetyState = ['queued', 'running'].includes(runStatus) ? 'checking' : normalizeBackendState(safetyStatus);
  const safetyIsReady = safetyState === 'ready' && findings === 0;
  const scoreValue = Number(activeProfileRun?.score ?? (activeProfileIsLatest ? data?.score : undefined) ?? (activeProfileHasRun && safetyIsReady ? 100 : Math.max(55, 100 - Math.max(findings, 1) * 12)));
  const safetyScore = Number.isFinite(scoreValue) ? Math.max(0, Math.min(100, Math.round(scoreValue))) : 0;
  const safetyLabel = runStatus === 'queued'
    ? 'Safety check queued'
    : runStatus === 'running'
      ? 'Safety check running'
      : backendLabel(safetyStatus, {
        ready: findings === 0 ? 'Protected' : 'Protected · review item',
        review: 'Needs review',
        danger: 'Needs attention',
        checking: 'Checking safety',
      });
  const safetyScoreSummary = !activeProfileHasRun
    ? `${activeProfileMeta.label} has not run yet.`
    : activeProfileRun?.partial_results
      ? 'Partial check completed. Available evidence was saved.'
      : (activeProfileIsLatest ? data?.summary : activeProfileRun?.summary) || 'Pocket Lab is checking the current safety state.';
  const healthBanner = deriveSecurityHealthBanner(data, null, allReviewFindings);
  const latestEvidenceReceipt = deriveLatestEvidenceReceipt(activeProfileIsLatest ? data : { ...data, last_run: activeProfileRun, evidence_refs: currentEvidenceRefs }, { evidence, evidenceRefs: currentEvidenceRefs, latestHistory, toolNames, sbomSaved });
  const scanQuality = deriveScanQuality(activeProfileIsLatest ? data : { ...data, last_run: activeProfileRun, evidence_refs: currentEvidenceRefs }, latestEvidenceReceipt, executionSteps);
  const securityFlow = useLiteSecurityCheckFlow({ security: data, backendReachable, savedStateOnly });
  const lastKnownGood = deriveLastKnownGood(activeProfileIsLatest ? data : { ...data, last_run: activeProfileRun }, allReviewFindings);
  const postureComparison = deriveSecurityPostureComparison(activeProfileIsLatest ? data : { ...data, history: profileHistory });
  const remediationContext = { data, lastRun: activeProfileRun, evidence, evidenceRefs: currentEvidenceRefs, toolResults };
  const trustSignals = [
    {
      icon: Server,
      title: 'Backend-run checks',
      summary: 'Security tools run on this device, not in your browser.',
    },
    {
      icon: EyeOff,
      title: 'Secrets stay hidden',
      summary: 'Findings are redacted before they appear in the app.',
    },
    {
      icon: FileCheck,
      title: 'Evidence saved',
      summary: evidenceRefs.length ? `${evidenceRefs.length} sanitized evidence files` : 'Evidence appears after a completed check.',
    },
  ];
  const protectedApps = Array.isArray(data?.protected_apps)
    ? data.protected_apps
    : Array.isArray(data?.app_security_profiles?.apps)
      ? data.app_security_profiles.apps
      : [];
  const lifecycleProfiles = Array.isArray(data?.app_lifecycle_profiles?.apps) ? data.app_lifecycle_profiles.apps : [];
  const lifecycleByApp = new Map(lifecycleProfiles.map((item) => [item.app_id, item]));
  const photoPrismAppCheckTarget = protectedApps.find((app) => app?.app_id === 'photoprism') || { app_id: 'photoprism', app_label: 'PhotoPrism', label: 'PhotoPrism' };


  React.useEffect(() => {
    if (!scanInProgress) return undefined;
    let cancelled = false;
    let timer = null;

    function tick() {
      if (cancelled) return;
      setProgressNow(Date.now());
      timer = window.setTimeout(tick, 1000);
    }

    tick();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [scanInProgress]);

  React.useEffect(() => {
    const panelOpen = evidence || evidenceError || evidenceLoading;
    if (!panelOpen) return undefined;
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setEvidence(null);
        setEvidenceError(null);
        setEvidenceLoading(false);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [evidence, evidenceError, evidenceLoading]);

  React.useEffect(() => {
    if (!remediationFinding) return undefined;
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        setRemediationFinding(null);
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [remediationFinding]);

  React.useEffect(() => {
    if (!selectedFinding) return undefined;
    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        closeFindingDetails();
      }
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedFinding]);

  function invalidateSecurityQuery(profile = scanProfile) {
    const normalizedProfile = normalizeSecurityProfileId(profile || 'quick');
    [
      liteQueryKeys.security(),
      liteQueryKeys.securityDetails(),
      liteQueryKeys.securityProfile(normalizedProfile),
      liteQueryKeys.securityHistory(),
    ].forEach((queryKey) => queryClient.invalidateQueries({ queryKey }));
  }

  async function scan() {
    const flowCheck = securityFlow.requestRun();
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    setBusy(true);
    setResult({ status: 'queued', scan_profile: 'quick', summary: 'Quick safety check queued.' });
    setActionError(null);
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    setReceiptCopied(false);
    try {
      const payload = await liteApi.runSecurityScan('local', { profile: 'quick', reason: 'manual quick safety check' });
      securityFlow.accepted(payload);
      setResult(payload);
      invalidateSecurityQuery('quick');
    } catch (err) {
      securityFlow.fail(err);
      setResult(null);
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function openFullLocalConfirm(event) {
    event?.stopPropagation?.();
    setFullLocalConfirmOpen(true);
  }

  function closeFullLocalConfirm() {
    setFullLocalConfirmOpen(false);
  }

  function openAppCheckConfirm(app = { app_id: 'photoprism', app_label: 'PhotoPrism' }, event) {
    event?.stopPropagation?.();
    setAppCheckTarget({
      app_id: app?.app_id || 'photoprism',
      app_label: app?.app_label || app?.label || app?.name || 'PhotoPrism',
    });
    setAppCheckConfirmOpen(true);
  }

  function closeAppCheckConfirm() {
    setAppCheckConfirmOpen(false);
  }

  async function startFullLocalCheck() {
    const flowCheck = securityFlow.requestRun();
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    setFullLocalConfirmOpen(false);
    setBusy(true);
    setResult({ status: 'queued', scan_profile: 'full', summary: 'Full Local Check queued.' });
    setActionError(null);
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    setReceiptCopied(false);
    try {
      const payload = await liteApi.runSecurityScan('local', { profile: 'full', reason: 'manual full local check' });
      securityFlow.accepted(payload);
      setResult(payload);
      invalidateSecurityQuery('full');
    } catch (err) {
      securityFlow.fail(err);
      setResult(null);
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function checkProtectedApp(app, event) {
    if (!app?.app_id) return;
    openAppCheckConfirm(app, event);
  }

  async function startAppCheck(targetApp = null) {
    const app = targetApp || appCheckTarget || { app_id: 'photoprism', app_label: 'PhotoPrism' };
    if (!app?.app_id) return;
    const flowCheck = securityFlow.requestRun();
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    setAppCheckConfirmOpen(false);
    setBusy(true);
    setResult({ status: 'queued', scan_profile: 'app', app_id: app.app_id, app_label: app.app_label || 'PhotoPrism', summary: `${app.app_label || 'PhotoPrism'} App Check queued.` });
    setActionError(null);
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    setReceiptCopied(false);
    try {
      const payload = await liteApi.checkSecurityApp(app.app_id, { reason: 'manual app safety check' });
      securityFlow.accepted(payload);
      setResult(payload);
      invalidateSecurityQuery('app');
    } catch (err) {
      securityFlow.fail(err);
      setResult(null);
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function closeEvidencePanel() {
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    setReceiptCopied(false);
    if (activeSecurityDetails === 'evidence') {
      setActiveSecurityDetails(null);
    }
  }

  async function copyEvidenceReceipt() {
    if (!evidenceReceipt) return;
    const copied = await copyTextToClipboard(JSON.stringify(evidenceReceipt, null, 2));
    if (copied) {
      setReceiptCopied(true);
      window.setTimeout(() => setReceiptCopied(false), 1800);
    }
  }

  async function showEvidence(event) {
    triggerHapticFeedback(8);
    securityDetailsTriggerRef.current = event?.currentTarget || null;
    setActiveSecurityDetails('evidence');
    if (evidence) {
      return;
    }
    const runId = activeProfileRun?.run_id || result?.run_id;
    if (!runId) {
      setEvidenceError('Run a safety check before opening evidence.');
      return;
    }
    setEvidenceError(null);
    setEvidenceLoading(true);
    try {
      setEvidence(await liteApi.securityEvidence(runId));
    } catch (err) {
      setEvidence(null);
      setEvidenceError(err.message);
    } finally {
      setEvidenceLoading(false);
    }
  }

  function openRemediation(finding, event) {
    triggerHapticFeedback(6);
    remediationTriggerRef.current = event?.currentTarget || null;
    setRemediationFinding(finding);
  }

  function closeRemediation() {
    setRemediationFinding(null);
    window.setTimeout(() => remediationTriggerRef.current?.focus?.(), 0);
  }

  function openFindingDetails(finding, event) {
    triggerHapticFeedback(6);
    findingDetailTriggerRef.current = event?.currentTarget || null;
    setSelectedFinding(finding);
  }

  function closeFindingDetails() {
    setSelectedFinding(null);
    window.setTimeout(() => findingDetailTriggerRef.current?.focus?.(), 0);
  }

  function openSecurityDetails(type, event) {
    securityDetailsTriggerRef.current = event?.currentTarget || null;
    setActiveSecurityDetails(type);
  }

  function closeSecurityDetails() {
    const closingDetails = activeSecurityDetails;
    setActiveSecurityDetails(null);
    if (closingDetails === 'evidence') {
      setEvidence(null);
      setEvidenceError(null);
      setEvidenceLoading(false);
      setReceiptCopied(false);
    }
    window.setTimeout(() => securityDetailsTriggerRef.current?.focus?.(), 0);
  }

  function openSecurityManage(event) {
    triggerHapticFeedback(6);
    securityDetailsTriggerRef.current = event?.currentTarget || null;
    setSecurityManageOpen(true);
    if (typeof refreshSecurityDetails === 'function') {
      refreshSecurityDetails().catch(() => {});
    }
  }

  function closeSecurityManage() {
    setSecurityManageOpen(false);
    window.setTimeout(() => securityDetailsTriggerRef.current?.focus?.(), 0);
  }

  function chooseSecurityManageSection(sectionId) {
    setSecurityManageSection(sectionId);
  }

  function chooseSecurityProfile(profileId) {
    const nextProfile = normalizeSecurityProfileId(profileId);
    setSelectedScanProfile(nextProfile);
    triggerHapticFeedback(4);
  }

  function cycleSecurityProfile(event) {
    event?.stopPropagation?.();
    const currentIndex = SECURITY_SCAN_PROFILE_IDS.indexOf(scanProfile);
    const nextProfile = SECURITY_SCAN_PROFILE_IDS[(currentIndex + 1) % SECURITY_SCAN_PROFILE_IDS.length] || 'quick';
    chooseSecurityProfile(nextProfile);
  }

  async function runSecurityProfile(profileId, event) {
    event?.stopPropagation?.();
    const profile = normalizeSecurityProfileId(profileId);
    chooseSecurityProfile(profile);
    if (profile === 'full') {
      await startFullLocalCheck();
      return;
    }
    if (profile === 'app') {
      setAppCheckTarget({ app_id: 'photoprism', app_label: 'PhotoPrism' });
      await startAppCheck({ app_id: 'photoprism', app_label: 'PhotoPrism' });
      return;
    }
    await scan();
  }

  function openSecurityDetailFromManage(type, event) {
    openSecurityDetails(type, event);
  }


  const savedSecurityDetails = savedStateOnly || data?.saved_snapshot || data?.offline_details?.visible;
  const offlineDetailsTitle = data?.offline_details?.title || cacheStatus?.title || 'Showing saved Security details';
  const offlineDetailsSummary = data?.offline_details?.summary || cacheStatus?.summary || 'Reconnect to run a new check or refresh live evidence. Saved details remain read-only.';

  const progressiveDetailsType = activeSecurityDetails || null;
  const progressiveDetailsHydrated = Boolean(progressiveDetailsType);
  const hydrateCoverageDetails = securityDetailNeedsHeavyModel(progressiveDetailsType, 'coverage');
  const hydrateTimelineDetails = securityDetailNeedsHeavyModel(progressiveDetailsType, 'timeline');
  const hydrateEvidenceDetails = securityDetailNeedsHeavyModel(progressiveDetailsType, 'evidence');
  const hydrateHistoryDetails = securityDetailNeedsHeavyModel(progressiveDetailsType, 'history');
  const hydrateFindingDetails = securityDetailNeedsHeavyModel(progressiveDetailsType, 'findings');

  const securityProgressiveDetailsModel = progressiveDetailsHydrated ? {
    detailsHydrated: true,
    detailsHydration: {
      type: progressiveDetailsType,
      profile: scanProfile,
      coverage: hydrateCoverageDetails,
      timeline: hydrateTimelineDetails,
      evidence: hydrateEvidenceDetails,
      history: hydrateHistoryDetails,
      findings: hydrateFindingDetails,
    },
    findingDelta: hydrateFindingDetails && activeProfileIsLatest ? findingDelta : {},
    deltaStats: hydrateFindingDetails && activeProfileIsLatest ? deltaStats : [],
    deltaPreview: hydrateFindingDetails && activeProfileIsLatest ? deltaPreview : [],
    allReviewFindings: hydrateFindingDetails && activeProfileIsLatest ? allReviewFindings : [],
    executionSteps: hydrateTimelineDetails ? executionSteps : [],
    executionLiveLabelAligned: hydrateTimelineDetails ? executionLiveLabelAligned : '',
    latestEvidenceReceipt,
    evidenceReceipt: hydrateEvidenceDetails ? evidenceReceipt : null,
    currentEvidenceRefs: hydrateEvidenceDetails ? currentEvidenceRefs : [],
    toolNames,
    sbomSaved: hydrateEvidenceDetails ? sbomSaved : false,
    evidenceFileCount: hydrateEvidenceDetails ? evidenceFileCount : 0,
    safetyScore,
    safetyLabel,
    lastRun: activeProfileRun,
    selectedScanProfile: scanProfile,
    savedStateOnly,
    savedSecurityDetails,
    offlineDetails: savedSecurityDetails ? { title: offlineDetailsTitle, summary: offlineDetailsSummary, profile: scanProfile, freshness: activeProfileFreshness } : null,
    profileFreshness,
    activeProfileFreshness,
    backendReachable,
    securityHistory: hydrateHistoryDetails ? (profileHistory.length ? profileHistory : securityHistory) : [],
    latestHistory: hydrateHistoryDetails ? latestHistory : null,
    previousHistory: hydrateHistoryDetails ? previousHistory : null,
    scoreTrendView: hydrateHistoryDetails ? scoreTrendView : null,
    scanProgressLabel,
    scanProfile,
    coverageSummary: hydrateCoverageDetails ? coverageSummary : {},
    checkedCoverageTargets: hydrateCoverageDetails ? checkedCoverageTargets : [],
    skippedCoverageTargets: hydrateCoverageDetails ? skippedCoverageTargets : [],
    partialCoverageTargets: hydrateCoverageDetails ? partialCoverageTargets : [],
    timedOutCoverageTargets: hydrateCoverageDetails ? timedOutCoverageTargets : [],
    missingCoverageTargets: hydrateCoverageDetails ? missingCoverageTargets : [],
    targetCoverageStatuses: hydrateCoverageDetails ? targetCoverageStatuses : [],
  } : {
    detailsHydrated: false,
    detailsHydration: { type: null, profile: scanProfile },
    lastRun: activeProfileRun,
    selectedScanProfile: scanProfile,
    scanProfile,
    safetyScore,
    safetyLabel,
    savedStateOnly,
    savedSecurityDetails,
    offlineDetails: savedSecurityDetails ? { title: offlineDetailsTitle, summary: offlineDetailsSummary, profile: scanProfile, freshness: activeProfileFreshness } : null,
    profileFreshness,
    activeProfileFreshness,
    backendReachable,
    latestEvidenceReceipt,
    toolNames,
    scanProgressLabel,
  };

  const activeSecurityDetailsMeta = securityDetailShellMeta(activeSecurityDetails);
  const activeManageSection = SECURITY_MANAGE_SECTIONS.some((section) => section.id === securityManageSection)
    ? securityManageSection
    : 'overview';
  const activeManageSectionMeta = SECURITY_MANAGE_SECTIONS.find((section) => section.id === activeManageSection) || SECURITY_MANAGE_SECTIONS[0];
  const lastCheckedLabel = activeProfileRun?.completed_at
    ? `Last checked ${formatLiteTime(activeProfileRun.completed_at)}`
    : activeProfileFreshness?.has_run
      ? activeProfileFreshness.label
      : savedStateOnly
        ? 'Showing saved state'
        : 'Run Safety Check to begin';
  const evidenceSaved = Boolean(activeProfileHasRun && (latestEvidenceReceipt || evidenceReceipt || currentEvidenceRefs.length || evidenceFileCount));
  const evidenceStatusLabel = evidenceSaved ? 'Evidence saved' : 'Evidence pending';
  const safetyCenterSummary = !activeProfileHasRun && !scanInProgress
    ? `${activeProfileMeta.label} not run yet`
    : scanInProgress
      ? scanProgressLabel
    : savedStateOnly
      ? 'Saved state only'
      : backendReachable === false
        ? 'Pocket Lab is not reachable'
        : safetyIsReady
          ? 'No urgent safety issues'
          : findings
            ? 'Needs attention'
            : safetyLabel;
  const toolChipContext = { runStatus, tools: toolNames, executionSteps, profile: scanProfile };
  const safetyCenterChips = scanProfile === 'app'
    ? [
      { key: 'route', label: activeProfileHasRun ? 'Route checked' : 'Route pending', tone: activeProfileHasRun ? 'ready' : 'checking' },
      securityToolChip('trivy', 'Trivy', toolResults?.trivy, toolChipContext),
      { key: 'media', label: 'Photos skipped', tone: 'ready' },
      { key: 'critical', label: criticalIssues.length ? `${criticalIssues.length} critical` : 'No critical issues', tone: criticalIssues.length ? 'danger' : 'ready' },
    ]
    : [
      securityToolChip('lynis', 'Lynis', toolResults?.lynis, toolChipContext),
      securityToolChip('trivy', 'Trivy', toolResults?.trivy, toolChipContext),
      { key: 'secrets', label: 'Secrets hidden', tone: 'ready' },
      { key: 'critical', label: criticalIssues.length ? `${criticalIssues.length} critical` : 'No critical issues', tone: criticalIssues.length ? 'danger' : 'ready' },
    ];
  const manageOverviewStats = [
    { label: 'Profile', value: activeProfileMeta.label },
    { label: 'Safety score', value: safetyScore },
    { label: 'Status', value: safetyCenterSummary },
    { label: 'Last checked', value: activeProfileRun?.completed_at ? formatLiteTime(activeProfileRun.completed_at) : activeProfileFreshness?.label || 'No saved check yet' },
    { label: 'Evidence', value: evidenceStatusLabel },
  ];
  const historyTrendLabel = scoreTrendView?.detail || scoreTrendView?.label || (scoreTrend > 0 ? 'Improving' : scoreTrend < 0 ? 'Needs review' : 'Stable');
  const safetyShellSpring = useSpring({
    from: { opacity: 0, y: 10 },
    to: { opacity: 1, y: 0 },
    immediate: securityMotionReduced,
    config: SECURITY_SPRING_CONFIG.calm,
  });
  const safetyCardSpring = useSpring({
    to: {
      scale: scanInProgress ? 1.006 : 1,
      boxShadow: scanInProgress
        ? '0 24px 70px rgba(14, 165, 233, 0.17), 0 12px 32px rgba(15, 23, 42, 0.08)'
        : '0 18px 54px rgba(15, 23, 42, 0.09), 0 1px 0 rgba(255, 255, 255, 0.82) inset',
    },
    immediate: securityMotionReduced,
    config: SECURITY_SPRING_CONFIG.micro,
  });
  const manageSectionSpring = useSpring({
    from: { opacity: 0, y: 8, scale: 0.992 },
    to: { opacity: 1, y: 0, scale: 1 },
    reset: true,
    immediate: securityMotionReduced,
    config: SECURITY_SPRING_CONFIG.section,
  });
  const scoreSpring = useSpring({
    number: safetyScore,
    immediate: securityMotionReduced,
    config: SECURITY_SPRING_CONFIG.calm,
  });
  const manageTabsSpring = useSpring({
    to: {
      opacity: securityManageOpen ? 1 : 0,
      y: securityManageOpen ? 0 : -4,
    },
    immediate: securityMotionReduced,
    config: SECURITY_SPRING_CONFIG.micro,
  });
  const liveProgressSpring = useSpring({
    to: {
      opacity: scanInProgress ? 1 : 0,
      y: scanInProgress ? 0 : 5,
      scale: scanInProgress ? 1 : 0.994,
    },
    immediate: securityMotionReduced,
    config: SECURITY_SPRING_CONFIG.micro,
  });
  const manageScrollSpring = useSpring({
    to: {
      opacity: securityManageOpen ? 1 : 0,
      y: securityManageOpen ? 0 : 6,
    },
    immediate: securityMotionReduced,
    config: SECURITY_SPRING_CONFIG.section,
  });
  const scoreRingStyle = {
    '--score': scoreSpring.number.to((value) => `${Math.max(0, Math.min(100, Math.round(value)))}%`),
  };


  return (
    <>
      <PageHeader
        eyebrow="Safety Center"
        title="Security"
        description="A calm safety overview. Pick Quick, Full, or App Scan, then review the selected profile details."
      />

      <animated.section className="lite-security-phase5-shell lite-security-phase4-motion" style={safetyShellSpring} aria-label="Safety Center" data-security-phase5-summary-first="true" data-security-phase4-motion="shell" data-security-react-spring="summary-shell">
        <GlassCard as={animated.section} style={safetyCardSpring} className={`lite-security-safety-center-card lite-security-phase1-hero lite-security-phase1-hero-${safetyState} lite-security-phase4-score-settle`} data-security-phase4-motion="score-settle" data-security-react-spring="safety-card">
          <div className="lite-security-safety-center-copy">
            <div className="lite-home-pill">
              <span className="lite-ready-dot" />
              {safetyCenterSummary}
            </div>
            <h2>Safety Center</h2>
            <button type="button" className="lite-security-quick-profile-chip lite-security-profile-rollup-trigger" onClick={cycleSecurityProfile} aria-label="Switch Security profile summary" data-security-profile-view="profile-linked">{activeProfileMeta.label}</button>
            <p>{scanInProgress ? 'Pocket Lab is checking safety through FastAPI and the backend worker.' : `${activeProfileMeta.summary} ${safetyScoreSummary}`}</p>
            <div className="lite-security-safety-center-meta" aria-label="Safety state">
              <span>{lastCheckedLabel}</span>
              <span>{evidenceStatusLabel}</span>
              <button type="button" className="lite-security-profile-rollup-link" onClick={cycleSecurityProfile} aria-label="Switch visible Security profile">Profile: {activeProfileMeta.chip}</button>
              {savedSecurityDetails ? <span>{activeProfileFreshness?.label || 'Showing saved state'}</span> : null}
              {refreshing && !scanInProgress ? <span>Refreshing quietly</span> : null}
              {backendReachable === false ? <span>Pocket Lab is not reachable</span> : null}
            </div>
            <div className="lite-security-safety-center-chips" aria-label="Safety chips">
              {safetyCenterChips.map((chip) => (
                <span key={chip.key} className={`lite-security-safety-chip lite-security-safety-chip-${chip.tone}`}>{chip.label}</span>
              ))}
            </div>
            <div className="lite-security-safety-center-actions">
              <div className="lite-security-profile-action-grid lite-security-phase4-safety-action" data-security-phase4-motion="check-button" data-security-profile-run-actions="quick-full-app" aria-label="Run Safety Check profiles">
                {SECURITY_SCAN_PROFILES.map((profile) => (
                  <LiteButton
                    key={profile.id}
                    tone={profile.id === scanProfile ? 'primary' : 'secondary'}
                    onClick={(event) => runSecurityProfile(profile.id, event)}
                    disabled={scanInProgress || securityFlow.writeBlocked}
                    haptic
                    ariaLabel={scanInProgress ? `${profile.label} cannot start while a safety check is running` : securityFlow.writeBlocked ? `Reconnect to run ${profile.label}` : `Run ${profile.label}`}
                  >
                    {scanInProgress && profile.id === latestScanProfile ? profile.running : securityFlow.writeBlocked ? 'Reconnect' : profile.actionLabel}
                  </LiteButton>
                ))}
              </div>
              <LiteButton tone="secondary" onClick={openSecurityManage} ariaLabel="Manage Security details">Manage</LiteButton>
            </div>
            {securityFlow.writeBlocked ? <p className="lite-security-phase1-note">{securityFlow.blockedReason || 'Reconnect to continue.'}</p> : null}
          </div>

          <div className="lite-security-safety-center-score" aria-label="Safety score">
            <animated.div className="lite-security-score-ring lite-security-score-ring-green-fill" style={scoreRingStyle} data-security-score-fill="spring">
              <animated.span>{scoreSpring.number.to((value) => Math.round(value))}</animated.span>
            </animated.div>
            <strong>Safety score</strong>
            <span>{scanInProgress ? `${scanProgressPercent}% complete` : safetyCenterSummary}</span>
            <StatusBadge status={backendBadgeStatus(safetyStatus)}>{safetyLabel}</StatusBadge>
          </div>

          {scanInProgress ? (
            <animated.div style={liveProgressSpring} className="lite-security-safety-center-live lite-security-phase4-live-motion lite-security-premium-v2-live-progress-motion" aria-live="polite" data-security-phase4-motion="live-check" data-security-react-spring="live-progress">
              <div>
                <strong>{scanProgressLabel}</strong>
                <span>{executionActiveStep?.title || securityFlow.label}</span>
              </div>
              <div className="lite-security-progress-track lite-security-phase4-progress-shine" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={scanProgressPercent} aria-label="Safety check progress">
                <span style={{ width: `${scanProgressPercent}%` }} />
              </div>
              <p>{scanProgressPercent}% · {scanProgressEta} remaining · {activeProfileMeta.label} is running.</p>
            </animated.div>
          ) : null}
        </GlassCard>
      </animated.section>

      {loading ? <LoadingCard label="Loading safety summary..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Safety summary needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      {savedSecurityDetails ? (
        <StateSurface
          tone="degraded"
          title={offlineDetailsTitle}
          description={offlineDetailsSummary}
          className="mb-5 lite-security-patch-e-offline-details"
          data-security-patch-e-offline-details="true"
        />
      ) : null}

      <LiteSheet
        open={securityManageOpen}
        onClose={closeSecurityManage}
        eyebrow="Safety Center"
        title="Manage Security"
        description="Review deeper safety sections without crowding the main page."
        layerClassName="lite-security-manage-layer"
        className="lite-security-manage-shell lite-security-manage-panel lite-security-phase4-panel-motion"
        bodyClassName="lite-security-manage-scroll"
        headerClassName="lite-security-manage-head"
        closeClassName="lite-security-manage-close"
        gripClassName="lite-security-manage-grip"
        variant="security"
        motion="safe-grip"
        surfaceProps={{ 'data-security-phase5-manage-shell': 'true', 'data-security-safe-motion': 'gesture-spring', 'data-security-react-spring': 'manage-shell' }}
      >
        <animated.div style={manageScrollSpring} className="lite-security-manage-scroll-frame" data-security-react-spring="manage-scroll-frame">
        <animated.div style={manageTabsSpring} className="lite-security-manage-tabs lite-security-premium-v2-manage-tabs-motion" role="tablist" aria-label="Security Manage sections" data-security-react-spring="manage-tabs">
          {SECURITY_MANAGE_SECTIONS.map((section) => (
            <button
              key={section.id}
              type="button"
              role="tab"
              aria-selected={activeManageSection === section.id}
              aria-label={`Open ${section.label} in Security Manage`}
              className={`lite-security-manage-tab-button ${activeManageSection === section.id ? 'is-active' : ''}`.trim()}
              onClick={() => chooseSecurityManageSection(section.id)}
            >
              {section.label}
            </button>
          ))}
        </animated.div>

        <animated.section style={manageSectionSpring} className={`lite-security-manage-section lite-security-manage-section-${activeManageSection}`} aria-label={activeManageSectionMeta.label} data-security-manage-section={activeManageSection} data-security-react-spring="manage-section">
          <div className="lite-security-manage-section-head">
            <span>{activeManageSectionMeta.label}</span>
            <h3>{activeManageSectionMeta.label}</h3>
            <p>{SECURITY_MANAGE_SECTION_DESCRIPTIONS[activeManageSection]}</p>
          </div>

          {activeManageSection === 'overview' ? (
            <div className="lite-security-manage-overview">
              <div className="lite-security-manage-score-row">
                <animated.div className="lite-security-score-ring lite-security-score-ring-green-fill" style={scoreRingStyle} data-security-score-fill="spring"><animated.span>{scoreSpring.number.to((value) => Math.round(value))}</animated.span></animated.div>
                <div>
                  <strong>{safetyCenterSummary}</strong>
                  <p>{savedStateOnly ? 'Showing saved state. Fresh details will refresh when Pocket Lab is reachable.' : lastCheckedLabel}</p>
                </div>
              </div>
              <div className="lite-security-profile-switcher" role="tablist" aria-label="Security scan profiles" data-security-profile-view="profile-linked" data-security-patch-e-profile-freshness="true">
                {SECURITY_SCAN_PROFILES.map((profile) => (
                  <button
                    key={profile.id}
                    type="button"
                    role="tab"
                    aria-selected={scanProfile === profile.id}
                    className={`lite-security-profile-switcher-button ${scanProfile === profile.id ? 'is-active' : ''}`.trim()}
                    onClick={() => chooseSecurityProfile(profile.id)}
                  >
                    <strong>{profile.label}</strong>
                    <span>{data?.security_profiles?.[profile.id]?.freshness?.label || profileFreshness?.[profile.id]?.label || profileRunTimestampLabel(data?.security_profiles?.[profile.id]?.latest_run || profileRunsById[profile.id])}</span>
                  </button>
                ))}
              </div>
              <div className="lite-security-manage-stat-grid">
                {manageOverviewStats.map((item) => (
                  <div key={item.label} className="lite-security-manage-stat">
                    <span>{item.label}</span>
                    <strong>{item.value}</strong>
                  </div>
                ))}
              </div>
              <div className="lite-security-safety-center-chips">
                {safetyCenterChips.map((chip) => <span key={chip.key} className={`lite-security-safety-chip lite-security-safety-chip-${chip.tone}`}>{chip.label}</span>)}
              </div>
              <div className="lite-security-profile-run-cards" aria-label="Run Security scan profile">
                {SECURITY_SCAN_PROFILES.map((profile) => (
                  <div key={profile.id} className={`lite-security-profile-run-card ${scanProfile === profile.id ? 'is-active' : ''}`.trim()}>
                    <div>
                      <strong>{profile.label}</strong>
                      <p>{data?.security_profiles?.[profile.id]?.summary || profile.summary}</p>
                      <small>{profile.id === 'quick' ? 'Skips photos, backups, and large caches.' : profile.id === 'full' ? 'Best while charging. Still skips photos, backups, and large caches.' : 'Checks PhotoPrism route, files, settings, backup metadata, and action state. Skips photos and media.'}</small>
                    </div>
                    <LiteButton tone={scanProfile === profile.id ? 'primary' : 'secondary'} onClick={(event) => runSecurityProfile(profile.id, event)} disabled={scanInProgress || securityFlow.writeBlocked} ariaLabel={`Run ${profile.label}`}>{profile.actionLabel}</LiteButton>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {activeManageSection === 'changes' ? (
            <div className="lite-security-manage-card-list">
              <div className="lite-security-delta-stats" aria-label="Finding changes">
                {deltaStats.map((item) => (
                  <div key={item.key} className={`lite-security-delta-stat lite-security-delta-${item.tone} lite-security-phase4-delta-count`}>
                    <strong>{item.value}</strong>
                    <span>{item.label}</span>
                  </div>
                ))}
              </div>
              <div className="lite-security-manage-row">
                <div>
                  <strong>{deltaSummary || 'No recent changes need attention'}</strong>
                  <p>{deltaPreview.length ? `${deltaPreview.length} safe change summaries available.` : 'New, resolved, and still-present changes appear after completed checks.'}</p>
                </div>
                <button type="button" className="lite-security-coverage-toggle" aria-label="Open Security changes details" onClick={(event) => openSecurityDetailFromManage('changes', event)}>Open changes</button>
              </div>
            </div>
          ) : null}

          {activeManageSection === 'issues' ? (
            <div className="lite-security-manage-card-list">
              <div className="lite-security-manage-row">
                <div>
                  <strong>{findings ? 'Needs attention' : 'No urgent issues'}</strong>
                  <p>{findings ? `${findings} item${findings === 1 ? '' : 's'} to review from the latest safety check.` : 'Pocket Lab will keep evidence ready after each check.'}</p>
                </div>
                {allReviewFindings.length > 3 ? <button type="button" className="lite-security-coverage-toggle" aria-label="Open all Security review items" onClick={(event) => openSecurityDetailFromManage('attention', event)}>Open all review items</button> : null}
              </div>
              {allReviewFindings.length ? allReviewFindings.slice(0, 5).map((item) => {
                const action = classifyFindingAction(item, remediationContext);
                return (
                  <div key={item.id || item.summary} className="lite-security-manage-row lite-security-phase1-finding-row">
                    <span className={`lite-security-severity lite-security-severity-${securityFindingTone(item.severity)}`}>{item.severity || 'review'}</span>
                    <div>
                      <strong>{securityFindingLabel(item)}</strong>
                      <p>{item.recommendation || item.summary || 'Review this item and keep the workspace protected.'}</p>
                      <SecurityActionIndicator action={action} />
                    </div>
                    <div className="lite-security-manage-row-actions">
                      <button type="button" className="lite-finding-detail-trigger" aria-label={`View details for ${securityFindingLabel(item)}`} onClick={(event) => openFindingDetails(item, event)}>View details</button>
                      <button type="button" className="lite-security-remediation-button" aria-label={`Show recommended next step for ${securityFindingLabel(item)}`} onClick={(event) => openRemediation(item, event)}>What should I do?</button>
                    </div>
                  </div>
                );
              }) : (
                <div className="lite-security-safe-panel"><Lock className="h-4 w-4" /><span>No urgent issues were found in the latest summary.</span></div>
              )}
            </div>
          ) : null}

          {activeManageSection === 'coverage' ? (
            <div className="lite-security-manage-card-list lite-security-quick-coverage-card" data-security-progressive-details-summary-first="coverage">
              <div className="lite-security-manage-row">
                <div>
                  <strong>{scanProfile === 'app' ? `${coverageSummary.app_label || 'PhotoPrism'} App Check coverage` : scanProfile === 'full' ? 'Full Local Check coverage' : 'Quick safety check coverage'}</strong>
                  <p>{scanProfile === 'app' ? 'Compact coverage summary is shown here. Full App Check coverage loads only after you open details.' : scanProfile === 'full' ? 'Compact coverage summary is shown here. Full Local Check rows load only after you open details.' : 'Compact coverage summary is shown here. Quick Safety Check rows load only after you open details.'}</p>
                </div>
                <span className="lite-security-quick-profile-chip">Profile: {activeProfileMeta.chip}</span>
              </div>
              <div className="lite-security-manage-stat-grid" aria-label="Security coverage summary counts">
                <div className="lite-security-manage-stat"><span>Checked</span><strong>{checkedCoverageTargets.length}</strong></div>
                <div className="lite-security-manage-stat"><span>Partial</span><strong>{partialCoverageTargets.length}</strong></div>
                <div className="lite-security-manage-stat"><span>Missing</span><strong>{missingCoverageTargets.length}</strong></div>
                <div className="lite-security-manage-stat"><span>Skipped</span><strong>{skippedCoverageTargets.length}</strong></div>
              </div>
              <div className="lite-security-manage-row">
                <div>
                  <strong>Progressive details</strong>
                  <p>Target rows, skipped groups, and optional missing targets mount only inside the focused details panel.</p>
                </div>
                <button type="button" className="lite-security-coverage-toggle" aria-label="Open Security coverage details" onClick={(event) => openSecurityDetailFromManage('coverage', event)}>Open coverage</button>
              </div>
            </div>
          ) : null}

          {activeManageSection === 'check_path' ? (
            <div className="lite-security-manage-card-list" data-security-progressive-details-summary-first="check-path">
              <div className="lite-security-manage-row">
                <div>
                  <strong>{executionTimelineLive ? 'Checking safety' : 'Last check path'}</strong>
                  <p>{executionLiveLabelAligned}</p>
                </div>
                <button type="button" className="lite-security-coverage-toggle" aria-label="Show Security check path details" onClick={(event) => openSecurityDetailFromManage('checkPath', event)}>Show check path</button>
              </div>
              <div className="lite-security-manage-stat-grid" aria-label="Security check path summary">
                <div className="lite-security-manage-stat"><span>Steps</span><strong>{executionSteps.length}</strong></div>
                <div className="lite-security-manage-stat"><span>Owner</span><strong>Backend</strong></div>
                <div className="lite-security-manage-stat"><span>Tools</span><strong>{toolNames.join(' + ')}</strong></div>
                <div className="lite-security-manage-stat"><span>Evidence</span><strong>{evidenceStatusLabel}</strong></div>
              </div>
              <div className="lite-security-safe-panel"><FileCheck className="h-4 w-4" /><span>Timeline rows load inside details so the main Security view stays snappy.</span></div>
            </div>
          ) : null}

          {activeManageSection === 'evidence' ? (
            <div className="lite-security-manage-card-list">
              <div className="lite-security-manage-row lite-security-phase4-evidence-stamp" data-security-phase4-motion="evidence-stamp">
                <div>
                  <strong>{latestEvidenceReceipt?.title || 'Evidence summary'}</strong>
                  <p>{latestEvidenceReceipt?.summary || 'Evidence appears after a completed safety check.'}</p>
                </div>
                <LiteButton tone="secondary" onClick={showEvidence} ariaLabel="View safe Security evidence summary">{evidenceLoading ? 'Opening evidence…' : 'View safe summary'}</LiteButton>
              </div>
              <div className="lite-security-phase1-meta-grid">
                <span>{evidenceStatusLabel}</span>
                <span>Secrets hidden</span>
                <span>Raw logs hidden</span>
                <span>Private paths hidden</span>
              </div>
            </div>
          ) : null}

          {activeManageSection === 'history' ? (
            <div className="lite-security-manage-card-list">
              <div className="lite-security-manage-row">
                <div>
                  <strong>Safety history</strong>
                  <p>{securityHistory.length ? `${securityHistory.length} recent check${securityHistory.length === 1 ? '' : 's'} available. ${historyTrendLabel}` : 'History will appear after more safety checks.'}</p>
                </div>
                <button type="button" className="lite-security-coverage-toggle" aria-label="Open Security history details" onClick={(event) => openSecurityDetailFromManage('history', event)}>Open history</button>
              </div>
              <div className="lite-security-manage-stat-grid">
                <div className="lite-security-manage-stat"><span>Last 7 checks</span><strong>{Math.min(securityHistory.length, 7)}</strong></div>
                <div className="lite-security-manage-stat"><span>Score trend</span><strong>{historyTrendLabel}</strong></div>
                <div className="lite-security-manage-stat"><span>Last issue</span><strong>{allReviewFindings.length ? 'Latest check' : 'None urgent'}</strong></div>
              </div>
            </div>
          ) : null}

          {activeManageSection === 'technical_details' ? (
            <div className="lite-security-manage-card-list">
              <div className="lite-security-manage-row">
                <div>
                  <strong>Technical details</strong>
                  <p>Collapsed by default. Shows only safe metadata such as backend-owned check path, tool names, snapshot state, and polling policy.</p>
                </div>
                <button type="button" className="lite-security-coverage-toggle" aria-label="Open safe Security technical details" onClick={(event) => openSecurityDetailFromManage('technical_details', event)}>Open technical details</button>
              </div>
              <div className="lite-security-phase1-meta-grid">
                <span>Backend-owned check path</span>
                <span>Tools: {toolNames.join(' + ')}</span>
                <span>{savedStateOnly ? 'Saved state' : 'Fresh state'}</span>
                <span>Polling: slow</span>
                <span>Snapshots: profile freshness + retention</span>
              </div>
            </div>
          ) : null}
        </animated.section>
        </animated.div>
      </LiteSheet>

      <LiteSheet
        open={fullLocalConfirmOpen}
        onClose={closeFullLocalConfirm}
        eyebrow="Security"
        title="Full Local Check"
        description="Checks this device more deeply while keeping heavy/private data skipped."
        layerClassName="lite-security-phase3-layer lite-security-detail-layer"
        className="lite-security-phase3-panel lite-security-full-local-confirm"
        bodyClassName="lite-security-phase3-scroll"
        headerClassName="lite-security-phase3-head"
      >
        <div className="lite-security-full-local-confirm-body">
          <p>This checks Pocket Lab, Termux, selected PROot Ubuntu areas, PhotoPrism app files, route config, service status, and backup metadata. It can take 10–30 minutes and is best while the phone is charging.</p>
          <div className="lite-security-phase1-meta-grid">
            <span>Does not scan your photo library</span>
            <span>Does not restore backups</span>
            <span>Does not change app settings</span>
            <span>Does not expose secrets</span>
            <span>Does not run anything in the browser</span>
          </div>
          <div className="lite-security-full-local-actions">
            <LiteButton tone="secondary" onClick={closeFullLocalConfirm}>Cancel</LiteButton>
            <LiteButton onClick={startFullLocalCheck} disabled={scanInProgress || securityFlow.writeBlocked}>Start Full Local Check</LiteButton>
          </div>
        </div>
      </LiteSheet>

      <LiteSheet
        open={appCheckConfirmOpen}
        onClose={closeAppCheckConfirm}
        eyebrow="Security"
        title="Check PhotoPrism"
        description="Checks PhotoPrism app safety while keeping photos and media skipped."
        layerClassName="lite-security-phase3-layer lite-security-detail-layer"
        className="lite-security-phase3-panel lite-security-app-check-confirm"
        bodyClassName="lite-security-phase3-scroll"
        headerClassName="lite-security-phase3-head"
      >
        <div className="lite-security-full-local-confirm-body">
          <p>This checks PhotoPrism route, app files, settings, backup metadata, and action state. It can take a few minutes. It skips your photo library, media folders, backup payloads, logs, and large caches.</p>
          <div className="lite-security-phase1-meta-grid">
            <span>Does not scan your photo library</span>
            <span>Does not read app secrets into the browser</span>
            <span>Does not change app settings</span>
            <span>Does not restore backups</span>
            <span>Does not run anything in the browser</span>
          </div>
          <div className="lite-security-full-local-actions">
            <LiteButton tone="secondary" onClick={closeAppCheckConfirm}>Cancel</LiteButton>
            <LiteButton onClick={startAppCheck} disabled={scanInProgress || securityFlow.writeBlocked}>Start App Check</LiteButton>
          </div>
        </div>
      </LiteSheet>

      <LiteSheet
        open={Boolean(activeSecurityDetails)}
        onClose={closeSecurityDetails}
        eyebrow={activeSecurityDetailsMeta.eyebrow}
        title={activeSecurityDetailsMeta.title}
        description={activeSecurityDetailsMeta.description}
        layerClassName="lite-security-phase3-layer lite-security-detail-layer"
        className="lite-security-phase3-panel lite-security-phase3-details-shell lite-security-phase4-panel-motion"
        bodyClassName="lite-security-phase3-scroll"
        headerClassName="lite-security-phase3-head"
        closeClassName="lite-security-phase3-close"
        gripClassName="lite-security-phase3-grip"
        variant="security"
        motion="safe-grip"
        surfaceProps={{ 'data-security-phase3-responsive-shell': 'true', 'data-security-safe-motion': 'gesture-spring', 'data-security-react-spring': 'focused-details', 'data-security-scan-details-profile-bound': scanProfile }}
      >
        <Suspense fallback={<div className="lite-security-details-loading">Loading Security details…</div>}>
          <SecurityProgressiveDetailsLazy type={activeSecurityDetails || 'evidence'} model={securityProgressiveDetailsModel} onClose={closeSecurityDetails} />
        </Suspense>
      </LiteSheet>

      <LiteSheet
        open={Boolean(selectedFinding)}
        onClose={closeFindingDetails}
        eyebrow="Finding Details"
        title={selectedFinding ? securityFindingLabel(selectedFinding) : 'Finding details'}
        description="Review one finding at a time. Technical details stay collapsed and sanitized."
        layerClassName="lite-security-phase3-layer lite-security-detail-layer"
        className="lite-security-phase3-panel lite-security-phase3-finding-shell lite-security-phase4-panel-motion"
        bodyClassName="lite-security-phase3-scroll"
        headerClassName="lite-security-phase3-head"
        closeClassName="lite-security-phase3-close"
        gripClassName="lite-security-phase3-grip"
        variant="security"
        motion="safe-grip"
        surfaceProps={{ 'data-security-phase3-responsive-shell': 'true', 'data-security-safe-motion': 'gesture-spring', 'data-security-react-spring': 'finding-details' }}
      >
        {selectedFinding ? (
          <Suspense fallback={<div className="lite-security-details-loading">Loading finding details…</div>}>
            <SecurityFindingDetailsLazy finding={selectedFinding} context={remediationContext} onClose={closeFindingDetails} />
          </Suspense>
        ) : null}
      </LiteSheet>

      {activeSecurityDetails === 'legacyEvidenceNeverMounts' && (evidence || evidenceError || evidenceLoading) ? (
        <section className="lite-security-evidence-dropdown" aria-label="Sanitized security evidence summary" aria-live="polite">
          <GlassCard className="lite-security-card lite-security-evidence-panel" role="region" aria-label="Sanitized security evidence">
            <div className="lite-security-card-head">
              <div className="lite-security-icon"><FileCheck className="h-5 w-5" /></div>
              <span className="lite-security-soft-badge">Sanitized evidence</span>
              <button type="button" className="lite-security-evidence-close" onClick={closeEvidencePanel} aria-label="Close evidence details"><X className="h-4 w-4" /></button>
            </div>
            <h2>{evidenceError ? 'Evidence not ready' : evidenceLoading ? 'Opening evidence...' : 'Evidence details'}</h2>
            {evidenceError ? <p>{evidenceError}</p> : null}
            {evidenceLoading ? <p>Pocket Lab is opening the sanitized evidence summary for the latest safety check.</p> : null}
            {evidence ? (
              <>
                <div className="lite-security-evidence-summary">
                  <div><span>Run</span><strong>{shortRunId(evidence?.run?.run_id || lastRun?.run_id)}</strong></div>
                  <div><span>Status</span><strong>{evidence?.run?.status || 'unknown'}</strong></div>
                  <div><span>Score</span><strong>{evidence?.score ?? safetyScore}</strong></div>
                  <div><span>Findings</span><strong>{evidenceFindings.length}</strong></div>
                </div>
                <div className="lite-security-evidence-tools">
                  {['lynis', 'trivy'].map((tool) => {
                    const item = toolResults?.[tool] || {};
                    return (
                      <div key={tool}>
                        <strong>{tool}</strong>
                        <span>{item.status || 'recorded'}</span>
                        <p>{tool === 'trivy' && item.sbom_saved ? 'SBOM saved and findings normalized.' : 'Output normalized before display.'}</p>
                      </div>
                    );
                  })}
                </div>
                {evidenceReceipt ? (
                  <div className="lite-security-receipt-card">
                    <div>
                      <span>Evidence receipt</span>
                      <strong>{shortRunId(evidenceReceipt.run_id)}</strong>
                      <p>Sanitized receipt for support, audit review, or your own records.</p>
                    </div>
                    <div className="lite-security-receipt-grid">
                      <div><span>Status</span><strong>{evidenceReceipt.status}</strong></div>
                      <div><span>Duration</span><strong>{formatSecurityDuration(evidenceReceipt.duration_seconds)}</strong></div>
                      <div><span>Tools</span><strong>{evidenceReceipt.tools.length}</strong></div>
                      <div><span>SBOM</span><strong>{evidenceReceipt.sbom_saved ? 'Saved' : 'Not saved'}</strong></div>
                    </div>
                    <LiteButton tone="secondary" onClick={copyEvidenceReceipt} ariaLabel="Copy Security evidence receipt summary">{receiptCopied ? 'Copied' : 'Copy Receipt'}</LiteButton>
                  </div>
                ) : null}
                <div className="lite-security-evidence-files">
                  {currentEvidenceRefs.slice(0, 6).map((ref) => <code key={ref}>{String(ref).split('/').slice(-1)[0]}</code>)}
                </div>
                <p className="lite-security-evidence-note">Sensitive values stay hidden. This panel shows only sanitized evidence metadata.</p>
              </>
            ) : null}
          </GlassCard>
        </section>
      ) : null}

      <SecurityRemediationDrawer finding={remediationFinding} context={remediationContext} onClose={closeRemediation} />

      <ResultNotice result={result} error={actionError} />
    </>
  );
}
