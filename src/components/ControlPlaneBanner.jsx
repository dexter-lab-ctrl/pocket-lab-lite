import React from 'react';
import { AlertTriangle, CheckCircle2, RefreshCw } from 'lucide-react';
import { useControlPlaneStatus } from '../hooks/useControlPlaneStatus.js';
import JetStreamFlowLine from './JetStreamFlowLine.jsx';
import { ProgressiveDisclosure, StatusBadge } from './ui.jsx';
import { enterpriseDisplayText } from '../lib/enterpriseLabels.js';

export default function ControlPlaneBanner({ compact = false, simpleMode = false }) {
  const { status, refresh } = useControlPlaneStatus(15000);
  const ready = status.ready;
  const Icon = ready ? CheckCircle2 : AlertTriangle;
  const label = simpleMode ? (ready ? 'Pocket Lab is ready' : 'Pocket Lab needs attention') : (ready ? 'Control plane ready' : 'Control plane degraded');

  if (compact && ready) return null;

  return (
    <section className={`mt-4 rounded-[2rem] border px-4 py-4 shadow-2xl shadow-black/20 backdrop-blur-xl ${ready ? 'border-emerald-300/20 bg-emerald-500/10' : 'degraded-mode-banner border-amber-300/30 bg-amber-500/10'}`} aria-live="polite">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className={`rounded-2xl border p-2.5 health-dot ${ready ? 'health-dot-healthy ' : 'health-dot-degraded '}${ready ? 'border-emerald-300/30 bg-emerald-500/10 text-emerald-200' : 'border-amber-300/30 bg-amber-500/10 text-amber-200'}`}><Icon className="h-5 w-5" /></div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><h2 className="text-sm font-black text-white">{label}</h2><StatusBadge status={ready ? 'ready' : 'degraded'}>{ready ? 'Ready' : 'Attention'}</StatusBadge></div>
            <p className="mt-1 text-sm leading-6 text-slate-300">{simpleMode ? (ready ? 'Installs, updates, backups, and device actions can run safely.' : 'Paused for safety. Actions are stopped so Pocket Lab does not make unsafe changes.') : enterpriseDisplayText(status.message)}</p>
            <ProgressiveDisclosure simpleMode={simpleMode} title={simpleMode ? 'Show readiness details' : 'Readiness details'} className="mt-3">
              <JetStreamFlowLine simpleMode={simpleMode} activeIndex={status.worker ? 4 : status.jetstream ? 2 : status.nats ? 1 : status.api ? 0 : 0} className="mb-3" />
              <div className="flex flex-wrap gap-2">
                <StatusBadge status={status.api ? 'healthy' : 'degraded'} simpleMode={simpleMode}>Control API {status.api ? 'ready' : 'not ready'}</StatusBadge>
                <StatusBadge status={status.nats ? 'healthy' : 'degraded'} simpleMode={simpleMode}>Event Bus {status.nats ? 'connected' : 'offline'}</StatusBadge>
                <StatusBadge status={status.jetstream ? 'healthy' : 'degraded'} simpleMode={simpleMode}>Durable Stream {status.jetstream ? 'enabled' : 'required'}</StatusBadge>
                <StatusBadge status={status.worker ? 'healthy' : 'degraded'} simpleMode={simpleMode}>Executor {status.worker ? 'ready' : 'not ready'}</StatusBadge>
              </div>
            </ProgressiveDisclosure>
          </div>
        </div>
        <button type="button" onClick={refresh} className="pocket-button pocket-button-secondary shrink-0"><RefreshCw className="h-4 w-4" /> Check now</button>
      </div>
    </section>
  );
}
