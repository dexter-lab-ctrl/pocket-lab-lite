import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  LayoutGrid,
  Server,
  ShieldCheck,
  Smartphone,
  HardDrive,
  ArrowUpRight,
  Activity,
} from 'lucide-react';
import { buildLiteHomeOverview } from '../lib/liteHomePresentation.js';
import {
  PageHeader,
  GlassCard,
  LiteRefreshButton,
  LoadingCard,
  LiteActionRow,
  LiteOperationalStory,
} from './LiteUi.jsx';
import { LiteFreshness, LiteTechnicalFacts } from './LiteUx.jsx';
import { LiteDetailsPanel } from './LiteOverlay.jsx';
import LiteReleaseUpdateCard from './LiteReleaseUpdateCard.jsx';
import LiteNextSteps from './components/LiteNextSteps.jsx';
import { prioritizeWorkspaceAttention } from './homeAttentionPriority.js';
import { useLiteQuery } from '../hooks/useLiteQuery.js';
import { liteApi } from '../lib/liteApi.js';
import { selectHomeActivityEvidence } from './homeActivityEvidence.js';
import HomeActivityDetails from './components/HomeActivityDetails.jsx';
import './components/homePremium.css';
import './components/azureHome.css';
import './components/homeActivityEvidence.css';

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

