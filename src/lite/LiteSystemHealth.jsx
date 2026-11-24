import React, { useEffect, useMemo, useState } from 'react';
import { Activity, AlertTriangle, ArrowLeft, BookOpen, ChevronRight, ClipboardCheck,
  Clock3, Cpu, GitBranch, HeartPulse, Info, ListChecks, RefreshCw, Settings2, ShieldCheck, Wrench } from 'lucide-react';
import { useLiteQuery } from '../hooks/useLiteQuery.js';
import { liteApi } from '../lib/liteApi.js';
import { liteQueryKeys } from '../lib/liteQueryClient.js';
import { GlassCard, LiteButton, LiteRefreshButton, LiteActionRow, PageHeader, StateSurface } from './LiteUi.jsx';
import { LiteDetailsPanel } from './LiteOverlay.jsx';
import { useDesktopManageGeometry } from './components/useDesktopManageGeometry.js';
import { useLitePanelSectionNavigation } from './hooks/useLitePanelSectionNavigation.js';
import HomeGroupedSections from './components/HomeGroupedSections.jsx';
import './components/azureHome.css';
import './components/homeCommand.css';
import { componentLabel, safeTechnicalIdentifier, healthStatusLabel, healthTimestamp, healthCounts, groupHealthIncidents, incidentEvidenceState, recoveryDestination, recoveryOperationLabel, recoveryAvailabilityLabel, recoveryLifecycleLabel, INCIDENT_STATE_LABELS, systemHealthPresentation } from './systemHealthPresentation.js';
import './systemHealth.css';

const SECTIONS = Object.freeze([
  { label: 'Overview', items: [
    { id: 'overview', label: 'Health overview', description: 'Freshness and what deserves attention', icon: HeartPulse },
  ] },
  { label: 'Problems & Diagnosis', items: [
    { id: 'incidents', label: 'Problems & Diagnosis', description: 'Current and saved concerns', icon: AlertTriangle },
    { id: 'diagnostics', label: 'Issue details', description: 'What happened and what to review next', icon: ClipboardCheck },
  ] },
  { label: 'Recovery & History', items: [
    { id: 'history', label: 'Recovery & History', description: 'Observed outcomes and recorded attempts', icon: Clock3 },
    { id: 'repairs', label: 'Recovery options', description: 'Existing, controlled recovery paths', icon: Wrench },
  ] },
  { label: 'Advanced Diagnostics', items: [
    { id: 'dependencies', label: 'Dependencies', description: 'Documented service relationships', icon: GitBranch },
    { id: 'resources', label: 'Resource signals', description: 'Saved device and storage signals', icon: Cpu },
    { id: 'policies', label: 'Repair policies', description: 'Authorization and availability', icon: ShieldCheck },
    { id: 'drift', label: 'Configuration review', description: 'Observed states, not automatic changes', icon: Settings2 },
    { id: 'details', label: 'Technical details', description: 'Sanitized diagnostic metadata', icon: Settings2 },
  ] },
]);
export const SYSTEM_HEALTH_SUMMARY_QUERY_OPTIONS = Object.freeze({
  staleTime: 90_000,
  pollingMode: 'relaxed',
  refetchOnWindowFocus: false,
  // A saved safe-read is useful for continuity, but it must not suppress the
  // first live revalidation when this screen mounts again.
  refetchOnMount: 'always',
});
export { systemHealthPresentation };

export function SystemHealthIncidentCard({ incident, onDiagnose, onRecover, recovering = false, saved = false }) {
  const evidenceState = incidentEvidenceState(incident, saved);
  const older = evidenceState !== 'current';
  return <GlassCard as="article" className="lite-system-health-incident" data-health-incident={incident.incident_id}
    data-health-concern={evidenceState}>
    <div className="lite-system-health-incident-head">
      <span className="lite-system-health-health-icon"><AlertTriangle size={19} aria-hidden="true" /></span>
      <div>
        <h3>{componentLabel(incident.source, incident.target_id, incident.device_label)}</h3>
        <p>{older ? 'A previous concern was recorded; the current condition is not confirmed.' : (incident.summary || 'A current observation needs review.')}</p>
      </div>
      <span className={'lite-system-health-state is-' + (older ? 'unknown' : incident.severity === 'critical' ? 'attention' : 'watch')}>
        {older ? 'Recheck needed' : incident.severity === 'critical' ? 'Critical' : 'Review needed'}
      </span>
    </div>
    <p className="lite-system-health-muted">
      {older ? 'Saved concern · Last reported ' : 'Current observation · Last reported '}
      {healthTimestamp(incident.last_seen_at)}
    </p>
    <div className="lite-system-health-actions">
      <LiteButton haptic tone="secondary" onClick={() => onDiagnose(incident)}>Review issue</LiteButton>
      {incident.repair_available && onRecover ? <LiteButton haptic tone="primary" disabled={recovering} busy={recovering}
        onClick={() => onRecover(incident)}>Review recovery</LiteButton> : null}
    </div>
  </GlassCard>;
}

