import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  LayoutGrid,
  Server,
  ShieldCheck,
  Smartphone,
  HardDrive,
  ArrowUpRight,
  Activity, CheckCircle2, AlertTriangle, AlertCircle, CloudOff, Clock3,
  Info, Wrench, ChevronRight,
} from 'lucide-react';
import { buildLiteHomeOverview } from '../lib/liteHomePresentation.js';
import {
  PageHeader,
  GlassCard,
  LiteRefreshButton,
  LiteActionRow,
} from './LiteUi.jsx';
import { LiteTechnicalFacts } from './LiteUx.jsx';
import { LiteDetailsPanel } from './LiteOverlay.jsx';
import { useDesktopManageGeometry } from './components/useDesktopManageGeometry.js';
import { useLitePanelSectionNavigation } from './hooks/useLitePanelSectionNavigation.js';
import LiteReleaseUpdateCard from './LiteReleaseUpdateCard.jsx';
import LiteNextSteps from './components/LiteNextSteps.jsx';
import { prioritizeWorkspaceAttention } from './homeAttentionPriority.js';
import { useLiteQuery } from '../hooks/useLiteQuery.js';
import { liteApi } from '../lib/liteApi.js';
import { selectHomeActivityEvidence } from './homeActivityEvidence.js';
import HomeActivityDetails from './components/HomeActivityDetails.jsx';
import HomeGroupedSections from './components/HomeGroupedSections.jsx';
import './components/homePremium.css';
import './components/azureHome.css';
import './components/homeActivityEvidence.css';
import './components/homePanelRefinement.css';
import './components/homeCommand.css';

const HOME_WORKFLOW_STEPS = Object.freeze([
  { id: 'device', label: 'Device', icon: Smartphone },
  { id: 'services', label: 'Services', icon: Server },
  { id: 'apps', label: 'Apps', icon: LayoutGrid },
  { id: 'safety', label: 'Safety', icon: ShieldCheck },
]);

export function homeWorkflowPresentation({ overallTone, attentionCount, savedStateOnly, checking }) {
  if (checking) {
    return {
      state: 'checking',
      motion: 'checking',
      eyebrow: 'Workspace status',
      title: 'Checking your workspace flow',
      summary: 'Refreshing the latest signals from your Pocket Lab.',
      badge: 'Checking',
      activeNodes: ['services', 'apps'],
      doneNodes: ['device'],
    };
  }
  if (savedStateOnly) {
    return {
      state: 'saved',
      motion: 'rest',
      eyebrow: 'Workspace status',
      title: 'Showing saved workspace state',
      summary: 'Reconnect to resume live workspace signals.',
      badge: 'Saved',
      activeNodes: [],
      doneNodes: [],
    };
  }
  if (overallTone !== 'ready') {
    return {
      state: 'attention',
      motion: 'rest',
      eyebrow: 'Workspace status',
      title: 'Some workspace services need attention',
      summary: `${attentionCount || 'Some'} ${attentionCount === 1 ? 'area needs' : 'areas need'} a review before everything is ready.`,
      badge: 'Review',
      activeNodes: ['services'],
      doneNodes: ['device'],
    };
  }
  return {
    state: 'ready',
    motion: 'live',
    eyebrow: 'Workspace status',
    title: 'Reported workspace checks are ready',
    summary: 'Review individual areas for their latest confirmed state.',
    badge: 'Live',
    activeNodes: ['device', 'services', 'apps', 'safety'],
    doneNodes: ['device', 'services', 'apps', 'safety'],
  };
}

export function HomeWorkspaceFlow({ overallTone, attentionCount, savedStateOnly, checking }) {
  const flow = homeWorkflowPresentation({ overallTone, attentionCount, savedStateOnly, checking });
  return (
    <section
      className={`lite-home-workflow is-${flow.state} motion-${flow.motion}`}
      aria-labelledby="lite-home-workflow-title"
      data-home-workflow-state={flow.state}
    >
      <div className="lite-home-workflow-copy">
        <span>{flow.eyebrow}</span>
        <strong id="lite-home-workflow-title">{flow.title}</strong>
        <p>{flow.summary}</p>
      </div>
      <div className="lite-home-workflow-visual" role="list" aria-label="Workspace flow areas">
        {HOME_WORKFLOW_STEPS.map((step, index) => {
          const Icon = step.icon;
          return (
            <React.Fragment key={step.id}>
              {index > 0 ? <span aria-hidden="true" className="lite-home-workflow-line" style={{ '--lite-home-workflow-delay': `${(index - 1) * 180}ms` }}><i /></span> : null}
              <span role="listitem" aria-label={`${step.label} workspace flow step`} className={`lite-home-workflow-node is-${step.id} ${flow.activeNodes.includes(step.id) ? 'is-active' : ''} ${flow.doneNodes.includes(step.id) ? 'is-done' : ''}`}>
                <Icon className="h-4 w-4" aria-hidden="true" />
                <small>{step.label}</small>
              </span>
            </React.Fragment>
          );
        })}
      </div>
      <span className="lite-home-workflow-badge">{flow.badge}</span>
    </section>
  );
}