function HomeWorkspaceFlow({ overallTone, attentionCount, savedStateOnly, checking }) {
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
      <div className="lite-home-workflow-visual" aria-hidden="true">
        {HOME_WORKFLOW_STEPS.map((step, index) => {
          const Icon = step.icon;
          return (
            <React.Fragment key={step.id}>
              {index > 0 ? <span className="lite-home-workflow-line" style={{ '--lite-home-workflow-delay': `${(index - 1) * 180}ms` }}><i /></span> : null}
              <span className={`lite-home-workflow-node is-${step.id} ${flow.activeNodes.includes(step.id) ? 'is-active' : ''} ${flow.doneNodes.includes(step.id) ? 'is-done' : ''}`}>
                <Icon className="h-4 w-4" />
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
const SERVICE_LABELS = { ready: 'Ready', review: 'Review', danger: 'Needs attention', neutral: 'Not available' };
const ACTIVITY_SCREENS = { devices: 'devices', apps: 'catalog', security: 'security', recovery: 'recovery' };

function HomeOverviewGrid({ services, onNavigate, saved }) {
  const [expanded, setExpanded] = useState(false);
  const rows = Array.isArray(services) ? services : [];
  const extra = rows.filter((item) => !HOME_TILES.some((tile) => tile.id === item.key) && item.screen && item.screen !== 'home');
  return <section className="lite-home-overview" aria-labelledby="lite-home-overview-title">
    <div className="lite-home-section-title"><h2 id="lite-home-overview-title">Workspace overview</h2><p>Open an area for its current status.</p></div>
    <div className="lite-home-overview-grid">
      {HOME_TILES.map(({ id, label, screen, icon: Icon }) => {
        const item = rows.find((entry) => entry.key === id);
        const tone = saved ? 'neutral' : item?.tone || 'neutral';
        return <GlassCard as="button" interactive key={id} type="button" className={'lite-home-overview-tile is-' + tone}
          onClick={() => onNavigate(screen)} aria-label={'Open ' + label}>
          <Icon size={20} aria-hidden="true" />
          <span><strong>{label}</strong><small>{saved ? 'Saved information' : item?.statusLabel || SERVICE_LABELS.neutral}</small></span>
          <ArrowUpRight size={17} aria-hidden="true" />
        </GlassCard>;
      })}
    </div>
    {extra.length ? <div className="lite-home-more-areas">
      <button type="button" aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? 'Show fewer areas' : 'More areas'}</button>
      {expanded ? <div className="lite-home-more-grid">{extra.map((item) =>
        <LiteActionRow key={item.key} label={item.label} value={saved ? 'Saved' : item.statusLabel}
          action={{ label: 'Open', onClick: () => onNavigate(item.screen) }} />)}</div> : null}
    </div> : null}
  </section>;
}

function HomeActivityPreview({ activity, onOpen }) {
  const latest = activity?.grouped?.[0] || activity?.latestEvent;
  return <GlassCard as="section" className="lite-home-activity-preview" aria-labelledby="lite-home-activity-preview-heading">
    <div className="lite-home-section-title"><h2 id="lite-home-activity-preview-heading">Recent activity</h2>
      <p>{activity?.summary || 'Activity information is not available yet.'}</p></div>
    {latest ? <div className="lite-home-activity-latest">
      <Activity size={19} aria-hidden="true" />
      <span><strong>{latest.label}</strong>
        <small>{latest.summary || latest.statusLabel}{latest.at ? ' · ' + new Date(latest.at).toLocaleString() : ''}</small></span>
    </div> : <p className="lite-home-muted">No recent activity to display.</p>}
    <button type="button" className="lite-home-text-action" onClick={onOpen}>View activity <ArrowUpRight size={16} aria-hidden="true" /></button>
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
  const [workspaceSection, setWorkspaceSection] = useState('overview');
  const workspaceDetailsScrollRef = useRef(null);
  const workspaceTabsScrollStateRef = useRef({ lastTop: 0, hidden: false, scrolled: false });
  const [workspaceTabsHidden, setWorkspaceTabsHidden] = useState(false);
  const [workspaceDetailsScrolled, setWorkspaceDetailsScrolled] = useState(false);
  const [activityOpen, setActivityOpen] = useState(false);
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

  useEffect(() => {
    if (!workspaceDetailsOpen) {
      workspaceTabsScrollStateRef.current = { lastTop: 0, hidden: false, scrolled: false };
      setWorkspaceTabsHidden(false);
      setWorkspaceDetailsScrolled(false);
      return undefined;
    }
    const scrollElement = workspaceDetailsScrollRef.current;
    if (!(scrollElement instanceof HTMLElement)) return undefined;

    const state = workspaceTabsScrollStateRef.current;
    state.lastTop = Math.max(0, scrollElement.scrollTop || 0);
    state.hidden = false;
    state.scrolled = state.lastTop > 4;
    setWorkspaceTabsHidden(false);
    setWorkspaceDetailsScrolled(state.scrolled);

    const onScroll = () => {
      const nextTop = Math.max(0, scrollElement.scrollTop || 0);
      const delta = nextTop - state.lastTop;
      const atTop = nextTop <= 4;
      const nextScrolled = nextTop > 4;
      const nextHidden = atTop ? false : Math.abs(delta) >= 4 ? delta > 0 : state.hidden;
      state.lastTop = nextTop;
      if (state.scrolled !== nextScrolled) {
        state.scrolled = nextScrolled;
        setWorkspaceDetailsScrolled(nextScrolled);
      }
      if (state.hidden !== nextHidden) {
        state.hidden = nextHidden;
        setWorkspaceTabsHidden(nextHidden);
      }
    };

    const onFocusIn = (event) => {
      if (event.target.closest?.('.lite-home-workspace-tabs')) {
        state.hidden = false;
        setWorkspaceTabsHidden(false);
      }
    };

    scrollElement.addEventListener('scroll', onScroll, { passive: true });
    scrollElement.addEventListener('focusin', onFocusIn);
    return () => {
      scrollElement.removeEventListener('scroll', onScroll);
      scrollElement.removeEventListener('focusin', onFocusIn);
    };
  }, [workspaceDetailsOpen]);

  const details = overview.workspaceDetails;
  const sectionNames = { overview: 'Overview', 'service-health': 'Service health', updates: 'Updates', diagnostics: 'Diagnostics' };
  const primaryAction = overview.nextAction
    && overview.nextAction.screen !== 'home'
    && !effectiveSavedStateOnly
    && !attentionItems.some((item) => item.screen === overview.nextAction.screen)
    ? {
        label: overview.nextAction.label,
        tone: overview.nextAction.tone === 'primary' ? 'primary' : 'secondary',
        onClick: () => goTo(overview.nextAction.screen),
      }
    : null;
  return <div className="lite-home-premium-shell lite-home-refined" data-lite-home-premium="true" data-azure-horizon-home="true" data-home-state-source="tanstack-dexie-fastapi">
    <PageHeader eyebrow="Self-hosted workspace" title="Home" description="Your workspace, at a glance."
      actions={<LiteRefreshButton scope="home" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />} />
    <LiteOperationalStory className="lite-home-operational-story" story={overview.workspaceStory}
      primaryAction={primaryAction}
      manageAction={{ label: 'Workspace details', onClick: () => { setWorkspaceSection('overview'); setWorkspaceDetailsOpen(true); } }} />
    <LiteFreshness
      saved={effectiveSavedStateOnly}
      stale={projectionStale}
      refreshing={refreshing}
      lastUpdatedLabel={lastUpdatedLabel}
      backendReachable={backendReachable}
    />
    {loading && !overview.services.length ? <LoadingCard label="Checking workspace status…" /> : null}
    <HomeOverviewGrid services={overview.services} saved={effectiveSavedStateOnly} onNavigate={goTo} />
    <div className="lite-home-lower-grid">
    <HomeActivityPreview activity={effectiveSavedStateOnly ? null : activity} onOpen={() => setActivityOpen(true)} />
    {attentionItems.length ? <LiteNextSteps title="Needs your attention"
      description={effectiveSavedStateOnly ? 'Last saved status — verify before acting.' : 'A few things to check.'}
      saved={effectiveSavedStateOnly} initialCount={3}
      items={(effectiveSavedStateOnly ? attentionItems.slice(0, 3) : attentionItems).map((item) => ({
        id: item.key, label: item.label, description: item.summary,
        actionLabel: 'Review ' + item.label,
        onClick: item.screen ? () => goTo(item.screen) : undefined,
      }))} className="lite-home-attention-list" /> : null}
    </div>
    <LiteDetailsPanel open={workspaceDetailsOpen} onClose={() => setWorkspaceDetailsOpen(false)}
      bodyRef={workspaceDetailsScrollRef} bodyClassName="lite-home-workspace-details-scroll"
      title="Workspace details" description="Current services and safe workspace information.">
      <div className="lite-home-workspace-details">
        <nav className="lite-home-details-nav lite-home-workspace-tabs"
          aria-label="Workspace details sections"
          data-tabs-hidden={workspaceTabsHidden ? 'true' : 'false'}
          data-tabs-scrolled={workspaceDetailsScrolled ? 'true' : 'false'}>
          {Object.entries(sectionNames).map(([id, label]) =>
            <button key={id} type="button" aria-current={workspaceSection === id ? 'page' : undefined}
              onClick={() => { setWorkspaceTabsHidden(false); setWorkspaceSection(id); }}>{label}</button>)}
        </nav>
        {workspaceSection === 'overview' ? <section aria-label="Workspace overview details">
          {details.resources.filter((item) => item.key !== 'activity').map((item) =>
            <LiteActionRow key={item.key} label={item.key === 'database' ? 'System data' : item.label}
              value={item.value} summary={item.note} attention={item.tone === 'danger' || item.tone === 'review'} />)}
          <LiteActionRow label="Information freshness" value={effectiveSavedStateOnly ? 'Saved' : 'Current'}
            summary={details.freshness || 'Not checked yet'} />
        </section> : null}
        {workspaceSection === 'service-health' ? <section aria-label="Service health">
          <HomeWorkspaceFlow overallTone={overview.overallTone} attentionCount={overview.attentionCount}
            savedStateOnly={effectiveSavedStateOnly} checking={loading || refreshing || status.refresh_pending === true} />
          {overview.services.map((item) => <LiteActionRow key={item.key} label={item.label}
            value={effectiveSavedStateOnly ? 'Saved' : item.statusLabel}
            attention={item.tone === 'danger' || item.tone === 'review'}
            action={item.screen !== 'home' ? { label: 'Open', onClick: () => goTo(item.screen) } : null} />)}
        </section> : null}
        {workspaceSection === 'updates' ? <section aria-label="Updates"><LiteReleaseUpdateCard /></section> : null}
        {workspaceSection === 'diagnostics' ? <section aria-label="Diagnostics">
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
      </div>
    </LiteDetailsPanel>
    <LiteDetailsPanel open={activityOpen} onClose={() => setActivityOpen(false)}
      title="Recent activity" description="Workspace history and personal review.">
      <HomeActivityDetails activity={history} cursor={cursor} cursorBusy={cursorBusy}
        cursorError={cursorError} saved={effectiveSavedStateOnly} onMarkReviewed={markReviewed}
        onNavigate={(domain) => { setActivityOpen(false); goTo(ACTIVITY_SCREENS[domain] || 'home'); }} />
    </LiteDetailsPanel>
  </div>;
}
