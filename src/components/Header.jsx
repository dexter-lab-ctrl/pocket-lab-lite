import React, { useState, useEffect, useRef } from 'react';
import { useExperienceMode } from '../context/ExperienceModeContext.jsx';
import { simpleTabLabel } from '../lib/simpleLabels.js';
import ModeSwitcher from './ModeSwitcher.jsx';
import {
  Package,
  Network,
  Activity,
  ShieldCheck,
  TestTube2,
  Database,
  CloudCog,
  Fingerprint,
  AlignLeft,
  FileCheck,
  GitBranch,
  Workflow,
  ChevronLeft,
  ChevronRight,
  Radar,
} from 'lucide-react';

const tabs = [
  { id: 'appstore', label: 'Service Catalog', icon: Package },
  { id: 'blueprint', label: 'System Map', icon: Network },
  { id: 'gitops', label: 'Environment Updates', icon: CloudCog },
  { id: 'registry', label: 'Service Registry', icon: GitBranch },
  { id: 'vault', label: 'Identity & Access', icon: Fingerprint },
  { id: 'logs', label: 'Activity & Evidence', icon: AlignLeft },
  { id: 'opa', label: 'Policy & Compliance', icon: FileCheck },
  { id: 'telemetry', label: 'System Operations', icon: Activity },
  { id: 'security', label: 'Security Posture', icon: ShieldCheck },
  { id: 'drift', label: 'Configuration Health', icon: Radar },
  { id: 'release', label: 'Release Workflow', icon: FileCheck },
  { id: 'fleet', label: 'Device Fleet', icon: Workflow },
  { id: 'recovery', label: 'Recovery Management', icon: Database },
];

