import React, { useState } from 'react';
import { Activity, ArchiveRestore, HeartPulse, KeyRound, Laptop, LayoutGrid, ShieldCheck, UploadCloud } from 'lucide-react';
import ControlPlaneBanner from '../components/ControlPlaneBanner.jsx';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import ModeSwitcher from '../components/ModeSwitcher.jsx';
import SimpleActionWizard from '../components/SimpleActionWizard.jsx';
import { executeOperation } from '../lib/operations.js';
import { useExperienceMode } from '../context/ExperienceModeContext.jsx';

const HOME_SHORTCUTS = [
  { label: 'Apps & Services', description: 'Install and manage apps or services safely.', target: 'appstore', icon: LayoutGrid, action: 'Open Apps' },
  { label: 'Health & Issues', description: 'Check what changed or needs attention.', target: 'drift', icon: HeartPulse, action: 'Check Health' },
  { label: 'My Devices', description: 'Add and manage connected devices.', target: 'fleet', icon: Laptop, action: 'Open Devices' },
  { label: 'System Status', description: 'See whether Pocket Lab services are working.', target: 'telemetry', icon: Activity, action: 'View Status' },
  { label: 'Passwords & Access', description: 'Change saved passwords and access safely.', target: 'vault', icon: KeyRound, action: 'Open Access' },
  { label: 'Safety Center', description: 'Review safety checks and protection settings.', target: 'security', icon: ShieldCheck, action: 'Open Safety' },
  { label: 'Backups', description: 'Create or restore from a safe restore point.', target: 'recovery', icon: ArchiveRestore, action: 'Open Backups' },
  { label: 'Updates', description: 'Keep Pocket Lab and installed services current.', target: 'release', icon: UploadCloud, action: 'Open Updates' },
];

