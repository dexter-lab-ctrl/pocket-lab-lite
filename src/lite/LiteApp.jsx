import React, { useEffect, useMemo, useRef, useState } from 'react';
import { QueryClientProvider } from '@tanstack/react-query';
import {
  ArrowLeft,
  Download,
  ExternalLink,
  Maximize2,
  Menu,
  WifiOff,
  X,
} from 'lucide-react';
import { useOnlineStatus } from '../hooks/useOnlineStatus.js';
import { useLiteResource, useLiteStatus } from '../hooks/useLiteStatus.js';
import { liteApi } from '../lib/liteApi.js';
import { liteQueryClient } from '../lib/liteQueryClient.js';
import HomeScreen from './LiteHome.jsx';
import CatalogScreen from './LiteCatalog.jsx';
import IdentityScreen from './LiteIdentity.jsx';
import SecurityScreen from './LiteSecurity.jsx';
import DevicesScreen from './LiteDevices.jsx';
import RulesScreen from './LiteRules.jsx';
import RecoveryScreen from './LiteRecovery.jsx';
import LiteToastHost from './LiteToastHost.jsx';
import { useLiteUiStore } from '../stores/liteUiStore.js';
import {
  GlassCard,
  LiteButton,
  NAV_ITEMS,
  StatusBadge,
  appWorkspaceEmbedAllowed,
  backendBadgeStatus,
  backendLabel,
  resolveSafeAppOpenPath,
} from './LiteUi.jsx';

function currentWorkspaceFromLocation() {
  if (typeof window === 'undefined') return null;
  const match = window.location.pathname.match(/^\/app-workspace\/([^/]+)\/?$/);
  if (!match) return null;
  const appId = decodeURIComponent(match[1] || '').trim();
  if (!appId) return null;
  return {
    appId,
    name: 'App workspace',
    openUrl: '',
    status: 'checking',
    fromTab: 'catalog',
  };
}

function workspacePathForApp(appId) {
  const safeId = encodeURIComponent(String(appId || '').trim());
  return safeId ? `/app-workspace/${safeId}` : '/app-workspace/app';
}

function pushPocketLabPath(path) {
  if (typeof window === 'undefined' || !window.history?.pushState) return;
  if (window.location.pathname === path) return;
  window.history.pushState({ pocketLabLitePath: path }, '', path);
}

function findWorkspaceApp(apps, appId) {
  const wanted = String(appId || '').toLowerCase();
  return apps.find((app) => String(app?.id || '').toLowerCase() === wanted) || null;
}

function appWorkspaceStatusLabel(status) {
  return backendLabel(status, {
    ready: 'Ready',
    review: 'Needs attention',
    danger: 'Needs attention',
    checking: 'Checking',
  });
}

function workspaceSwitcherTabLabel(item) {
  if (item.id === 'catalog') return 'Apps';
  if (item.id === 'identity') return 'Identity';
  return item.label;
}

