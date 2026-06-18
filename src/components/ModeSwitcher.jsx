import React from 'react';
import { ShieldCheck, SlidersHorizontal } from 'lucide-react';
import { useExperienceMode } from '../context/ExperienceModeContext.jsx';
import { useGovernanceMode } from '../context/GovernanceModeContext.jsx';

export default function ModeSwitcher({ compact = false, className = '' }) {
  const { experienceMode, setExperienceMode } = useExperienceMode();
  const { governanceMode, setGovernanceMode, status } = useGovernanceMode();
  const isSimple = experienceMode === 'simple';
  const isEnterprise = governanceMode === 'enterprise';

  const experienceLabel = isSimple ? 'Simple' : 'Professional';
  const governanceLabel = isEnterprise ? 'Enterprise' : 'Personal';

  return (
    <div className={`mode-switcher ${compact ? 'mode-switcher-compact' : ''} ${className}`} aria-label="Pocket Lab mode switcher">
      {!compact && (
        <div className="min-w-0">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-400">Current mode</p>
          <p className="mt-1 text-sm font-bold text-white">{experienceLabel} · {governanceLabel} Governance</p>
        </div>
      )}
      <div className="mode-switcher-group" role="group" aria-label="Experience mode">
        <SlidersHorizontal className="hidden h-4 w-4 text-blue-200 sm:block" />
        <button type="button" onClick={() => setExperienceMode('simple')} aria-pressed={isSimple} className={`mode-chip ${isSimple ? 'mode-chip-active' : ''}`}>Simple</button>
        <button type="button" onClick={() => setExperienceMode('professional')} aria-pressed={!isSimple} className={`mode-chip ${!isSimple ? 'mode-chip-active' : ''}`}>Professional</button>
      </div>
      <div className="mode-switcher-group" role="group" aria-label="Governance mode">
        <ShieldCheck className="hidden h-4 w-4 text-indigo-200 sm:block" />
        <button type="button" onClick={() => setGovernanceMode('personal')} aria-pressed={!isEnterprise} className={`mode-chip ${!isEnterprise ? 'mode-chip-active' : ''}`}>Personal</button>
        <button type="button" onClick={() => setGovernanceMode('enterprise')} aria-pressed={isEnterprise} className={`mode-chip ${isEnterprise ? 'mode-chip-enterprise' : ''}`}>Enterprise</button>
      </div>
      {!compact && <p className="text-[11px] text-slate-500">Settings sync: {status}</p>}
    </div>
  );
}
