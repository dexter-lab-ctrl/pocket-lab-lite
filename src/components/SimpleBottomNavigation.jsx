import React, { useMemo, useState } from 'react';
import { Activity, ArchiveRestore, HeartPulse, Home, KeyRound, Laptop, LayoutGrid, Menu, Settings, ShieldCheck, UploadCloud, X } from 'lucide-react';
import { SIMPLE_MORE_NAV_ITEMS, SIMPLE_PRIMARY_NAV_ITEMS, isSimpleMoreTarget } from '../lib/simpleNavigation.js';

const SIMPLE_ICON_BY_ID = {
  'simple-home': Home,
  'simple-apps': LayoutGrid,
  'simple-health': HeartPulse,
  'simple-devices': Laptop,
  'simple-more': Menu,
  'simple-status': Activity,
  'simple-passwords': KeyRound,
  'simple-safety': ShieldCheck,
  'simple-backups': ArchiveRestore,
  'simple-updates': UploadCloud,
  'simple-activity': Activity,
  'simple-advanced': Settings,
};

export default function SimpleBottomNavigation({ currentTarget, onSelectTarget }) {
  const [moreOpen, setMoreOpen] = useState(false);
  const moreIsActive = useMemo(() => isSimpleMoreTarget(currentTarget), [currentTarget]);

  const handleSelect = (target) => {
    if (!target) return;
    if (target === 'simple-more') {
      setMoreOpen(true);
      return;
    }
    onSelectTarget(target);
    setMoreOpen(false);
  };

  return (
    <>
      <nav className="pocket-nav-dock simple-bottom-nav scrollbar-none" aria-label="Simple Mode sections">
        {SIMPLE_PRIMARY_NAV_ITEMS.map((item) => {
          const Icon = SIMPLE_ICON_BY_ID[item.id] || LayoutGrid;
          const isActive = item.kind === 'more' ? moreIsActive || moreOpen : currentTarget === item.target;
          return (
            <button key={item.id} type="button" onClick={() => handleSelect(item.target)} aria-current={isActive ? 'page' : undefined} className={`pocket-nav-button nav-active-rail-item ${isActive ? 'pocket-nav-button-active' : ''}`}>
              <Icon className="nav-active-rail-icon relative z-10 h-5 w-5" />
              <span className="relative z-10 mt-1 text-[0.68rem] font-bold tracking-wide">{item.label}</span>
            </button>
          );
        })}
      </nav>

      {moreOpen && <div className="mobile-more-backdrop" onClick={() => setMoreOpen(false)} aria-hidden="true" />}
      <aside className={`mobile-more-sheet ${moreOpen ? 'mobile-more-sheet-open' : ''}`} aria-hidden={!moreOpen} aria-label="More Simple Mode sections">
        <div className="flex items-center justify-between gap-3 border-b border-white/10 p-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-indigo-200">More</p>
            <h2 className="text-lg font-black text-white">Open another simple area</h2>
            <p className="mt-1 text-xs leading-5 text-slate-400">These tools stay available without crowding the main navigation.</p>
          </div>
          <button type="button" onClick={() => setMoreOpen(false)} className="rounded-2xl border border-white/10 bg-white/5 p-2 text-slate-200 hover:bg-white/10" aria-label="Close more sections"><X className="h-5 w-5" /></button>
        </div>
        <div className="grid gap-2 p-4">
          {SIMPLE_MORE_NAV_ITEMS.map((item) => {
            const Icon = SIMPLE_ICON_BY_ID[item.id] || LayoutGrid;
            const isActive = currentTarget === item.target;
            return (
              <button key={item.id} type="button" onClick={() => handleSelect(item.target)} aria-current={isActive ? 'page' : undefined} className={`mobile-more-item nav-active-rail-item ${isActive ? 'mobile-more-item-active' : ''}`}>
                <Icon className="nav-active-rail-icon h-5 w-5" />
                <span className="min-w-0 text-left">
                  <span className="block font-black text-white">{item.label}</span>
                  <span className="mt-1 block text-xs font-medium leading-5 text-slate-400">{item.description}</span>
                </span>
              </button>
            );
          })}
        </div>
      </aside>
    </>
  );
}