const HOME_TILES = [
  { id: 'app_catalog', label: 'Apps', screen: 'catalog', icon: LayoutGrid },
  { id: 'device_fleet', label: 'Devices', screen: 'devices', icon: Smartphone },
  { id: 'security', label: 'Safety', screen: 'security', icon: ShieldCheck },
  { id: 'recovery', label: 'Backups', screen: 'recovery', icon: HardDrive },
];
const ACTIVITY_SCREENS = { devices: 'devices', apps: 'catalog', security: 'security', recovery: 'recovery' };
const HOME_WORKSPACE_GROUPS = [
  { label: 'Workspace', items: [
    { id: 'overview', label: 'Overview', description: 'Workspace facts and readiness', icon: LayoutGrid },
    { id: 'service-health', label: 'Service health', description: 'How your services connect', icon: Activity },
  ] },
  { label: 'Maintenance', items: [
    { id: 'updates', label: 'Updates', description: 'Check available updates', icon: ArrowUpRight },
    { id: 'diagnostics', label: 'Diagnostics', description: 'Technical details on demand', icon: Wrench },
  ] },
];

export function homeCommandHeroPresentation({
  overview, loading = false, refreshing = false, saved = false,
  reachable = true, partial = false, running = false, error = false,
}) {
  const services = overview?.services || [];
  if (!reachable) return { state: 'offline', eyebrow: 'Workspace unavailable',
    title: 'Current status is unavailable', summary: saved
      ? 'Showing saved information. Reconnect to confirm current workspace health.'
      : 'Pocket Lab cannot confirm your workspace status right now.', icon: CloudOff };
  if (partial) return { state: 'partial', eyebrow: 'Information needs refresh',
    title: 'Workspace status needs confirmation',
    summary: 'The latest prepared information is incomplete or too old. Review saved details while Pocket Lab reconnects.', icon: AlertTriangle };
  if (saved) return { state: 'saved', eyebrow: 'Saved workspace state',
    title: 'Showing saved information',
    summary: 'Current workspace health is not confirmed. Actions need a live connection.', icon: Clock3 };
  if (loading && !services.length) return { state: 'loading', eyebrow: 'Checking workspace',
    title: 'Checking your workspace', summary: 'Current status has not been reported yet.', icon: Clock3 };
  if (error || !services.length || !['ready','review','danger'].includes(overview?.overallTone))
    return { state: 'unknown', eyebrow: 'Workspace status unknown', title: 'Workspace status is not confirmed',
      summary: 'Pocket Lab has not confirmed enough information to report a healthy workspace.', icon: Info };
  if (overview.overallTone === 'danger' || services.some((item) => item.tone === 'danger'))
    return { state: 'critical', eyebrow: 'Needs attention', title: 'Some services need your attention',
      summary: 'Review the reported problem before making important changes.', icon: AlertCircle };
  if (overview.overallTone === 'review' || services.some((item) => item.tone !== 'ready'))
    return { state: 'attention', eyebrow: 'Review recommended', title: 'Your workspace needs a review',
      summary: 'Some reported services are not ready yet. Review the affected areas below.', icon: AlertTriangle };
  if (running) return { state: 'running', eyebrow: 'Work in progress',
    title: 'Workspace operations are running',
    summary: 'The latest prepared activity reports work in progress. Open Recent activity for details.', icon: Activity };
  if (refreshing) return { state: 'checking', eyebrow: 'Checking latest information',
    title: 'Refreshing workspace status',
    summary: 'The previous confirmed status remains visible while fresh information is requested.', icon: Clock3 };
  return { state: 'ready', eyebrow: 'Workspace ready', title: 'Everything is running smoothly',
    summary: 'Your reported workspace services are available. No immediate action is needed.', icon: CheckCircle2 };
}

