import React, { useEffect, useState } from 'react';
import { executeOperation } from '../lib/operations';
import { Lock, Unlock, Key, ShieldCheck, Fingerprint, RefreshCw, Eye, EyeOff, ShieldAlert, Database, Cpu, TestTube2, Timer, Zap, Server, Calendar, Bot, TerminalSquare, LockKeyhole } from 'lucide-react';
import { AdvancedDetails } from '../components/SimpleModeControls.jsx';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import { useControlPlaneStatus, productionWriteBlockedMessage } from '../hooks/useControlPlaneStatus.js';

export default function IdentityVaultTab({ simpleMode = false }) {
  const [isSealed, setIsSealed] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [showDynamic, setShowDynamic] = useState(false);
  const [rotating, setRotating] = useState(false);
  const [secretFlip, setSecretFlip] = useState(false);
  const [generatingDynamic, setGeneratingDynamic] = useState(false);
  const { status: controlPlane } = useControlPlaneStatus();
  const isLiveEnv = controlPlane.ready;
  const [rotateJobId, setRotateJobId] = useState('');
  const [dynamicJobId, setDynamicJobId] = useState('');
  const [photoPrismIdentity, setPhotoPrismIdentity] = useState({
    username: 'admin',
    password: '••••••••••••••••',
    lastRotated: new Date().toLocaleString(),
  });
  const [dynamicLease, setDynamicLease] = useState(null);
  const [rotateMetadata, setRotateMetadata] = useState({ version: null, lease_duration: null, rotated_at: null });

  const [machineIdentities, setMachineIdentities] = useState([
    { id: 'infra-runner', name: 'Gitea Action Worker', icon: TerminalSquare, status: 'active', ttl: '58m 42s', policies: ['gitops-policy'], color: 'text-emerald-400', bg: 'bg-emerald-500/20', border: 'border-emerald-500/30' },
    { id: 'pocket-api', name: 'Control Plane API', icon: Bot, status: 'active', ttl: '1h 45m', policies: ['dashboard-ui-policy'], color: 'text-sky-400', bg: 'bg-sky-500/20', border: 'border-sky-500/30' },
    { id: 'db-runner', name: 'Automated Backup Drone', icon: Database, status: 'idle', ttl: 'Expired', policies: ['backup-policy'], color: 'text-slate-400', bg: 'bg-slate-800', border: 'border-white/10' },
  ]);

  const vaultKicker = simpleMode ? 'Passwords & Access' : 'KMS Status';
  const vaultHeading = simpleMode
    ? `Passwords & Access is ${isSealed ? 'Locked' : 'Ready'}`
    : `Vault is ${isSealed ? 'Sealed' : 'Active'}`;
  const vaultBody = simpleMode
    ? (isSealed ? 'Password access is locked.' : 'Passwords and access controls are ready.')
    : `The Identity engine is ${isSealed ? 'locked.' : 'authenticated and can issue typed operations.'}`;
  const rotateTaskLabel = simpleMode ? 'Password change reference' : 'Rotate task';
  const dynamicTaskLabel = simpleMode ? 'Temporary access reference' : 'Dynamic task';
  const identityStoreTitle = simpleMode ? 'Saved App Password' : 'Application Identity Store';
  const identityStoreSubtitle = simpleMode ? 'Stored access' : 'Persistent KMS Vault';
  const rotateButtonLabel = simpleMode ? 'Change Password' : 'Rotate Secret';
  const versionLabel = simpleMode ? 'Release' : 'Secret Version';


  useEffect(() => {
    if (isSealed) return;
    const interval = setInterval(() => {
      setMachineIdentities((prev) => prev.map((machine) => {
        if (machine.status !== 'active' || machine.ttl === 'Expired') return machine;
        const parts = machine.ttl.split(' ');
        let hours = 0; let mins = 0; let secs = 0;
        if (parts.length === 2 && parts[0].includes('h')) {
          hours = parseInt(parts[0].replace('h', ''), 10) || 0;
          mins = parseInt(parts[1].replace('m', ''), 10) || 0;
        } else {
          mins = parseInt(parts[0].replace('m', ''), 10) || 0;
          secs = parseInt(parts[1].replace('s', ''), 10) || 0;
        }
        if (secs === 0 && mins > 0) { mins -= 1; secs = 59; } else if (secs > 0) { secs -= 1; }
        const expired = mins <= 0 && hours <= 0 && secs <= 0;
        return { ...machine, ttl: expired ? 'Expired' : (hours > 0 ? `${hours}h ${mins}m` : `${mins}m ${secs}s`), status: expired ? 'idle' : 'active' };
      }));
    }, 1000);
    return () => clearInterval(interval);
  }, [isSealed]);

  const handleRotate = async () => {
    setRotating(true);
    setSecretFlip(true);
    window.setTimeout(() => setSecretFlip(false), 620);
    try {
      if (!isLiveEnv) {
        setRotateJobId('blocked');
        setRotateMetadata((prev) => ({ ...prev, rotated_at: productionWriteBlockedMessage(simpleMode) }));
        return;
      }
      const data = await executeOperation('rotate_secret', {
        target: { type: 'secret', ref: 'photoprism' },
        params: { target: 'photoprism' },
      });
      const artifact = data?.artifacts || {};
      const identity = JSON.parse(data?.stdout || '{}')?.identity || {};
      const secret = JSON.parse(data?.stdout || '{}')?.secret || {};
      setPhotoPrismIdentity({
        username: identity.username || 'admin',
        password: identity.password || artifact.value || 'rotated-secret',
        lastRotated: identity.lastRotated || secret.rotated_at || artifact.rotated_at || new Date().toLocaleString(),
      });
      setRotateMetadata({
        version: secret.version || artifact.version || null,
        lease_duration: secret.lease_duration || artifact.lease_duration || null,
        rotated_at: secret.rotated_at || artifact.rotated_at || null,
      });
      setRotateJobId(data?.job_id || '');
    } finally {
      setRotating(false);
    }
  };

  const handleGenerateDynamic = async () => {
    setGeneratingDynamic(true);
    setSecretFlip(true);
    window.setTimeout(() => setSecretFlip(false), 620);
    try {
      if (!isLiveEnv) {
        setDynamicLease({ error: productionWriteBlockedMessage(simpleMode), ttl: 'blocked' });
        setDynamicJobId('blocked');
        return;
      }
      const data = await executeOperation('secret_read_dynamic', {
        target: { type: 'vault', ref: 'mariadb' },
        params: { target: 'mariadb' },
      });
      const lease = data?.artifacts?.lease || JSON.parse(data?.stdout || '{}')?.lease || null;
      setDynamicLease(lease);
      setDynamicJobId(data?.job_id || '');
    } finally {
      setGeneratingDynamic(false);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-4 animate-in fade-in duration-700 space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className={`col-span-2 p-8 rounded-[2.5rem] border flex items-center justify-between shadow-2xl relative overflow-hidden transition-colors duration-500 ${isSealed ? 'bg-red-950/20 border-red-500/30' : 'bg-emerald-950/20 border-emerald-500/30'}`}>
          <div className="relative z-10">
            <div className="flex items-center space-x-2 mb-2">
              {!isLiveEnv ? <ShieldAlert className="w-4 h-4 text-amber-400" /> : <ShieldCheck className={`w-4 h-4 ${isSealed ? 'text-red-400' : 'text-emerald-400'}`} />}
              <h3 className="text-xs font-black text-slate-500 uppercase tracking-widest">{vaultKicker}</h3>
            </div>
            <h2 className="text-4xl font-black text-white tracking-tight">{vaultHeading}</h2>
            <p className="text-slate-400 text-sm mt-2 max-w-md">{vaultBody}</p>
            <AdvancedDetails simpleMode={simpleMode} title="Access task references"><div>{rotateTaskLabel}: {rotateJobId || 'queued'} · {dynamicTaskLabel}: {dynamicJobId || 'queued'} · {simpleMode ? 'Evidence saved' : 'Audit evidence recorded'}</div></AdvancedDetails>
          </div>
          <button onClick={() => setIsSealed(!isSealed)} className={`p-6 rounded-3xl border transition-all transform active:scale-95 z-10 ${isSealed ? 'bg-red-600 border-red-400 text-white shadow-[0_0_20px_rgba(220,38,38,0.4)]' : 'bg-slate-800 border-white/10 text-emerald-400 hover:border-emerald-500/50'}`}>
            {isSealed ? <Lock className="w-10 h-10" /> : <Unlock className="w-10 h-10" />}
          </button>
        </div>

        <div className="bg-[#05080f] border border-white/10 rounded-[2.5rem] p-8 flex flex-col items-center justify-center text-center shadow-xl">
          <Fingerprint className="w-12 h-12 text-blue-400 mb-4" />
          <h4 className="text-white font-bold">{simpleMode ? 'Protected Access' : 'Zero Trust Auth'}</h4>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-8 shadow-2xl flex flex-col">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-purple-500/20 rounded-2xl border border-purple-500/30">
                <Database className="w-6 h-6 text-purple-400" />
              </div>
              <div>
                <h3 className="text-xl font-black text-white">{identityStoreTitle}</h3>
                <p className="text-slate-500 text-[10px] font-bold uppercase tracking-widest mt-1">{identityStoreSubtitle}</p>
              </div>
            </div>
            <button onClick={handleRotate} disabled={rotating || isSealed} className="px-4 py-3 rounded-full transition-all duration-300 disabled:opacity-20 flex items-center gap-2 shadow-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-white/5 risk-level-glow risk-medium">
              <RefreshCw className={`w-5 h-5 ${rotating ? 'animate-spin' : ''}`} />
              <span className="text-sm font-bold">{rotateButtonLabel}</span>
            </button>
          </div>

          <div className="space-y-4 flex-1">
            <div className="bg-black/60 border border-white/5 rounded-2xl p-5 flex items-center justify-between">
              <div>
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">{simpleMode ? 'Username' : 'Admin Username'}</label>
                <span className="text-white font-mono">{photoPrismIdentity.username}</span>
              </div>
              <Key className="w-4 h-4 text-slate-700" />
            </div>

            <div className="bg-black/60 border border-white/5 rounded-2xl p-5 flex items-center justify-between">
              <div className="flex-1">
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">{simpleMode ? 'Saved Password' : 'Static Password'}</label>
                <span className={`text-white font-mono break-all pr-4 secret-mask-pill ${secretFlip && !showSecret ? 'secret-rotation-flip' : ''}`}>{isSealed ? '****************' : (showSecret ? photoPrismIdentity.password : '••••••••••••••••••••')}</span>
              </div>
              <button onClick={() => setShowSecret(!showSecret)} disabled={isSealed} className="p-2 hover:bg-white/10 rounded-lg text-slate-400 transition-colors disabled:opacity-20">
                {showSecret ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>

            <div className="bg-black/60 border border-white/5 rounded-2xl p-5 flex items-center justify-between">
              <div>
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">{simpleMode ? 'Last Changed' : 'Last Rotated'}</label>
                <span className="text-slate-400 font-mono text-sm">{photoPrismIdentity.lastRotated}</span>
              </div>
              <Timer className="w-4 h-4 text-slate-700" />
            </div>
            <div className="bg-black/60 border border-white/5 rounded-2xl p-5 flex items-center justify-between">
              <div>
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">{versionLabel}</label>
                <span className="text-slate-400 font-mono text-sm">{rotateMetadata.version ?? '—'}</span>
              </div>
              <LockKeyhole className="w-4 h-4 text-slate-700" />
            </div>
            <div className="bg-black/60 border border-white/5 rounded-2xl p-5 flex items-center justify-between">
              <div>
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest block mb-1">{simpleMode ? 'Valid For' : 'Lease Duration'}</label>
                <span className="text-slate-400 font-mono text-sm">{rotateMetadata.lease_duration || '—'}</span>
              </div>
              <Calendar className="w-4 h-4 text-slate-700" />
            </div>
          </div>
        </div>

        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-8 shadow-2xl flex flex-col">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center space-x-4">
              <div className="p-3 bg-sky-500/20 rounded-2xl border border-sky-500/30">
                <Zap className="w-6 h-6 text-sky-400" />
              </div>
              <div>
                <h3 className="text-xl font-black text-white">{simpleMode ? 'Temporary Access' : 'Dynamic Secret Issuance'}</h3>
                <p className="text-slate-500 text-[10px] font-bold uppercase tracking-widest mt-1">{simpleMode ? 'Short-lived access' : 'Ephemeral lease'}</p>
              </div>
            </div>
            <button onClick={handleGenerateDynamic} disabled={generatingDynamic || isSealed} className="w-14 h-14 rounded-full bg-sky-600 hover:bg-sky-500 text-white flex items-center justify-center disabled:opacity-20">
              {generatingDynamic ? <RefreshCw className="w-5 h-5 animate-spin" /> : <Server className="w-5 h-5" />}
            </button>
          </div>

          <div className="space-y-4 flex-1">
            <div className="bg-black/60 border border-white/5 rounded-2xl p-5">
              <div className="flex items-center justify-between mb-2">
                <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest">{simpleMode ? 'Temporary login' : 'Current lease'}</label>
                <button onClick={() => setShowDynamic(!showDynamic)} disabled={isSealed || !dynamicLease} className="p-1 hover:bg-white/10 rounded-lg text-slate-400 transition-colors disabled:opacity-20">
                  {showDynamic ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
              <pre className={`text-white font-mono text-sm break-all secret-mask-pill ${secretFlip && !showDynamic ? 'secret-rotation-flip' : ''}`}>{dynamicLease ? (showDynamic ? (simpleMode ? `Temporary access for ${dynamicLease.username || 'service'} valid ${dynamicLease.ttl || 'briefly'}` : JSON.stringify(dynamicLease, null, 2)) : '••••••••••••••••••••') : (simpleMode ? 'No temporary access yet' : 'No lease yet')}</pre>
              <AdvancedDetails simpleMode={simpleMode} title="Temporary access support details"><div>Task id: {dynamicJobId || 'queued'}</div></AdvancedDetails>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: simpleMode ? 'Active Access' : 'Active Leases', val: dynamicLease ? '15' : '14', icon: Cpu },
          { label: simpleMode ? 'Secure Keys' : 'Transit Keys', val: '3', icon: Key },
          { label: simpleMode ? 'Login Methods' : 'Auth Methods', val: '2', icon: ShieldCheck },
          { label: 'Violations', val: '0', icon: ShieldAlert, color: 'text-emerald-400' },
        ].map((item, i) => (
          <div key={i} className="bg-[#05080f] border border-white/5 rounded-3xl p-6 flex flex-col items-center justify-center text-center shadow-lg">
            <item.icon className={`w-5 h-5 mb-3 ${item.color || 'text-indigo-400'}`} />
            <span className="text-3xl font-black text-white">{item.val}</span>
            <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-1">{item.label}</span>
          </div>
        ))}
      </div>
      <LiveEventPanel
        simpleMode={simpleMode}
        title="Passwords & Access activity"
        description="Password changes, temporary access, and operation progress appear here."
        subjectPrefixes={['pocketlab.events.vault.', 'pocketlab.audit.', 'pocketlab.events.operation.']}
        maxItems={4}
        compact
      />

    </div>
  );
}
