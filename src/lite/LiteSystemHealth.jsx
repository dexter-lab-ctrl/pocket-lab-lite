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
import { componentLabel, healthStatusLabel, healthTimestamp, healthCounts, groupHealthIncidents, incidentEvidenceState, recoveryDestination, recoveryOperationLabel, recoveryAvailabilityLabel, INCIDENT_STATE_LABELS, systemHealthPresentation } from './systemHealthPresentation.js';
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
export { systemHealthPresentation };

export function SystemHealthIncidentCard({ incident, onDiagnose, onDetails, saved = false }) {
  const evidenceState = incidentEvidenceState(incident, saved);
  const older = evidenceState !== 'current';
  return <GlassCard as="article" className="lite-system-health-incident" data-health-incident={incident.incident_id}
    data-health-concern={evidenceState}>
    <div className="lite-system-health-incident-head">
      <span className="lite-system-health-health-icon"><AlertTriangle size={19} aria-hidden="true" /></span>
      <div>
        <h3>{componentLabel(incident.source, incident.target_id)}</h3>
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
      <LiteButton haptic tone="secondary" onClick={() => onDetails(incident)}>View details</LiteButton>
    </div>
  </GlassCard>;
}

function EvidenceRows({ rows = [], emptyMessage = 'No authoritative records are available for this view.' }) {
  return Array.isArray(rows) && rows.length
    ? rows.slice(0, 30).map((row, i) => <LiteActionRow key={row.incident_id || row.target_id || i}
      label={componentLabel(row.source, row.target_id || row.component)}
      value={row.state ? (INCIDENT_STATE_LABELS[row.state] || healthStatusLabel(row.state)) : healthStatusLabel(row.status || row.observed_status)}
      summary={row.evidence_freshness === 'stale' || row.freshness === 'stale' || row.concern_state === 'saved_concern'
        ? 'Saved record. Check current conditions before acting.' : row.summary || ''}
      attention={row.status === 'unavailable' || row.state === 'failed'} />)
    : <StateSurface tone="empty" title="Nothing recorded" description={emptyMessage} />;
}