export default function SimpleDashboard({ onNavigate = () => {} }) {
  const { setExperienceMode } = useExperienceMode();
  const [recMessage, setRecMessage] = useState('');

  const runQuickAction = async (operation, target, params, message) => {
    setRecMessage('Getting ready...');
    try {
      await executeOperation({ operation, target, params });
      setRecMessage(message);
    } catch (err) {
      setRecMessage(`Needs attention: ${err?.message || 'Pocket Lab could not start this task.'}`);
    }
  };

  const handleUpdateAll = () => runQuickAction('release_sync', { type: 'repo', ref: 'pocket_lab_iac' }, { branch: 'main' }, 'Update request started safely.');
  const handleBackup = () => runQuickAction('backup_now', { type: 'backup', ref: 'latest' }, { note: 'simple-mode-request' }, 'Backup request started safely.');
  const handleAddDevice = () => runQuickAction('fleet_join', { type: 'fleet', ref: 'compute' }, { role: 'compute', hostname: `pocket-device-${Date.now().toString().slice(-4)}` }, 'Device invite started safely.');
  const handleSecurity = () => runQuickAction('policy_deploy', { type: 'policy', ref: 'baseline' }, { policy_pack: 'baseline' }, 'Safety check started safely.');

  return (
    <div className="simple-dashboard mx-auto w-full max-w-[1500px] px-4 pb-28 pt-6 sm:px-6 lg:px-8">
      <ControlPlaneBanner simpleMode />
      <div className="mb-6 flex flex-col gap-4 rounded-[2rem] border border-blue-300/20 bg-blue-500/10 p-6 shadow-2xl shadow-blue-950/20 sm:p-7 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="mb-2 text-xs font-black uppercase tracking-[0.24em] text-blue-200">Pocket Lab Simple Mode</p>
          <h2 className="text-2xl font-black tracking-tight text-white sm:text-3xl">Start here</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">Install apps, check health, add devices, manage passwords, and review safety in plain language. Pocket Lab handles the technical steps behind the scenes.</p>
        </div>
        <div className="flex flex-col gap-3 sm:items-end">
          <ModeSwitcher compact />
          <button type="button" onClick={() => setExperienceMode('professional')} className="pocket-button pocket-button-secondary bg-white/5 text-slate-100 hover:bg-white/10">Switch to Professional Mode</button>
        </div>
      </div>

      <div className="mb-8 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        {HOME_SHORTCUTS.map((item) => {
          const Icon = item.icon;
          return (
            <button key={item.target} type="button" onClick={() => onNavigate(item.target)} className="group rounded-[1.75rem] border border-white/10 bg-white/5 p-5 text-left shadow-xl shadow-blue-950/10 transition-all duration-200 hover:border-blue-300/25 hover:bg-blue-500/10 hover:-translate-y-0.5">
              <span className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl border border-blue-300/20 bg-blue-500/15 text-blue-100"><Icon className="h-5 w-5" /></span>
              <span className="block text-base font-black text-white">{item.label}</span>
              <span className="mt-2 block text-sm leading-6 text-slate-400">{item.description}</span>
              <span className="mt-4 inline-flex rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-black text-slate-200 group-hover:bg-white/10">{item.action}</span>
            </button>
          );
        })}
      </div>

      <div className="mb-8">
        <LiveEventPanel simpleMode title="What Pocket Lab is doing now" description="Live progress from installs, updates, backups, device invites, safety checks, and system health appears here." subjectPrefixes={['pocketlab.events.', 'pocketlab.audit.']} maxItems={5} />
      </div>

      <div className="simple-section-card mb-8 rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-blue-950/20 sm:p-7">
        <h3 className="mb-3 text-xl font-black text-white">Quick guided actions</h3>
        <p className="mb-5 max-w-3xl text-sm leading-6 text-slate-300">Run common tasks with safe defaults. Pocket Lab checks first and records what changed.</p>
        <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
          <SimpleActionWizard title="Install Something" operation="deploy_blueprint" target={{ type: 'repo', ref: 'pocket_lab_iac' }} params={{ playbook: 'site.yml', source_type: 'repo', source: 'pocket_lab_iac' }} />
          <SimpleActionWizard title="Add Device" operation="fleet_join" target={{ type: 'fleet', ref: 'compute' }} params={{ role: 'compute', hostname: `pocket-device-${Date.now().toString().slice(-4)}` }} />
          <SimpleActionWizard title="Restore Safely" operation="restore_backup" target={{ type: 'backup', ref: 'latest' }} params={{ backup_ref: 'latest' }} />
          <SimpleActionWizard title="Update Everything" operation="release_sync" target={{ type: 'repo', ref: 'pocket_lab_iac' }} params={{ branch: 'main' }} />
          <SimpleActionWizard title="Change Password" operation="rotate_secret" target={{ type: 'secret', ref: 'photoprism' }} params={{ target: 'photoprism' }} />
        </div>
      </div>

      <div className="simple-section-card rounded-[2rem] border border-indigo-300/20 bg-indigo-500/10 p-6 shadow-2xl shadow-indigo-950/20 sm:p-7">
        <h3 className="mb-4 text-xl font-black text-white">Helpful next steps</h3>
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={handleUpdateAll} className="rounded-2xl border border-indigo-300/20 bg-indigo-500/15 px-4 py-2.5 text-sm font-bold text-indigo-100 hover:bg-indigo-500/25">Update Everything</button>
          <button type="button" onClick={handleBackup} className="rounded-2xl border border-emerald-300/20 bg-emerald-500/10 px-4 py-2.5 text-sm font-bold text-emerald-100 hover:bg-emerald-500/20">Back Up Now</button>
          <button type="button" onClick={handleAddDevice} className="rounded-2xl border border-blue-300/20 bg-blue-500/15 px-4 py-2.5 text-sm font-bold text-blue-100 hover:bg-blue-500/25">Add Device</button>
          <button type="button" onClick={handleSecurity} className="rounded-2xl border border-violet-300/20 bg-violet-500/15 px-4 py-2.5 text-sm font-bold text-violet-100 hover:bg-violet-500/25">Safety Check</button>
        </div>
        {recMessage && <p className="mt-3 text-sm text-slate-400">{recMessage}</p>}
      </div>
    </div>
  );
}
