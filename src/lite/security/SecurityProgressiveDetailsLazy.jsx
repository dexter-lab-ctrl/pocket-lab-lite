import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { animated, useSpring } from '@react-spring/web';
import LiteProgressiveDetails from '../components/LiteProgressiveDetails.jsx';

const SecurityHistoryLazy = React.lazy(() => import('./SecurityHistoryLazy.jsx'));

const SECURITY_PHASE2_PROGRESSIVE_DETAILS = true;
const SECURITY_PHASE2_SUMMARY_FIRST = true;
const SECURITY_PHASE2_NO_RAW_SCANNER_OUTPUT = 'Security progressive details show sanitized summaries only';
const SECURITY_PHASE2_EVIDENCE_ON_DEMAND = 'Evidence summary opens only after user action';
void SECURITY_PHASE2_PROGRESSIVE_DETAILS;
void SECURITY_PHASE2_SUMMARY_FIRST;
void SECURITY_PHASE2_NO_RAW_SCANNER_OUTPUT;
void SECURITY_PHASE2_EVIDENCE_ON_DEMAND;

const SECURITY_DETAILS_PREMIUM_POLISH_V5_SOURCE_GUARDS = [
  'details panels use safe React Spring polish',
  'lite-security-details-premium-panel',
  'lite-security-details-premium-content',
];
void SECURITY_DETAILS_PREMIUM_POLISH_V5_SOURCE_GUARDS;

const SECURITY_PROGRESSIVE_DETAILS_PATCH_E_GUARDS = [
  'SECURITY_PROGRESSIVE_DETAILS_PATCH_E',
  'offlineDetails',
  'profile freshness appears in saved Security details',
];
void SECURITY_PROGRESSIVE_DETAILS_PATCH_E_GUARDS;

const SECURITY_PROGRESSIVE_DETAILS_PATCH_D_GUARDS = [
  'SECURITY_PROGRESSIVE_DETAILS_PATCH_D',
  'detailsHydration',
  'coverage rows mount only inside focused details',
  'history rows mount only inside focused details',
];
void SECURITY_PROGRESSIVE_DETAILS_PATCH_D_GUARDS;

function useReducedMotionPreference() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return undefined;
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(Boolean(media.matches));
    update();
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', update);
      return () => media.removeEventListener('change', update);
    }
    media.addListener?.(update);
    return () => media.removeListener?.(update);
  }, []);

  return reduced;
}

const SENSITIVE_TEXT_PATTERN = /(token|password|api[_-]?key|authorization|private[_-]?key|nats:\/\/|command payload|raw log|raw evidence|\/data\/data|\/storage\/emulated|restic password|backend secret)/i;

function safeText(value, fallback = '') {
  const text = String(value ?? '').trim();
  if (!text || SENSITIVE_TEXT_PATTERN.test(text)) return fallback;
  return text.slice(0, 220);
}

function safeList(values = [], fallback = []) {
  const source = Array.isArray(values) ? values : values ? [values] : fallback;
  return source.map((item) => safeText(item)).filter(Boolean).slice(0, 8);
}

function shortId(value) {
  const text = safeText(value);
  if (!text) return '';
  if (text.length <= 22) return text;
  return `${text.slice(0, 11)}…${text.slice(-6)}`;
}

function findingTitle(finding = {}) {
  return safeText(finding.title || finding.summary || finding.name || finding.id, 'Security review item');
}

function findingSummary(finding = {}) {
  return safeText(finding.recommendation || finding.summary || finding.description, 'Review this item and keep Pocket Lab protected.');
}

function sourceLabel(finding = {}) {
  const raw = `${finding.source || ''} ${finding.tool || ''} ${finding.category || ''}`.toLowerCase();
  if (raw.includes('lynis') || raw.includes('host')) return 'Lynis';
  if (raw.includes('trivy') || raw.includes('dependency') || raw.includes('secret')) return 'Trivy';
  return 'Security check';
}

function findingRows(findings = []) {
  return (Array.isArray(findings) ? findings : []).slice(0, 8).map((finding) => {
    const title = findingTitle(finding);
    const source = sourceLabel(finding);
    const severity = safeText(finding.severity || finding.status || 'review', 'review');
    return `${title} · ${severity} · ${source}`;
  });
}

function timelineRows(steps = []) {
  return (Array.isArray(steps) ? steps : []).slice(0, 8).map((step) => {
    const title = safeText(step.title || step.key, 'Security step');
    const state = safeText(step.state || step.status || 'waiting', 'waiting');
    return `${title} · ${state}`;
  });
}

