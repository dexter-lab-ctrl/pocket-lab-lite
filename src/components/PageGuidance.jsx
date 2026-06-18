import React from 'react';
import { Info, ShieldCheck } from 'lucide-react';
import { useExperienceMode } from '../context/ExperienceModeContext.jsx';
import { useGovernanceMode } from '../context/GovernanceModeContext.jsx';
import { guidanceFor, guidanceTitleFor } from '../lib/pageGuidance.js';
import { ProgressiveDisclosure } from './ui.jsx';

export default function PageGuidance({ tabId, className = '' }) {
  const { experienceMode } = useExperienceMode();
  const { governanceMode } = useGovernanceMode();
  const title = guidanceTitleFor(experienceMode);
  const copy = guidanceFor(tabId, experienceMode, governanceMode);

  return (
    <aside className={`pocket-guidance ${className}`} aria-label={title}>
      <div className="rounded-2xl border border-blue-300/20 bg-blue-500/10 p-2 text-blue-100">
        <Info className="h-4 w-4" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-200/90">{title}</p>
        <p className="mt-1 text-sm leading-6 text-slate-300">{copy}</p>
        <ProgressiveDisclosure simpleMode={experienceMode === 'simple'} title={experienceMode === 'simple' ? 'Why this is safe' : 'Control-plane boundary'} className="mt-3">
          <div className="flex items-start gap-2">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-200" />
            <p>{experienceMode === 'simple' ? 'Pocket Lab sends safe requests to the control plane and shows progress here. It does not ask your browser to run commands.' : 'The frontend stays inside the control API contract. Execution, approvals, recovery, and audit evidence remain backend-owned.'}</p>
          </div>
        </ProgressiveDisclosure>
      </div>
    </aside>
  );
}
