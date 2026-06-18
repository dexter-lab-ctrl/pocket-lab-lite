import React from 'react';
import { simpleStatusLabel, redactTechnicalText } from '../lib/simpleLabels';
import { ProgressiveDisclosure } from './ui.jsx';

export function AdvancedDetails({ simpleMode = false, title = 'Advanced details', children, defaultOpen = false }) {
  if (!simpleMode) return <>{children}</>;
  return (
    <ProgressiveDisclosure simpleMode title={title} defaultOpen={defaultOpen}>
      <div className="space-y-3">{children}</div>
    </ProgressiveDisclosure>
  );
}

export function SimpleStatus({ simpleMode = false, phase, message, jobId }) {
  if (!simpleMode) return null;
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200">
      <div className="font-semibold">Status: {simpleStatusLabel(phase, 'Ready')}</div>
      {message ? <div className="mt-1 text-slate-400">{redactTechnicalText(message)}</div> : <div className="mt-1 text-slate-400">Ready when you are.</div>}
      {jobId ? <div className="mt-2 text-xs text-slate-500">Reference: {jobId}</div> : null}
    </div>
  );
}

export function TechnicalBadge({ simpleMode = false, children }) {
  if (simpleMode) return null;
  return <>{children}</>;
}
