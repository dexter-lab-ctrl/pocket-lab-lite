import React, { Suspense, useCallback, useMemo, useRef, useState } from 'react';
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
import { isLiteSecurityViewLive, selectSecurityScreenView } from '../lib/liteViewModels.js';
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
void SECURITY_PHASE1_SOURCE_GUARDS;
void SECURITY_PHASE2_PROGRESSIVE_DETAILS_SOURCE_GUARDS;
void SECURITY_PHASE3_RESPONSIVE_SHELL_SOURCE_GUARDS;


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
};

function securityDetailShellMeta(type) {
  return SECURITY_DETAIL_SHELL_META[type] || SECURITY_DETAIL_SHELL_META.evidence;
}

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
      { label: lynisCompleted ? 'Lynis completed' : lynisState === 'review' ? 'Lynis partial' : 'Lynis pending', tone: lynisCompleted ? 'ready' : 'review' },
      { label: trivyCompleted ? 'Trivy completed' : trivyState === 'review' ? 'Trivy partial' : 'Trivy pending', tone: trivyCompleted ? 'ready' : 'review' },
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
  if (!finding) return null;
  const remediation = buildSecurityRemediation(finding, context);
  const detail = finding?.recommendation || finding?.summary || finding?.title || 'Review this item and keep Pocket Lab protected.';
  return (
    <div className="lite-security-remediation-backdrop" role="presentation" onClick={onClose}>
      <aside className="lite-security-remediation-drawer" role="dialog" aria-modal="true" aria-labelledby="lite-security-remediation-title" onClick={(event) => event.stopPropagation()}>
        <div className="lite-security-remediation-head">
          <div>
            <span className="lite-security-soft-badge">What should I do?</span>
            <h2 id="lite-security-remediation-title">{remediation.title}</h2>
          </div>
          <button type="button" className="lite-security-evidence-close" onClick={onClose} aria-label="Close remediation guidance">
            <X className="h-4 w-4" />
          </button>
        </div>
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
      </aside>
    </div>
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
  const queryClient = useQueryClient();
  const securityPollingIsLive = useCallback((payload) => (
    Boolean(busy) || isLiteSecurityViewLive(payload) || hasLiveSecurityOperation(result)
  ), [busy, result]);
  const { data, loading, error, refresh, backendReachable, savedStateOnly } = useLiteResource(liteApi.security, [], {
    pollingMode: 'slow',
    isLive: securityPollingIsLive,
    staleTime: 30_000,
    select: selectSecurityScreenView,
    snapshotSelect: selectSecurityScreenView,
  });
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
  const [activeSecurityDetails, setActiveSecurityDetails] = useState(null);
  const findingDetailTriggerRef = useRef(null);
  const securityDetailsTriggerRef = useRef(null);

  const lastRun = data?.last_run || null;
  const findings = Number(data?.items_to_review ?? data?.findings_count ?? 0);
  const checks = Number(data?.checks_reviewed ?? data?.checks_count ?? 0);
  const criticalIssues = Array.isArray(data?.critical_issues) ? data.critical_issues : [];
  const reviewItems = Array.isArray(data?.findings) ? data.findings : [];
  const evidenceRefs = Array.isArray(data?.evidence_refs) ? data.evidence_refs : [];
  const componentPosture = Array.isArray(data?.component_posture) ? data.component_posture : [];
  const healthyComponents = componentPosture.filter((item) => normalizeBackendState(item?.status) === 'ready').length;
  const guidance = Array.isArray(data?.guidance) && data.guidance.length ? data.guidance : [

  ];
  const evidenceFindings = Array.isArray(evidence?.findings) ? evidence.findings : [];
  const allReviewFindings = [...criticalIssues, ...reviewItems];
  const evidenceRun = evidence?.run || null;
  const toolResults = evidenceRun?.tool_results || lastRun?.tool_results || data?.tool_results || {};
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
  const toolNames = Array.isArray(lastRun?.tools) && lastRun.tools.length ? lastRun.tools : ['lynis', 'trivy'];
  const sbomSaved = currentEvidenceRefs.some((ref) => String(ref).includes('sbom.cdx.json')) || Boolean(toolResults?.trivy?.sbom_saved || lastRun?.sbom_saved || data?.sbom_saved);
  const evidenceFileCount = currentEvidenceRefs.length;
  const postureDashboard = [
    { label: 'Tools active', value: toolNames.length, detail: toolNames.join(' + ') },
    { label: 'Protected files', value: protectedFileCount || '—', detail: protectedFileCount ? 'with sanitized findings' : 'no file findings' },
    { label: 'Evidence files', value: evidenceFileCount, detail: sbomSaved ? 'SBOM saved' : 'saved after check' },
    { label: 'Protected areas', value: healthyComponents || componentPosture.length || 0, detail: 'components watched' },
  ];
  const securityHistory = Array.isArray(data?.history) ? data.history : [];
  const findingDelta = data?.finding_delta && typeof data.finding_delta === 'object' ? data.finding_delta : {};
  const latestHistory = securityHistory[0] || null;
  const previousHistory = securityHistory.find((item) => item?.run_id && item.run_id !== latestHistory?.run_id) || null;
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
  const runStatus = String(lastRun?.status || result?.status || '').toLowerCase();
  const scanProgress = data?.scan_progress || result?.scan_progress || null;
  const scanInProgress = busy || ['queued', 'running'].includes(runStatus);
  const liveProgress = liveSecurityProgress(scanProgress, runStatus, busy, progressNow);
  const scanProgressPercent = liveProgress.percent;
  const scanProgressEta = liveProgress.eta;
  const scanProgressLabel = securityProgressStage(scanProgress, runStatus);
  const scanProgressStep = Number(scanProgress?.step || (runStatus === 'queued' ? 1 : 2));
  const scanProgressStepsTotal = Number(scanProgress?.steps_total || 3);
  const executionSteps = securityExecutionTimeline({
    executionTimeline: data?.execution_timeline || evidenceRun?.execution_timeline || lastRun?.execution_timeline,
    currentRunId: lastRun?.run_id || result?.run_id,
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
    : lastRun?.completed_at
      ? `Completed ${formatLiteTime(lastRun.completed_at)}`
      : 'Ready for the next safety check';
  const securityConfidence = useMemo(() => deriveSecurityConfidence({
    lastRun,
    runStatus,
    executionSteps,
    evidenceRefs: currentEvidenceRefs,
    evidence,
    toolResults,
    sbomSaved,
    reviewItems,
  }), [lastRun, runStatus, executionSteps, currentEvidenceRefs, evidence, toolResults, sbomSaved, reviewItems]);
  const evidenceReceipt = evidence ? {
    run_id: evidenceRun?.run_id || lastRun?.run_id,
    status: evidenceRun?.status || data?.status || 'unknown',
    score: evidence?.score ?? data?.score ?? 0,
    findings: evidenceFindings.length,
    completed_at: evidenceRun?.completed_at || lastRun?.completed_at,
    duration_seconds: evidenceRun?.duration_seconds || (typeof latestHistory !== 'undefined' ? latestHistory?.duration_seconds : undefined),
    tools: Object.keys(toolResults).length ? Object.keys(toolResults) : toolNames,
    evidence_files: currentEvidenceRefs,
    sbom_saved: Boolean(toolResults?.trivy?.sbom_saved || sbomSaved),
    sanitized: true,
  } : null;
  const safetyStatus = data?.status || (findings === 0 ? 'healthy' : 'degraded');
  const safetyState = ['queued', 'running'].includes(runStatus) ? 'checking' : normalizeBackendState(safetyStatus);
  const safetyIsReady = safetyState === 'ready' && findings === 0;
  const scoreValue = Number(data?.score ?? (safetyIsReady ? 100 : Math.max(55, 100 - Math.max(findings, 1) * 12)));
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
  const safetyScoreSummary = lastRun?.partial_results
    ? 'Partial check completed. Available evidence was saved.'
    : data?.summary || 'Pocket Lab is checking the current safety state.';
  const healthBanner = deriveSecurityHealthBanner(data, null, allReviewFindings);
  const latestEvidenceReceipt = deriveLatestEvidenceReceipt(data, { evidence, evidenceRefs, latestHistory, toolNames, sbomSaved });
  const scanQuality = deriveScanQuality(data, latestEvidenceReceipt, executionSteps);
  const securityFlow = useLiteSecurityCheckFlow({ security: data, backendReachable, savedStateOnly });
  const lastKnownGood = deriveLastKnownGood(data, allReviewFindings);
  const postureComparison = deriveSecurityPostureComparison(data);
  const remediationContext = { data, lastRun, evidence, evidenceRefs, toolResults };
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

  function invalidateSecurityQuery() {
    queryClient.invalidateQueries({ queryKey: liteQueryKeys.security() });
  }

  async function scan() {
    const flowCheck = securityFlow.requestRun();
    if (!flowCheck.ok) { setActionError(flowCheck.reason); return; }
    setBusy(true);
    setResult({ status: 'queued', summary: 'Safety check queued.' });
    setActionError(null);
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    setReceiptCopied(false);
    try {
      const payload = await liteApi.runSecurityScan('local', { reason: 'manual safety check' });
      securityFlow.accepted(payload);
      setResult(payload);
      invalidateSecurityQuery();
    } catch (err) {
      securityFlow.fail(err);
      setResult(null);
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function checkProtectedApp(app) {
    if (!app?.app_id) return;
    setBusy(true);
    setResult({ status: 'checking', summary: 'Check app request sent through Pocket Lab.' });
    setActionError(null);
    try {
      const payload = await liteApi.checkSecurityApp(app.app_id, { reason: 'manual app safety check' });
      setResult(payload);
      invalidateSecurityQuery();
    } catch (err) {
      const payload = err?.payload || {};
      if (err.status === 501 && payload?.status === 'not_implemented') {
        setResult(payload);
      } else {
        setActionError(err.message);
      }
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
    const runId = lastRun?.run_id || result?.run_id;
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

  function openRemediation(finding) {
    triggerHapticFeedback(6);
    setRemediationFinding(finding);
  }

  function closeRemediation() {
    setRemediationFinding(null);
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


  const securityProgressiveDetailsModel = {
    findingDelta,
    deltaStats,
    deltaPreview,
    allReviewFindings,
    executionSteps,
    executionLiveLabelAligned,
    latestEvidenceReceipt,
    evidenceReceipt,
    currentEvidenceRefs,
    toolNames,
    sbomSaved,
    evidenceFileCount,
    safetyScore,
    safetyLabel,
    lastRun,
    savedStateOnly,
  };

  const activeSecurityDetailsMeta = securityDetailShellMeta(activeSecurityDetails);


  return (
    <>
      <PageHeader
        eyebrow="Safety Center"
        title="Security"
        description="A calmer safety overview with clear next steps. Details stay available when you need them."
        actions={<LiteButton onClick={scan} disabled={scanInProgress || securityFlow.writeBlocked} haptic>{scanInProgress ? 'Checking...' : securityFlow.writeBlocked ? 'Reconnect to continue' : 'Run Safety Check'}</LiteButton>}
      />

      <section className="lite-security-phase1-shell" aria-label="Safety Center overview">
        <GlassCard className={`lite-security-phase1-hero lite-security-phase1-hero-${safetyState}`}>
          <div className="lite-security-phase1-hero-copy">
            <div className="lite-home-pill">
              <span className="lite-ready-dot" />
              {scanInProgress ? 'Checking safety' : safetyLabel}
            </div>
            <h2>{scanInProgress
              ? 'Checking safety now.'
              : backendHeroTitle(safetyStatus, {
                ready: safetyIsReady ? 'No urgent safety issues.' : 'Review items found.',
                review: 'Review items found.',
                danger: 'Safety needs attention.',
                checking: 'Checking safety.',
              })}</h2>
            <p>{safetyScoreSummary}</p>
            <div className="lite-security-phase1-actions">
              <LiteButton onClick={scan} disabled={scanInProgress || securityFlow.writeBlocked} haptic>{scanInProgress ? 'Checking...' : securityFlow.writeBlocked ? 'Reconnect to continue' : 'Run Safety Check'}</LiteButton>
              <LiteButton tone="secondary" onClick={showEvidence}>{evidenceLoading ? 'Opening...' : 'View safe summary'}</LiteButton>
            </div>
            {securityFlow.writeBlocked ? <p className="lite-security-phase1-note">{securityFlow.blockedReason || 'Reconnect to continue.'}</p> : null}
          </div>

          <div className="lite-security-phase1-score" aria-label="Safety score">
            <div className="lite-security-score-ring" style={{ '--score': `${safetyScore}%` }}>
              <span>{safetyScore}</span>
            </div>
            <strong>Safety score</strong>
            <span>{scanInProgress ? `${scanProgressPercent}% complete` : lastRun?.completed_at ? `Last checked ${formatLiteTime(lastRun.completed_at)}` : 'Run a check to refresh'}</span>
            <StatusBadge status={backendBadgeStatus(safetyStatus)}>{safetyLabel}</StatusBadge>
          </div>
        </GlassCard>

        {scanInProgress ? (
          <GlassCard className="lite-security-phase1-live" aria-live="polite">
            <div className="lite-security-card-head">
              <div className="lite-security-icon"><Activity className="h-5 w-5" /></div>
              <span className="lite-security-soft-badge">Live check</span>
            </div>
            <h2>{scanProgressLabel}</h2>
            <p>{scanProgress?.message || 'Pocket Lab is checking host readiness and dependency risks in the backend worker.'}</p>
            <div className="lite-security-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={scanProgressPercent} aria-label="Safety check progress">
              <span style={{ width: `${scanProgressPercent}%` }} />
            </div>
            <div className="lite-security-phase1-live-meta">
              <span>Step {scanProgressStep} of {scanProgressStepsTotal}</span>
              <span>{scanProgressEta} remaining</span>
            </div>
            <LiteFlowStatusPanel title="Check path" label={securityFlow.label} steps={securityFlow.steps} note="Request, worker, Lynis, Trivy, and Evidence steps follow backend state." className="mt-4" />
          </GlassCard>
        ) : null}
      </section>

      <SecurityHealthBanner banner={healthBanner} />

      {loading ? <LoadingCard label="Loading safety summary..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Safety summary needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <section className="lite-security-phase1-layout" aria-label="Security summary sections">
        <div className="lite-security-phase1-main">
          <GlassCard className="lite-security-card lite-security-phase1-change-card">
            <div className="lite-security-card-head">
              <div className="lite-security-icon"><RefreshCw className="h-5 w-5" /></div>
              <span className="lite-security-soft-badge">What changed</span>
            </div>
            <h2>{deltaSummary || 'Baseline ready'}</h2>
            <div className="lite-security-delta-stats" aria-label="Finding changes">
              {deltaStats.map((item) => (
                <div key={item.key} className={`lite-security-delta-stat lite-security-delta-${item.tone}`}>
                  <strong>{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
            {timeoutDeltaCount ? (
              <div className="lite-security-delta-insight">
                <Activity className="h-4 w-4" />
                <span>Lynis host readiness was partial. Treat this as a recheck recommendation.</span>
              </div>
            ) : null}
            <div className="lite-security-safe-panel lite-security-phase2-summary-only">
              <Lock className="h-4 w-4" />
              <span>{deltaPreview.length ? `${deltaPreview.length} safe change summary${deltaPreview.length === 1 ? '' : 'ies'} available.` : 'No recent changes need attention.'}</span>
            </div>
            <button type="button" className="lite-security-coverage-toggle" onClick={(event) => openSecurityDetails('changes', event)}>Open changes</button>
          </GlassCard>

          <GlassCard className="lite-security-card lite-security-phase1-attention-card">
            <div className="lite-security-card-head">
              <div className="lite-security-icon"><ShieldCheck className="h-5 w-5" /></div>
              <StatusBadge status={findings ? 'review' : backendBadgeStatus(safetyStatus)}>{findings ? 'Needs review' : 'No urgent issues'}</StatusBadge>
            </div>
            <h2>{findings ? 'Needs attention' : 'No urgent issues'}</h2>
            <p>{findings ? `${findings} item${findings === 1 ? '' : 's'} to review from the latest safety check.` : 'Pocket Lab will keep evidence ready after each check.'}</p>
            {allReviewFindings.length ? (
              <div className="lite-security-phase1-compact-list">
                {allReviewFindings.slice(0, 3).map((item) => {
                  const action = classifyFindingAction(item, remediationContext);
                  return (
                    <div key={item.id || item.summary} className="lite-security-review-item lite-security-phase1-finding-row">
                      <span className={`lite-security-severity lite-security-severity-${securityFindingTone(item.severity)}`}>{item.severity || 'review'}</span>
                      <div>
                        <div className="lite-security-finding-head">
                          <strong>{securityFindingLabel(item)}</strong>
                          <SecurityActionIndicator action={action} />
                        </div>
                        <p>{item.recommendation || item.summary || 'Review this item and keep the workspace protected.'}</p>
                        <div className="lite-security-finding-actions">
                          <button type="button" className="lite-finding-detail-trigger" onClick={(event) => openFindingDetails(item, event)}>View details</button>
                          <button type="button" className="lite-security-remediation-button" onClick={() => openRemediation(item)}>What should I do?</button>
                        </div>
                      </div>
                    </div>
                  );
                })}
                {allReviewFindings.length > 3 ? (
                  <button type="button" className="lite-security-coverage-toggle" onClick={(event) => openSecurityDetails('attention', event)}>Open all review items</button>
                ) : null}
              </div>
            ) : (
              <div className="lite-security-safe-panel">
                <Lock className="h-4 w-4" />
                <span>No urgent issues were found in the latest summary.</span>
              </div>
            )}
          </GlassCard>
        </div>

        <aside className="lite-security-phase1-side" aria-label="Security details summary">
          <GlassCard className={`lite-security-card lite-security-execution-card ${executionTimelineLive ? 'lite-security-execution-card-live' : ''}`}>
            <div className="lite-security-card-head">
              <div className="lite-security-icon"><Activity className="h-5 w-5" /></div>
              <span className="lite-security-soft-badge">{executionTimelineLive ? 'Live path' : 'Last check path'}</span>
              <span className={`lite-security-live-chip ${executionTimelineLive ? 'lite-security-live-chip-active' : ''}`}>{executionTimelineLive ? 'Live' : 'Last run'}</span>
            </div>
            <h2>{executionTimelineLive ? 'Checking safety' : 'Evidence path'}</h2>
            <p>{executionLiveLabelAligned}</p>
            {executionTimelineLive ? (
              <div id="lite-security-execution-timeline-body" className="lite-security-collapsible-body">
                <div className="lite-security-execution-livebar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={executionProgressAligned} aria-label="Security execution progress">
                  <span style={{ width: `${executionProgressAligned}%` }} />
                </div>
                <div className="lite-security-execution-timeline" role="list" aria-label="Security tool execution timeline">
                  {executionSteps.map((step, index) => (
                    <div key={step.key} className={`lite-security-execution-step lite-security-execution-${securityExecutionStateTone(step.state)} ${step.state === 'active' ? 'lite-security-execution-step-active' : ''}`} role="listitem" aria-current={step.state === 'active' ? 'step' : undefined}>
                      <span>{securityExecutionStepGlyph(step, index)}</span>
                      <div>
                        <div className="lite-security-execution-step-head">
                          <strong>{step.title}</strong>
                          {step.state !== 'waiting' ? <span className={`lite-security-execution-pill lite-security-execution-pill-${step.state}`}>{securityExecutionStepLabel(step.state)}</span> : null}
                        </div>
                        <p>{step.detail}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : <p className="lite-progressive-disclosure-summary">Open the check path to review request, worker, Lynis, Trivy, and evidence steps.</p>}
            {!executionTimelineLive ? <button type="button" className="lite-security-coverage-toggle" onClick={(event) => openSecurityDetails('checkPath', event)}>Show check path</button> : null}
          </GlassCard>

          <GlassCard className="lite-security-card lite-security-phase1-evidence-card">
            <div className="lite-security-card-head">
              <div className="lite-security-icon"><FileCheck className="h-5 w-5" /></div>
              <span className="lite-security-soft-badge">Evidence</span>
            </div>
            <h2>{latestEvidenceReceipt?.title || 'Evidence summary'}</h2>
            <p>{latestEvidenceReceipt?.summary || 'Evidence appears after a completed safety check.'}</p>
            <div className="lite-security-phase1-meta-grid">
              <span>Tools: {toolNames.join(' + ')}</span>
              <span>{sbomSaved ? 'SBOM saved' : 'SBOM pending'}</span>
              <span>Secrets hidden</span>
              <span>{evidenceFileCount} evidence file{evidenceFileCount === 1 ? '' : 's'}</span>
            </div>
            <LiteButton tone="secondary" onClick={showEvidence}>{evidenceLoading ? 'Opening...' : 'View safe summary'}</LiteButton>
          </GlassCard>

          <GlassCard className="lite-security-card lite-security-phase1-history-card" id="lite-security-history-body">
            <div className="lite-security-card-head">
              <div className="lite-security-icon"><Database className="h-5 w-5" /></div>
              <span className="lite-security-soft-badge">History</span>
            </div>
            <h2>Safety history</h2>
            <p>{securityHistory.length ? `${securityHistory.length} recent check${securityHistory.length === 1 ? '' : 's'} available. ${scoreTrendView.detail || scoreTrendView.label}` : 'History will appear after more safety checks.'}</p>
            {isSecurityCardCollapsed('securityHistory') ? (
              <button type="button" className="lite-security-coverage-toggle" onClick={() => toggleSecurityCard('securityHistory')}>Open history</button>
            ) : (
              <Suspense fallback={<div className="lite-security-details-loading">Loading security history…</div>}>
                <SecurityHistoryLazy history={securityHistory} latestScore={latestHistory?.score ?? safetyScore} trendLabel={scoreTrendView.label} trendDetail={scoreTrendView.detail} savedStateOnly={savedStateOnly} />
              </Suspense>
            )}
          </GlassCard>
        </aside>
      </section>

      <LiteSheet
        open={Boolean(activeSecurityDetails)}
        onClose={closeSecurityDetails}
        eyebrow={activeSecurityDetailsMeta.eyebrow}
        title={activeSecurityDetailsMeta.title}
        description={activeSecurityDetailsMeta.description}
        layerClassName="lite-security-phase3-layer"
        className="lite-security-phase3-panel lite-security-phase3-details-shell"
        bodyClassName="lite-security-phase3-scroll"
        headerClassName="lite-security-phase3-head"
        closeClassName="lite-security-phase3-close"
        gripClassName="lite-security-phase3-grip"
        surfaceProps={{ 'data-security-phase3-responsive-shell': 'true' }}
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
        layerClassName="lite-security-phase3-layer"
        className="lite-security-phase3-panel lite-security-phase3-finding-shell"
        bodyClassName="lite-security-phase3-scroll"
        headerClassName="lite-security-phase3-head"
        closeClassName="lite-security-phase3-close"
        gripClassName="lite-security-phase3-grip"
        surfaceProps={{ 'data-security-phase3-responsive-shell': 'true' }}
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
                    <LiteButton tone="secondary" onClick={copyEvidenceReceipt}>{receiptCopied ? 'Copied' : 'Copy Receipt'}</LiteButton>
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

      <section className="lite-security-phase1-more" aria-label="Additional security details">
        <GlassCard className="lite-security-card lite-security-phase1-more-card">
          <div className="lite-security-card-head lite-security-card-head-collapsible">
            <div className="lite-security-icon"><Menu className="h-5 w-5" /></div>
            <span className="lite-security-soft-badge">More details</span>
            <SecurityCollapseToggle label="More security details" collapsed={isSecurityCardCollapsed('moreSecurityDetails')} onToggle={() => toggleSecurityCard('moreSecurityDetails')} controls="lite-security-more-details-body" />
          </div>
          <h2>More security details</h2>
          <p>Protected apps, coverage, trust boundary, scan quality, and local protection details are available when needed.</p>
          <div id="lite-security-more-details-body" className="lite-security-collapsible-body" hidden={isSecurityCardCollapsed('moreSecurityDetails')}>
            <section className="lite-security-insight-grid" aria-label="Security evidence and posture summaries">
              <SecurityEvidenceReceiptSummary receipt={latestEvidenceReceipt} onOpen={showEvidence} collapsed={isSecurityCardCollapsed('latestEvidence')} onToggle={() => toggleSecurityCard('latestEvidence')} />
              <SecurityLastKnownGoodCard marker={lastKnownGood} collapsed={isSecurityCardCollapsed('lastKnownGood')} onToggle={() => toggleSecurityCard('lastKnownGood')} />
              <SecurityPostureComparisonCard comparison={postureComparison} collapsed={isSecurityCardCollapsed('postureComparison')} onToggle={() => toggleSecurityCard('postureComparison')} />
            </section>
            <SecurityScanQualityCard quality={scanQuality} collapsed={isSecurityCardCollapsed('scanQuality')} onToggle={() => toggleSecurityCard('scanQuality')} />
            <section className="lite-security-assurance-grid" aria-label="Security assurances">
              {trustSignals.map((item) => {
                const Icon = item.icon;
                return (
                  <div key={item.title} className="lite-security-assurance-card">
                    <span><Icon className="h-4 w-4" /></span>
                    <strong>{item.title}</strong>
                    <p>{item.summary}</p>
                  </div>
                );
              })}
            </section>
            <section className="lite-security-trust-grid" aria-label="Security trust and coverage">
              <SecurityProtectionReasonsCard />
              <SecurityTrustBoundaryCard />
              <SecurityCoverageMatrixCard expanded={coverageExpanded} onToggle={() => setCoverageExpanded((value) => !value)} />
            </section>
            <section className="lite-security-app-profiles" aria-label="Protected apps">
              <div className="lite-security-section-heading">
                <div>
                  <span>Protected apps</span>
                  <h2>App safety profiles</h2>
                  <p>PhotoPrism and future apps get their own safety summary without exposing secrets.</p>
                </div>
              </div>
              {protectedApps.length ? (
                <div className="lite-security-app-grid">
                  {protectedApps.map((app) => {
                    const lifecycle = lifecycleByApp.get(app.app_id) || app.lifecycle;
                    return (
                      <GlassCard key={app.app_id || app.name} className="lite-security-card lite-security-app-card">
                        <div className="lite-security-card-head">
                          <div className="lite-security-icon"><ShieldCheck className="h-5 w-5" /></div>
                          <StatusBadge status={backendBadgeStatus(app.status)}>{backendLabel(app.status, { ready: 'Ready', review: 'Needs review', danger: 'Needs attention', checking: 'Checking' })}</StatusBadge>
                        </div>
                        <h3>{app.name || 'Self-hosted app'}</h3>
                        <p>{app.summary || 'App security profile is available.'}</p>
                        {lifecycle ? (
                          <div className="lite-security-app-lifecycle">
                            <span>{lifecycle?.security?.summary || 'Protected app'}</span>
                            <span>{lifecycle?.backup?.summary || 'Backup ready'}</span>
                            <span>{lifecycle?.media?.last_indexed_at ? `Last indexed ${formatLiteTime(lifecycle.media.last_indexed_at)}` : lifecycle?.media?.summary || 'Last indexed not available yet'}</span>
                            <span>{lifecycle?.host_device?.label || 'Runs on Server Phone'}</span>
                          </div>
                        ) : null}
                        <div className="lite-security-app-actions">
                          <LiteButton tone="secondary" onClick={() => checkProtectedApp(app)} disabled={busy}>Check app</LiteButton>
                          <LiteButton tone="ghost" onClick={showEvidence}>View evidence</LiteButton>
                        </div>
                      </GlassCard>
                    );
                  })}
                </div>
              ) : <StateSurface tone="empty" title="No protected apps yet" description="Install an app from Apps to include it in safety checks." />}
            </section>
          </div>
        </GlassCard>
      </section>
      <SecurityRemediationDrawer finding={remediationFinding} context={remediationContext} onClose={closeRemediation} />

      <ResultNotice result={result} error={actionError} />
    </>
  );
}
