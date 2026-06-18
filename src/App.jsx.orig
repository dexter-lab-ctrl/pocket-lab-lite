import React, { useEffect, useState } from 'react';
import { Download, LayoutGrid, ShieldCheck, GitBranch, Activity, Map, ShieldAlert, Workflow, Settings as SettingsIcon, Database, FileCheck, Fingerprint, AlignLeft, Network, Menu, WifiOff, X } from 'lucide-react';
import { useDeviceMotion } from './hooks/useDeviceMotion';
import { useOnlineStatus } from './hooks/useOnlineStatus.js';
import Header from './components/Header';
import OTAUpdater from './components/OTAUpdater';
import ControlPlaneBanner from './components/ControlPlaneBanner.jsx';
import ActivityDrawer from './components/ActivityDrawer.jsx';
import LiveEventPanel from './components/LiveEventPanel.jsx';
import SimpleBottomNavigation from './components/SimpleBottomNavigation.jsx';
import PageGuidance from './components/PageGuidance.jsx';
import FirstRunOnboarding from './components/FirstRunOnboarding.jsx';
import SimpleDashboard from './tabs/SimpleDashboard.jsx';
import SettingsTab from './tabs/SettingsTab.jsx';
import { useExperienceMode } from './context/ExperienceModeContext.jsx';
import { simpleTabLabel } from './lib/simpleLabels.js';
import { SIMPLE_ACTIVITY_TARGET, SIMPLE_HOME_TARGET, simpleMoreItemForTarget, simplePrimaryItemForTarget } from './lib/simpleNavigation.js';
import { groupedNavItems, productAreaForTab } from './lib/productAreas.js';
import AppStoreTab from './tabs/AppStoreTab';
import GitOpsTab from './tabs/GitOpsTab';
import GiteaRegistryTab from './tabs/GiteaRegistryTab';
import DisasterRecoveryTab from './tabs/DisasterRecoveryTab';
import BlueprintTab from './tabs/BlueprintTab';
import IdentityVaultTab from './tabs/IdentityVaultTab';
import LogExplorerTab from './tabs/LogExplorerTab';
import PolicyGuardrailsTab from './tabs/PolicyGuardrailsTab';
import NocTelemetryTab from './tabs/NocTelemetryTab';
import SecurityPostureTab from './tabs/SecurityPostureTab';
import FleetScalingTab from './tabs/FleetScalingTab';
import DriftCenterTab from './tabs/DriftCenterTab';
import ReleaseWorkflowTab from './tabs/ReleaseWorkflowTab';

const NAV_ITEMS = [
  { id: 'appstore', label: 'App Catalog', compactLabel: 'Apps', icon: LayoutGrid },
  { id: 'telemetry', label: 'NOC Telemetry', compactLabel: 'Status', icon: Activity },
  { id: 'security', label: 'Security Posture', compactLabel: 'Safety', icon: ShieldCheck },
  { id: 'gitops', label: 'GitOps Pipeline', compactLabel: 'GitOps', icon: GitBranch },
  { id: 'release', label: 'Release Workflow', compactLabel: 'Release', icon: Workflow },
  { id: 'drift', label: 'Drift Center', compactLabel: 'Drift', icon: ShieldAlert },
  { id: 'blueprint', label: 'System Map', compactLabel: 'Map', icon: Map },
  { id: 'fleet', label: 'Mesh Fleet', compactLabel: 'Fleet', icon: Network },
  { id: 'vault', label: 'Identity Vault', compactLabel: 'Vault', icon: Fingerprint },
  { id: 'logs', label: 'Log Explorer', compactLabel: 'Logs', icon: AlignLeft },
  { id: 'opa', label: 'Policy Guardrails', compactLabel: 'Policy', icon: FileCheck },
  { id: 'recovery', label: 'Disaster Recovery', compactLabel: 'Recover', icon: Database },
  { id: 'settings', label: 'Settings', compactLabel: 'Settings', icon: SettingsIcon },
];