export function HomeHealthHero({ overview, loading, refreshing, saved, reachable, partial, running, error, lastUpdatedLabel, onDetails }) {
  const hero = homeCommandHeroPresentation({ overview, loading, refreshing, saved, reachable, partial, running, error });
  const Icon = hero.icon;
  return <GlassCard as="section" className={'lite-home-command-hero is-' + hero.state}
    data-home-hero-state={hero.state} aria-label="Workspace health">
    <div className="lite-home-command-status"><Icon size={19} aria-hidden="true" /><span>{hero.eyebrow}</span></div>
    <h2>{hero.title}</h2>
    <p>{hero.summary}</p>
    <div className="lite-home-command-hero-footer">
      <span className="lite-home-command-freshness">{saved || !reachable || partial ? 'Current status not confirmed' :
        refreshing ? 'Checking for updates' : lastUpdatedLabel || 'Latest reported status'}</span>
      <button type="button" className="lite-home-command-details" onClick={onDetails}>
        Workspace details <ChevronRight size={17} aria-hidden="true" />
      </button>
    </div>
  </GlassCard>;
}

function HomeOverviewGrid({ services, status, onNavigate, saved }) {
  const rows = Array.isArray(services) ? services : [];
  const summary = status?.summary || {};
  return <section className="lite-home-overview" aria-labelledby="lite-home-overview-title">
    <div className="lite-home-section-title"><h2 id="lite-home-overview-title">Your workspace</h2></div>
    <div className="lite-home-overview-grid">
      {HOME_TILES.map(({ id, label, screen, icon: Icon }) => {
        const item = rows.find((entry) => entry.key === id);
        const tone = saved ? 'neutral' : item?.tone || 'neutral';
        let description = saved ? 'Saved information' : item?.statusLabel || 'Status not reported';
        if (!saved && tone === 'ready') {
          if (id === 'app_catalog' && Number.isSafeInteger(summary.apps_available) && summary.apps_available >= 0)
            description = summary.apps_available + ' available';
          if (id === 'device_fleet' && Number.isSafeInteger(summary.devices_known) && summary.devices_known >= 0)
            description = summary.devices_known + ' known';
          if (id === 'security' && summary.security_findings === 0) description = 'No urgent issues reported';
        }
        return <GlassCard as="button" interactive key={id} type="button" className={'lite-home-overview-tile is-' + tone}
          onClick={() => onNavigate(screen)} aria-label={'Open ' + label}>
          <Icon size={20} aria-hidden="true" />
          <span><strong>{label}</strong><small>{description}</small></span>
          <ArrowUpRight size={17} aria-hidden="true" />
        </GlassCard>;
      })}
    </div>
  </section>;
}

function HomeActivityPreview({ activity, saved, onOpen }) {
  const latest = activity?.latestEvent;
  const at = latest && Number.isFinite(latest.at) ? new Date(latest.at) : null;
  return <GlassCard as="section" className="lite-home-activity-preview" aria-labelledby="lite-home-activity-preview-heading">
    <div className="lite-home-section-title"><h2 id="lite-home-activity-preview-heading">Recent activity</h2></div>
    {latest ? <div className="lite-home-activity-latest">
      <Activity size={19} aria-hidden="true" />
      <span><strong>{latest.label}</strong><small>{latest.statusLabel}</small>
        {at && Number.isFinite(at.getTime()) ? <time dateTime={at.toISOString()}>{at.toLocaleString()}</time> : null}</span>
    </div> : <p className="lite-home-muted">{saved ? 'Live activity is unavailable. Reconnect to review current changes.' :
      activity ? 'No recent activity was reported.' : 'Recent activity is not available yet.'}</p>}
    <button type="button" className="lite-home-text-action" onClick={onOpen}>View all activity
      <ChevronRight size={16} aria-hidden="true" /></button>
  </GlassCard>;
}