function evidenceRows(evidenceRefs = []) {
  return (Array.isArray(evidenceRefs) ? evidenceRefs : [])
    .map((ref) => String(ref || '').split('/').slice(-1)[0])
    .map((ref) => safeText(ref))
    .filter(Boolean)
    .slice(0, 8);
}

function buildDetails({ type, model = {} }) {
  const {
    findingDelta = {},
    deltaStats = [],
    deltaPreview = [],
    allReviewFindings = [],
    executionSteps = [],
    executionLiveLabelAligned = '',
    latestEvidenceReceipt = null,
    evidenceReceipt = null,
    currentEvidenceRefs = [],
    toolNames = [],
    sbomSaved = false,
    evidenceFileCount = 0,
    safetyScore = 0,
    safetyLabel = '',
    lastRun = null,
    savedStateOnly = false,
    savedSecurityDetails = false,
    offlineDetails = null,
    activeProfileFreshness = null,
    backendReachable = true,
    securityHistory = [],
    securityHistoryPage = null,
    latestHistory = null,
    previousHistory = null,
    scoreTrendView = null,
    scanProgressLabel = '',
    scanProfile = 'quick',
    coverageSummary = {},
    checkedCoverageTargets = [],
    skippedCoverageTargets = [],
    partialCoverageTargets = [],
    timedOutCoverageTargets = [],
    missingCoverageTargets = [],
    targetCoverageStatuses = [],
    detailsHydrated = false,
    detailsHydration = {},
  } = model;
  const savedDetailsNote = savedSecurityDetails || savedStateOnly
    ? safeText(offlineDetails?.summary || activeProfileFreshness?.label || 'Showing saved Security details. Reconnect to run a new check.', 'Showing saved Security details.')
    : '';

  if (type === 'changes') {
    const statRows = (Array.isArray(deltaStats) ? deltaStats : []).map((item) => `${item.label}: ${item.value}`);
    const previewRows = findingRows(deltaPreview);
    return {
      title: 'What changed',
      status: Number(findingDelta?.new_count || 0) ? 'review' : 'ready',
      statusLabel: Number(findingDelta?.new_count || 0) ? 'New review items' : 'No urgent changes',
      summary: previewRows.length ? 'Pocket Lab found changes since the previous safety check.' : 'No recent changes need attention.',
      what_happened: ['Pocket Lab compared the latest safety summary with the previous saved check.', ...safeList(statRows)],
      what_changed: previewRows.length ? previewRows : ['No new findings were added to the main review list.'],
      what_needs_attention: Number(findingDelta?.new_count || 0) ? findingRows(findingDelta?.new) : [],
      what_did_not_happen: [
        'The browser did not run security tools.',
        'No repair or system change was started.',
        'Raw scanner output was not loaded into this view.',
      ],
      saved_for_troubleshooting: {
        saved: Boolean(lastRun?.run_id),
        backend_only: true,
        summary: savedDetailsNote || (savedStateOnly ? 'Showing saved state. Fresh details will refresh when Pocket Lab is reachable.' : 'Backend keeps the full safety record protected.'),
      },
      next_step: Number(findingDelta?.new_count || 0) ? 'Review the new items, then rerun Safety Check after taking action.' : 'No action is needed right now.',
      technicalDetails: [
        { label: 'Latest run', value: shortId(lastRun?.run_id) || 'not available' },
        { label: 'New', value: Number(findingDelta?.new_count || 0) },
        { label: 'Resolved', value: Number(findingDelta?.resolved_count || 0) },
        { label: 'Still present', value: Number(findingDelta?.unchanged_count || 0) },
      ],
    };
  }

  if (type === 'attention') {
    const rows = findingRows(allReviewFindings);
    return {
      title: 'Needs attention',
      status: rows.length ? 'review' : 'ready',
      statusLabel: rows.length ? `${rows.length} safe item${rows.length === 1 ? '' : 's'}` : 'No urgent issues',
      summary: rows.length ? 'These are the current review items from the latest safety summary.' : 'No urgent issues were found in the latest summary.',
      what_happened: rows.length ? rows : ['Pocket Lab checked the latest safety summary and found no urgent items.'],
      what_changed: ['Nothing changed by opening this view.'],
      what_needs_attention: rows,
      what_did_not_happen: [
        'The browser did not scan files.',
        'No Lynis or Trivy command was run from this screen.',
        'No repair was started.',
        'Raw logs and private paths stay hidden.',
      ],
      saved_for_troubleshooting: {
        saved: Boolean(lastRun?.run_id),
        backend_only: true,
        summary: savedDetailsNote || 'Full troubleshooting records stay backend-only. This view shows safe summaries.',
      },
      next_step: rows.length ? 'Open one finding at a time for the safest next step.' : 'Run Safety Check again later to keep evidence fresh.',
      technicalDetails: [
        { label: 'Latest run', value: shortId(lastRun?.run_id) || 'not available' },
        { label: 'Safety score', value: safetyScore },
        { label: 'Status', value: safetyLabel },
      ],
    };
  }



  if (type === 'coverage') {
    const profile = safeText(scanProfile, 'quick').toLowerCase();
    const fullProfile = profile === 'full';
    const appProfile = profile === 'app';
    const checked = safeList(checkedCoverageTargets, appProfile ? ['PhotoPrism route', 'App files', 'App settings', 'Backup metadata', 'Action state'] : fullProfile ? ['Termux host', 'Pocket Lab Lite', 'Runtime config', 'PROot Ubuntu', 'PhotoPrism', 'Backup metadata'] : ['Termux host posture', 'Pocket Lab Lite files', 'Caddy route config', 'NATS config posture', 'Services summary', 'Security evidence state']);
    const skipped = safeList(skippedCoverageTargets, appProfile ? ['Photos and originals', 'Import media', 'Thumbnails and sidecars', 'PhotoPrism database', 'Backup payloads', 'Logs and caches'] : fullProfile ? ['Photo library/media', 'Android shared storage', 'Backup payloads', 'Restic repository contents', 'PM2 logs', 'Go/npm/tool caches'] : ['Photo library/media', 'Backup payloads', 'PROot Ubuntu full filesystem', 'Go/npm/cache folders', 'Old PWA builds', 'Large runtime histories']);
    const partial = safeList(partialCoverageTargets);
    const timedOut = safeList(timedOutCoverageTargets);
    const missing = safeList(missingCoverageTargets);
    const targetRows = Array.isArray(targetCoverageStatuses)
      ? targetCoverageStatuses.slice(0, 8).map((item) => `${safeText(item?.target_label || item?.target_id, 'Security target')} · ${safeText(item?.status || 'unknown', 'unknown')}`)
      : [];
    return {
      title: appProfile ? 'App Check coverage' : fullProfile ? 'Full Local Check coverage' : 'Quick safety coverage',
      status: partial.length || timedOut.length ? 'review' : 'ready',
      statusLabel: `Profile: ${safeText(scanProfile, 'quick')}`,
      summary: appProfile
        ? 'App Check focuses on PhotoPrism route, app metadata, settings, backup metadata, and action state while skipping photos and media.'
        : fullProfile
          ? 'Full Local Check checks this device more deeply while still skipping photos, backup payloads, logs, Android shared storage, and large caches.'
          : 'Quick Safety Check checks Pocket Lab basics and skips huge or private areas by default.',
      what_happened: [
        appProfile ? 'Pocket Lab used the app scan profile.' : fullProfile ? 'Pocket Lab used the full local scan profile.' : 'Pocket Lab used the quick scan profile.',
        ...checked.map((item) => `Checked: ${item}`),
        ...targetRows,
      ],
      what_changed: ['Opening this coverage view did not start a scan or change the device.'],
      what_needs_attention: [...partial.map((item) => `Partial: ${item}`), ...timedOut.map((item) => `Timed out: ${item}`), ...missing.map((item) => `Missing optional target: ${item}`)],
      what_did_not_happen: appProfile ? [
        'Photos, originals, imports, thumbnails, sidecars, and media files were not scanned.',
        'PhotoPrism media indexing was not started.',
        'Backup payloads and raw logs were not scanned.',
        'The browser did not access PhotoPrism internals.',
      ] : fullProfile ? [
        'Photo libraries and user media were not scanned.',
        'Backup payloads and restic repository contents were not scanned.',
        'Android shared storage was not scanned.',
        'Logs, caches, thumbnails, sidecars, and old PWA builds were skipped.',
      ] : [
        'Photo libraries and user media were not scanned by the quick profile.',
        'Backup payloads and restore checkpoints were not scanned by the quick profile.',
        'The full PROot Ubuntu filesystem was not scanned by the quick profile.',
        'Large cache folders and old PWA builds were skipped.',
      ],
      saved_for_troubleshooting: {
        saved: Boolean(lastRun?.run_id),
        backend_only: true,
        summary: 'Coverage metadata is saved with sanitized evidence. Raw scanner output stays backend-owned.',
      },
      next_step: partial.length || timedOut.length ? 'Run the check again while charging, then review any timed-out or partial targets.' : appProfile ? 'Use App Check after PhotoPrism settings, route, or backup changes.' : fullProfile ? 'Use Full Local Check after major updates or route/security changes.' : 'Use Quick Safety Check daily for a fast safety signal.',
      technicalDetails: [
        { label: 'Profile', value: safeText(scanProfile, 'quick') },
        { label: 'Checked targets', value: checked.length },
        { label: 'Skipped targets', value: skipped.length },
        { label: 'Excluded groups', value: Array.isArray(coverageSummary.excluded_groups) ? coverageSummary.excluded_groups.length : 0 },
      ],
      history: {
        title: appProfile ? 'Skipped by App Check' : fullProfile ? 'Skipped by Full Local Check' : 'Skipped by Quick Safety Check',
        summary: appProfile ? 'These areas are intentionally skipped so App Check stays private, fast, and app-focused.' : fullProfile ? 'These areas are intentionally skipped to protect private data and keep the deeper check bounded.' : 'These areas are intentionally skipped to keep daily checks bounded on mobile devices.',
        items: skipped.map((title, index) => ({ id: `coverage-skip-${index}`, title, meta: appProfile ? 'skipped by app profile' : fullProfile ? 'skipped by full profile' : 'skipped by quick profile' })),
        enabled: true,
        emptyMessage: 'No skipped targets were reported.',
      },
    };
  }

  if (type === 'history') {
    const safeHistory = Array.isArray(securityHistory) ? securityHistory.slice(0, 7) : [];
    const historyItems = safeHistory.map((item, index) => ({
      id: safeText(item?.run_id || `history-${index}`, `history-${index}`),
      title: `Safety check ${index + 1}`,
      meta: safeText(item?.completed_at || item?.started_at || item?.status || 'saved check', 'saved check'),
      status: safeText(item?.status || 'recorded', 'recorded'),
    }));
    return {
      title: 'Safety history',
      status: safeHistory.length ? 'ready' : 'review',
      statusLabel: safeHistory.length ? `${safeHistory.length} saved check${safeHistory.length === 1 ? '' : 's'}` : 'No history yet',
      summary: safeHistory.length ? 'Recent safety checks are shown as safe saved summaries.' : 'History appears after completed safety checks.',
      what_happened: safeHistory.length ? [
        `${safeHistory.length} recent check${safeHistory.length === 1 ? '' : 's'} summarized.`,
        `Score trend: ${safeText(scoreTrendView?.detail || scoreTrendView?.label, 'Stable')}`,
      ] : ['Run Safety Check to create safety history.'],
      what_changed: ['Opening history did not start a new check or change the device.'],
      what_did_not_happen: [
        'The browser did not load raw scanner output.',
        'Raw evidence files were not opened in this view.',
        'Private paths and backend logs stay hidden.',
      ],
      saved_for_troubleshooting: {
        saved: Boolean(safeHistory.length),
        backend_only: true,
        summary: savedStateOnly ? 'Showing saved state. Fresh history will refresh when Pocket Lab is reachable.' : 'Backend keeps detailed history and evidence protected.',
      },
      next_step: safeHistory.length ? 'Use history to spot score drift, then run Safety Check when needed.' : 'Run Safety Check to create the first history entry.',
      technicalDetails: [
        { label: 'Latest run', value: shortId(latestHistory?.run_id || lastRun?.run_id) || 'not available' },
        { label: 'Previous run', value: shortId(previousHistory?.run_id) || 'not available' },
        { label: 'Shown checks', value: safeHistory.length },
        { label: 'Snapshot state', value: savedStateOnly ? 'Saved state' : 'Fresh state' },
      ],
      history: {
        title: 'Recent safety checks',
        summary: safeHistory.length ? 'History rows mount only inside this details surface.' : 'No saved checks are available yet.',
        items: historyItems,
        enabled: true,
        emptyMessage: 'Run Safety Check to create history.',
      },
    };
  }

  if (type === 'technical_details') {
    const safeToolNames = safeList(toolNames.length ? toolNames : ['Lynis', 'Trivy']);
    return {
      title: 'Technical details',
      status: backendReachable === false ? 'review' : 'ready',
      statusLabel: savedStateOnly ? 'Saved state only' : backendReachable === false ? 'Pocket Lab not reachable' : 'Safe metadata',
      summary: 'Technical details are collapsed by default and only show safe metadata.',
      what_happened: [
        'Security checks remain backend-owned.',
        `Visible stage: ${safeText(scanProgressLabel, 'Ready for the next safety check')}`,
        `Tools summarized: ${safeToolNames.join(' + ')}`,
      ],
      what_changed: ['Opening technical details did not start a check, repair, or system change.'],
      what_did_not_happen: [
        'No raw scanner output was shown.',
        'No raw logs were shown.',
        'No private Android paths were shown.',
        'No backend command payloads or secrets were shown.',
      ],
      saved_for_troubleshooting: {
        saved: Boolean(lastRun?.run_id),
        backend_only: true,
        summary: 'Detailed evidence and troubleshooting records stay backend-owned and sanitized before display.',
      },
      next_step: backendReachable === false ? 'Reconnect to Pocket Lab before running a new safety check.' : 'Use these details only for support or troubleshooting.',
      technicalDetails: [
        { label: 'Execution owner', value: 'FastAPI and worker' },
        { label: 'Polling policy', value: 'slow' },
        { label: 'Snapshot state', value: savedStateOnly ? 'Saved state' : 'Fresh state' },
        { label: 'Backend reachable', value: backendReachable === false ? 'No' : 'Yes' },
        { label: 'Latest run', value: shortId(lastRun?.run_id) || 'not available' },
        { label: 'Evidence refs', value: Number(evidenceFileCount || currentEvidenceRefs.length || 0) },
        { label: 'Details hydrated', value: detailsHydrated ? 'Yes' : 'No' },
        { label: 'Detail type', value: safeText(detailsHydration?.type || type, 'not open') },
      ],
    };
  }

  if (type === 'checkPath') {
    const rows = timelineRows(executionSteps);
    return {
      title: 'Check path',
      status: rows.some((row) => row.toLowerCase().includes('failed')) ? 'review' : 'ready',
      statusLabel: executionLiveLabelAligned || 'Backend-owned check path',
      summary: 'This path shows the safe backend-owned handoff for the latest safety check.',
      what_happened: rows.length ? rows : ['The check path appears after a safety check starts.'],
      what_changed: ['Opening this view did not start a new check.'],
      what_did_not_happen: [
        'The frontend did not talk directly to NATS.',
        'The frontend did not run shell commands.',
        'The frontend did not run Lynis or Trivy.',
        'No backend command payload was shown.',
      ],
      saved_for_troubleshooting: {
        saved: Boolean(lastRun?.run_id),
        backend_only: true,
        summary: 'Backend events and evidence remain protected. This view shows only the safe step summary.',
      },
      next_step: rows.length ? 'Use this path to confirm request, worker, tool, and evidence progress.' : 'Run Safety Check to create a fresh check path.',
      technicalDetails: [
        { label: 'Latest run', value: shortId(lastRun?.run_id) || 'not available' },
        { label: 'Step count', value: rows.length },
        { label: 'Execution owner', value: 'FastAPI and worker' },
      ],
    };
  }

  return {
    title: 'Evidence summary',
    status: latestEvidenceReceipt || evidenceReceipt ? 'ready' : 'review',
    statusLabel: latestEvidenceReceipt?.status || evidenceReceipt?.status || 'Evidence summary',
    summary: latestEvidenceReceipt?.summary || 'Evidence appears after a completed safety check.',
    what_happened: [
      `Tools: ${(Array.isArray(toolNames) && toolNames.length ? toolNames : ['Lynis', 'Trivy']).join(' + ')}`,
      sbomSaved ? 'SBOM was saved.' : 'SBOM is pending or not available yet.',
      `${Number(evidenceFileCount || currentEvidenceRefs.length || 0)} evidence file${Number(evidenceFileCount || currentEvidenceRefs.length || 0) === 1 ? '' : 's'} summarized.`,
    ],
    what_changed: ['Opening the evidence summary did not change the device.'],
    what_did_not_happen: [
      'Raw evidence was not loaded into the normal UI.',
      'Raw scanner output was not shown.',
      'Secrets, tokens, private paths, and backend command payloads stay hidden.',
    ],
    saved_for_troubleshooting: {
      saved: Boolean(latestEvidenceReceipt || evidenceReceipt || currentEvidenceRefs.length),
      backend_only: true,
      summary: 'Sanitized evidence metadata is shown here. Full backend evidence remains protected.',
    },
    next_step: latestEvidenceReceipt || evidenceReceipt ? 'Use this summary for support or audit review without exposing secrets.' : 'Run Safety Check to create fresh evidence.',
    technicalDetails: [
      { label: 'Latest run', value: shortId(lastRun?.run_id || evidenceReceipt?.run_id) || 'not available' },
      { label: 'Evidence files', value: Number(evidenceFileCount || currentEvidenceRefs.length || 0) },
      { label: 'SBOM', value: sbomSaved ? 'Saved' : 'Not saved' },
      { label: 'Sanitization', value: 'Secrets hidden before display' },
    ],
    history: {
      title: 'Evidence files',
      summary: currentEvidenceRefs.length ? `${currentEvidenceRefs.length} sanitized evidence reference${currentEvidenceRefs.length === 1 ? '' : 's'} available.` : 'Evidence references will appear after a check completes.',
      items: evidenceRows(currentEvidenceRefs).map((title, index) => ({ id: `evidence-${index}`, title, meta: 'sanitized reference' })),
      enabled: true,
      emptyMessage: 'Evidence references will appear after a check completes.',
    },
  };
}

