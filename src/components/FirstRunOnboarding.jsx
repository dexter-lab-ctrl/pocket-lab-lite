import React, { useEffect, useMemo, useState } from 'react';
import { Activity, CheckCircle2, LayoutGrid, ShieldCheck, Sparkles, X } from 'lucide-react';
import { useControlPlaneStatus } from '../hooks/useControlPlaneStatus.js';
import { useExperienceMode } from '../context/ExperienceModeContext.jsx';
import { useGovernanceMode } from '../context/GovernanceModeContext.jsx';
import ModeSwitcher from './ModeSwitcher.jsx';
import { ProgressiveDisclosure, StandardList, StandardListItem, StatusBadge } from './ui.jsx';

const STORAGE_KEY = 'pocketlab_first_run_onboarding_completed_v1';

export default function FirstRunOnboarding({ onNavigate }) {
  const { experienceMode } = useExperienceMode();
  const { governanceMode } = useGovernanceMode();
  const { status, refresh } = useControlPlaneStatus();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const completed = window.localStorage.getItem(STORAGE_KEY) === 'true';
    setOpen(!completed);
  }, []);

  const finish = () => {
    if (typeof window !== 'undefined') window.localStorage.setItem(STORAGE_KEY, 'true');
    setOpen(false);
  };

  const steps = useMemo(() => [
    {
      id: 'control-plane',
      title: experienceMode === 'simple' ? 'Make sure Pocket Lab is ready' : 'Validate control-plane readiness',
      description: experienceMode === 'simple' ? 'Pocket Lab checks whether safe actions can run.' : 'Check Control API, Event Bus, Durable Event Stream, and worker readiness before launching write flows.',
      status: status.ready ? 'healthy' : 'degraded',
      icon: Activity,
    },
    {
      id: 'modes',
      title: experienceMode === 'simple' ? 'Choose how Pocket Lab talks to you' : 'Choose experience and governance mode',
      description: experienceMode === 'simple' ? 'Simple changes wording and layout. Personal or Enterprise controls approval strictness.' : 'Experience mode controls UI language; governance mode controls approval behavior.',
      status: governanceMode === 'enterprise' ? 'approval_required' : 'ready',
      icon: ShieldCheck,
    },
    {
      id: 'first-app',
      title: experienceMode === 'simple' ? 'Install your first app or service' : 'Open the Apps & Services workflow',
      description: experienceMode === 'simple' ? 'Start with a guided install when you are ready.' : 'Blueprint installs are queued through Control API typed operations and executor processing.',
      status: 'queued',
      icon: LayoutGrid,
      action: () => onNavigate?.('appstore'),
    },
    {
      id: 'activity',
      title: experienceMode === 'simple' ? 'Watch what Pocket Lab is doing' : 'Watch lifecycle events',
      description: experienceMode === 'simple' ? 'The activity drawer shows installs, updates, backups, and safety checks.' : 'The activity drawer summarizes event and audit records from the control plane.',
      status: 'running',
      icon: Sparkles,
    },
  ], [experienceMode, governanceMode, status.ready, onNavigate]);

  if (!open) return null;

  return (
    <div className="first-run-overlay" role="dialog" aria-modal="true" aria-labelledby="first-run-title">
      <section className="first-run-panel">
        <div className="flex items-start justify-between gap-4 border-b border-white/10 p-5 sm:p-6">
          <div className="min-w-0">
            <p className="text-xs font-black uppercase tracking-[0.22em] text-blue-200">Welcome to Pocket Lab</p>
            <h2 id="first-run-title" className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
              {experienceMode === 'simple' ? 'Let’s make sure Pocket Lab is ready' : 'First-run control-plane checklist'}
            </h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
              {experienceMode === 'simple'
                ? 'This quick guide helps you choose a comfortable mode, check readiness, and find your first safe action.'
                : 'Validate readiness, choose governance behavior, and confirm the UI is using Control API-owned typed-operation flows.'}
            </p>
          </div>
          <button type="button" onClick={finish} className="rounded-2xl border border-white/10 bg-white/5 p-2 text-slate-200 hover:bg-white/10" aria-label="Close onboarding"><X className="h-5 w-5" /></button>
        </div>

        <div className="grid gap-5 p-5 sm:p-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
          <div className="space-y-5">
            <StandardList title={experienceMode === 'simple' ? 'Setup steps' : 'Readiness checklist'} description={experienceMode === 'simple' ? 'Complete these in any order.' : 'These checks preserve the control plane/worker control-plane model.'}>
              {steps.map((step) => (
                <StandardListItem
                  key={step.id}
                  icon={step.icon}
                  title={step.title}
                  description={step.description}
                  status={step.status}
                  simpleMode={experienceMode === 'simple'}
                  actions={step.action ? <button type="button" onClick={step.action} className="pocket-button pocket-button-secondary">Open</button> : null}
                />
              ))}
            </StandardList>

            <ProgressiveDisclosure title={experienceMode === 'simple' ? 'Show support details' : 'Show technical checklist'} simpleMode={experienceMode === 'simple'}>
              <div className="grid gap-2 text-sm">
                <div>Control API: <StatusBadge status={status.api ? 'healthy' : 'degraded'}>{status.api ? 'Ready' : 'Needs attention'}</StatusBadge></div>
                <div>Event Bus: <StatusBadge status={status.nats ? 'healthy' : 'degraded'}>{status.nats ? 'Connected' : 'Offline'}</StatusBadge></div>
                <div>Durable Event Stream: <StatusBadge status={status.jetstream ? 'healthy' : 'degraded'}>{status.jetstream ? 'Enabled' : 'Required'}</StatusBadge></div>
                <div>Worker: <StatusBadge status={status.worker ? 'healthy' : 'degraded'}>{status.worker ? 'Ready' : 'Not ready'}</StatusBadge></div>
                <p className="text-slate-400">Frontend actions remain API-owned. Workers own execution and lifecycle events remain observable.</p>
              </div>
            </ProgressiveDisclosure>
          </div>

          <aside className="space-y-4">
            <div className="rounded-[1.75rem] border border-blue-300/20 bg-blue-500/10 p-4">
              <h3 className="text-sm font-black text-white">Mode setup</h3>
              <p className="mt-1 text-sm leading-6 text-slate-300">Simple changes language and spacing. Governance controls approval strictness.</p>
              <ModeSwitcher className="mt-4" />
            </div>

            <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-4 text-sm leading-6 text-slate-300">
              <h3 className="font-black text-white">Recommended first actions</h3>
              <button type="button" onClick={() => onNavigate?.('appstore')} className="pocket-button pocket-button-primary mt-3 w-full">Open Apps & Services</button>
              <button type="button" onClick={() => onNavigate?.('telemetry')} className="pocket-button pocket-button-secondary mt-2 w-full">Open System Status</button>
              <button type="button" onClick={refresh} className="pocket-button pocket-button-secondary mt-2 w-full">Check readiness now</button>
            </div>

            <div className="flex flex-col gap-2 sm:flex-row lg:flex-col">
              <button type="button" onClick={finish} className="pocket-button pocket-button-primary flex-1">Finish setup</button>
              <button type="button" onClick={finish} className="pocket-button pocket-button-secondary flex-1">Skip for now</button>
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}
