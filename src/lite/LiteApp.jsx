import React, { useState } from 'react';
import {
  Download,
  Menu,
  WifiOff,
  X,
} from 'lucide-react';
import { useOnlineStatus } from '../hooks/useOnlineStatus.js';
import { useLiteStatus } from '../hooks/useLiteStatus.js';
import HomeScreen from './LiteHome.jsx';
import CatalogScreen from './LiteCatalog.jsx';
import IdentityScreen from './LiteIdentity.jsx';
import SecurityScreen from './LiteSecurity.jsx';
import DevicesScreen from './LiteDevices.jsx';
import RulesScreen from './LiteRules.jsx';
import RecoveryScreen from './LiteRecovery.jsx';
import { GlassCard, LiteButton, NAV_ITEMS } from './LiteUi.jsx';

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
  const [active, setActive] = useState('home');
  const [menuOpen, setMenuOpen] = useState(false);
  const online = useOnlineStatus();
  const { status, loading, error, refresh } = useLiteStatus();

  const content = {
    home: <HomeScreen status={status} loading={loading} error={error} refresh={refresh} onNavigate={setActive} />,
    catalog: <CatalogScreen />,
    identity: <IdentityScreen />,
    security: <SecurityScreen />,
    devices: <DevicesScreen />,
    rules: <RulesScreen />,
    recovery: <RecoveryScreen />,
  }[active];

  return (
    <div className="pocket-app-shell theme-pocket-lite-daylight lite-motion-system">
      <a href="#pocket-lite-main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-xl focus:bg-indigo-500 focus:px-4 focus:py-2 focus:text-sm focus:font-black focus:text-white">Skip to Pocket Lab Lite content</a>
      <div className="pocket-app-backdrop" aria-hidden="true" />

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
            <button key={item.id} type="button" onClick={() => setActive(item.id)} aria-current={isActive ? 'page' : undefined} className={`pocket-nav-button nav-active-rail-item ${isActive ? 'pocket-nav-button-active' : ''}`}>
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
            <button key={item.id} type="button" onClick={() => setActive(item.id)} title={item.label} aria-label={item.label} aria-current={isActive ? 'page' : undefined} className={`pocket-side-button nav-active-rail-item ${isActive ? 'pocket-side-button-active' : ''}`}>
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
              <button key={item.id} type="button" onClick={() => { setActive(item.id); setMenuOpen(false); }} className="mobile-more-item nav-active-rail-item">
                <Icon className="nav-active-rail-icon h-5 w-5" />
                <span>{item.label}</span>
              </button>
            );
          })}
        </div>
      </aside>

      <main id="pocket-lite-main" key={active} className="pocket-main nav-page-fade lg:pl-24 xl:pl-28">
        {content}
      </main>
    </div>
  );
}

export default function LiteApp() {
  return (
    <LiteErrorBoundary>
      <LiteAppShell />
    </LiteErrorBoundary>
  );
}
