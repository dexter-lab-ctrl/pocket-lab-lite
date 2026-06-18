import React from 'react';
import { CheckCircle2 } from 'lucide-react';

export default function DesiredStateSnap({ active = false, complete = false, simpleMode = false, className = '' }) {
  const activeClass = active || complete ? 'desired-state-snap-active' : '';
  return (
    <div className={`desired-state-snap ${activeClass} ${className}`} aria-label={simpleMode ? 'What should be installed is being matched' : 'Desired state reconciliation preview'}>
      <div className="desired-state-card desired-state-card-target">
        <span>{simpleMode ? 'What Should Be Installed' : 'Target Configuration'}</span>
        <strong>{simpleMode ? 'Ready' : 'declared'}</strong>
      </div>
      <div className="desired-state-rail" aria-hidden="true" />
      <div className={`desired-state-card desired-state-actual ${active || complete ? 'desired-state-actual-active' : ''}`}>
        <span>{simpleMode ? 'Current' : 'Actual State'}</span>
        <strong>{complete ? (simpleMode ? 'Matched' : 'reconciled') : (simpleMode ? 'Aligning' : 'applying')}</strong>
      </div>
      {complete ? <CheckCircle2 className="desired-state-check" aria-hidden="true" /> : null}
    </div>
  );
}
