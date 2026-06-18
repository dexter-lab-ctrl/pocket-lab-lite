import React, { useEffect, useState } from 'react';
import { executeOperation } from '../lib/operations';
import { Database, HardDrive, History, UploadCloud, DownloadCloud, RefreshCw, CheckCircle2 } from 'lucide-react';
import { AdvancedDetails, SimpleStatus } from '../components/SimpleModeControls.jsx';
import { simpleActionLabel, simpleStatusLabel } from '../lib/simpleLabels';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import { useControlPlaneStatus, productionWriteBlockedMessage } from '../hooks/useControlPlaneStatus.js';

export default function DisasterRecoveryTab({ simpleMode = false }) {
  const [backupRef, setBackupRef] = useState('latest');
  const [status, setStatus] = useState({ phase: 'idle', jobId: '', message: '' });
  const [verification, setVerification] = useState(null);
  const { status: controlPlane } = useControlPlaneStatus(15000);
  const isLiveEnv = controlPlane.ready;
  const [recentBackups, setRecentBackups] = useState([]);


  useEffect(() => {
    if (!isLiveEnv) return;
    fetch('/api/operations/runs')
      .then((res) => res.json())
      .then((data) => setRecentBackups(Array.isArray(data?.runs) ? data.runs.filter((run) => ['backup_now', 'restore_backup'].includes(run.operation)).slice(0, 5) : []))
      .catch(() => setRecentBackups([]));
  }, [isLiveEnv, status.phase]);

  const submit = async (operation, params) => {
    setStatus({ phase: operation, jobId: '', message: simpleMode ? `Starting ${simpleActionLabel(operation, 'action').toLowerCase()}...` : `Submitting ${operation}...` });
    try {
      if (!isLiveEnv) {
        setStatus({ phase: 'blocked', jobId: '', message: productionWriteBlockedMessage(simpleMode) });
        return;
      }
      const result = await executeOperation(operation, {
        target: operation === 'restore_backup' ? { type: 'backup', ref: backupRef } : { type: 'backup', ref: 'snapshot' },
        params,
      });
      setStatus({
        phase: result?.status || 'succeeded',
        jobId: result?.job_id || '',
        message: operation === 'restore_backup' ? 'Restore request recorded.' : operation === 'backup_verify' ? 'Backup verification completed.' : 'Backup snapshot created.',
      });
      setVerification(result?.artifacts || null);
    } catch (err) {
      setStatus({ phase: 'error', jobId: '', message: err.message || 'Recovery action failed.' });
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-4 animate-in fade-in duration-700 space-y-6">
      <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-8 relative overflow-hidden shadow-2xl">
        <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none transform translate-x-4 -translate-y-4">
          <Database className="w-48 h-48 text-emerald-400" />
        </div>

        <div className="relative z-10 flex flex-col gap-6">
          <div>
            <div className="flex items-center gap-2 text-slate-400 text-xs font-black uppercase tracking-widest">
              <HardDrive className="h-4 w-4" /> {simpleMode ? 'Backups' : 'Disaster recovery'}
            </div>
            <h2 className="mt-2 text-4xl font-black text-white tracking-tight">{simpleMode ? 'Back up and restore safely' : 'Recovery Management'}</h2>
            <p className="mt-2 text-sm text-slate-400 max-w-2xl">
              {simpleMode ? 'Create safe restore points and recover your environment without dealing with scripts or backend commands.' : 'Backups and restores are submitted as backend operations. There is no shell payload editor in this flow.'}
            </p>
          </div>

          {simpleMode ? <SimpleStatus simpleMode phase={status.phase} message={status.message} jobId={status.jobId} /> : null}
          <AdvancedDetails simpleMode={simpleMode} title="Backup selection and support details">
            <div className="grid gap-3 md:grid-cols-2">
              <label className="block">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Backup reference</span>
                <input value={backupRef} onChange={(e) => setBackupRef(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white" />
              </label>

              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="text-[10px] font-black uppercase tracking-widest text-slate-500">Current task</div>
                <div className="mt-1 text-white">{status.phase}</div>
                <div className="mt-1 text-xs uppercase tracking-widest text-slate-400">Task id: {status.jobId || 'queued'}</div>
              </div>
            </div>
          </AdvancedDetails>

          <div className="flex flex-wrap gap-3">
            <button disabled={!isLiveEnv} onClick={() => submit('backup_now', { scope: 'full' })} className={`inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 font-semibold text-white hover:bg-emerald-500 ${!isLiveEnv ? 'write-blocked-action' : ''}`}>
              <DownloadCloud className="h-4 w-4" /> {simpleMode ? 'Create Backup' : 'Backup Now'}
            </button>
            <button disabled={!isLiveEnv} onClick={() => submit('restore_backup', { backup_ref: backupRef })} className={`inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-500 risk-level-glow risk-high ${!isLiveEnv ? 'write-blocked-action' : ''}`}>
              <UploadCloud className="h-4 w-4" /> {simpleMode ? 'Restore' : 'Restore Backup'}
            </button>
            <button disabled={!isLiveEnv} onClick={() => submit('backup_verify', { backup_ref: backupRef })} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-5 py-3 font-semibold text-slate-200 hover:bg-black/30">
              <RefreshCw className="h-4 w-4" /> {simpleMode ? 'Check Backup' : 'Verify Backup'}
            </button>
          </div>

          <div className={`rounded-2xl border p-4 ${status.phase === 'error' ? 'border-red-500/30 bg-red-500/10 text-red-100' : 'border-white/10 bg-black/20 text-slate-200'}`}>
            <div className="font-semibold">{status.message}</div>
          </div>
          <div className={`backup-vault-seal ${verification ? 'backup-vault-seal-verified' : ''} ${status.phase === 'restore_backup' ? 'restore-preview-path' : ''}`}>
            <div className="backup-seal-icon" aria-hidden="true">▣</div>
            <div>
              <strong>{simpleMode ? 'Backup safety check' : 'Backup verification seal'}</strong>
              <span>{status.phase === 'restore_backup' ? (simpleMode ? 'Confirmation required before restore' : 'Restore preview requires approval') : (verification ? (simpleMode ? 'Verification saved' : 'Backup verification recorded') : (simpleMode ? 'Ready to verify' : 'Awaiting verification evidence'))}</span>
            </div>
            <span className="backup-seal-badge">{verification ? (simpleMode ? 'Safe' : 'Verified') : (simpleMode ? 'Check' : 'Pending')}</span>
          </div>
          {verification && (
            <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-sm text-emerald-100">
              Verified checksum: {verification.checksum_sha256 || '—'}
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="bg-[#05080f] border border-white/10 rounded-[2rem] p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <History className="h-4 w-4 text-slate-400" />
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'Recent backup activity' : 'Recent recovery operations'}</h3>
          </div>
          <div className="space-y-3">
            {recentBackups.length === 0 ? (
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-400">No recent backup operations yet.</div>
            ) : recentBackups.map((run) => (
              <div key={run.job_id} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-semibold text-white">{simpleMode ? simpleActionLabel(run.operation, run.operation) : run.operation}</div>
                    <div className="text-xs text-slate-400">{new Date(run.created_at || Date.now()).toLocaleString()}</div>
                  </div>
                  <span className="rounded-full border border-white/10 px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-slate-400">{simpleMode ? simpleStatusLabel(run.status, run.status) : run.status}</span>
                </div>
                {!simpleMode && <div className="mt-2 text-xs text-slate-400">Task id: {run.job_id}</div>}
              </div>
            ))}
          </div>
        </div>

        <div className="bg-[#05080f] border border-white/10 rounded-[2rem] p-6 shadow-xl">
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle2 className="h-4 w-4 text-slate-400" />
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'What this means' : 'Operational notes'}</h3>
          </div>
          <div className="space-y-3 text-sm text-slate-300">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              {simpleMode ? 'Create Backup saves a restore point for your environment.' : 'Use the typed `backup_now` operation for snapshots.'}
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              {simpleMode ? 'Restore recovers your environment from the selected restore point.' : 'Use governed recovery actions to request restoration from a stored backup reference.'}
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              {simpleMode ? 'Pocket Lab runs these safely in the background using approved workflows.' : 'Recovery tasks are shown as operation jobs, not ad hoc shell scripts.'}
            </div>
          </div>
        </div>
      </div>
      <LiveEventPanel
        simpleMode={simpleMode}
        title="Backup and restore activity"
        description="Backup, restore, and background operation progress appears here."
        subjectPrefixes={['pocketlab.events.backup.', 'pocketlab.events.operation.']}
        maxItems={4}
        compact
      />

    </div>
  );
}
