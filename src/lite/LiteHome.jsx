import React, { useCallback, useMemo, useState } from 'react';
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
  LiteTechnicalDetails,
} from './LiteUi.jsx';
import { LiteDetailsPanel } from './LiteOverlay.jsx';
import LiteReleaseUpdateCard from './LiteReleaseUpdateCard.jsx';

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
      eyebrow: 'Workspace pulse',
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
      eyebrow: 'Workspace pulse',
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
      eyebrow: 'Workspace pulse',
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
    eyebrow: 'Workspace pulse',
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
        description="Your workspace status and the next useful action."
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

      <section className="lite-home-premium-services lite-render-containment lite-render-containment--home" aria-labelledby="lite-home-key-areas">
        <div className="lite-home-premium-section-head">
          <div>
            <span>Key areas</span>
            <h2 id="lite-home-key-areas">Where to look next</h2>
            <p>Open an area when you want its current detail and available actions.</p>
          </div>
          {loading ? <span className="lite-home-premium-checking">Checking…</span> : null}
        </div>

        {loading && !overview.keyAreas.length ? <LoadingCard label="Loading workspace status…" /> : overview.keyAreas.map((item) => (
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
          <LiteTechnicalDetails>
            <p>{effectiveSavedStateOnly ? 'Showing saved workspace information.' : 'Showing current workspace information.'} Last status: {overview.workspaceDetails.freshness}.</p>
          </LiteTechnicalDetails>
          <LiteReleaseUpdateCard />
        </div>
      </LiteDetailsPanel>
    </div>
  );
}