export default function HomeScreen({
  status = {}, loading, error, refresh, cacheStatus, refreshing,
  savedStateOnly = false, backendReachable = true, lastUpdatedLabel = '', onNavigate,
}) {
  const projectionStale = status.read_degraded === true || status.degraded_reason === 'projection_too_old';
  const effectiveSavedStateOnly = savedStateOnly || projectionStale || !backendReachable;
  const overview = useMemo(
    () => buildLiteHomeOverview(status, { savedStateOnly: effectiveSavedStateOnly, backendReachable, lastUpdatedLabel }),
    [backendReachable, effectiveSavedStateOnly, lastUpdatedLabel, status],
  );
  const [workspaceDetailsOpen, setWorkspaceDetailsOpen] = useState(false);
  const [workspaceSection, setWorkspaceSection] = useState(null);
  const [activityOpen, setActivityOpen] = useState(false);
  const workspaceNav = useLitePanelSectionNavigation(workspaceDetailsOpen);
  const activityNav = useLitePanelSectionNavigation(activityOpen);
  const workspaceGeometry = useDesktopManageGeometry({ open: workspaceDetailsOpen, defaultWidth: 660, minWidth: 380, minHeight: 360 });
  const activityGeometry = useDesktopManageGeometry({ open: activityOpen, defaultWidth: 660, minWidth: 380, minHeight: 360 });
  const [cursor, setCursor] = useState(null);
  const [cursorBusy, setCursorBusy] = useState(false);
  const [cursorError, setCursorError] = useState('');
  const { data: activityData } = useLiteQuery({
    queryKey: ['lite', 'system', 'activity-summary', 'home'], path: '/api/lite/system/activity-summary',
    queryFn: liteApi.activitySummary, enabled: backendReachable && !effectiveSavedStateOnly,
    pollingMode: 'relaxed', staleTime: 60000,
  });
  const { data: historyData } = useLiteQuery({
    queryKey: ['lite', 'home', 'activity-history'],
    path: '/api/lite/home/activity-history',
    queryFn: liteApi.homeActivityHistory,
    enabled: activityOpen && backendReachable && !effectiveSavedStateOnly,
    staleTime: 60000, pollingMode: 'relaxed',
  });
  const activity = useMemo(() => selectHomeActivityEvidence(activityData), [activityData]);
  const history = useMemo(() => historyData?.history_available !== false && historyData
    ? selectHomeActivityEvidence({ ...activityData, ...historyData,
        counts_available: activityData?.counts_available !== false && historyData.counts_available !== false }) || activity
    : activity, [historyData, activityData, activity]);

  const attentionItems = useMemo(() => prioritizeWorkspaceAttention(overview.services), [overview.services]);

  useEffect(() => {
    if (!activityOpen || effectiveSavedStateOnly || !backendReachable) return;
    let alive = true;
    liteApi.homeActivityCursor().then((value) => {
      if (alive) { setCursor(value); setCursorError(''); }
    }).catch(() => {
      if (alive) { setCursor(null); setCursorError("Review history couldn't be loaded."); }
    });
    return () => { alive = false; };
  }, [activityOpen, effectiveSavedStateOnly, backendReachable]);

  const markReviewed = useCallback(async () => {
    if (cursorBusy || !cursor?.changed_since_review || effectiveSavedStateOnly || !backendReachable) return;
    setCursorBusy(true);
    setCursorError('');
    try { setCursor(await liteApi.reviewHomeActivityCursor()); }
    catch { setCursorError('Could not confirm your review. Try again.'); }
    finally { setCursorBusy(false); }
  }, [cursor, cursorBusy, effectiveSavedStateOnly, backendReachable]);

  const goTo = useCallback((screen) => {
    if (screen === 'home') { setWorkspaceSection('service-health'); setWorkspaceDetailsOpen(true); return; }
    onNavigate?.(screen);
  }, [onNavigate]);


  const details = overview.workspaceDetails;
  const selectedWorkspaceSection = workspaceSection || 'overview';
  return <div className="lite-home-premium-shell lite-home-refined" data-lite-home-premium="true" data-azure-horizon-home="true" data-home-state-source="tanstack-dexie-fastapi">
    <PageHeader eyebrow="Self-hosted workspace" title="Home" description="Your private workspace, at a glance."
      actions={<LiteRefreshButton scope="home" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />} />
    <HomeHealthHero overview={overview} loading={loading} refreshing={refreshing || status.refresh_pending === true}
      saved={effectiveSavedStateOnly} reachable={backendReachable} partial={projectionStale}
      running={!effectiveSavedStateOnly && Number.isSafeInteger(activity?.active) && activity.active > 0}
      error={Boolean(error)} lastUpdatedLabel={lastUpdatedLabel}
      onDetails={() => { setWorkspaceSection(null); setWorkspaceDetailsOpen(true); }} />
    <HomeOverviewGrid services={overview.services} status={status} saved={effectiveSavedStateOnly} onNavigate={goTo} />
    <div className="lite-home-lower-grid">
      {!effectiveSavedStateOnly && overview.overallTone !== 'unknown' && attentionItems.some((item) => item.screen && item.screen !== 'home') ?
        <LiteNextSteps title="Needs your attention"
          description="Reported areas to review, in priority order."
          saved={false} initialCount={3}
          items={attentionItems.filter((item) => item.screen && item.screen !== 'home').map((item) => ({
            id: item.key, label: item.label, description: item.summary,
            actionLabel: 'Review ' + item.label, onClick: () => goTo(item.screen),
          }))} className="lite-home-attention-list" /> : null}
      <HomeActivityPreview activity={effectiveSavedStateOnly ? null : activity} saved={effectiveSavedStateOnly} onOpen={() => setActivityOpen(true)} />
    </div>
    <LiteDetailsPanel open={workspaceDetailsOpen} onClose={() => setWorkspaceDetailsOpen(false)}
      variant="home" className="lite-home-details-panel" desktopGeometry={workspaceGeometry}
      bodyRef={workspaceNav.bodyRef} bodyClassName="lite-home-workspace-details-scroll lite-home-panel-scroll"
      title="Workspace details" description="Current services and safe workspace information.">
      <div className="lite-home-workspace-details">
        <HomeGroupedSections groups={HOME_WORKSPACE_GROUPS} section={workspaceSection}
          onSectionChange={setWorkspaceSection} defaultSection="overview"
          navigation={workspaceNav} title="Workspace details">
        {selectedWorkspaceSection === 'overview' ? <section className="lite-home-workspace-section" aria-label="Workspace overview details">
          {details.resources.filter((item) => item.key !== 'activity').map((item) =>
            <LiteActionRow key={item.key} label={item.key === 'database' ? 'System data' : item.label}
              value={item.value} summary={item.note} attention={item.tone === 'danger' || item.tone === 'review'} />)}
          <LiteActionRow label="Information freshness" value={effectiveSavedStateOnly ? 'Saved' : 'Current'}
            summary={details.freshness || 'Not checked yet'} />
        </section> : null}
        {selectedWorkspaceSection === 'service-health' ? <section className="lite-home-workspace-section" aria-label="Service health">
          <HomeWorkspaceFlow overallTone={overview.overallTone} attentionCount={overview.attentionCount}
            savedStateOnly={effectiveSavedStateOnly} checking={loading || refreshing || status.refresh_pending === true} />
          {overview.services.map((item) => <LiteActionRow key={item.key} label={item.label}
            value={effectiveSavedStateOnly ? 'Saved' : item.statusLabel}
            attention={item.tone === 'danger' || item.tone === 'review'}
            action={item.screen !== 'home' ? { label: 'Open', onClick: () => goTo(item.screen) } : null} />)}
        </section> : null}
        {selectedWorkspaceSection === 'updates' ? <section className="lite-home-workspace-section" aria-label="Updates"><LiteReleaseUpdateCard /></section> : null}
        {selectedWorkspaceSection === 'diagnostics' ? <section className="lite-home-workspace-section" aria-label="Diagnostics">
          <LiteTechnicalFacts title="Technical details" description="Sanitized status and projection information."
            facts={[
              ...details.resources.filter((item) => item.key !== 'activity').map((item) => ({
                id: item.key, label: item.key === 'database' ? 'System data' : item.label,
                value: item.value, note: item.note, tone: item.tone,
              })),
              { id: 'source', label: 'Source availability', value: backendReachable ? 'Connected' : 'Not available' },
              { id: 'information', label: 'Projection freshness', value: effectiveSavedStateOnly ? 'Saved information' : 'Current information', note: details.freshness },
            ]} />
        </section> : null}
        </HomeGroupedSections>
      </div>
    </LiteDetailsPanel>
    <LiteDetailsPanel open={activityOpen} onClose={() => setActivityOpen(false)}
      variant="home" className="lite-home-details-panel" desktopGeometry={activityGeometry}
      bodyRef={activityNav.bodyRef} bodyClassName="lite-home-panel-scroll lite-home-activity-scroll"
      title="Recent activity" description="Workspace history and personal review.">
      <HomeActivityDetails activity={history} navigation={activityNav} cursor={cursor} cursorBusy={cursorBusy}
        cursorError={cursorError} saved={effectiveSavedStateOnly} onMarkReviewed={markReviewed}
        onNavigate={(domain) => { setActivityOpen(false); goTo(ACTIVITY_SCREENS[domain] || 'home'); }} />
    </LiteDetailsPanel>
  </div>;
}
