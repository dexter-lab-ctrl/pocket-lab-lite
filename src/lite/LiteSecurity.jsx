import React, { useMemo, useState } from 'react';
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
import { formatLiteTime, liteApi } from '../lib/liteApi.js';
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
  friendlyOverallLabel,
  deviceLinkState,
  restartProgressTitle,
  restartStepStateLabel,
  safeRestartSteps
} from './LiteUi.jsx';

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

export default function SecurityScreen() {
  const { data, loading, error, refresh } = useLiteResource(liteApi.security, []);
  const [result, setResult] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [evidence, setEvidence] = useState(null);
  const [evidenceError, setEvidenceError] = useState(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [receiptCopied, setReceiptCopied] = useState(false);
  const [coverageExpanded, setCoverageExpanded] = useState(false);
  const [progressNow, setProgressNow] = useState(() => Date.now());

  const lastRun = data?.last_run || null;
  const findings = Number(data?.items_to_review ?? data?.findings_count ?? 0);
  const checks = Number(data?.checks_reviewed ?? data?.checks_count ?? 0);
  const criticalIssues = Array.isArray(data?.critical_issues) ? data.critical_issues : [];
  const reviewItems = Array.isArray(data?.findings) ? data.findings : [];
  const evidenceRefs = Array.isArray(data?.evidence_refs) ? data.evidence_refs : [];
  const componentPosture = Array.isArray(data?.component_posture) ? data.component_posture : [];
  const healthyComponents = componentPosture.filter((item) => normalizeBackendState(item?.status) === 'ready').length;
  const guidance = Array.isArray(data?.guidance) && data.guidance.length ? data.guidance : [
    { step: 1, title: 'Check local readiness', summary: 'Pocket Lab reviews local security and dependency posture.' },
    { step: 2, title: 'Summarize what changed', summary: 'New issues are compared against the last safety check.' },
    { step: 3, title: 'Show clear next steps', summary: 'Only actionable items are shown.' },
  ];
  const evidenceFindings = Array.isArray(evidence?.findings) ? evidence.findings : [];
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

  React.useEffect(() => {
    if (!scanInProgress) return undefined;
    setProgressNow(Date.now());
    const timer = window.setInterval(() => setProgressNow(Date.now()), 1000);
    const refreshTimer = window.setInterval(() => refresh(), 8000);
    return () => {
      window.clearInterval(timer);
      window.clearInterval(refreshTimer);
    };
  }, [scanInProgress, refresh]);

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

  function scheduleSecurityRefresh() {
    refresh();
    [700, 1800, 4000].forEach((delay) => window.setTimeout(() => refresh(), delay));
  }

  async function scan() {
    setBusy(true);
    setResult({ status: 'queued', summary: 'Safety check queued.' });
    setActionError(null);
    setEvidence(null);
    setEvidenceError(null);
    setEvidenceLoading(false);
    setReceiptCopied(false);
    try {
      const payload = await liteApi.runSecurityScan('local', { reason: 'manual safety check' });
      setResult(payload);
      scheduleSecurityRefresh();
    } catch (err) {
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
  }

  async function copyEvidenceReceipt() {
    if (!evidenceReceipt) return;
    const copied = await copyTextToClipboard(JSON.stringify(evidenceReceipt, null, 2));
    if (copied) {
      setReceiptCopied(true);
      window.setTimeout(() => setReceiptCopied(false), 1800);
    }
  }

  async function showEvidence() {
    triggerHapticFeedback(8);
    if (evidence) {
      closeEvidencePanel();
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

  return (
    <>
      <PageHeader
        eyebrow="Safety"
        title="Security"
        description="Check whether your Pocket Lab needs attention. The results are summarized clearly so you know what to do next."
        actions={<LiteButton onClick={scan} disabled={scanInProgress} haptic>{scanInProgress ? 'Checking...' : 'Run Safety Check'}</LiteButton>}
      />

      <section className="lite-security-hero">
        <div className="lite-security-hero-copy">
          <div className="lite-home-pill">
            <span className="lite-ready-dot" />
            {safetyLabel}
          </div>
          <h2>{runStatus === 'queued'
            ? 'Safety check queued.'
            : runStatus === 'running'
              ? 'Safety check running.'
              : backendHeroTitle(safetyStatus, {
                ready: safetyIsReady ? 'No urgent safety issues found.' : 'A few items may need your review.',
                review: 'A few items may need your review.',
                danger: 'Safety needs attention.',
                checking: 'Checking your safety status.',
              })}</h2>
          <p>
            Pocket Lab checks host readiness, dependency risks, configuration concerns, and secret-like findings through the backend worker. Sensitive values stay hidden and evidence is saved for review.
          </p>
          <div className="lite-security-trust-strip" aria-label="Security assurances">
            {trustSignals.map((item) => {
              const Icon = item.icon;
              return (
                <div key={item.title}>
                  <Icon className="h-4 w-4" />
                  <span>{item.title}</span>
                </div>
              );
            })}
          </div>
          {scanInProgress ? (
            <div className="lite-security-progress-card" aria-live="polite">
              <div className="lite-security-progress-head">
                <div>
                  <strong>{scanProgressLabel}</strong>
                  <span>Step {scanProgressStep} of {scanProgressStepsTotal}</span>
                </div>
                <span>{scanProgressEta} remaining</span>
              </div>
              <div className="lite-security-progress-track" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={scanProgressPercent} aria-label="Safety check progress">
                <span style={{ width: `${scanProgressPercent}%` }} />
              </div>
              <p>{scanProgress?.message || 'Pocket Lab is checking host readiness and dependency risks in the backend worker.'}</p>
            </div>
          ) : null}
          <div className="lite-security-actions">
            <LiteButton onClick={scan} disabled={scanInProgress} haptic>{scanInProgress ? 'Checking...' : 'Run Safety Check'}</LiteButton>
            <LiteButton onClick={showEvidence} tone="secondary">{evidence ? 'Hide Evidence' : evidenceLoading ? 'Opening...' : 'Evidence'}</LiteButton>
          </div>
        </div>

        <div className="lite-security-score-card">
          <div className="lite-security-score-ring" style={{ '--score': `${safetyScore}%` }}>
            <span>{safetyScore}</span>
          </div>
          <strong>Safety score</strong>
          <p>{safetyScoreSummary}</p>
          <StatusBadge status={backendBadgeStatus(safetyStatus)}>
            {safetyLabel}
          </StatusBadge>
          <div className="lite-security-score-meta">
            <span>{scanInProgress ? `${scanProgressPercent}% complete · ${scanProgressEta} remaining` : lastRun?.completed_at ? `Last check ${formatLiteTime(lastRun.completed_at)}` : 'Run a check to refresh posture'}</span>
            <span>{healthyComponents || componentPosture.length || 0} protected areas healthy</span>
          </div>
          <SecurityConfidenceCard confidence={securityConfidence} />
        </div>
      </section>

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

      {loading ? <LoadingCard label="Loading safety summary..." /> : null}

      {error ? (
        <StateSurface
          tone="degraded"
          title="Safety summary needs a moment"
          description={error}
          className="mb-5"
        />
      ) : null}

      <GlassCard className={`lite-security-card lite-security-execution-card ${executionTimelineLive ? 'lite-security-execution-card-live' : ''}`}>
        <div className="lite-security-card-head">
          <div className="lite-security-icon">
            <Activity className="h-5 w-5" />
          </div>
          <span className="lite-security-soft-badge">Execution timeline</span>
          <span className={`lite-security-live-chip ${executionTimelineLive ? 'lite-security-live-chip-active' : ''}`}>
            {executionTimelineLive ? 'Live' : 'Last run'}
          </span>
        </div>
        <h2>Per-tool check path</h2>
        <p>Security checks move through FastAPI, the backend worker, Lynis, Trivy, and sanitized evidence.</p>
        <div className="lite-security-execution-livebar" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow={executionProgressAligned} aria-label="Security execution progress">
          <span style={{ width: `${executionProgressAligned}%` }} />
        </div>
        <p className="lite-security-execution-status">{executionLiveLabelAligned}</p>
        <div className="lite-security-execution-timeline" role="list" aria-label="Security tool execution timeline">
          {executionSteps.map((step, index) => (
            <div
              key={step.key}
              className={`lite-security-execution-step lite-security-execution-${securityExecutionStateTone(step.state)} ${step.state === 'active' ? 'lite-security-execution-step-active' : ''}`}
              role="listitem"
              aria-current={step.state === 'active' ? 'step' : undefined}
            >
              <span>{securityExecutionStepGlyph(step, index)}</span>
              <div>
                <div className="lite-security-execution-step-head">
                  <strong>{step.title}</strong>
                  {step.state !== 'waiting' ? (
                    <span className={`lite-security-execution-pill lite-security-execution-pill-${step.state}`}>
                      {securityExecutionStepLabel(step.state)}
                    </span>
                  ) : null}
                </div>
                <p>{step.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </GlassCard>

      {(securityHistory.length || findingDelta.summary) ? (
        <section className="lite-security-history-grid" aria-label="Security history and change summary">
          <GlassCard className="lite-security-card lite-security-history-card">
            <div className="lite-security-card-head">
              <div className="lite-security-icon">
                <Activity className="h-5 w-5" />
              </div>
              <span className="lite-security-soft-badge">Security history</span>
            </div>
            <h2>Trend timeline</h2>
            <p>Recent checks show whether the safety score is improving, stable, or needs attention.</p>
            <div className="lite-security-trend-summary">
              <div>
                <span>Latest score</span>
                <strong>{latestHistory?.score ?? safetyScore}</strong>
              </div>
              <div>
                <span>Trend</span>
                <strong className={`lite-security-trend-tone lite-security-trend-${scoreTrendView.tone}`}>{scoreTrendView.label}</strong>
                <small>{scoreTrendView.detail}</small>
              </div>
              <div>
                <span>Last duration</span>
                <strong>{formatSecurityDuration(latestHistory?.duration_seconds)}</strong>
              </div>
            </div>
            <div className="lite-security-timeline" role="list">
              {securityHistory.slice(0, 6).map((entry, index) => {
                const reviewCount = Number(entry.items_to_review || 0);
                return (
                  <div key={entry.run_id || index} className="lite-security-timeline-row" role="listitem">
                    <span className={`lite-security-timeline-dot lite-security-timeline-${normalizeBackendState(entry.status)}`} />
                    <div>
                      <strong>{entry.completed_at ? formatLiteTime(entry.completed_at) : entry.status || 'recorded'}</strong>
                      <p>{reviewCount ? `${reviewCount} review item${reviewCount === 1 ? '' : 's'}` : 'No urgent items'} · {entry.evidence_count || 0} evidence file{entry.evidence_count === 1 ? '' : 's'}</p>
                    </div>
                    <div className="lite-security-timeline-score">
                      <span>{entry.score ?? '—'}</span>
                      <small>{formatSecurityDuration(entry.duration_seconds)}</small>
                    </div>
                  </div>
                );
              })}
            </div>
          </GlassCard>

          <GlassCard className="lite-security-card lite-security-delta-card">
            <div className="lite-security-card-head">
              <div className="lite-security-icon">
                <RefreshCw className="h-5 w-5" />
              </div>
              <span className="lite-security-soft-badge">What changed</span>
            </div>
            <h2>Finding delta</h2>
            <p>{deltaSummary}</p>
            {timeoutDeltaCount ? (
              <div className="lite-security-delta-insight">
                <Activity className="h-4 w-4" />
                <span>Lynis host readiness was partial. Treat this as a recheck recommendation, not a confirmed security failure.</span>
              </div>
            ) : null}
            <div className="lite-security-delta-stats" aria-label="Finding changes">
              {deltaStats.map((item) => (
                <div key={item.key} className={`lite-security-delta-stat lite-security-delta-${item.tone}`}>
                  <strong>{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
            {deltaPreview.length ? (
              <div className="lite-security-delta-list">
                {deltaPreview.map((item) => (
                  <div key={`${item.delta_type}-${item.id || item.summary}`} className="lite-security-delta-item">
                    <span className={`lite-security-severity lite-security-severity-${securityDeltaTone(item.delta_type, item)}`}>
                      {securityDeltaBadge(item)}
                    </span>
                    <div>
                      <strong>{securityDeltaTitle(item)}</strong>
                      <p>{securityDeltaDescription(item)}</p>
                      {securityDeltaAction(item) ? <small>{securityDeltaAction(item)}</small> : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="lite-security-safe-panel">
                <Lock className="h-4 w-4" />
                <span>Baseline ready. The next check will show what changed.</span>
              </div>
            )}
          </GlassCard>
        </section>
      ) : null}

      <div className="lite-security-grid">
        <GlassCard className="lite-security-card">
          <div className="lite-security-card-head">
            <div className="lite-security-icon">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <StatusBadge status={backendBadgeStatus(safetyStatus)}>
              {safetyLabel}
            </StatusBadge>
          </div>

          <h2>{criticalIssues.length ? 'Critical issues found' : 'No critical issues'}</h2>
          <p>{criticalIssues.length ? 'Review the items below before making more changes.' : 'No urgent safety issues were found in the latest summary.'}</p>

          <div className="lite-security-summary-list">
            <div>
              <span className="lite-security-dot" />
              <strong>{checks || '—'}</strong>
              <p>checks reviewed</p>
            </div>
            <div>
              <span className={findings === 0 ? 'lite-security-dot' : 'lite-security-dot lite-security-dot-warning'} />
              <strong>{findings}</strong>
              <p>items to review</p>
            </div>
          </div>

          {criticalIssues.length ? (
            <div className="lite-security-issue-list">
              {criticalIssues.slice(0, 4).map((issue) => (
                <div key={issue.id || issue.summary} className="lite-security-issue">
                  <strong>{issue.summary || 'Critical issue found'}</strong>
                  <p>{issue.recommendation || 'Review this item and apply the recommended fix.'}</p>
                </div>
              ))}
            </div>
          ) : null}

          {reviewItems.length ? (
            <div className="lite-security-review-list">
              {reviewItems.slice(0, 4).map((item) => (
                <div key={item.id || item.summary} className="lite-security-review-item">
                  <span className={`lite-security-severity lite-security-severity-${securityFindingTone(item.severity)}`}>
                    {item.severity || 'review'}
                  </span>
                  <div>
                    <strong>{securityFindingLabel(item)}</strong>
                    <p>{item.recommendation || item.summary || 'Review this item and keep the workspace protected.'}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="lite-security-safe-panel">
              <Lock className="h-4 w-4" />
              <span>No urgent issues. Pocket Lab will keep evidence ready after each check.</span>
            </div>
          )}
        </GlassCard>

        <GlassCard className="lite-security-card lite-security-dashboard-card">
          <div className="lite-security-card-head">
            <div className="lite-security-icon">
              <FileCheck className="h-5 w-5" />
            </div>
            <span className="lite-security-soft-badge">Protection dashboard</span>
          </div>

          <h2>Local protection summary</h2>
          <p>
            Lynis checks host readiness. Trivy checks dependency, config, secret-like findings, and saves SBOM evidence.
          </p>

          <div className="lite-security-mini-dashboard" aria-label="Security protection dashboard">
            {postureDashboard.map((item) => (
              <div key={item.label}>
                <strong>{item.value}</strong>
                <span>{item.label}</span>
                <p>{item.detail}</p>
              </div>
            ))}
          </div>

          <div className="lite-security-steps lite-security-compact-steps">
            {guidance.slice(0, 3).map((item, index) => (
              <div key={item.step || item.title || index}>
                <span>{item.step || index + 1}</span>
                <p>{item.title || item.summary}</p>
              </div>
            ))}
          </div>
        </GlassCard>
      </div>

      {(evidence || evidenceError || evidenceLoading) ? (
        <div className="lite-security-evidence-modal-backdrop" role="presentation" onClick={closeEvidencePanel}>
          <GlassCard className="lite-security-card lite-security-evidence-panel" role="dialog" aria-modal="true" aria-label="Sanitized security evidence" onClick={(event) => event.stopPropagation()}>
            <div className="lite-security-card-head">
              <div className="lite-security-icon">
                <FileCheck className="h-5 w-5" />
              </div>
              <span className="lite-security-soft-badge">Sanitized evidence</span>
              <button type="button" className="lite-security-evidence-close" onClick={closeEvidencePanel} aria-label="Close evidence details">
                <X className="h-4 w-4" />
              </button>
            </div>

            <h2>{evidenceError ? 'Evidence not ready' : evidenceLoading ? 'Opening evidence...' : 'Evidence details'}</h2>
            {evidenceError ? <p>{evidenceError}</p> : null}
            {evidenceLoading ? <p>Pocket Lab is opening the sanitized evidence summary for the latest safety check.</p> : null}
            {evidence ? (
              <>
              <div className="lite-security-evidence-summary">
                <div>
                  <span>Run</span>
                  <strong>{shortRunId(evidence?.run?.run_id || lastRun?.run_id)}</strong>
                </div>
                <div>
                  <span>Status</span>
                  <strong>{evidence?.run?.status || 'unknown'}</strong>
                </div>
                <div>
                  <span>Score</span>
                  <strong>{evidence?.score ?? safetyScore}</strong>
                </div>
                <div>
                  <span>Findings</span>
                  <strong>{evidenceFindings.length}</strong>
                </div>
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
                {currentEvidenceRefs.slice(0, 6).map((ref) => (
                  <code key={ref}>{String(ref).split('/').slice(-1)[0]}</code>
                ))}
              </div>
              <p className="lite-security-evidence-note">Raw scanner output and sensitive values stay hidden. This panel shows only sanitized evidence metadata.</p>
            </>
          ) : null}
          </GlassCard>
        </div>
      ) : null}

      <ResultNotice result={result} error={actionError} />
    </>
  );
}
