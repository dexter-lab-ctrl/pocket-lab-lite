import React, { memo, useCallback, useMemo } from 'react';
import {
  Activity,
  ChevronRight,
  Cpu,
  Database,
  HardDrive,
  LayoutGrid,
  MemoryStick,
  Network,
  Server,
  ShieldCheck,
  Smartphone,
  Sparkles,
  Thermometer,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { formatLiteTime } from '../lib/liteApi.js';
import { buildLiteHomeOverview } from '../lib/liteHomePresentation.js';
import {
  GlassCard,
  StatusBadge,
  StateSurface,
  PageHeader,
  LiteRefreshButton,
  LoadingCard,
} from './LiteUi.jsx';
import {
  LiteElevationSurface,
  LiteMotionReveal,
  LitePressableButton,
  triggerLiteTactileFeedback,
} from './LiteMotion.jsx';

const HOME_STAT_ICONS = Object.freeze({
  apps: LayoutGrid,
  devices: Smartphone,
  safety: ShieldCheck,
  access: Network,
});

const HOME_RESOURCE_ICONS = Object.freeze({
  processor: Cpu,
  temperature: Thermometer,
  storage: HardDrive,
  memory: MemoryStick,
});

const HOME_SERVICE_ICONS = Object.freeze({
  app_catalog: LayoutGrid,
  device_fleet: Smartphone,
  security: ShieldCheck,
  recovery: Database,
  remote_access: Network,
  identity_access: ShieldCheck,
  control_api: Server,
  worker_execution: Activity,
  command_bus: Sparkles,
  policy_compliance: ShieldCheck,
  database: Database,
  local_source_store: HardDrive,
});

function badgeStatus(tone) {
  if (tone === 'ready') return 'healthy';
  if (tone === 'danger') return 'failed';
  return 'degraded';
}

const HomeStatCard = memo(function HomeStatCard({ item, onNavigate }) {
  const Icon = HOME_STAT_ICONS[item.key] || Activity;
  return (
    <LiteElevationSurface as="article" settle className={`lite-home-premium-stat is-${item.key}`}>
      <button type="button" onClick={() => { triggerLiteTactileFeedback('selection'); onNavigate(item.screen); }} aria-label={`Open ${item.label}`}>
        <span className="lite-home-premium-stat-icon"><Icon className="h-5 w-5" /></span>
        <span className="lite-home-premium-stat-copy">
          <small>{item.label}</small>
          <strong>{item.value}</strong>
          <em>{item.note}</em>
        </span>
        <ChevronRight className="h-4 w-4" aria-hidden="true" />
      </button>
    </LiteElevationSurface>
  );
});

const HomeResourceCard = memo(function HomeResourceCard({ item }) {
  const Icon = HOME_RESOURCE_ICONS[item.key] || Activity;
  return (
    <div className={`lite-home-premium-resource is-${item.tone}`}>
      <span><Icon className="h-4 w-4" /></span>
      <div>
        <small>{item.label}</small>
        <strong>{item.value}</strong>
        <em>{item.note}</em>
      </div>
    </div>
  );
});

const HomeServiceCard = memo(function HomeServiceCard({ item, onNavigate }) {
  const Icon = HOME_SERVICE_ICONS[item.key] || Activity;
  const interactive = item.screen && item.screen !== 'home';
  const content = (
    <>
      <span className={`lite-home-premium-service-icon is-${item.tone}`}><Icon className="h-5 w-5" /></span>
      <span className="lite-home-premium-service-copy">
        <strong>{item.label}</strong>
        <small>{item.summary}</small>
      </span>
      <StatusBadge status={badgeStatus(item.tone)}>{item.statusLabel}</StatusBadge>
      {interactive ? <ChevronRight className="h-4 w-4" aria-hidden="true" /> : null}
    </>
  );

  return (
    <LiteElevationSurface as="article" settle className={`lite-home-premium-service is-${item.tone}`}>
      {interactive ? (
        <button type="button" onClick={() => { triggerLiteTactileFeedback('selection'); onNavigate(item.screen); }} aria-label={`Open ${item.label}`}>
          {content}
        </button>
      ) : (
        <div>{content}</div>
      )}
    </LiteElevationSurface>
  );
});

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
  const overview = useMemo(
    () => buildLiteHomeOverview(status, { savedStateOnly, backendReachable }),
    [backendReachable, savedStateOnly, status],
  );
  const checkedLabel = lastUpdatedLabel || (status.checked_at ? formatLiteTime(status.checked_at) : 'Not checked yet');

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
        description="A focused view of your apps, devices, safety, backups, and the next useful action."
        actions={<LiteRefreshButton scope="home" refresh={refresh} cacheStatus={cacheStatus} error={error} refreshing={refreshing} />}
      />

      {error ? (
        <StateSurface
          tone="degraded"
          title="Current information is temporarily unavailable"
          description={error}
          className="mb-5"
        />
      ) : null}

      <LiteMotionReveal as="section" className="lite-home-hero lite-home-premium-hero" motionKey={overview.heroTitle}>
        <div className="lite-home-hero-copy">
          <div className={`lite-home-pill is-${overview.overallTone}`}>
            <span className="lite-ready-dot" />
            {savedStateOnly ? 'Showing saved information' : overview.overallTone === 'ready' ? 'Workspace ready' : 'Review recommended'}
          </div>
          <h2>{overview.heroTitle}</h2>
          <p>{overview.heroSummary}</p>

          <div className="lite-home-premium-actions" aria-label="Workspace shortcuts">
            <LitePressableButton className="lite-home-native-action is-primary" haptic="accepted" onClick={() => goTo(overview.nextAction.screen)}>
              <Sparkles className="h-4 w-4" />
              <span>{overview.nextAction.label}</span>
            </LitePressableButton>
            <LitePressableButton className="lite-home-native-action" haptic="selection" onClick={() => goTo('catalog')}>
              <LayoutGrid className="h-4 w-4" />
              <span>Apps</span>
            </LitePressableButton>
            <LitePressableButton className="lite-home-native-action" haptic="selection" onClick={() => goTo('devices')}>
              <Smartphone className="h-4 w-4" />
              <span>Devices</span>
            </LitePressableButton>
            <LitePressableButton className="lite-home-native-action" haptic="selection" onClick={() => goTo('recovery')}>
              <Database className="h-4 w-4" />
              <span>Backups</span>
            </LitePressableButton>
          </div>
        </div>

        <LiteElevationSurface as="aside" settle active={overview.overallTone !== 'ready'} className={`lite-home-readiness-card lite-home-premium-priority is-${overview.nextAction.tone}`}>
          <span className="lite-home-premium-priority-icon"><Sparkles className="h-5 w-5" /></span>
          <p className="lite-home-card-label">Recommended next step</p>
          <strong>{overview.nextAction.title}</strong>
          <p>{overview.nextAction.detail}</p>
          <LitePressableButton className="lite-home-priority-action" haptic="accepted" onClick={() => goTo(overview.nextAction.screen)}>
            <span>{overview.nextAction.label}</span>
            <ChevronRight className="h-4 w-4" />
          </LitePressableButton>
        </LiteElevationSurface>
      </LiteMotionReveal>

      <section className="lite-home-premium-overview" aria-label="Workspace overview">
        {overview.stats.map((item) => (
          <HomeStatCard key={item.key} item={item} onNavigate={goTo} />
        ))}
      </section>

      <section className="lite-home-premium-detail-grid lite-render-containment lite-render-containment--home">
        <GlassCard as={LiteElevationSurface} settle className="lite-home-premium-capacity">
          <div className="lite-home-premium-section-head">
            <div>
              <span>Workspace device</span>
              <h2>{status.device?.name || 'Pocket Lab Lite'}</h2>
              <p>Current capacity for apps, backups, and private services.</p>
            </div>
            <StatusBadge status={badgeStatus(overview.overallTone)}>
              {savedStateOnly ? 'Saved state' : overview.overallTone === 'ready' ? 'Available' : 'Review'}
            </StatusBadge>
          </div>
          <div className="lite-home-premium-resource-grid">
            {overview.resources.map((item) => <HomeResourceCard key={item.key} item={item} />)}
          </div>
          <div className="lite-home-premium-freshness">
            {backendReachable ? <Wifi className="h-4 w-4" /> : <WifiOff className="h-4 w-4" />}
            <span>{savedStateOnly ? 'Saved information' : 'Current information'} · {checkedLabel}</span>
          </div>
        </GlassCard>

        <GlassCard as={LiteElevationSurface} settle className="lite-home-premium-readiness">
          <div className="lite-home-premium-section-head">
            <div>
              <span>Workspace readiness</span>
              <h2>{overview.readyCount} of {overview.totalCount || '—'} areas ready</h2>
              <p>{overview.attentionCount ? `${overview.attentionCount} ${overview.attentionCount === 1 ? 'area is' : 'areas are'} worth reviewing.` : 'No immediate follow-up is required.'}</p>
            </div>
            <span className={`lite-home-premium-readiness-ring is-${overview.overallTone}`} aria-label={`${overview.readyCount} of ${overview.totalCount} areas ready`}>
              <strong>{overview.readyCount}</strong>
              <small>ready</small>
            </span>
          </div>
          <div className="lite-home-premium-trust-note">
            <ShieldCheck className="h-5 w-5" />
            <div>
              <strong>Private by design</strong>
              <p>Apps and device operations stay inside your Pocket Lab control plane.</p>
            </div>
          </div>
        </GlassCard>
      </section>

      <section className="lite-home-premium-services lite-render-containment lite-render-containment--home" aria-labelledby="lite-home-key-areas">
        <div className="lite-home-premium-section-head">
          <div>
            <span>Key areas</span>
            <h2 id="lite-home-key-areas">Workspace status</h2>
            <p>Friendly summaries of the areas that keep Pocket Lab Lite useful and protected.</p>
          </div>
          {loading ? <span className="lite-home-premium-checking">Checking…</span> : null}
        </div>

        {loading && !overview.services.length ? <LoadingCard label="Loading workspace status…" /> : (
          <div className="lite-home-premium-service-grid">
            {overview.services.map((item) => (
              <HomeServiceCard key={item.key} item={item} onNavigate={goTo} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