function WorkspaceQuickSwitcher({
  open,
  triggerRef,
  appName,
  rawStatus,
  statusLabel,
  openUrl,
  onClose,
  onBackToApps,
  onOpenFullScreen,
  onNavigate,
}) {
  const panelRef = useRef(null);
  const firstActionRef = useRef(null);
  const primaryTabs = useMemo(
    () => NAV_ITEMS.filter((item) => ['home', 'catalog', 'devices', 'security', 'recovery'].includes(item.id)),
    [],
  );
  const moreTabs = useMemo(
    () => NAV_ITEMS.filter((item) => !['home', 'catalog', 'devices', 'security', 'recovery'].includes(item.id)),
    [],
  );

  useEffect(() => {
    if (!open) return undefined;

    const focusTimer = window.setTimeout(() => {
      if (firstActionRef.current?.focus) {
        firstActionRef.current.focus();
        return;
      }
      panelRef.current?.focus?.();
    }, 0);

    const closeOnEscape = (event) => {
      if (event.key !== 'Escape') return;
      event.stopPropagation();
      onClose();
    };

    window.addEventListener('keydown', closeOnEscape);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener('keydown', closeOnEscape);
      window.setTimeout(() => triggerRef?.current?.focus?.(), 0);
    };
  }, [open, onClose, triggerRef]);

  if (!open) return null;

  const rememberSafeLastTab = (tabId) => {
    try {
      window.localStorage.setItem('pocketlab:workspace:lastTab', String(tabId || ''));
    } catch {
      // Non-sensitive UI preference only; ignore private-mode storage failures.
    }
  };

  const selectTab = (tabId) => {
    rememberSafeLastTab(tabId);
    onClose();
    onNavigate(tabId);
  };

  const backToApps = () => {
    rememberSafeLastTab('catalog');
    onClose();
    onBackToApps();
  };

  const openAppFullScreen = () => {
    if (!openUrl) return;
    onClose();
    onOpenFullScreen(openUrl);
  };

  return (
    <div className="lite-workspace-quick-switcher-layer" role="presentation">
      <button
        type="button"
        className="lite-workspace-quick-switcher-backdrop"
        onClick={onClose}
        aria-label="Close Pocket Lab switcher"
      />
      <section
        ref={panelRef}
        className="lite-workspace-quick-switcher"
        role="dialog"
        aria-modal="true"
        aria-labelledby="lite-workspace-quick-switcher-title"
        tabIndex={-1}
      >
        <div className="lite-workspace-quick-switcher-head">
          <div>
            <p>Pocket Lab</p>
            <h2 id="lite-workspace-quick-switcher-title">Switch workspace</h2>
          </div>
          <button type="button" className="lite-workspace-quick-switcher-close" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="lite-workspace-quick-switcher-current" aria-label="Current app">
          <span>Current app</span>
          <strong>{appName}</strong>
          <StatusBadge status={backendBadgeStatus(rawStatus)}>{statusLabel}</StatusBadge>
        </div>

        <div className="lite-workspace-quick-switcher-actions">
          <button ref={firstActionRef} type="button" onClick={backToApps}>
            <ArrowLeft className="h-4 w-4" />
            <span>Back to Apps</span>
          </button>
          <button type="button" onClick={openAppFullScreen} disabled={!openUrl}>
            <Maximize2 className="h-4 w-4" />
            <span>Open full screen</span>
          </button>
        </div>

        <div className="lite-workspace-quick-switcher-tabs" aria-label="Pocket Lab tabs">
          {primaryTabs.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} type="button" onClick={() => selectTab(item.id)}>
                <Icon className="h-4 w-4" />
                <span>{workspaceSwitcherTabLabel(item)}</span>
              </button>
            );
          })}
        </div>

        {moreTabs.length ? (
          <div className="lite-workspace-quick-switcher-more">
            <span>More</span>
            <div>
              {moreTabs.map((item) => {
                const Icon = item.icon;
                return (
                  <button key={item.id} type="button" onClick={() => selectTab(item.id)}>
                    <Icon className="h-4 w-4" />
                    <span>{workspaceSwitcherTabLabel(item)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function LiteAppWorkspace({ workspace, onBackToApps, onNavigate, onOpenFullScreen }) {
  const { data, refresh } = useLiteResource(liteApi.catalog, [workspace?.appId]);
  const [frameReady, setFrameReady] = useState(false);
  const [frameFallback, setFrameFallback] = useState(false);
  const [switcherOpen, setSwitcherOpen] = useState(false);
  const switcherTriggerRef = useRef(null);
  const lastSwitcherTriggerRef = useRef(null);

  const apps = useMemo(() => data?.apps || data?.items || [], [data]);
  const catalogApp = useMemo(() => findWorkspaceApp(apps, workspace?.appId), [apps, workspace?.appId]);
  const app = catalogApp || workspace || {};
  const openUrl = resolveSafeAppOpenPath(catalogApp) || resolveSafeAppOpenPath(workspace?.openUrl || '');
  const embedAllowed = appWorkspaceEmbedAllowed(catalogApp || workspace);
  const displayName = app?.name || workspace?.name || 'App workspace';
  const rawStatus = app?.status || (openUrl ? 'ready' : 'checking');
  const statusLabel = appWorkspaceStatusLabel(rawStatus);
  const frameTitle = `${displayName} inside Pocket Lab Lite`;
  const showFrame = Boolean(openUrl && embedAllowed && !frameFallback);

  useEffect(() => {
    const onFocus = () => refresh();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [refresh]);

  useEffect(() => {
    setFrameReady(false);
    setFrameFallback(false);

    if (!openUrl || !embedAllowed) {
      setFrameFallback(true);
    }

    return undefined;
  }, [embedAllowed, openUrl]);

  const openFullScreen = () => {
    if (!openUrl) return;
    onOpenFullScreen(openUrl);
  };

  const openSwitcher = (event) => {
    lastSwitcherTriggerRef.current = event?.currentTarget || switcherTriggerRef.current;
    setSwitcherOpen(true);
  };

  const closeSwitcher = () => {
    setSwitcherOpen(false);
  };

  const navigateFromWorkspace = (tabId) => {
    closeSwitcher();
    onNavigate(tabId);
  };

  return (
    <section className="lite-workspace-shell" aria-label={`${displayName} workspace`}>
      <div className="lite-workspace-bar">
        <div className="lite-workspace-title-block">
          <p className="lite-workspace-eyebrow">Pocket Lab Lite · Self-hosted workspace</p>
          <div className="lite-workspace-heading-row">
            <h1>{displayName}</h1>
            <StatusBadge status={backendBadgeStatus(rawStatus)}>{statusLabel}</StatusBadge>
          </div>
        </div>
        <div className="lite-workspace-actions">
          <LiteButton onClick={onBackToApps} tone="secondary"><ArrowLeft className="h-4 w-4" />Back to Apps</LiteButton>
          <LiteButton onClick={openFullScreen} tone="primary" disabled={!openUrl}><Maximize2 className="h-4 w-4" />Open full screen</LiteButton>
          <button
            ref={switcherTriggerRef}
            type="button"
            className="lite-workspace-more-button lite-workspace-switcher-trigger"
            onClick={openSwitcher}
            aria-label="Open Pocket Lab switcher"
            aria-haspopup="dialog"
            aria-expanded={switcherOpen}
          >
            <span>Switch</span>
          </button>
        </div>
      </div>

      <nav className="lite-workspace-nav-strip" aria-label="Pocket Lab Lite tabs while app is open">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.id} type="button" onClick={() => navigateFromWorkspace(item.id)}>
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <GlassCard className="lite-workspace-frame-card">
        {showFrame ? (
          <div className={`lite-workspace-frame-wrap ${frameReady ? 'is-ready' : ''}`}>
            {!frameReady ? <div className="lite-workspace-frame-loading" role="status">Opening app workspace…</div> : null}
            <iframe
              src={openUrl}
              title={frameTitle}
              className="lite-workspace-frame"
              onLoad={() => {
                setFrameReady(true);
                setFrameFallback(false);
              }}
              onError={() => {
                setFrameReady(false);
                setFrameFallback(true);
              }}
            />
          </div>
        ) : (
          <div className="lite-workspace-fallback" role="status">
            <div className="lite-workspace-fallback-icon"><ExternalLink className="h-6 w-6" /></div>
            <h2>This app opens full screen for safety.</h2>
            <p>This app does not allow being shown inside another page. Pocket Lab kept your tabs available and preserved the app's own security settings.</p>
            <div className="lite-workspace-fallback-actions">
              <LiteButton onClick={openFullScreen} tone="primary" disabled={!openUrl}><Maximize2 className="h-4 w-4" />Open full screen</LiteButton>
              <LiteButton onClick={onBackToApps} tone="secondary"><ArrowLeft className="h-4 w-4" />Back to Apps</LiteButton>
            </div>
          </div>
        )}
      </GlassCard>

      <WorkspaceQuickSwitcher
        open={switcherOpen}
        triggerRef={lastSwitcherTriggerRef}
        appName={displayName}
        rawStatus={rawStatus}
        statusLabel={statusLabel}
        openUrl={openUrl}
        onClose={closeSwitcher}
        onBackToApps={onBackToApps}
        onOpenFullScreen={onOpenFullScreen}
        onNavigate={navigateFromWorkspace}
      />

    </section>
  );
}

class LiteErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="pocket-app-shell theme-pocket-lite-daylight lite-motion-system">
          <main className="pocket-main lite-error-boundary-wrap">
            <GlassCard className="lite-error-boundary-card">
              <div className="lite-devices-mini-icon">
                <WifiOff className="h-5 w-5" />
              </div>
              <h1>Pocket Lab needs a moment</h1>
              <p>Refresh the Devices tab. Your services are still running, and Pocket Lab kept the action safely contained.</p>
              <LiteButton onClick={() => window.location.reload()} tone="secondary">Refresh app</LiteButton>
            </GlassCard>
          </main>
        </div>
      );
    }
    return this.props.children;
  }
}

function LiteAppShell() {
  const active = useLiteUiStore((state) => state.activeTab);
  const setActiveTab = useLiteUiStore((state) => state.setActiveTab);
  const menuOpen = useLiteUiStore((state) => state.mobileMenuOpen);
  const setMenuOpen = useLiteUiStore((state) => state.setMobileMenuOpen);
  const [workspaceApp, setWorkspaceApp] = useState(() => currentWorkspaceFromLocation());
  const online = useOnlineStatus();
  const { status, loading, error, refresh, cacheStatus, refreshing } = useLiteStatus();

  useEffect(() => {
    const syncWorkspaceFromHistory = () => {
      setWorkspaceApp(currentWorkspaceFromLocation());
    };
    window.addEventListener('popstate', syncWorkspaceFromHistory);
    return () => window.removeEventListener('popstate', syncWorkspaceFromHistory);
  }, []);

  const openWorkspace = (app, openUrl) => {
    const appId = app?.id || app?.app_id;
    if (!appId || !resolveSafeAppOpenPath(openUrl || app)) return;
    setWorkspaceApp({
      appId,
      name: app?.name || app?.title || 'App workspace',
      openUrl: resolveSafeAppOpenPath(openUrl || app),
      status: app?.status || 'ready',
      embedAllowed: appWorkspaceEmbedAllowed(app),
      fromTab: active || 'catalog',
    });
    setActiveTab('catalog');
    setMenuOpen(false);
    pushPocketLabPath(workspacePathForApp(appId));
  };

  const closeWorkspaceToTab = (tabId = 'catalog') => {
    setWorkspaceApp(null);
    setActiveTab(tabId);
    setMenuOpen(false);
    pushPocketLabPath('/');
  };

  const openFullScreen = (openUrl) => {
    const target = resolveSafeAppOpenPath(openUrl);
    if (!target) return;
    window.location.assign(target);
  };

  const navigateToTab = (tabId) => {
    closeWorkspaceToTab(tabId);
  };

  const content = workspaceApp ? (
    <LiteAppWorkspace
      workspace={workspaceApp}
      onBackToApps={() => closeWorkspaceToTab('catalog')}
      onNavigate={navigateToTab}
      onOpenFullScreen={openFullScreen}
    />
  ) : ({
    home: <HomeScreen status={status} loading={loading} error={error} refresh={refresh} cacheStatus={cacheStatus} refreshing={refreshing} onNavigate={setActiveTab} />,
    catalog: <CatalogScreen onOpenWorkspace={openWorkspace} />,
    identity: <IdentityScreen />,
    security: <SecurityScreen />,
    devices: <DevicesScreen />,
    rules: <RulesScreen />,
    recovery: <RecoveryScreen />,
  }[active]);

  const shellClassName = `pocket-app-shell theme-pocket-lite-daylight lite-motion-system ${workspaceApp ? 'is-app-workspace' : ''}`;

  return (
    <div className={shellClassName}>
      <a href="#pocket-lite-main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-xl focus:bg-indigo-500 focus:px-4 focus:py-2 focus:text-sm focus:font-black focus:text-white">Skip to Pocket Lab Lite content</a>
      <div className="pocket-app-backdrop" aria-hidden="true" />
      <LiteToastHost />

      {!online && (
        <div className="fixed left-1/2 top-4 z-[90] w-[calc(100vw-2rem)] max-w-2xl -translate-x-1/2 rounded-3xl border border-slate-300/20 bg-slate-950/95 px-4 py-3 text-slate-100 shadow-2xl shadow-black/40 backdrop-blur-xl" role="status">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl border border-slate-300/20 bg-slate-500/10 p-2 text-slate-200"><WifiOff className="h-5 w-5" /></div>
            <div className="min-w-0">
              <p className="text-sm font-black text-white">You are offline</p>
              <p className="mt-1 text-sm text-slate-300">Pocket Lab Lite will show cached information where possible. Changes are paused until your connection returns.</p>
            </div>
          </div>
        </div>
      )}

      <header className="relative z-20 border-b border-white/10 bg-slate-950/70 backdrop-blur-xl">
        <div className="mx-auto flex w-full max-w-[1500px] items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="rounded-2xl border border-indigo-300/25 bg-indigo-500/15 p-2 text-indigo-100"><Download className="h-5 w-5" /></div>
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Pocket Lab Lite</p>
              <p className="text-sm text-slate-400">Self-hosted workspace</p>
            </div>
          </div>
          <button type="button" onClick={() => setMenuOpen(true)} className="rounded-2xl border border-white/10 bg-white/5 p-3 text-slate-100 md:hidden" aria-label="Open navigation"><Menu className="h-5 w-5" /></button>
        </div>
      </header>

      <nav className="pocket-nav-dock scrollbar-none" aria-label="Pocket Lab Lite sections">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button key={item.id} type="button" onClick={() => setActiveTab(item.id)} aria-current={isActive ? 'page' : undefined} className={`pocket-nav-button nav-active-rail-item ${isActive ? 'pocket-nav-button-active' : ''}`}>
              <Icon className="nav-active-rail-icon relative z-10 h-5 w-5" />
              <span className="relative z-10 mt-1 text-[0.68rem] font-bold tracking-wide">{item.label.split(' ')[0]}</span>
            </button>
          );
        })}
      </nav>

      <nav className="pocket-side-rail" aria-label="Pocket Lab Lite primary sections">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button key={item.id} type="button" onClick={() => workspaceApp ? navigateToTab(item.id) : setActiveTab(item.id)} title={item.label} aria-label={item.label} aria-current={isActive ? 'page' : undefined} className={`pocket-side-button nav-active-rail-item ${isActive ? 'pocket-side-button-active' : ''}`}>
              <Icon className="nav-active-rail-icon h-5 w-5" />
            </button>
          );
        })}
      </nav>

      {menuOpen && <div className="mobile-more-backdrop" onClick={() => setMenuOpen(false)} aria-hidden="true" />}
      <aside className={`mobile-more-sheet ${menuOpen ? 'mobile-more-sheet-open' : ''}`} aria-hidden={!menuOpen} aria-label="Pocket Lab Lite sections">
        <div className="flex items-center justify-between gap-3 border-b border-white/10 p-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">Sections</p>
            <h2 className="text-lg font-black text-white">Open Pocket Lab Lite</h2>
          </div>
          <button type="button" onClick={() => setMenuOpen(false)} className="rounded-2xl border border-white/10 bg-white/5 p-2 text-slate-200 hover:bg-white/10" aria-label="Close navigation"><X className="h-5 w-5" /></button>
        </div>
        <div className="grid gap-2 p-4">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <button key={item.id} type="button" onClick={() => workspaceApp ? navigateToTab(item.id) : (setActiveTab(item.id), setMenuOpen(false))} className="mobile-more-item nav-active-rail-item">
                <Icon className="nav-active-rail-icon h-5 w-5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </aside>

      <main id="pocket-lite-main" key={workspaceApp ? `workspace-${workspaceApp.appId}` : active} className="pocket-main nav-page-fade lg:pl-24 xl:pl-28">
        {content}
      </main>
    </div>
  );
}

export default function LiteApp() {
  return (
    <QueryClientProvider client={liteQueryClient}>
      <LiteErrorBoundary>
        <LiteAppShell />
      </LiteErrorBoundary>
    </QueryClientProvider>
  );
}
