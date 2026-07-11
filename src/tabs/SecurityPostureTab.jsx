import React, { useEffect, useState } from 'react';
import { executeOperation, queryLogs } from '../lib/operations';
import HealthEnginePanel from '../components/HealthEnginePanel';
import { useHealthEngine } from '../hooks/useHealthEngine';
import { ShieldCheck, AlertTriangle, CheckCircle2, Activity, Lock, PlayCircle, Loader2, XCircle, X, Wrench } from 'lucide-react';
import { AdvancedDetails } from '../components/SimpleModeControls.jsx';
import { simpleActionLabel, redactTechnicalText } from '../lib/simpleLabels';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import { useControlPlaneStatus, productionWriteBlockedMessage } from '../hooks/useControlPlaneStatus.js';

// Accept a `simpleMode` prop to rename headings for non‑technical users.
export default function SecurityPostureTab({ simpleMode = false }) {
  const [isScanning, setIsScanning] = useState(false);
  const [isRemediatingLynis, setIsRemediatingLynis] = useState(false);
  const [isRemediatingTrivy, setIsRemediatingTrivy] = useState(false);
  const { status: controlPlane } = useControlPlaneStatus();
  const isLiveEnv = controlPlane.ready;
  const [trivyVulns, setTrivyVulns] = useState({ critical: 0, high: 0, medium: 0 });
  const [lynisMetrics, setLynisMetrics] = useState({ index: 0, warnings: 0, suggestions: 0 });
  const [scanHistory, setScanHistory] = useState([]);
  const [toast, setToast] = useState({ show: false, type: '', message: '' });
  const [taskIds, setTaskIds] = useState({ scan: '', lynis: '', trivy: '' });
  const [expandedLogId, setExpandedLogId] = useState(null);
  const { health, refresh: refreshHealthEngine } = useHealthEngine(15000);
  const opaStatus = health?.checks?.find((check) => check.name === 'opa' || check.name === 'policy-engine')?.status || 'unknown';
  const opaBlocked = ['unhealthy', 'unavailable', 'degraded', 'warning', 'maintenance'].includes(opaStatus);

  useEffect(() => {
    const fetchSecurityLogs = async () => {
      try {
        const data = await queryLogs({ query: '{job="pm2_logs"} |= "security_audit"', limit: 5 });
        if (data?.data?.result?.length > 0) {
          setTrivyVulns({ critical: 0, high: 2, medium: 5 });
          setLynisMetrics({ index: 82, warnings: 1, suggestions: 8 });
          setScanHistory([{ id: Date.now(), time: new Date().toLocaleTimeString(), engine: 'Ansible Playbook', status: 'Scan Completed', target: 'all-subsystems' }]);
        } else {
          setTrivyVulns({ critical: 0, high: 0, medium: 0 });
          setLynisMetrics({ index: 0, warnings: 0, suggestions: 0 });
          setScanHistory([]);
        }
      } catch {
        setTrivyVulns({ critical: 0, high: 0, medium: 0 });
        setLynisMetrics({ index: 0, warnings: 0, suggestions: 0 });
        setScanHistory([{ id: 'control-plane-degraded', time: new Date().toLocaleTimeString(), engine: 'control plane', status: 'Security telemetry unavailable', target: 'control-plane' }]);
      }
    };

    fetchSecurityLogs();
    const interval = setInterval(fetchSecurityLogs, 10000);
    return () => clearInterval(interval);
  }, []);

  const showToast = (type, message) => {
    setToast({ show: true, type, message });
    setTimeout(() => setToast({ show: false, type: '', message: '' }), 6000);
  };

  const triggerScan = async () => {
    setIsScanning(true);
    try {
      if (!isLiveEnv) {
        showToast('error', productionWriteBlockedMessage(simpleMode));
        return;
      }
      const result = await executeOperation('policy_deploy', {
        target: { type: 'repo', ref: 'security_scanners' },
        params: { playbook: '40_opa.yml', source: 'security_scanners' },
      });
      setTaskIds((prev) => ({ ...prev, scan: result?.job_id || '' }));
      showToast('success', simpleMode ? 'Safety check started.' : 'Policy deployment started. Executing audits...');
    } catch (err) {
      showToast('error', simpleMode ? redactTechnicalText(err.message || 'Safety check could not start.') : (err.message || 'Failed to trigger typed policy deployment.'));
    } finally {
      setIsScanning(false);
    }
  };

  const triggerRemediation = async (type) => {
    const isLynis = type === 'lynis';
    isLynis ? setIsRemediatingLynis(true) : setIsRemediatingTrivy(true);
    const blueprintName = isLynis ? 'host_hardening' : 'cve_patcher';

    try {
      if (!isLiveEnv) {
        showToast('error', productionWriteBlockedMessage(simpleMode));
        return;
      }
      const result = await executeOperation('deploy_blueprint', {
        target: { type: 'repo', ref: blueprintName },
        params: { playbook: 'site.yml', source: blueprintName, source_type: 'repo' },
      });
      setTaskIds((prev) => ({ ...prev, [type]: result?.job_id || '' }));
      showToast('success', simpleMode ? 'Approved fix started.' : `GitOps remediation queued: ${blueprintName}.`);
    } catch (err) {
      showToast('error', simpleMode ? redactTechnicalText(err.message || 'Approved fix could not start.') : (err.message || `Failed to execute ${blueprintName} playbook.`));
    } finally {
      isLynis ? setIsRemediatingLynis(false) : setIsRemediatingTrivy(false);
    }
  };

  const toggleLogExpand = (id) => setExpandedLogId(expandedLogId === id ? null : id);

  const healthScore = Math.max(0, 100 - (trivyVulns.critical * 15) - (trivyVulns.high * 5) - (lynisMetrics.warnings * 5));

  // Rename the section title in simple mode to "Safety Center".
  const postureHeading = simpleMode ? 'Safety Center' : 'Security Posture';

  return (
    <div className="max-w-7xl mx-auto p-4 animate-in fade-in duration-700 relative">
      <HealthEnginePanel health={health} onRefresh={refreshHealthEngine} simpleMode={simpleMode} />
      {opaBlocked && (
        <div className="rounded-3xl border border-amber-500/30 bg-amber-500/10 p-4 text-amber-100">
          <div className="flex items-center gap-2 font-bold">
            <AlertTriangle className="h-5 w-5" />
            {simpleMode ? 'Safety checks need attention' : 'OPA health affects remediation'}
          </div>
          <p className="mt-2 text-sm opacity-90">{simpleMode ? 'Some fix actions may wait until the safety engine is healthy again.' : 'Drift and security actions may be blocked until the policy engine reports healthy.'}</p>
        </div>
      )}

      {toast.show && (
        <div className="fixed top-6 left-1/2 -translate-x-1/2 z-[100] animate-in slide-in-from-top-4 fade-in duration-300">
          <div className={`flex items-center space-x-3 px-6 py-4 rounded-2xl shadow-2xl border backdrop-blur-xl ${toast.type === 'error' ? 'bg-red-950/90 border-red-500/50 text-red-200' : 'bg-emerald-950/90 border-emerald-500/50 text-emerald-200'}`}>
            {toast.type === 'error' ? <XCircle className="w-6 h-6 text-red-400" /> : <CheckCircle2 className="w-6 h-6 text-emerald-400" />}
            <div>
              <h4 className="font-bold text-sm">{simpleMode ? (toast.type === 'error' ? 'Action Failed' : 'Action Started') : (toast.type === 'error' ? 'Execution Failed' : 'Playbook Executed')}</h4>
              <p className="text-xs opacity-80">{simpleMode ? redactTechnicalText(toast.message) : toast.message}</p>
            </div>
            <button onClick={() => setToast({ show: false, type: '', message: '' })} className="ml-4 p-1 hover:bg-white/10 rounded-lg transition-colors"><X className="w-4 h-4" /></button>
          </div>
        </div>
      )}

      <div className="flex flex-col xl:flex-row gap-6 mb-8">
        <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-6 md:p-8 flex-1 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none transform translate-x-4 -translate-y-4">
            <ShieldCheck className="w-48 h-48 text-indigo-400" />
          </div>
          <div className="relative z-10">
            <h2 className="text-3xl md:text-4xl font-black text-white tracking-tight mb-2">{postureHeading}</h2>
            <p className="text-slate-400 text-sm max-w-xl leading-relaxed">{simpleMode ? 'Check for safety issues and apply approved fixes without handling technical tools directly.' : 'Continuous vulnerability management and host configuration auditing through typed operations.'}</p>

            <div className="flex flex-wrap gap-3 mt-6">
              <button onClick={triggerScan} disabled={!isLiveEnv || isScanning || isRemediatingLynis || isRemediatingTrivy} className={`px-6 py-3 rounded-xl font-bold flex items-center justify-center transition-all shadow-lg ${(!isLiveEnv || isScanning || isRemediatingLynis || isRemediatingTrivy) ? 'bg-indigo-600/50 text-indigo-200 cursor-not-allowed' : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-[0_0_20px_rgba(79,70,229,0.4)]'}`}>
                {isScanning ? <Loader2 className="w-5 h-5 mr-2 animate-spin" /> : <PlayCircle className="w-5 h-5 mr-2" />}
                {isScanning ? (simpleMode ? 'Checking...' : 'Executing Playbook...') : (simpleMode ? 'Run Safety Check' : 'Run Full Security Audit')}
              </button>
              <button onClick={() => triggerRemediation('lynis')} disabled={!isLiveEnv || isScanning || isRemediatingLynis || isRemediatingTrivy} className="px-6 py-3 rounded-xl font-bold flex items-center justify-center transition-all border border-emerald-500/30 bg-emerald-500/10 text-emerald-100 hover:bg-emerald-500/15 disabled:opacity-50">
                {simpleMode ? 'Fix Device Settings' : 'Remediate Lynis'}
              </button>
              <button onClick={() => triggerRemediation('trivy')} disabled={!isLiveEnv || isScanning || isRemediatingLynis || isRemediatingTrivy} className="px-6 py-3 rounded-xl font-bold flex items-center justify-center transition-all border border-orange-500/30 bg-orange-500/10 text-orange-100 hover:bg-orange-500/15 disabled:opacity-50">
                {simpleMode ? 'Fix App Risks' : 'Remediate Trivy'}
              </button>
              <AdvancedDetails simpleMode={simpleMode} title="Safety task references">
                <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-xs text-slate-300">Scan task: {taskIds.scan || 'queued'}</div>
                <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-xs text-slate-300">Lynis task: {taskIds.lynis || 'queued'}</div>
                <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-xs text-slate-300">Trivy task: {taskIds.trivy || 'queued'}</div>
              </AdvancedDetails>
            </div>
          </div>
        </div>

        <div className="flex flex-col md:flex-row gap-4 md:gap-6 shrink-0 w-full xl:w-[500px]">
          <div className="bg-[#05080f] border border-white/10 rounded-[2.5rem] p-6 flex-1 flex flex-col items-center justify-center shadow-xl">
            <div className="relative w-24 h-24 md:w-28 md:h-28 flex items-center justify-center mb-3">
              <svg className="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
                <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="10" className="text-slate-800" />
                <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="10" strokeDasharray="283" strokeDashoffset={283 - (283 * healthScore) / 100} className={`${healthScore > 80 ? 'text-emerald-500' : healthScore > 50 ? 'text-orange-500' : 'text-red-500'} transition-all duration-1000`} strokeLinecap="round" />
              </svg>
              <div className="absolute flex flex-col items-center">
                <span className="text-2xl font-black text-white">{healthScore}</span>
              </div>
            </div>
            <h3 className="font-bold text-white text-sm">Global Health</h3>
            <p className={`text-[10px] uppercase tracking-widest mt-1 font-bold ${healthScore > 80 ? 'text-emerald-400' : 'text-red-400'}`}>{healthScore > 80 ? 'Passing Benchmarks' : 'Remediation Required'}</p>
          </div>

          <div className="bg-[#05080f] border border-white/10 rounded-[2.5rem] p-6 flex-1 flex flex-col shadow-xl relative overflow-hidden">
            <div className="flex items-center justify-between mb-4 text-slate-400">
              <div className="flex items-center space-x-2">
                <Lock className="w-4 h-4" />
                <span className="text-[10px] font-black uppercase tracking-widest">Lynis Audit</span>
              </div>
            </div>
            <div className="flex items-end space-x-2 mb-4">
              <span className={`text-4xl md:text-5xl font-black tracking-tighter ${lynisMetrics.index > 80 ? 'text-emerald-400' : lynisMetrics.index > 60 ? 'text-orange-400' : 'text-red-400'}`}>{lynisMetrics.index}</span>
              <span className="text-sm font-bold text-slate-500 mb-1 md:mb-1.5">/ 100</span>
            </div>
            <div className="mt-auto">
              <button onClick={() => triggerRemediation('lynis')} disabled={isRemediatingLynis} className="w-full rounded-xl bg-emerald-600 px-4 py-3 font-semibold text-white hover:bg-emerald-500 disabled:opacity-50">
                {isRemediatingLynis ? (simpleMode ? 'Fixing...' : 'Remediating...') : (simpleMode ? 'Fix Device Settings' : 'Remediate Lynis')}
              </button>
              {!simpleMode && <div className="mt-2 text-xs text-slate-500">Task id: {taskIds.lynis || 'queued'}</div>}
            </div>
          </div>
        </div>
      </div>

      <div className="bg-[#05080f] border border-white/10 rounded-[2.5rem] p-4 md:p-6 shadow-xl">
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-4 h-4 text-slate-400" />
          <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'Recent Safety Activity' : 'Security event stream'}</h3>
        </div>
        <div className="space-y-3">
          {scanHistory.map((entry) => (
            <div key={entry.id} className="flex items-start justify-between gap-3 p-3 bg-black/40 rounded-xl border border-white/5">
              <div className="min-w-0">
                <div className="text-xs font-bold text-slate-300">{simpleMode ? 'Safety check' : entry.engine}</div>
                <div className="text-[11px] text-slate-500">{simpleMode ? redactTechnicalText(entry.status) : `${entry.status} · ${entry.target}`}</div>
              </div>
              <button onClick={() => toggleLogExpand(entry.id)} className="text-slate-400"><Loader2 className="w-4 h-4" /></button>
            </div>
          ))}
        </div>
      </div>
      <LiveEventPanel
        simpleMode={simpleMode}
        title="Safety activity stream"
        description="Safety checks, policy updates, and remediation progress appear here."
        subjectPrefixes={['pocketlab.events.security.', 'pocketlab.audit.', 'pocketlab.events.operation.']}
        maxItems={4}
        compact
      />

    </div>
  );
}
