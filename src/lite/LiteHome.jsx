import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  LayoutGrid,
  Server,
  ShieldCheck,
  Smartphone,
} from 'lucide-react';
import { buildLiteHomeOverview } from '../lib/liteHomePresentation.js';
import {
  PageHeader,
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
      title: 'Workspace flow needs attention',
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
    title: 'Your workspace is flowing smoothly',
    summary: 'Device, services, apps, and safety are all ready together.',
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

export default function HomeScreen({
  status,
  loading,
  error,
  refresh,
  cacheStatus,
  refreshing,
  savedStateOnly = false,
  backendReachable = true,
  lastUpdatedLabel = '',
  onNavigate,
}) {
  const projectionStale = status.read_degraded === true || status.degraded_reason === 'projection_too_old';
  const effectiveSavedStateOnly = savedStateOnly || projectionStale;
  const overview = useMemo(
    () => buildLiteHomeOverview(status, { savedStateOnly: effectiveSavedStateOnly, backendReachable, lastUpdatedLabel }),
    [backendReachable, effectiveSavedStateOnly, lastUpdatedLabel, status],
  );
  const [workspaceDetailsOpen, setWorkspaceDetailsOpen] = useState(false);
  const {data: activityData} = useLiteQuery({queryKey:['lite','system','activity-summary','home'],path:'/api/lite/system/activity-summary',queryFn:liteApi.activitySummary,enabled:backendReachable && !effectiveSavedStateOnly,pollingMode:'relaxed',staleTime:60000});
  const activityEvidence = useMemo(()=>selectHomeActivityEvidence(activityData),[activityData]);
  const [activityCursor,setActivityCursor]=useState(null);
  const [cursorBusy,setCursorBusy]=useState(false);
  const [cursorError,setCursorError]=useState('');
  useEffect(()=>{
    let cancelled=false;
    if (!backendReachable || effectiveSavedStateOnly || !activityEvidence) {
      setActivityCursor(null);
      return ()=>{cancelled=true;};
    }
    liteApi.homeActivityCursor().then(value=>{
      if(!cancelled){setActivityCursor(value);setCursorError('');}
    }).catch(()=>{
      if(!cancelled){setActivityCursor(null);setCursorError('Personal activity review is unavailable.');}
    });
    return ()=>{cancelled=true;};
  },[backendReachable,effectiveSavedStateOnly,activityEvidence?.completed,activityEvidence?.latestChange]);
  const markActivityReviewed=useCallback(async()=>{
    if(cursorBusy || effectiveSavedStateOnly || !backendReachable || !activityCursor?.changed_since_review)return;
    setCursorBusy(true);setCursorError('');
    try{setActivityCursor(await liteApi.reviewHomeActivityCursor());}
    catch{setCursorError('Could not confirm your review. Try again.');}
    finally{setCursorBusy(false);}
  },[cursorBusy,effectiveSavedStateOnly,backendReachable,activityCursor]);


  const goTo = useCallback((screen) => {
    if (screen === 'home') {
      refresh?.();
      return;
    }
    onNavigate?.(screen);
  }, [onNavigate, refresh]);

  return (
    <div className="lite-home-premium-shell" data-lite-home-premium="true" data-home-state-source="tanstack-dexie-fastapi">
      <PageHeader
        eyebrow="Workspace"
        title="Home"
        description="What is ready, what needs you, and the next useful action for your workspace."
        actions={<LiteRefreshButton scope="home" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      <LiteOperationalStory
        className="lite-home-operational-story"
        story={overview.workspaceStory}
        primaryAction={overview.nextAction ? {
          label: overview.nextAction.label,
          tone: overview.nextAction.tone === 'primary' ? 'primary' : 'secondary',
          onClick: () => goTo(overview.nextAction.screen),
        } : null}
        manageAction={{ label: 'Workspace details', onClick: () => setWorkspaceDetailsOpen(true) }}
      />
      <LiteFreshness
        saved={effectiveSavedStateOnly}
        stale={projectionStale}
        refreshing={refreshing || status.refresh_pending === true}
        lastUpdatedLabel={lastUpdatedLabel || overview.workspaceDetails.freshness}
        backendReachable={backendReachable}
      />

      {activityEvidence ? <section className="lite-home-activity-evidence" aria-label="Recent workspace activity">
        <h2>Recent workspace activity</h2><p>{activityEvidence.summary}</p>
        {activityCursor?.changed_since_review ? <p role="status">Something changed since you last reviewed this workspace.</p> : null}
        <dl><div><dt>Currently active</dt><dd>{activityEvidence.active}</dd></div><div><dt>Recently completed</dt><dd>{activityEvidence.completed}</dd></div><div><dt>Needs review</dt><dd>{activityEvidence.attention}</dd></div></dl>
        <p>{activityEvidence.latestChange || 'No recent change details reported.'}</p>
        {activityEvidence.saved ? <small>Activity projection may be stale. Check again when connected.</small> : null}
        {activityCursor?.last_reviewed_at ? <small>Last reviewed: {new Date(activityCursor.last_reviewed_at).toLocaleString()}</small> : null}
        {activityCursor?.changed_since_review ? <button type="button" disabled={cursorBusy || effectiveSavedStateOnly} onClick={markActivityReviewed}>{cursorBusy ? 'Saving review…' : 'Mark activity reviewed'}</button> : null}
        {cursorError ? <small role="status">{cursorError}</small> : null}
      </section> : null}
      <LiteNextSteps
        title={overview.attentionCount ? "Review what needs attention" : "Your workspace at a glance"}
        description={effectiveSavedStateOnly ? "These details are saved, not verified live." : "Follow a known area to its current details."}
        saved={effectiveSavedStateOnly}
        items={prioritizeWorkspaceAttention(overview.keyAreas).slice(0, 3).map((item) => ({
          id: item.key, label: item.label, description: item.summary,
          actionLabel: "Open", onClick: item.screen && item.screen !== "home" ? () => goTo(item.screen) : undefined,
        }))}
        className="lite-p1-home-guidance"
      />

      <section className="lite-home-premium-services lite-render-containment lite-render-containment--home" aria-labelledby="lite-home-key-areas">
        <div className="lite-home-premium-section-head">
          <div>
            <span>{overview.attentionCount ? 'What needs you' : 'Your workspace'}</span>
            <h2 id="lite-home-key-areas">{overview.attentionCount ? 'Review these areas next' : 'Everything in one place'}</h2>
            <p>{overview.attentionCount ? 'Only areas that need a closer look should interrupt you.' : 'Open an area when you want its current detail or available actions.'}</p>
          </div>
          {loading ? <span className="lite-home-premium-checking">Checking…</span> : null}
        </div>

        {loading && !overview.keyAreas.length ? <LoadingCard label="Checking workspace status…" /> : overview.keyAreas.map((item) => (
          <LiteActionRow
            key={item.key}
            className="lite-home-key-area"
            label={item.label}
            value={item.statusLabel}
            summary={item.summary}
            attention={item.tone !== 'ready'}
            action={item.screen && item.screen !== 'home' ? { label: 'Open', onClick: () => goTo(item.screen) } : null}
          />
        ))}
      </section>

      <LiteDetailsPanel
        open={workspaceDetailsOpen}
        onClose={() => setWorkspaceDetailsOpen(false)}
        title={overview.workspaceDetails.title}
        description={overview.workspaceDetails.description}
      >
        <div className="lite-home-workspace-details">
          {overview.workspaceDetails.resources.map((item) => (
            <LiteActionRow key={item.key} label={item.label} value={item.value} summary={item.note} attention={['review', 'danger'].includes(item.tone)} />
          ))}
          {overview.workspaceDetails.showWorkflow ? <HomeWorkspaceFlow overallTone={overview.overallTone} attentionCount={overview.attentionCount} savedStateOnly={effectiveSavedStateOnly} checking={loading || refreshing || status.refresh_pending === true} /> : null}
          <LiteTechnicalFacts
            facts={[
              ...overview.workspaceDetails.resources.map((item) => ({ id: item.key, label: item.label, value: item.value, note: item.note, tone: item.tone })),
              { id: 'information-state', label: 'Information', value: effectiveSavedStateOnly ? 'Saved information' : 'Current information' },
              { id: 'last-update', label: 'Last update', value: overview.workspaceDetails.freshness || lastUpdatedLabel || 'Just now' },
            ]}
          />
          <LiteReleaseUpdateCard />
        </div>
      </LiteDetailsPanel>
    </div>
  );
}