function DetailContent({ incident, diagnosis, diagnosing, diagnosisError, onDiagnose, onOpenArea, readOnly = false }) {
  if (!incident) return <StateSurface tone="empty" title="Choose a problem" description="Select a concern to review what was observed and what to do next." />;
  const evidenceState = incidentEvidenceState(incident, readOnly);
  const isCurrent = evidenceState === 'current';
  const destination = recoveryDestination(incident.source);
  const verifiedCause = typeof diagnosis?.verified_cause === 'string' && diagnosis.verified_cause
    ? diagnosis.verified_cause : null;
  return <section className="lite-system-health-detail" aria-label="Problem details">
    <h3>{componentLabel(incident.source, incident.target_id)}</h3>
    <span className={'lite-system-health-state is-' + (isCurrent ? 'watch' : 'unknown')}>
      {isCurrent ? 'Current concern' : evidenceState === 'resolved' ? 'Observed healthy' : 'Saved concern'}
    </span>
    <div className="lite-system-health-detail-block">
      <h4>What happened</h4>
      <p>{incident.summary || 'A saved health observation was recorded.'}</p>
    </div>
    <div className="lite-system-health-detail-block">
      <h4>What we know</h4>
      <p>{isCurrent ? 'The latest matching observation reports an unhealthy state.' :
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
    {diagnosis?.supporting_signals?.length ? <details className="lite-system-health-disclosure">
      <summary>Supporting observations</summary>
      <EvidenceRows rows={diagnosis.supporting_signals} />
    </details> : null}
    <div className="lite-system-health-detail-block">
      <h4>Recommended next step</h4>
      <p>{isCurrent ? 'Check the cause or review the component in its existing protected controls.' :
        'Review a fresh status before requesting any recovery action.'}</p>
    </div>
    <div className="lite-system-health-actions">
      <LiteButton haptic disabled={diagnosing || !isCurrent || readOnly} busy={diagnosing}
        disabledReason={!isCurrent || readOnly ? 'Current evidence is required' : ''} onClick={onDiagnose} tone="primary">Check cause</LiteButton>
      {destination && onOpenArea ? <LiteButton haptic tone="secondary" onClick={() => onOpenArea(destination)}>
        {destination === 'devices' ? 'Open device controls' : destination === 'catalog' ? 'Open app controls' :
          destination === 'recovery' ? 'Review recovery options' : 'Open safety controls'}
      </LiteButton> : null}
    </div>
    <details className="lite-system-health-disclosure">
      <summary>Advanced technical details</summary>
      <dl className="lite-system-health-tech-facts">
        <div><dt>Incident ID</dt><dd>{incident.incident_id}</dd></div>
        <div><dt>Source</dt><dd>{incident.source}</dd></div>
        <div><dt>Target ID</dt><dd>{incident.target_id}</dd></div>
        <div><dt>Generation</dt><dd>{incident.generation}</dd></div>
        <div><dt>Evidence revision</dt><dd>{incident.evidence_revision || 'Not available'}</dd></div>
        <div><dt>Observation freshness</dt><dd>{incident.observation_freshness || incident.evidence_freshness || 'Unknown'}</dd></div>
      </dl>
    </details>
    <p className="lite-system-health-muted">Only sanitized metadata is displayed. No repair executor is enabled here; checking a cause cannot restart a service, overwrite settings or restore data.</p>
  </section>;
}

export default function LiteSystemHealth({ onNavigate }) {
  const [open, setOpen] = useState(false);
  const [section, setSection] = useState(null);
  const [selectedIncident, setSelectedIncident] = useState(null);
  const [diagnosis, setDiagnosis] = useState(null);
  const [diagnosing, setDiagnosing] = useState(false);
  const [diagnosisError, setDiagnosisError] = useState(false);
  const geometry = useDesktopManageGeometry({ open, defaultWidth: 680, minWidth: 380, minHeight: 360 });
  const navigation = useLitePanelSectionNavigation(open);
  const summaryQuery = useLiteQuery({
    queryKey: liteQueryKeys.healthIntelligence(), path: '/api/lite/system-health/summary',
    queryFn: liteApi.healthIntelligenceSummary, staleTime: 90_000, pollingMode: 'relaxed', refetchOnWindowFocus: false,
  });
  const incidentsQuery = useLiteQuery({
    queryKey: liteQueryKeys.healthIncidents(), path: '/api/lite/system-health/incidents',
    queryFn: liteApi.healthIntelligenceIncidents, enabled: !summaryQuery.savedStateOnly && summaryQuery.backendReachable !== false,
    staleTime: 90_000, pollingMode: 'relaxed',
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
  const items = incidentsQuery.data?.items || [];
  const selected = items.find((item) => item.incident_id === selectedIncident) || null;

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
    if (!item || diagnosing || summaryQuery.savedStateOnly || !summaryQuery.backendReachable) return;
    setDiagnosing(true); setDiagnosisError(false);
    try { setDiagnosis(await liteApi.healthIntelligenceDiagnose(item.incident_id)); }
    catch { setDiagnosisError(true); setDiagnosis(null); }
    finally { setDiagnosing(false); }
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
    <PageHeader eyebrow="Self-hosted workspace" title="System Health" description="Understand problems, recovery and service readiness."
      actions={<LiteRefreshButton scope="system-health" refresh={() => { summaryQuery.refresh(); incidentsQuery.refresh(); }}
        refreshing={summaryQuery.refreshing || incidentsQuery.refreshing} error={summaryQuery.error} cacheStatus={summaryQuery.cacheStatus} />} />
    <GlassCard as="section" className={'lite-system-health-hero is-' + current.state} aria-label="System Health overview">
      <span className="lite-system-health-kicker"><HeartPulse size={19} aria-hidden="true" /> Health overview</span>
      <h2>{current.title}</h2><p>{current.detail}</p>
      <div className="lite-system-health-metrics">
        <div><strong>{summaryQuery.data?.freshness === 'current' ? summaryQuery.data?.healthy_services ?? '—' : '—'}</strong><span>Confirmed healthy</span></div>
        <div><strong>{summaryQuery.data?.active_problems ?? '—'}</strong><span>Active problems</span></div>
        <div><strong>{summaryQuery.data?.automatic_repairs_running ?? '—'}</strong><span>Automatic repairs</span></div>
      </div>
      <p className="lite-system-health-muted" role="status">{current.state === 'saved' ? 'Showing saved information; live status not confirmed.' : summaryQuery.data?.freshness === 'current' ? 'Based on recent persisted backend observations.' : 'Waiting for trustworthy health observations.'}</p>
    </GlassCard>
    <section className="lite-system-health-problems" aria-label="Active System Health problems">
      <div className="lite-system-health-section-head"><h2>Active Problems</h2><span>{items.length ? items.length + ' reported' : 'No confirmed list'}</span></div>
      {incidentsQuery.error ? <StateSurface tone="degraded" title="Problems are unavailable" description="Pocket Lab could not load the current incident list." /> :
        !incidentsQuery.data && incidentsQuery.loading ? <StateSurface tone="empty" title="Loading recent problems" description="Reading persisted health records." /> :
        items.length ? items.slice(0, 4).map(item => <SystemHealthIncidentCard key={item.incident_id} incident={item}
          onDiagnose={viewIncident} onDetails={(i) => viewIncident(i, 'incidents')} />) :
        <StateSurface tone="empty" title={current.state === 'ready' ? 'No problems observed' : 'No current problem records'} description={current.state === 'ready' ? 'Current saved health signals did not identify a problem.' : 'No incident records are available yet. Unknown is not healthy.'} />}
    </section>
    <GlassCard as="section" className="lite-system-health-history-preview">
      <div className="lite-system-health-section-head"><h2>Recovery activity</h2><Clock3 size={19} aria-hidden="true" /></div>
      <p>{summaryQuery.data?.recent_resolutions?.length ? 'Recent problems were observed healthy. This does not prove a repair succeeded.' : 'No verified repair outcomes are available yet.'}</p>
      <LiteButton tone="secondary" onClick={() => { setSection('history'); setOpen(true); }}>Recovery history <ChevronRight size={16} aria-hidden="true" /></LiteButton>
    </GlassCard>
    <LiteButton tone="primary" className="lite-system-health-manage-button" onClick={() => { setSection(null); setOpen(true); }}>Manage System Health</LiteButton>
    <LiteDetailsPanel open={open} onClose={close} variant="home" className="lite-system-health-manage" desktopGeometry={geometry} mobileSnap bodyRef={navigation.bodyRef}
      bodyClassName="lite-home-workspace-details-scroll lite-home-panel-scroll" title="System Health Manage"
      description="Current evidence, diagnosis and reviewed recovery paths.">
      <HomeGroupedSections groups={SECTIONS} section={section} defaultSection="overview" onSectionChange={setSection}
        navigation={navigation} title="System Health">
        {(!section || section === 'overview') ? <section aria-label="Health overview details">
          <LiteActionRow label="Health state" value={summaryQuery.data?.status || 'Unknown'} summary={current.detail} />
          <LiteActionRow label="Reported services" value={String(summaryQuery.data?.observed_services ?? 'Unknown')} />
          <LiteActionRow label="Evidence freshness" value={summaryQuery.data?.freshness || 'Unavailable'} />
          <LiteActionRow label="Unknown services" value={String(summaryQuery.data?.unknown_services ?? 'Unknown')} />
        </section> : null}
        {section === 'incidents' ? <section><EvidenceRows rows={items} />{selected ? <LiteButton onClick={() => setSection('diagnostics')}>Open diagnosis <ChevronRight size={16} /></LiteButton> : null}</section> : null}
        {section === 'diagnostics' ? <DetailContent incident={selected} diagnosis={diagnosis} diagnosing={diagnosing} diagnosisError={diagnosisError}
          onDiagnose={() => diagnose(selected)} onOpenArea={onNavigate ? (destination) => { close(); onNavigate(destination); } : null} /> : null}
        {section === 'repairs' ? <section><p className="lite-system-health-muted">Automatic recovery remains owned by existing guardians and watchdogs. No additional repair executor is enabled.</p>
          {(policies.data?.repair_catalog || []).map((item) => <LiteActionRow key={item.operation_id} label={item.operation_id} value={item.risk_class}
            summary={item.summary + ' ' + item.availability} />)}</section> : null}
        {section === 'history' ? <section><EvidenceRows rows={history.data?.items || []} />
          {(history.data?.repairs || []).length ? <p>Saved repair attempts: {history.data.repairs.length}</p> : <p className="lite-system-health-muted">No verified System Health repair attempts are recorded.</p>}</section> : null}
        {section === 'dependencies' ? <section className="lite-system-health-dependencies"><p className="lite-system-health-muted">Relationships describe reviewed contracts, not live connectivity.</p>
          {(dependencies.data?.edges || []).map((edge, i) => <LiteActionRow key={i} label={edge.upstream + ' → ' + edge.downstream}
            value={edge.authority === 'verified_contract' ? 'Contract' : 'Inferred'} summary={edge.summary} />)}
          <EvidenceRows rows={dependencies.data?.nodes || []} /></section> : null}
        {section === 'resources' ? <section><p className="lite-system-health-muted">Predictive forecast: {resources.data?.forecast === 'not_enough_information' ? 'Not enough information' : 'Unavailable'}.</p><EvidenceRows rows={resources.data?.signals || []} /></section> : null}
        {section === 'policies' ? <section><LiteActionRow label="Automatic repair" value="Existing supervisors only" summary="New System Health automatic operations remain disabled." />
          <LiteActionRow label="Sensitive operations" value="Confirmation required" summary="Database restore and identity changes never auto-execute." />
          <EvidenceRows rows={(policies.data?.repair_catalog || []).map(item => ({ target_id: item.operation_id, status: item.availability }))} /></section> : null}
        {section === 'drift' ? <section>
          <p className="lite-system-health-muted">Unexpected process states require review; an observed mismatch does not authorize overwriting configuration.</p>
          <EvidenceRows rows={(drift.data?.observations || []).map(item => ({ target_id: item.component, status: item.observed_status, summary: item.explanation }))} />
          <LiteActionRow label="Automatic configuration reconciliation" value="Disabled" summary="Existing runtime owner and authorization must confirm any repair." />
        </section> : null}
        {section === 'details' ? <section><LiteActionRow label="Diagnosis engine" value="Deterministic" />
          <LiteActionRow label="Optional AI assistance" value="Unavailable" summary="No cloud AI dependency is required." />
          <LiteActionRow label="Recurring components" value={String(intelligence.data?.recurring_components?.length ?? 'Unknown')} />
          <p className="lite-system-health-muted">Only sanitized incidents and safe status metadata are displayed. Raw backend troubleshooting records remain private.</p></section> : null}
      </HomeGroupedSections>
    </LiteDetailsPanel>
  </div>;
}