export default function App() {
  const { experienceMode } = useExperienceMode();
  const [activeTab, setActiveTab] = useState('appstore');
  const [simpleActiveTarget, setSimpleActiveTarget] = useState(SIMPLE_HOME_TARGET);
  const [deferredPrompt, setDeferredPrompt] = useState(null);
  const [mobileMoreOpen, setMobileMoreOpen] = useState(false);
  const { motionEnabled, getParallaxStyle, handleEnableMotion } = useDeviceMotion();
  const online = useOnlineStatus();
  const isSimpleMode = experienceMode === 'simple';

  useEffect(() => {
    const handleBeforeInstallPrompt = (event) => {
      event.preventDefault();
      setDeferredPrompt(event);
    };
    window.addEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
    return () => window.removeEventListener('beforeinstallprompt', handleBeforeInstallPrompt);
  }, []);

  const handleInstallClick = async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === 'accepted') setDeferredPrompt(null);
  };

  const handleTabChange = (tabId) => {
    if (navigator.vibrate) navigator.vibrate(35);
    setActiveTab(tabId);
    setMobileMoreOpen(false);
  };

  const handleSimpleTargetChange = (target) => {
    if (navigator.vibrate) navigator.vibrate(35);
    setSimpleActiveTarget(target);
    if (target !== SIMPLE_HOME_TARGET && target !== SIMPLE_ACTIVITY_TARGET) {
      setActiveTab(target);
    }
  };

  const handleOnboardingNavigate = (tabId) => {
    if (isSimpleMode) {
      handleSimpleTargetChange(tabId);
      return;
    }
    handleTabChange(tabId);
  };

  const renderTabById = (tabId, simpleMode = false) => (
    <>
      {tabId === 'appstore' && <AppStoreTab simpleMode={simpleMode} />}
      {tabId === 'blueprint' && <BlueprintTab simpleMode={simpleMode} motionEnabled={motionEnabled} getParallaxStyle={getParallaxStyle} handleEnableMotion={handleEnableMotion} />}
      {tabId === 'gitops' && <GitOpsTab simpleMode={simpleMode} />}
      {tabId === 'registry' && <GiteaRegistryTab simpleMode={simpleMode} />}
      {tabId === 'recovery' && <DisasterRecoveryTab simpleMode={simpleMode} />}
      {tabId === 'vault' && <IdentityVaultTab simpleMode={simpleMode} />}
      {tabId === 'logs' && <LogExplorerTab simpleMode={simpleMode} />}
      {tabId === 'opa' && <PolicyGuardrailsTab simpleMode={simpleMode} />}
      {tabId === 'telemetry' && <NocTelemetryTab simpleMode={simpleMode} />}
      {tabId === 'security' && <SecurityPostureTab simpleMode={simpleMode} />}
      {tabId === 'fleet' && <FleetScalingTab simpleMode={simpleMode} />}
      {tabId === 'release' && <ReleaseWorkflowTab simpleMode={simpleMode} />}
      {tabId === 'drift' && <DriftCenterTab simpleMode={simpleMode} />}
      {tabId === 'settings' && <SettingsTab simpleMode={simpleMode} />}
    </>
  );

  const renderActiveTab = () => renderTabById(activeTab, false);

  const renderSimpleContent = () => {
    if (simpleActiveTarget === SIMPLE_HOME_TARGET) {
      return <SimpleDashboard onNavigate={handleSimpleTargetChange} />;
    }

    if (simpleActiveTarget === SIMPLE_ACTIVITY_TARGET) {
      return (
        <div className="mx-auto w-full max-w-[1500px] px-4 pb-28 pt-6 sm:px-6 lg:px-8">
          <ControlPlaneBanner simpleMode />
          <section className="simple-content-card rounded-[2rem] border border-white/10 bg-slate-900/55 p-5 shadow-2xl shadow-blue-950/20 backdrop-blur-xl sm:p-6">
            <LiveEventPanel simpleMode title="Activity" description="Review recent installs, updates, backups, device invites, safety checks, and system health updates." subjectPrefixes={['pocketlab.events.', 'pocketlab.audit.']} maxItems={20} />
          </section>
        </div>
      );
    }

    const simpleItem = simplePrimaryItemForTarget(simpleActiveTarget) || simpleMoreItemForTarget(simpleActiveTarget);
    return (
      <div className="mx-auto w-full max-w-[1500px] px-4 pb-28 pt-6 sm:px-6 lg:px-8">
        <ControlPlaneBanner simpleMode />
        <section className="mb-5 rounded-[2rem] border border-blue-300/20 bg-blue-500/10 p-5 shadow-2xl shadow-blue-950/20 sm:p-6">
          <p className="text-xs font-black uppercase tracking-[0.22em] text-blue-200">Simple Mode</p>
          <h1 className="mt-2 text-2xl font-black text-white">{simpleItem?.label || simpleTabLabel(simpleActiveTarget, 'Pocket Lab')}</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{simpleItem?.description || 'Use this area with safe defaults and plain-language guidance.'}</p>
        </section>
        <PageGuidance tabId={simpleActiveTarget} className="mb-5" />
        <section className="simple-content-card rounded-[2rem] border border-white/10 bg-slate-900/55 p-5 shadow-2xl shadow-blue-950/20 backdrop-blur-xl sm:p-6">
          {renderTabById(simpleActiveTarget, true)}
        </section>
      </div>
    );
  };

  const navLabel = (item) => isSimpleMode ? simpleTabLabel(item.id, item.compactLabel) : item.compactLabel;
  const navGroups = groupedNavItems(NAV_ITEMS);
  const activeArea = navGroups.find((area) => area.key === productAreaForTab(activeTab));
  const primaryMobileItems = NAV_ITEMS.slice(0, 6);
  const secondaryMobileItems = NAV_ITEMS.slice(6);
  const secondaryMobileIds = new Set(secondaryMobileItems.map((item) => item.id));
  const secondaryMobileGroups = navGroups
    .map((area) => ({ ...area, items: area.items.filter((item) => secondaryMobileIds.has(item.id)) }))
    .filter((area) => area.items.length > 0);

  return (
    <div className={`pocket-app-shell theme-control-plane-graphite ${isSimpleMode ? 'theme-midnight-saas-simple' : ''}`}>
      <a href="#pocket-main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[80] focus:rounded-xl focus:bg-indigo-500 focus:px-4 focus:py-2 focus:text-sm focus:font-black focus:text-white">
        Skip to Pocket Lab content
      </a>
      <div className="pocket-app-backdrop" aria-hidden="true" />

      {!online && (
        <div className="fixed left-1/2 top-4 z-[90] w-[calc(100vw-2rem)] max-w-2xl -translate-x-1/2 rounded-3xl border border-slate-300/20 bg-slate-950/95 px-4 py-3 text-slate-100 shadow-2xl shadow-black/40 backdrop-blur-xl" role="status">
          <div className="flex items-start gap-3">
            <div className="rounded-2xl border border-slate-300/20 bg-slate-500/10 p-2 text-slate-200"><WifiOff className="h-5 w-5" /></div>
            <div className="min-w-0">
              <p className="text-sm font-black text-white">{isSimpleMode ? 'You are offline' : 'Browser offline'}</p>
              <p className="mt-1 text-sm text-slate-300">{isSimpleMode ? 'Pocket Lab will keep showing cached information where possible. Changes are paused until your connection returns.' : 'Live events and write flows are paused while the browser is offline.'}</p>
            </div>
          </div>
        </div>
      )}

      <FirstRunOnboarding onNavigate={handleOnboardingNavigate} />

      {deferredPrompt && (
        <div className="fixed top-4 left-1/2 z-50 w-[calc(100vw-2rem)] max-w-xl -translate-x-1/2 rounded-3xl border border-indigo-300/30 bg-slate-950/95 px-4 py-3 shadow-2xl shadow-indigo-950/40 backdrop-blur-xl">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="flex items-start gap-3 min-w-0">
              <div className="rounded-2xl border border-indigo-300/25 bg-indigo-500/10 p-2 text-indigo-200"><Download className="h-5 w-5" /></div>
              <div className="min-w-0 text-sm">
                <div className="font-black text-white">Install Pocket Lab</div>
                <div className="text-slate-400">Add the control plane to your device for faster access and offline readiness.</div>
              </div>
            </div>
            <button type="button" onClick={handleInstallClick} className="pocket-button pocket-button-primary sm:ml-auto">Install</button>
          </div>
        </div>
      )}

      {isSimpleMode ? (
        <>
          <main id="pocket-main" key={`simple-${simpleActiveTarget}`} className="relative z-10 nav-page-fade">
            {renderSimpleContent()}
          </main>
          <SimpleBottomNavigation currentTarget={simpleActiveTarget} onSelectTarget={handleSimpleTargetChange} />
          <ActivityDrawer />
        </>
      ) : (
        <>
          <div className="relative z-10">
            <Header activeTab={activeTab} setActiveTab={handleTabChange} />
            <div className="mx-auto w-full max-w-[1680px] px-4 sm:px-6 lg:px-8">
              <ControlPlaneBanner />
              <OTAUpdater />
            </div>
            <main id="pocket-main" key={activeTab} className="pocket-main nav-page-fade lg:pl-24 xl:pl-28">
              {activeArea ? (
                <div className="product-area-banner mb-5">
                  <div>
                    <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-200/80">{isSimpleMode ? activeArea.simpleLabel : activeArea.label}</p>
                    <p className="mt-1 text-sm leading-6 text-slate-300">{activeArea.description}</p>
                  </div>
                </div>
              ) : null}
              <PageGuidance tabId={activeTab} className="mb-5" />
              {renderActiveTab()}
            </main>
          </div>

          <nav className="pocket-side-rail" aria-label="Pocket Lab primary sections">
            {NAV_ITEMS.map((item) => {
              const isActive = activeTab === item.id;
              const Icon = item.icon;
              return (
                <button key={item.id} type="button" onClick={() => handleTabChange(item.id)} title={isSimpleMode ? simpleTabLabel(item.id, item.label) : item.label} aria-label={isSimpleMode ? simpleTabLabel(item.id, item.label) : item.label} aria-current={isActive ? 'page' : undefined} className={`pocket-side-button nav-active-rail-item ${isActive ? 'pocket-side-button-active' : ''}`}>
                  <Icon className="nav-active-rail-icon h-5 w-5" />
                </button>
              );
            })}
          </nav>

          <nav className="pocket-nav-dock scrollbar-none" aria-label="Pocket Lab mobile sections">
            {primaryMobileItems.map((item) => {
              const isActive = activeTab === item.id;
              const Icon = item.icon;
              return (
                <button key={item.id} type="button" onClick={() => handleTabChange(item.id)} aria-current={isActive ? 'page' : undefined} className={`pocket-nav-button nav-active-rail-item ${isActive ? 'pocket-nav-button-active' : ''}`}>
                  <Icon className="nav-active-rail-icon relative z-10 h-5 w-5" />
                  <span className="relative z-10 mt-1 text-[0.68rem] font-bold tracking-wide">{navLabel(item)}</span>
                </button>
              );
            })}
            <button type="button" onClick={() => setMobileMoreOpen(true)} className="pocket-nav-button" aria-label="More Pocket Lab sections">
              <Menu className="relative z-10 h-5 w-5" />
              <span className="relative z-10 mt-1 text-[0.68rem] font-bold tracking-wide">More</span>
            </button>
          </nav>

          {mobileMoreOpen && <div className="mobile-more-backdrop" onClick={() => setMobileMoreOpen(false)} aria-hidden="true" />}
          <aside className={`mobile-more-sheet ${mobileMoreOpen ? 'mobile-more-sheet-open' : ''}`} aria-hidden={!mobileMoreOpen} aria-label="More Pocket Lab sections">
            <div className="flex items-center justify-between gap-3 border-b border-white/10 p-4">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">More sections</p>
                <h2 className="text-lg font-black text-white">Open another Pocket Lab area</h2>
              </div>
              <button type="button" onClick={() => setMobileMoreOpen(false)} className="rounded-2xl border border-white/10 bg-white/5 p-2 text-slate-200 hover:bg-white/10" aria-label="Close more sections"><X className="h-5 w-5" /></button>
            </div>
            <div className="grid gap-4 p-4">
              {secondaryMobileGroups.map((area) => (
                <section key={area.key} className="mobile-more-group">
                  <div className="mb-2 px-1">
                    <p className="text-[10px] font-black uppercase tracking-[0.18em] text-cyan-200/75">{isSimpleMode ? area.simpleLabel : area.label}</p>
                    <p className="mt-1 text-xs text-slate-500">{area.description}</p>
                  </div>
                  <div className="grid gap-2">
                    {area.items.map((item) => {
                      const isActive = activeTab === item.id;
                      const Icon = item.icon;
                      return (
                        <button key={item.id} type="button" onClick={() => handleTabChange(item.id)} aria-current={isActive ? 'page' : undefined} className={`mobile-more-item nav-active-rail-item ${isActive ? 'mobile-more-item-active' : ''}`}>
                          <Icon className="nav-active-rail-icon h-5 w-5" />
                          <span>{isSimpleMode ? simpleTabLabel(item.id, item.label) : item.label}</span>
                        </button>
                      );
                    })}
                  </div>
                </section>
              ))}
            </div>
          </aside>

          <ActivityDrawer />
        </>
      )}
    </div>
  );
}
