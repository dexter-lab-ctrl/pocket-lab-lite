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
  const selected = items.find((item) => item.incident_id === selectedIncident) || selectedQuery.data || null;

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
    if (!item || diagnosing || readOnly || incidentEvidenceState(item) !== 'current') return;
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
    <PageHeader eyebrow="Self-hosted workspace" title="System Health" description="Your workspace health — what needs attention and what to do next."
      actions={<LiteRefreshButton scope="system-health" refresh={() => { summaryQuery.refresh(); incidentsQuery.refresh(); }}
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
          onDiagnose={viewIncident} onDetails={(i) => viewIncident(i, 'diagnostics')} />) :
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
    <LiteDetailsPanel open={open} onClose={close} variant="home" className="lite-system-health-manage" desktopGeometry={geometry} mobileSnap bodyRef={navigation.bodyRef}
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
            label={componentLabel(item.source, item.target_id)} value={item.severity === 'critical' ? 'Critical' : 'Review needed'}
            summary={item.summary || 'Current evidence needs review.'} action={{ label: 'Review issue', haptic: true, onClick: () => viewIncident(item, 'diagnostics') }} />)
            : <StateSurface tone="empty" title="No current concern confirmed" description="Unknown and saved evidence are not treated as current problems." />}
          <h3>Saved concerns requiring revalidation</h3>
          {groups.saved.length ? groups.saved.slice(0, 30).map(item => <LiteActionRow key={item.incident_id}
            label={componentLabel(item.source, item.target_id)} value="Recheck needed"
            summary="Previously reported, but current status is not established."
            action={{ label: 'Review issue', haptic: true, onClick: () => viewIncident(item, 'diagnostics') }} />)
            : <p className="lite-system-health-muted">No older unresolved records in the loaded page.</p>}
          {incidentsQuery.data?.next_offset != null ? <p className="lite-system-health-muted">Additional historical records exist. Use the bounded history view for more records.</p> : null}
        </section> : null}
        {section === 'diagnostics' ? <DetailContent incident={selected} diagnosis={diagnosis} diagnosing={diagnosing} diagnosisError={diagnosisError}
          onDiagnose={() => diagnose(selected)} readOnly={readOnly} onOpenArea={onNavigate ? (destination) => { close(); onNavigate(destination); } : null} /> : null}
        {section === 'repairs' ? <section className="lite-system-health-manage-section">
          <p className="lite-system-health-muted">Existing supervisors and protected recovery workflows own execution. This workspace has no new repair executor.</p>
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
          <EvidenceRows rows={history.data?.items || []} emptyMessage="No previous incident records are available." />
          <h3>Recorded repair attempts</h3>
          {(history.data?.repairs || []).length ? history.data.repairs.slice(0, 30).map((item, i) =>
            <LiteActionRow key={item.repair_id || i} label={recoveryOperationLabel(item.operation_id)}
              value={item.execution_state === 'failed' ? 'Repair failed' : item.execution_state === 'blocked' ? 'Repair blocked' :
                item.verification_state === 'verified' && item.execution_state === 'completed' ? 'Repair verified' :
                  'Outcome not verified'}
              summary={item.safe_summary || 'Recorded attempt. Execution and verification must be independently confirmed.'} />)
            : <p className="lite-system-health-muted">No verified System Health repair attempts are recorded.</p>}
        </section> : null}
        {section === 'dependencies' ? <section className="lite-system-health-manage-section">
          <p className="lite-system-health-muted">These relationships describe documented dependencies, not proof of live connectivity.</p>
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
