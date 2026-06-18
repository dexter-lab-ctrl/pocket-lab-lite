import React from 'react';
import { ShieldCheck, Settings as SettingsIcon } from 'lucide-react';
import { useExperienceMode } from '../context/ExperienceModeContext.jsx';
import { useGovernanceMode } from '../context/GovernanceModeContext.jsx';
import { GlassCard, PageShell, SegmentedControl, StatusBadge } from '../components/ui.jsx';

/**
 * Settings panel for user-facing experience and governance behavior.
 *
 * Personal governance is the public GitHub/self-hosted default: approval-gated
 * runbooks are auto-approved and logged. Enterprise governance is explicit opt-in
 * and enforces human authorization for governed runbooks.
 */
export default function SettingsTab() {
  const { experienceMode, setExperienceMode } = useExperienceMode();
  const { governanceMode, setGovernanceMode, status, error } = useGovernanceMode();
  const enterpriseEnabled = governanceMode === 'enterprise';

  return (
    <PageShell eyebrow="Operator preferences" title="Settings" description="Tune Pocket Lab for everyday self-hosted use, professional operation, or strict enterprise governance without changing the runtime architecture.">
      <div className="grid gap-4 lg:grid-cols-2">
        <GlassCard>
          <div className="mb-5 flex items-start gap-3">
            <div className="rounded-2xl border border-indigo-300/25 bg-indigo-500/10 p-3 text-indigo-200"><SettingsIcon className="h-5 w-5" /></div>
            <div>
              <h3 className="text-xl font-black text-white">Experience Mode</h3>
              <p className="mt-1 text-sm leading-6 text-slate-400">Simple Mode uses plain-language labels. Professional Mode keeps detailed operator language.</p>
            </div>
          </div>
          <SegmentedControl label="UI language" value={experienceMode} onChange={setExperienceMode} options={[{ value: 'professional', label: 'Professional', description: 'Technical labels and diagnostics' }, { value: 'simple', label: 'Simple', description: 'Plain language for daily use' }]} />
          <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm leading-6 text-slate-300">Simple labels preserve plain-language mappings such as environment updates, health checks, and system status for non-technical users.</div>
        </GlassCard>

        <GlassCard className={enterpriseEnabled ? 'border-amber-300/30 bg-amber-950/20' : 'border-emerald-300/25 bg-emerald-950/10'}>
          <div className="mb-5 flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <div className={`rounded-2xl border p-3 ${enterpriseEnabled ? 'border-amber-300/25 bg-amber-500/10 text-amber-200' : 'border-emerald-300/25 bg-emerald-500/10 text-emerald-200'}`}><ShieldCheck className="h-5 w-5" /></div>
              <div>
                <h3 className="text-xl font-black text-white">Enterprise Governance</h3>
                <p className="mt-1 text-sm leading-6 text-slate-400">Choose how approval-gated runbooks proceed after Control API queues them for worker-owned execution.</p>
              </div>
            </div>
            <StatusBadge status={enterpriseEnabled ? 'warning' : 'healthy'}>{enterpriseEnabled ? 'Strict' : 'Personal'}</StatusBadge>
          </div>

          <SegmentedControl label="Approval policy" value={governanceMode} onChange={setGovernanceMode} options={[{ value: 'personal', label: 'Personal', description: 'Auto-approve eligible safe runs and log evidence' }, { value: 'enterprise', label: 'Enterprise', description: 'Require human approval and reason capture' }]} />

          {!enterpriseEnabled ? (
            <div className="mt-4 rounded-2xl border border-emerald-300/20 bg-emerald-500/10 p-4 text-sm leading-6 text-emerald-100">Default self-hosted experience: governed runbooks continue automatically, while Pocket Lab records auto-approval evidence in the runbook event journal and audit stream.</div>
          ) : (
            <div className="mt-4 rounded-2xl border border-amber-300/20 bg-amber-500/10 p-4 text-sm leading-6 text-amber-100">Enterprise Mode is opt-in and strict. Approval-gated runbooks pause until an authorized role approves or rejects them with a reason.</div>
          )}

          <p className="mt-4 text-xs text-slate-500">Sync status: {status}{error ? ` — ${error}` : ''}</p>
        </GlassCard>
      </div>
    </PageShell>
  );
}
