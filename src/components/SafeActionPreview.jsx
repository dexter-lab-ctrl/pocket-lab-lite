import React from 'react';
import { CheckCircle2, ShieldCheck, XCircle } from 'lucide-react';
import { safeActionPreview, riskStatus } from '../lib/safeActionPreview.js';
import { ProgressiveDisclosure, StatusBadge } from './ui.jsx';

export default function SafeActionPreview({ operation, simpleMode = false, defaultOpen = false, className = '' }) {
  const preview = safeActionPreview(operation, { simpleMode });
  const riskLabel = preview.risk === 'high' ? (simpleMode ? 'Needs careful review' : 'High risk') : preview.risk === 'medium' ? (simpleMode ? 'Review before running' : 'Medium risk') : (simpleMode ? 'Low risk' : 'Low risk');

  return (
    <ProgressiveDisclosure simpleMode={simpleMode} title={simpleMode ? 'Preview what will happen' : 'Safe action preview'} defaultOpen={defaultOpen} className={`safe-action-preview risk-level-glow risk-${preview.risk} ${className}`}>
      <div className="safe-preview-header">
        <StatusBadge status={riskStatus(preview.risk)} simpleMode={simpleMode}>{riskLabel}</StatusBadge>
        <span className="text-xs text-slate-400">{simpleMode ? 'Pocket Lab shows this before the task starts.' : 'Preview only; execution remains worker-owned.'}</span>
      </div>
      <div className="safe-preview-grid">
        <section>
          <h4><CheckCircle2 className="h-4 w-4" /> {simpleMode ? 'Will do' : 'Will happen'}</h4>
          <ul>{preview.will.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
        <section>
          <h4><XCircle className="h-4 w-4" /> {simpleMode ? 'Will not do' : 'Will not happen'}</h4>
          <ul>{preview.willNot.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
        <section>
          <h4><ShieldCheck className="h-4 w-4" /> {simpleMode ? 'Safety record' : 'Evidence'}</h4>
          <ul>{preview.evidence.map((item) => <li key={item}>{item}</li>)}</ul>
        </section>
      </div>
    </ProgressiveDisclosure>
  );
}
