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
import './systemHealth.css';

const SECTIONS = Object.freeze([
  { label: 'Health', items: [
    { id: 'overview', label: 'Overview', description: 'Current evidence and readiness', icon: HeartPulse },
    { id: 'incidents', label: 'Active Problems', description: 'Reported issues that need review', icon: AlertTriangle },
    { id: 'diagnostics', label: 'Diagnostics', description: 'Evidence-backed cause assessment', icon: ClipboardCheck },
    { id: 'repairs', label: 'Repairs', description: 'Approved options and execution ownership', icon: Wrench },
  ] },
  { label: 'Review', items: [
    { id: 'history', label: 'Recovery History', description: 'Persisted outcomes and recurrence', icon: Clock3 },
    { id: 'dependencies', label: 'Dependencies', description: 'Contract relationships and evidence', icon: GitBranch },
    { id: 'resources', label: 'Resource Intelligence', description: 'Current resource signals', icon: Cpu },
    { id: 'policies', label: 'Policies', description: 'Safety rules and authority', icon: ShieldCheck },
    { id: 'details', label: 'Technical Details', description: 'Sanitized diagnostic metadata', icon: Settings2 },
  ] },
]);

export function systemHealthPresentation(payload, saved = false) {
  if (!payload || typeof payload !== 'object') return { state: 'unknown', title: 'System status is not confirmed', detail: 'No current System Health information is available.' };
  const freshness = saved ? 'saved' : String(payload.freshness || 'unknown');
  if (freshness !== 'current') return { state: 'saved', title: 'Showing saved information', detail: 'Live health has not been confirmed. Reconnect or refresh to check again.' };
  if (payload.status === 'attention') return { state: 'attention', title: 'Some services need attention', detail: payload.summary || 'Review active problems before changing services.' };
  if (payload.status === 'healthy' && Number(payload.unknown_services || 0) === 0) return { state: 'ready', title: 'Observed services are healthy', detail: payload.summary || 'Current observations show no detected problems.' };
  return { state: 'unknown', title: 'System status needs confirmation', detail: payload.summary || 'Not enough current evidence to confirm health.' };
}

export function SystemHealthIncidentCard({ incident, onDiagnose, onDetails }) {
  const stale = incident.evidence_freshness !== 'current';
  return <GlassCard as="article" className="lite-system-health-incident" data-health-incident={incident.incident_id}>
    <div className="lite-system-health-incident-head">
      <span className="lite-system-health-health-icon"><AlertTriangle size={19} aria-hidden="true" /></span>
      <div><h3>{incident.target_id || 'Affected service'}</h3><p>{incident.summary || 'The latest observation needs attention.'}</p></div>
      <span className={'lite-system-health-state is-' + (stale ? 'unknown' : incident.severity === 'critical' ? 'attention' : 'watch')}>{stale ? 'Saved' : incident.severity === 'critical' ? 'Critical' : 'Needs attention'}</span>
    </div>
    <p className="lite-system-health-muted">{stale ? 'Evidence is no longer current.' : 'Based on a committed backend health observation.'}</p>
    <div className="lite-system-health-actions">
      <LiteButton tone="secondary" onClick={() => onDiagnose(incident)}>Diagnose &amp; Fix</LiteButton>
      <LiteButton tone="secondary" onClick={() => onDetails(incident)}>Details</LiteButton>
    </div>
  </GlassCard>;
}

function EvidenceRows({ rows = [] }) {
  return rows.length ? rows.map((row, i) => <LiteActionRow key={row.incident_id || row.target_id || i}
    label={row.target_id || row.source || 'Component'}
    value={row.status || row.state || 'Not confirmed'}
    summary={row.freshness === 'stale' || row.evidence_freshness === 'stale' ? 'Saved observation — current state unknown' : row.summary || ''}
    attention={row.status === 'unavailable' || row.state === 'failed'} />)
    : <StateSurface tone="empty" title="Not enough information" description="No authoritative records are available for this view." />;
}

function DetailContent({ incident, diagnosis, diagnosing, diagnosisError, onDiagnose, onOpenArea }) {
  if (!incident) return <StateSurface tone="empty" title="Choose a problem" description="Select a reported problem to review its evidence and safe next steps." />;
  return <section className="lite-system-health-detail" aria-label="Problem details">
    <h3>{incident.target_id}</h3>
    <p>{incident.summary}</p>
    <LiteActionRow label="Observed state" value={incident.state} summary={incident.evidence_freshness === 'current' ? 'Current saved projection' : 'Evidence is stale. Current status is not confirmed.'} />
    <LiteActionRow label="What Pocket Lab checked" value={incident.source} summary="The last persisted worker-owned health signal; no live process inspection happens in this panel." />
    <LiteActionRow label="Likely cause" value={diagnosis?.cause_confidence || 'Not established'} summary={diagnosis?.suspected_cause || 'No verified root cause has been established.'} />
    <LiteActionRow label="What changed" value="Nothing" summary="Diagnosis does not restart or reconfigure services." />
    <LiteActionRow label="How recovery was verified" value={incident.state === 'resolved' ? 'Observed healthy' : 'Not verified'} summary="A healthy observation is not proof of a completed repair." />
    <p className="lite-system-health-muted">Saved for troubleshooting: sanitized incident metadata only. Raw evidence is backend-only.</p>
    {diagnosisError ? <StateSurface tone="degraded" title="Diagnosis unavailable" description="Pocket Lab could not confirm the latest diagnosis." /> : null}
    {diagnosis?.supporting_signals?.length ? <EvidenceRows rows={diagnosis.supporting_signals} /> : null}
    <div className="lite-system-health-actions">
      <LiteButton disabled={diagnosing || incident.evidence_freshness !== 'current'} busy={diagnosing}
        disabledReason={incident.evidence_freshness !== 'current' ? 'Evidence is stale' : ''} onClick={onDiagnose} tone="primary">Check cause</LiteButton>
      <LiteButton disabled disabledReason="No new System Health repair executor is qualified">Fix</LiteButton>
      {onOpenArea ? <LiteButton tone="secondary" onClick={() => onOpenArea(incident.source === 'agent' || incident.source === 'supervisor' ? 'devices' : incident.source === 'security' ? 'security' : incident.source === 'storage' ? 'recovery' : 'catalog')}>Open existing recovery controls</LiteButton> : null}
    </div>
    <p className="lite-system-health-muted">No configuration overwrite, restart, app update or database restore is performed by this view.</p>
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
        {section === 'details' ? <section><LiteActionRow label="Diagnosis engine" value="Deterministic" />
          <LiteActionRow label="Optional AI assistance" value="Unavailable" summary="No cloud AI dependency is required." />
          <LiteActionRow label="Recurring components" value={String(intelligence.data?.recurring_components?.length ?? 'Unknown')} />
          <p className="lite-system-health-muted">Only sanitized incidents and safe status metadata are displayed. Raw backend troubleshooting records remain private.</p></section> : null}
      </HomeGroupedSections>
    </LiteDetailsPanel>
  </div>;
}