export default function Header({ activeTab, setActiveTab }) {
  const { experienceMode } = useExperienceMode();
  const isSimple = experienceMode === 'simple';
  const activeMeta = tabs.find((tab) => tab.id === activeTab) || tabs[0];
  const [scrolled, setScrolled] = useState(false);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);
  const scrollContainerRef = useRef(null);
  const isDevMode = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const checkScroll = () => {
    if (!scrollContainerRef.current) return;
    const { scrollLeft, scrollWidth, clientWidth } = scrollContainerRef.current;
    setCanScrollLeft(scrollLeft > 0);
    setCanScrollRight(Math.ceil(scrollLeft) < scrollWidth - clientWidth - 1);
  };

  useEffect(() => {
    checkScroll();
    window.addEventListener('resize', checkScroll);
    return () => window.removeEventListener('resize', checkScroll);
  }, []);

  useEffect(() => {
    const activeEl = document.getElementById(`tab-${activeTab}`);
    if (activeEl && scrollContainerRef.current) {
      setTimeout(() => {
        activeEl.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        checkScroll();
      }, 50);
    }
  }, [activeTab]);

  const scroll = (direction) => {
    if (!scrollContainerRef.current) return;
    scrollContainerRef.current.scrollBy({ left: direction === 'left' ? -320 : 320, behavior: 'smooth' });
  };

  const handleWheel = (event) => {
    if (!scrollContainerRef.current) return;
    if (Math.abs(event.deltaY) > Math.abs(event.deltaX)) scrollContainerRef.current.scrollLeft += event.deltaY;
  };

  const handleTabClick = (id) => {
    setActiveTab(id);
    if (typeof window !== 'undefined' && navigator.vibrate) navigator.vibrate(10);
  };

  const headerLabel = isSimple ? simpleTabLabel(activeMeta.id, activeMeta.label) : activeMeta.label;

  return (
    <header className={`sticky top-0 z-40 border-b border-white/10 transition-all duration-300 ${scrolled ? 'bg-slate-950/90 shadow-[0_18px_50px_rgba(0,0,0,0.42)] backdrop-blur-2xl' : 'bg-slate-950/72 backdrop-blur-xl'}`}>
      <div className="mx-auto max-w-[1800px] px-3 sm:px-4 lg:px-6">
        <div className="flex flex-col gap-3 py-3 lg:flex-row lg:items-center">
          <div className="flex min-w-0 items-center justify-between gap-3 lg:w-[24rem] lg:justify-start">
            <div className="flex min-w-0 items-center gap-3">
              <div className={`grid h-11 w-11 place-items-center rounded-2xl border shadow-lg ${isDevMode ? 'border-orange-400/30 bg-orange-500/15 text-orange-200 shadow-orange-950/20' : 'border-indigo-300/30 bg-indigo-500/15 text-indigo-200 shadow-indigo-950/30'}`}>
                <TestTube2 className="h-5 w-5" />
              </div>
              <div className="min-w-0">
                <div className="flex min-w-0 items-center gap-2">
                  <h1 className="truncate text-lg font-black tracking-tight text-white sm:text-xl">Pocket Lab</h1>
                  <span className={`health-breathing-dot h-2.5 w-2.5 shrink-0 rounded-full ${isDevMode ? 'health-dot-degraded bg-orange-300' : 'health-dot-healthy bg-emerald-300'} shadow-[0_0_18px_currentColor]`} />
                </div>
                <div className="truncate text-xs text-slate-400">{headerLabel} · {isDevMode ? 'Local dev control plane' : 'Control plane'}</div>
              </div>
            </div>
            <ModeSwitcher compact className="hidden sm:flex" />
          </div>

          <nav className="min-w-0 flex-1" aria-label="Pocket Lab primary navigation">
            <div className="relative rounded-[1.6rem] border border-white/10 bg-black/15 p-1 shadow-inner shadow-black/25">
              <div className="pointer-events-none absolute inset-y-1 left-1 w-10 rounded-l-[1.35rem] bg-gradient-to-r from-slate-950/90 to-transparent" />
              <div className="pointer-events-none absolute inset-y-1 right-1 w-10 rounded-r-[1.35rem] bg-gradient-to-l from-slate-950/90 to-transparent" />
              <div className="flex items-center gap-1">
                {canScrollLeft && <button type="button" onClick={() => scroll('left')} aria-label="Scroll tabs left" className="z-10 ml-1 rounded-2xl border border-white/10 bg-slate-950/90 p-2 text-white shadow-lg transition hover:bg-slate-900"><ChevronLeft className="h-4 w-4" /></button>}
                <div ref={scrollContainerRef} onWheel={handleWheel} onScroll={checkScroll} className="no-scrollbar flex items-center gap-1 overflow-x-auto scroll-smooth px-1 py-1">
                  {tabs.map((tab) => {
                    const isActive = activeTab === tab.id;
                    const label = isSimple ? simpleTabLabel(tab.id, tab.label) : tab.label;
                    return (
                      <button key={tab.id} id={`tab-${tab.id}`} type="button" onClick={() => handleTabClick(tab.id)} aria-current={isActive ? 'page' : undefined} className={`nav-active-rail-item group flex min-h-11 shrink-0 items-center gap-2 rounded-2xl border px-3 py-2 text-xs font-black transition-all duration-200 sm:text-sm ${isActive ? 'border-indigo-300/30 bg-indigo-500/20 text-white shadow-lg shadow-indigo-950/30' : 'border-transparent text-slate-400 hover:border-white/10 hover:bg-white/5 hover:text-white'}`}>
                        <tab.icon className={`nav-active-rail-icon h-4 w-4 ${isActive ? 'text-indigo-200' : 'text-slate-500 group-hover:text-slate-300'}`} />
                        <span className="whitespace-nowrap">{label}</span>
                      </button>
                    );
                  })}
                </div>
                {canScrollRight && <button type="button" onClick={() => scroll('right')} aria-label="Scroll tabs right" className="z-10 mr-1 rounded-2xl border border-white/10 bg-slate-950/90 p-2 text-white shadow-lg transition hover:bg-slate-900"><ChevronRight className="h-4 w-4" /></button>}
              </div>
            </div>
          </nav>
        </div>
      </div>
    </header>
  );
}