function EvidenceRows({ rows = [], emptyMessage = 'No authoritative records are available for this view.', onHistory }) {
  return Array.isArray(rows) && rows.length
    ? rows.slice(0, 30).map((row, i) => <LiteActionRow key={row.incident_id || row.target_id || i}
      label={componentLabel(row.source, row.target_id || row.component, row.device_label)}
      value={row.membership_state === 'removed' || row.membership_state === 'retired' ? 'Device removed — historical record' : row.current_monitoring === false ? 'Membership not confirmed — historical record' : row.state ? (INCIDENT_STATE_LABELS[row.state] || healthStatusLabel(row.state)) : healthStatusLabel(row.status || row.observed_status)}
      summary={row.current_monitoring === false ? 'No longer monitored. Earlier evidence is retained; removal is not recovery.' : row.summary || ''}
      action={onHistory && row.incident_id ? { label: 'View history', haptic: true, onClick: () => onHistory(row) } : undefined}
      attention={row.status === 'unavailable' || row.state === 'failed'} />)
    : <StateSurface tone="empty" title="Nothing recorded" description={emptyMessage} />;
}

function DetailContent({ incident, diagnosis, diagnosing, diagnosisError, onDiagnose, onRecover, recovering = false,
  recoveryState = 'idle', recoveryError = '', recoveryRequest = null, onOpenArea, decisions, readOnly = false }) {
  if (!incident) return <StateSurface tone="empty" title="Choose a problem" description="Select a concern to review what was observed and what to do next." />;
  const evidenceState = incidentEvidenceState(incident, readOnly);
  const isCurrent = evidenceState === 'current';
  const historical = evidenceState === 'historical';
  const destination = historical ? null : recoveryDestination(incident.source);
  const verifiedCause = typeof diagnosis?.verified_cause === 'string' && diagnosis.verified_cause
    ? diagnosis.verified_cause : null;
  return <section className="lite-system-health-detail" aria-label="Problem details">
    <h3>{componentLabel(incident.source, incident.target_id, incident.device_label)}</h3>
    <span className={'lite-system-health-state is-' + (isCurrent ? 'watch' : 'unknown')}>
      {historical ? (incident.membership_state === 'unknown' ? 'Membership not confirmed' : 'Device removed — historical record') : isCurrent ? 'Current concern' : evidenceState === 'resolved' ? 'Observed healthy' : 'Saved concern'}
    </span>
    <div className="lite-system-health-detail-block">
      <h4>What happened</h4>
      <p>{incident.summary || 'A saved health observation was recorded.'}</p>
    </div>
    <div className="lite-system-health-detail-block">
      <h4>What we know</h4>
      <p>{historical ? 'This record is not a current recovery target. Earlier incident evidence is retained.' : isCurrent ? 'The latest matching observation reports an unhealthy state.' :
        evidenceState === 'resolved' ? 'A subsequent healthy observation was recorded. That does not establish a completed repair.' :
          'The previous concern remains unresolved; the current condition needs revalidation.'}</p>
      <p className="lite-system-health-muted">Last reported {healthTimestamp(incident.last_seen_at)} · {INCIDENT_STATE_LABELS[incident.state] || 'Status not confirmed'}</p>
    </div>
    <div className="lite-system-health-detail-block">
      <h4>Cause assessment</h4>
      {verifiedCause ? <p>Verified cause: {verifiedCause}</p> :
        diagnosis?.cause_confidence === 'inferred'
          ? <p>Possible contributing factor: {diagnosis.suspected_cause || 'Not established'}. This is not a verified root cause.</p>
          : <p>No verified root cause has been established.</p>}
    </div>
    {diagnosisError ? <StateSurface tone="degraded" title="Diagnosis unavailable" description="Pocket Lab could not record a current cause assessment." /> : null}
    {recoveryError ? <StateSurface tone="degraded" title="Recovery request unavailable" description={recoveryError} /> : null}
    {diagnosis?.supporting_signals?.length ? <details className="lite-system-health-disclosure">
      <summary>Supporting observations</summary>
      <EvidenceRows rows={diagnosis.supporting_signals} />
    </details> : null}
    <div className="lite-system-health-detail-block">
      <h4>Recommended next step</h4>
      <p>{historical ? 'Review the earlier record. Device removal does not establish a successful recovery.' : isCurrent ? 'Check the cause or review the component in its existing protected controls.' :
        'Review a fresh status before requesting any recovery action.'}</p>
    </div>
    <div className="lite-system-health-detail-block" aria-label="Recovery status">
      <h4>Recovery</h4>
      {recoveryState !== 'idle' ? <p role="status">{recoveryLifecycleLabel(recoveryState)}{recoveryRequest?.summary ? ` — ${recoveryRequest.summary}` : ''}</p> : null}
      {historical ? <p className="lite-system-health-muted">Historical records are read-only. They cannot submit recovery.</p> :
        incident.repair_available && isCurrent && !readOnly ? <LiteButton haptic tone="primary" disabled={recovering} busy={recovering}
          onClick={() => onRecover(incident)}>{recoveryState === 'idle' ? 'Review recovery' : 'Check recovery status'}</LiteButton> :
          <p className="lite-system-health-muted">Recovery is not enabled for this evidence or candidate. Existing protected controls remain authoritative.</p>}
    </div>
    <div className="lite-system-health-actions">
      {!historical && <LiteButton haptic disabled={diagnosing || !isCurrent || readOnly} busy={diagnosing}
        disabledReason={!isCurrent || readOnly ? 'Current evidence is required' : ''} onClick={onDiagnose} tone="primary">Check cause</LiteButton>}
      {destination && onOpenArea ? <LiteButton haptic tone="secondary" onClick={() => onOpenArea(destination)}>
        {destination === 'devices' ? 'Open device controls' : destination === 'catalog' ? 'Open app controls' :
          destination === 'recovery' ? 'Review recovery options' : 'Open safety controls'}
      </LiteButton> : null}
    </div>
    {historical && <section className="lite-system-health-detail-block" aria-label="Earlier evidence">
      <h4>Earlier evidence</h4>
      <p className="lite-system-health-muted">Removal and recovery are separate events. Only recorded outcomes are shown.</p>
      {(decisions?.removal_receipts || []).map((receipt) => <LiteActionRow key={receipt.receipt_id}
        label="Device removal recorded" value={healthTimestamp(receipt.created_at)} />)}
      {(decisions?.diagnoses || []).map((entry) => <LiteActionRow key={entry.diagnosis_id}
        label="Earlier cause assessment" value={healthTimestamp(entry.created_at)} summary={entry.suspected_cause || 'Not established'} />)}
      {(decisions?.repair_denials || []).map((entry) => <LiteActionRow key={entry.denial_id}
        label="Recovery blocked" value={healthTimestamp(entry.denied_at)} summary={entry.safe_summary} />)}
      {(decisions?.repairs || []).map((entry) => <LiteActionRow key={entry.repair_id}
        label={recoveryOperationLabel(entry.operation_id)}
        value={entry.execution_state === 'completed' && entry.verification_state === 'verified' ? 'Recovery verified' : 'Outcome not verified'}
        summary={entry.safe_summary} />)}
      {!decisions && <p className="lite-system-health-muted">Earlier decisions are not available yet.</p>}
    </section>}
    <details className="lite-system-health-disclosure">
      <summary>Advanced technical details</summary>
      <dl className="lite-system-health-tech-facts">
        <div><dt>Incident ID</dt><dd>{safeTechnicalIdentifier(incident.incident_id)}</dd></div>
        <div><dt>Source</dt><dd>{safeTechnicalIdentifier(incident.source)}</dd></div>
        <div><dt>Target ID</dt><dd>{safeTechnicalIdentifier(incident.target_id)}</dd></div>
        <div><dt>Generation</dt><dd>{incident.generation}</dd></div>
        {historical && incident.membership_retired_at && <div><dt>Enrollment ended</dt><dd>{healthTimestamp(incident.membership_retired_at)}</dd></div>}
        <div><dt>Evidence revision</dt><dd>{safeTechnicalIdentifier(String(incident.evidence_revision || ''))}</dd></div>
        <div><dt>Observation freshness</dt><dd>{healthStatusLabel(incident.observation_freshness || incident.evidence_freshness)}</dd></div>
      </dl>
    </details>
    <p className="lite-system-health-muted">Only sanitized metadata is displayed. Recovery requests are authorized by FastAPI and executed only by the existing worker recovery owner; this view never runs shell commands.</p>
  </section>;
}