export default function SecurityProgressiveDetailsLazy({ type = 'evidence', model = {}, onClose }) {
  const details = buildDetails({ type, model });
  const detailsHydrated = Boolean(model?.detailsHydrated);
  const detailsHydration = model?.detailsHydration && typeof model.detailsHydration === 'object'
    ? model.detailsHydration
    : {};
  const securityDetailsMotionReduced = useReducedMotionPreference();
  const detailsPanelSpring = useSpring({
    from: { opacity: 0, y: securityDetailsMotionReduced ? 0 : 12, scale: securityDetailsMotionReduced ? 1 : 0.985 },
    to: { opacity: 1, y: 0, scale: 1 },
    config: { tension: 260, friction: 28, mass: 0.9 },
    immediate: securityDetailsMotionReduced,
  });
  const detailsContentSpring = useSpring({
    from: { opacity: 0, y: securityDetailsMotionReduced ? 0 : 8 },
    to: { opacity: 1, y: 0 },
    delay: securityDetailsMotionReduced ? 0 : 70,
    config: { tension: 240, friction: 30, mass: 0.8 },
    immediate: securityDetailsMotionReduced,
  });

  return (
    <animated.section
      className={`lite-security-phase2-details-panel lite-security-details-premium-panel is-${details.status || 'neutral'}`}
      role="region"
      aria-label={`${details.title} details`}
      data-security-phase2-progressive-details="true"
      data-security-react-spring="details-panel"
      data-security-progressive-details-hydrated={detailsHydrated ? 'true' : 'false'}
      data-security-progressive-details-type={safeText(detailsHydration?.type || type, 'evidence')}
      style={detailsPanelSpring}
    >
      <div className="lite-security-phase2-details-head lite-security-details-premium-head">
        <div>
          <span>Progressive details</span>
          <h2>{details.title}</h2>
          <p>Summary first. Technical details stay collapsed and sanitized.</p>
        </div>
        <button type="button" className="lite-finding-detail-close" onClick={onClose} aria-label="Close Security details">
          <X className="h-4 w-4" />
        </button>
      </div>
      <animated.div className="lite-security-details-premium-content" data-security-react-spring="details-content" style={detailsContentSpring}>
        <LiteProgressiveDetails
          {...details}
          history={type === 'history' ? {
            ...details.history,
            title: details.history?.title || 'History',
            summary: details.history?.summary || 'Open saved checks and load older history when needed.',
            items: [],
            children: (
              <React.Suspense fallback={<div className="lite-security-details-loading">Loading saved history…</div>}>
                <SecurityHistoryLazy
                  history={model?.securityHistory || []}
                  initialPage={model?.securityHistoryPage || null}
                  latestScore={model?.safetyScore}
                  trendLabel={model?.scoreTrendView?.label || ''}
                  trendDetail={model?.scoreTrendView?.detail || ''}
                  savedStateOnly={Boolean(model?.savedStateOnly)}
                />
              </React.Suspense>
            ),
          } : details.history}
        />
      </animated.div>
    </animated.section>
  );
}
