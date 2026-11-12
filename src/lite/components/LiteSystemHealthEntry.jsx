import React from 'react';
import { HeartPulse } from 'lucide-react';
import { LiteButton } from '../LiteUi.jsx';

// Harmless contextual navigation. Existing FastAPI-backed System Health is
// canonical; this component does not invent an incident or submit a repair.
export default function LiteSystemHealthEntry({ onNavigate, label = 'Diagnose & Fix', className = '' }) {
  if (typeof onNavigate !== 'function') return null;
  return <div className={`lite-system-health-context-entry ${className}`.trim()}>
    <LiteButton haptic tone="secondary" onClick={() => onNavigate('system-health')}
      ariaLabel={label}><HeartPulse size={17} aria-hidden="true" /> {label}</LiteButton>
  </div>;
}