export default function LiteSystemHealth({ onNavigate }) {
  const [open, setOpen] = useState(false);
  const [section, setSection] = useState(null);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [diagnosis, setDiagnosis] = useState(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnosisError, setDiagnosisError] = useState(false);
  const [recoveryState, setRecoveryState] = useState('idle');
  const [recoveryError, setRecoveryError] = useState('');
  const [recoveryRequest, setRecoveryRequest] = useState(null);
  const [recovering, setRecovering] = useState(false);
  const geometry = useDesktopManageGeometry({ open, defaultWidth: 680, minWidth: 380, minHeight: 360 });
  const navigation = useLitePanelSectionNavigation(open);
  const summaryQuery = useLiteQuery({
    queryKey: liteQueryKeys.healthIntelligence(), path: '/api/lite/system-health/summary',
    queryFn: liteApi.healthIntelligenceSummary, ...SYSTEM_HEALTH_SUMMARY_QUERY_OPTIONS,
  });
  const incidentsQuery = useLiteQuery({
    queryKey: liteQueryKeys.healthIncidents(), path: '/api/lite/system-health/incidents',
    queryFn: liteApi.healthIntelligenceIncidents, enabled: !summaryQuery.savedStateOnly && summaryQuery.backendReachable !== false,
    staleTime: 90_000, pollingMode: 'relaxed', refetchOnMount: 'always',
  });
  const history = useLiteQuery({
    queryKey: liteQueryKeys.healthHistory(), path: '/api/lite/system-health/history',
    queryFn: liteApi.healthIntelligenceHistory, enabled: open && section === 'history',
    staleTime: 120_000, pollingMode: 'relaxed',
  });
  const dependencies = useLiteQuery({
    queryKey: liteQueryKeys.healthDependencies(), path: '/api/lite/system-health/dependencies',
    queryFn: liteApi.healthIntelligenceDependencies, enabled: open && section === 'dependencies',
    staleTime: 120_000, pollingMode: 'relaxed',
  });
  const resources = useLiteQuery({
    queryKey: ['lite', 'system-health', 'resources'], path: '/api/lite/system-health/resources',
    queryFn: liteApi.healthIntelligenceResources, enabled: open && section === 'resources',
    staleTime: 120_000, pollingMode: 'relaxed',
  });
  const drift = useLiteQuery({
    queryKey: ['lite', 'system-health', 'configuration-drift'],
    path: '/api/lite/system-health/configuration-drift',
    queryFn: liteApi.healthIntelligenceDrift, enabled: open && section === 'drift',
    staleTime: 120_000, pollingMode: 'relaxed',
  });
  const intelligence = useLiteQuery({
    queryKey: ['lite', 'system-health', 'knowledge'], path: '/api/lite/system-health/intelligence',
    queryFn: liteApi.healthIntelligenceKnowledge, enabled: open && section === 'details',
    staleTime: 120_000, pollingMode: 'relaxed',
  });
  const policies = useLiteQuery({
    queryKey: ['lite', 'system-health', 'policies'], path: '/api/lite/system-health/policies',
    queryFn: liteApi.healthIntelligencePolicies, enabled: open && (section === 'policies' || section === 'repairs'),
    staleTime: 120_000, pollingMode: 'relaxed',
  });
  const current = useMemo(() => systemHealthPresentation(summaryQuery.data, summaryQuery.savedStateOnly || summaryQuery.backendReachable === false), [summaryQuery.data, summaryQuery.savedStateOnly, summaryQuery.backendReachable]);
  const items = Array.isArray(incidentsQuery.data?.items) ? incidentsQuery.data.items : [];
  const readOnly = summaryQuery.savedStateOnly || summaryQuery.backendReachable === false;
  const groups = useMemo(() => groupHealthIncidents(items, readOnly), [items, readOnly]);
  const counts = healthCounts(summaryQuery.data, groups, readOnly);
  const selectedQuery = useLiteQuery({
    queryKey: ['lite', 'system-health', 'incident', selectedIncident],
    path: selectedIncident ? '/api/lite/system-health/incidents/' + selectedIncident : '/api/lite/system-health/incidents',
    queryFn: () => liteApi.healthIntelligenceIncident(selectedIncident),
    enabled: open && Boolean(selectedIncident) && !readOnly,
    staleTime: 90_000, pollingMode: 'relaxed',
  });
  const selected = (selectedQuery.data?.incident_id === selectedIncident ? selectedQuery.data : null) || items.find((item) => item.incident_id === selectedIncident) || (history.data?.items || []).find((item) => item.incident_id === selectedIncident) || null;
  const decisions = useLiteQuery({
    queryKey: ['lite', 'system-health', 'decisions', selectedIncident],
    path: selectedIncident ? '/api/lite/system-health/incidents/' + selectedIncident + '/decisions' : '/api/lite/system-health/incidents',
    queryFn: () => liteApi.healthIntelligenceDecisions(selectedIncident),
    enabled: open && section === 'diagnostics' && Boolean(selectedIncident) && !readOnly,
    staleTime: 120_000, pollingMode: 'off',
  });

  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get('incident');
    if (id && /^health-[a-f0-9]{24}$/.test(id)) {
      setSelectedIncident(id);
      setSection('diagnostics');
      setOpen(true);
    }
  }, []);

  const viewIncident = (item, nextSection = 'diagnostics') => {
    setSelectedIncident(item.incident_id);
    setDiagnosis(null);
    setDiagnosisError(false);
    setRecoveryState('idle');
    setRecoveryError('');
    setRecoveryRequest(null);
    setSection(nextSection);
    setOpen(true);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.set('screen', 'system-health');
      url.searchParams.set('incident', item.incident_id);
      window.history.replaceState({ ...window.history.state, pocketLabLiteScreen: 'system-health' }, '', url.pathname + url.search);
    }
  };
  const diagnose = async (item = selected) => {
    if (!item || diagnosing || readOnly || incidentEvidenceState(item) !== 'current') return;
    setDiagnosing(true); setDiagnosisError(false);
    try { setDiagnosis(await liteApi.healthIntelligenceDiagnose(item.incident_id)); }
    catch { setDiagnosisError(true); setDiagnosis(null); }
    finally { setDiagnosing(false); }
  };
  const recover = async (item = selected) => {
    if (!item || recovering || readOnly || incidentEvidenceState(item) !== 'current' || !item.repair_available) return;
    setRecovering(true); setRecoveryError(''); setRecoveryState('preflight_checked');
    const idempotencyKey = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? crypto.randomUUID() : `system-health-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    const body = { operation_id: 'runtime.consumer.reconnect', expected_generation: Number(item.generation), idempotency_key: idempotencyKey, confirm: false };
    try {
      const preflight = await liteApi.healthIntelligencePreflight(item.incident_id, body);
      if (!preflight?.allowed) {
        setRecoveryState(preflight?.status || 'blocked');
        setRecoveryError('Recovery is not currently eligible. Review the latest evidence before trying again.');
        return;
      }
      setRecoveryState('admitted');
      const result = await liteApi.healthIntelligenceRepair(item.incident_id, body);
      const request = result?.request || result?.detail?.request || null;
      setRecoveryRequest(request);
      setRecoveryState(result?.status || request?.status || 'admitted');
      if (request?.request_id) {
        const terminal = new Set(['verified', 'execution_failed', 'verification_failed', 'verification_unavailable', 'manual_attention_required', 'blocked', 'expired', 'cancelled']);
        for (let attempt = 0; attempt < 45; attempt += 1) {
          let decisionSnapshot;
          try {
            decisionSnapshot = await liteApi.healthIntelligenceDecisions(item.incident_id);
          } catch {
            // A lost read must not become a false failure or false success. Keep
            // the durable request at its last confirmed lifecycle state.
            break;
          }
          const latest = (decisionSnapshot?.recovery_requests || []).find((entry) => entry?.request_id === request.request_id);
          if (latest) {
            setRecoveryRequest(latest);
            setRecoveryState(latest.status || 'admitted');
            if (terminal.has(latest.status)) break;
          }
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
      await Promise.all([summaryQuery.refresh(), incidentsQuery.refresh(), history.refresh?.() || Promise.resolve()]);
    } catch (error) {
      const payload = error?.payload?.detail || error?.payload || {};
      const status = payload?.status || payload?.request?.status || 'execution_failed';
      setRecoveryState(status);
      setRecoveryRequest(payload?.request || null);
      setRecoveryError(status === 'approval_required'
        ? 'Independent approval is required before the worker can accept this recovery.'
        : 'The recovery request was not completed. No success is shown without fresh verification.');
    } finally { setRecovering(false); }
  };
  const close = () => {
    setOpen(false);
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.searchParams.delete('incident');
      window.history.replaceState({ ...window.history.state }, '', url.pathname + url.search);
    }
  };
  return <div className="lite-system-health-page" data-system-health-page="true">
    <PageHeader eyebrow="Self-hosted workspace" title="System Health" description="Your workspace health — what needs attention and what to do next."
      actions={<LiteRefreshButton haptic scope="system-health" refresh={() => { summaryQuery.refresh(); incidentsQuery.refresh(); }}
        refreshing={summaryQuery.refreshing || incidentsQuery.refreshing} error={summaryQuery.error} cacheStatus={summaryQuery.cacheStatus} />} />
    <GlassCard as="section" className={'lite-system-health-hero is-' + current.state} aria-label="System Health overview"
      data-health-overview={current.state}>
      <span className="lite-system-health-kicker"><HeartPulse size={19} aria-hidden="true" /> Health overview</span>
      <h2>{current.title}</h2><p>{current.detail}</p>
      <div className="lite-system-health-metrics" aria-label="Health evidence counts">
        <div><strong>{counts.healthy}</strong><span>Healthy signals</span></div>
        <div><strong>{counts.current}</strong><span>Current concerns</span></div>
        <div><strong>{counts.saved}</strong><span>Older unresolved records</span></div>
      </div>
      <p className="lite-system-health-muted" role="status">
        {current.state === 'saved' ? 'Saved information only · Live state not confirmed.' :
          summaryQuery.data?.freshness === 'current' ? 'Based on recent persisted backend observations.' :
            'Current observations are not sufficient to confirm health.'}
      </p>
    </GlassCard>
    <section className="lite-system-health-problems" aria-label="Current System Health concerns">
      <div className="lite-system-health-section-head"><h2>What needs attention</h2><span>{typeof counts.current === 'number' ? counts.current + ' current' : 'Not confirmed'}</span></div>
      {incidentsQuery.error ? <StateSurface tone="degraded" title="Concerns unavailable" description="Pocket Lab could not load incident records." /> :
        !incidentsQuery.data && incidentsQuery.loading ? <StateSurface tone="empty" title="Loading health records" description="Reading persisted health observations." /> :
        groups.current.length ? groups.current.slice(0, 4).map(item => <SystemHealthIncidentCard key={item.incident_id} incident={item}
          onDiagnose={viewIncident} onRecover={recover} recovering={recovering} />) :
        <StateSurface tone="empty" title={current.state === 'ready' ? 'No current concerns observed' : 'No current concern confirmed'}
          description={current.state === 'ready' ? 'Recent observations are healthy; this does not confirm a repair.'
            : 'Saved concerns and unknown health are reviewed separately. No current issue is confirmed here.'} />}
      {groups.current.length > 4 ? <LiteButton haptic tone="secondary" onClick={() => { setSection('incidents'); setOpen(true); }}>
        Review more concerns</LiteButton> : null}
    </section>
    {(groups.saved.length > 0 || counts.saved > 0 || current.state === 'saved') && <GlassCard as="section" className="lite-system-health-history-preview"
      data-health-saved-preview="true">
      <div className="lite-system-health-section-head"><h2>Earlier observations</h2><Clock3 size={19} aria-hidden="true" /></div>
      <p>{typeof counts.saved === 'number' && counts.saved > 0 ? counts.saved + ' unresolved record(s) need a fresh check.' :
        'Previously saved information is available. Current conditions have not been confirmed.'}</p>
      <LiteButton haptic tone="secondary" onClick={() => { setSection('incidents'); setOpen(true); }}>Review saved concerns <ChevronRight size={16} aria-hidden="true" /></LiteButton>
    </GlassCard>}
    <GlassCard as="section" className="lite-system-health-history-preview">
      <div className="lite-system-health-section-head"><h2>Recovery &amp; History</h2><Clock3 size={19} aria-hidden="true" /></div>
      <p>{summaryQuery.data?.recent_resolutions?.length
        ? 'Earlier problems were observed healthy. A healthy observation alone does not prove that a repair succeeded.'
        : 'Review recorded recovery activity and available history. No unverified repair is presented as successful.'}</p>
      <LiteButton haptic tone="secondary" onClick={() => { setSection('history'); setOpen(true); }}>Review history <ChevronRight size={16} aria-hidden="true" /></LiteButton>
    </GlassCard>
    <LiteButton haptic tone="primary" className="lite-system-health-manage-button" onClick={() => { setSection(null); setOpen(true); }}>Manage System Health</LiteButton>
    <LiteDetailsPanel open={open} onClose={close} variant="home" className="lite-home-details-panel lite-system-health-manage" desktopGeometry={geometry} mobileSnap hapticNavigation bodyRef={navigation.bodyRef}
      bodyClassName="lite-home-workspace-details-scroll lite-home-panel-scroll" title="System Health Manage"
      description="Current evidence, diagnosis and reviewed recovery paths.">
      <HomeGroupedSections groups={SECTIONS} section={section} defaultSection="overview" onSectionChange={setSection}
        navigation={navigation} title="System Health" haptic>
        {(!section || section === 'overview') ? <section className="lite-system-health-manage-section" aria-label="Health overview details">
          <div className="lite-system-health-manage-intro"><h3>{current.title}</h3><p>{current.detail}</p></div>
          <LiteActionRow label="Current concerns" value={String(counts.current)} summary="Supported by recent observations only." />
          <LiteActionRow label="Saved unresolved concerns" value={String(counts.saved)} summary="Still unresolved, but not currently confirmed." />
          <LiteActionRow label="Healthy observations" value={String(counts.healthy)} />
          <LiteActionRow label="Evidence freshness" value={summaryQuery.data?.freshness === 'current' ? 'Recent' :
            summaryQuery.data?.freshness === 'stale' ? 'Saved' : 'Not confirmed'} />
          <p className="lite-system-health-muted">Historical concerns are never silently treated as resolved. This view does not run repairs.</p>
        </section> : null}
        {section === 'incidents' ? <section className="lite-system-health-manage-section">
          <h3>Current confirmed concerns</h3>
          {groups.current.length ? groups.current.slice(0, 30).map(item => <LiteActionRow key={item.incident_id}
            label={componentLabel(item.source, item.target_id, item.device_label)} value={item.severity === 'critical' ? 'Critical' : 'Review needed'}
            summary={item.summary || 'Current evidence needs review.'} action={{ label: 'Review issue', haptic: true, onClick: () => viewIncident(item, 'diagnostics') }} />)
            : <StateSurface tone="empty" title="No current concern confirmed" description="Unknown and saved evidence are not treated as current problems." />}
          <h3>Saved concerns requiring revalidation</h3>
          <p className="lite-system-health-muted">These records are unresolved, but their current condition is not confirmed. Review a fresh status before recovery.</p>
          {groups.saved.length ? groups.saved.slice(0, 30).map(item => <LiteActionRow key={item.incident_id}
            label={componentLabel(item.source, item.target_id, item.device_label)} value="Recheck needed"
            summary={item.summary || 'A previous concern is recorded.'}
            action={{ label: 'Review issue', haptic: true, onClick: () => viewIncident(item, 'diagnostics') }} />)
            : <p className="lite-system-health-muted">No older unresolved records in the loaded page.</p>}
          {incidentsQuery.data?.next_offset != null ? <p className="lite-system-health-muted">Additional historical records exist. Use the bounded history view for more records.</p> : null}
        </section> : null}
        {section === 'diagnostics' ? <DetailContent incident={selected} diagnosis={diagnosis} diagnosing={diagnosing} diagnosisError={diagnosisError}
          onDiagnose={() => diagnose(selected)} onRecover={() => recover(selected)} recovering={recovering}
          recoveryState={recoveryState} recoveryError={recoveryError} recoveryRequest={recoveryRequest}
          decisions={decisions.data} readOnly={readOnly} onOpenArea={onNavigate ? (destination) => { close(); onNavigate(destination); } : null} /> : null}
        {section === 'repairs' ? <section className="lite-system-health-manage-section">
          <p className="lite-system-health-muted">Existing supervisors and the worker recovery watchdog own execution. The qualified System Health adapter is candidate-only and remains disabled by default; no button can bypass backend authorization.</p>
          {(policies.data?.repair_catalog || []).map((item) => <LiteActionRow key={item.operation_id}
            label={recoveryOperationLabel(item.operation_id)}
            value={recoveryAvailabilityLabel(item.availability)}
            summary={item.availability === 'guided_existing_flow' ? 'Review the existing controls and their current eligibility.' :
              item.availability === 'externally_managed' ? 'Managed by an existing guardian; this button does not execute a repair.' :
                item.availability === 'never_automatic' ? 'Use the protected preview and confirmation workflow.' :
                  'No action is currently available.'} />)}
        </section> : null}
        {section === 'history' ? <section className="lite-system-health-manage-section">
          <h3>Previous observations</h3>
          <p className="lite-system-health-muted">Removed-device records remain available here without being treated as active problems or successful repairs.</p>
          <EvidenceRows rows={history.data?.items || []} onHistory={(item) => viewIncident(item, 'diagnostics')} emptyMessage="No previous incident records are available." />
          <h3>Recorded repair attempts</h3>
          {(history.data?.repairs || []).length ? history.data.repairs.slice(0, 30).map((item, i) =>
            <LiteActionRow key={item.repair_id || i} label={recoveryOperationLabel(item.operation_id)}
              value={item.execution_state === 'failed' ? 'Repair failed' : item.execution_state === 'blocked' ? 'Repair blocked' :
                item.verification_state === 'verified' && item.execution_state === 'completed' ? 'Repair verified' :
                  'Outcome not verified'}
              summary={item.safe_summary || 'Recorded attempt. Execution and verification must be independently confirmed.'} />)
            : <p className="lite-system-health-muted">No verified System Health repair attempts are recorded.</p>}
          {(history.data?.recovery_requests || []).length ? history.data.recovery_requests.slice(0, 30).map((item) =>
            <LiteActionRow key={item.request_id} label="Governed recovery request"
              value={recoveryLifecycleLabel(item.status)} summary={item.safe_summary || 'Execution and verification remain backend-owned.'} />) : null}
        </section> : null}
        {section === 'dependencies' ? <section className="lite-system-health-manage-section">
          <p className="lite-system-health-muted">These relationships describe documented dependencies, not proof of live connectivity. Previously removed devices are excluded from current monitoring.</p>
          {(dependencies.data?.edges || []).map((edge, i) => <LiteActionRow key={i}
            label={componentLabel(edge.upstream, edge.upstream) + ' → ' + componentLabel(edge.downstream, edge.downstream)}
            value={edge.authority === 'verified_contract' ? 'Documented relationship' : 'Possible relationship'}
            summary={edge.summary} />)}
          <EvidenceRows rows={dependencies.data?.nodes || []} />
        </section> : null}
        {section === 'resources' ? <section className="lite-system-health-manage-section">
          <p className="lite-system-health-muted">A reliable trend forecast is not available from this evidence.</p>
          <EvidenceRows rows={resources.data?.signals || []} />
        </section> : null}
        {section === 'policies' ? <section className="lite-system-health-manage-section">
          <LiteActionRow label="Automatic recovery" value="Existing guardians only" summary="No new System Health automatic operation is enabled." />
          <LiteActionRow label="Sensitive operations" value="Protected" summary="Data restoration and identity changes require governed steps." />
          {(policies.data?.repair_catalog || []).map(item => <LiteActionRow key={item.operation_id}
            label={recoveryOperationLabel(item.operation_id)} value={recoveryAvailabilityLabel(item.availability)} />)}
        </section> : null}
        {section === 'drift' ? <section className="lite-system-health-manage-section">
          <p className="lite-system-health-muted">A mismatch in observed process state does not prove configuration drift or authorize changing settings.</p>
          <EvidenceRows rows={(drift.data?.observations || []).map(item => ({ ...item, target_id: item.component, source: 'processes', status: item.observed_status }))} />
          <LiteActionRow label="Automatic configuration changes" value="Not available" summary="The runtime owner and authorization must approve any future repair." />
        </section> : null}
        {section === 'details' ? <section className="lite-system-health-manage-section">
          <LiteActionRow label="Cause assessment" value="Deterministic" />
          <LiteActionRow label="Cloud AI" value="Not required" summary="This experience relies on backend-owned observations." />
          <LiteActionRow label="Recurring components" value={String(intelligence.data?.recurring_components?.length ?? 'Not confirmed')} />
          <details className="lite-system-health-disclosure">
            <summary>Evidence and technical identifiers</summary>
            <p>Source IDs, incident generations and evidence revisions are retained in the backend and shown in individual issue details for troubleshooting.</p>
          </details>
          <p className="lite-system-health-muted">Raw evidence, logs, credentials and private paths remain backend-only.</p>
        </section> : null}
      </HomeGroupedSections>
    </LiteDetailsPanel>
  </div>;
}
