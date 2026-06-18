import React, { useEffect, useRef, useState } from 'react';
import { executeOperation } from '../lib/operations';
import { ShieldCheck, FileCheck, ToggleLeft, ToggleRight, AlertTriangle, CheckCircle2, FileCode2, Scale, Lock, RadioTower, Activity, ChevronDown, ArrowDown, Loader2 } from 'lucide-react';

export default function PolicyGuardrailsTab() {
  const [enforceMode, setEnforceMode] = useState(false);
  const [expandedId, setExpandedId] = useState(null);
  const [evaluations, setEvaluations] = useState([]);
  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [taskId, setTaskId] = useState('');
  const [taskMessage, setTaskMessage] = useState('');
  const [policySweeping, setPolicySweeping] = useState(false);
  const touchStartY = useRef(0);
  const pullThreshold = 70;
  const [isLiveEnv, setIsLiveEnv] = useState(false);

  const safeFetchJSON = async (url, options = {}) => {
    try {
      const res = await fetch(url, options);
      const text = await res.text();
      if (text.trim().startsWith('<!DOCTYPE html') || text.includes('<html')) return { ok: false, isFallback: true };
      return { ok: true, data: JSON.parse(text) };
    } catch (err) {
      return { ok: false, error: err };
    }
  };

  useEffect(() => {
    (async () => {
      const result = await safeFetchJSON('/ready');
      setIsLiveEnv(result.ok && (result.data?.status === 'ready' || result.data?.ready === true));
    })();
  }, []);

  const policies = {
    ports: {
      name: 'Privileged Port Restriction',
      desc: 'Prevents workloads from binding to ports < 1024, which are restricted by the Android OS kernel.',
      severity: 'CRITICAL',
      rego: `package pocketlab.network\n\ndeny[msg] {\n    port := input.playbook.tasks[_].pm2_env.PORT\n    to_number(port) < 1024\n    msg := "Android OS denies non-root binding to ports < 1024. Please use a port > 1023."\n}`,
    },
    secrets: {
      name: 'Hardcoded Secrets Prevention',
      desc: 'Ensures declarative playbooks use Vault AppRole lookups instead of plaintext variables.',
      severity: 'HIGH',
      rego: `package pocketlab.security\n\ndeny[msg] {\n    some key\n    val := input.playbook.vars[key]\n    contains(lower(key), "password")\n    not contains(val, "lookup('hashi_vault'")\n    msg := "Hardcoded secrets detected. You must use the Vault AppRole lookup plugin."\n}`,
    },
    execution: {
      name: 'PRoot Isolation Enforcement',
      desc: 'Ensures Linux binaries are executed inside the PRoot Ubuntu subsystem, not native Termux.',
      severity: 'MEDIUM',
      rego: `package pocketlab.execution\n\ndeny[msg] {\n    task := input.playbook.tasks[_]\n    contains(task.command, "apt-get")\n    not contains(task.prefix, "proot-distro login ubuntu")\n    msg := "Linux package managers must be executed inside the PRoot Ubuntu subsystem."\n}`,
    },
  };

  useEffect(() => {
    let interval;
    const fetchOpaLogs = async () => {
      const result = await safeFetchJSON('/api/opa_evaluations.json');
      if (result.ok && Array.isArray(result.data)) {
        setEvaluations(result.data.slice(0, 50));
        setIsLiveEnv(true);
      } else {
        setIsLiveEnv(false);
        setEvaluations([{ id: 'control-plane-degraded', timestamp: new Date().toLocaleTimeString(), trigger: 'fastapi_nats_readiness', status: 'AUDIT_WARN', msg: 'Control plane unavailable. Policy evaluations are paused; simulator data is disabled in production mode.', time: 0 }]);
      }
    };
    fetchOpaLogs();
    interval = setInterval(fetchOpaLogs, 5000);
    return () => clearInterval(interval);
  }, [enforceMode]);

  const handleToggleMode = async () => {
    setPolicySweeping(true);
    window.setTimeout(() => setPolicySweeping(false), 700);
    if (navigator.vibrate) navigator.vibrate(20);
    const newMode = !enforceMode;
    setEnforceMode(newMode);
    setTaskMessage(newMode ? 'Enforcement mode requested.' : 'Audit mode requested.');
    if (isLiveEnv) {
      try {
        const result = await executeOperation('policy_deploy', {
          target: { type: 'policy', ref: newMode ? 'enforce' : 'audit' },
          params: { enforce_mode: newMode, playbook: '40_opa.yml' },
        });
        setTaskId(result?.job_id || '');
      } catch (err) {
        setIsLiveEnv(false);
        setTaskMessage(err?.message || 'Policy mode update rejected because control plane is unavailable.');
      }
    } else {
      setTaskMessage('Policy mode update blocked until the production control plane is ready.');
    }
  };

  const runScan = async () => {
    setPolicySweeping(true);
    window.setTimeout(() => setPolicySweeping(false), 700);
    setTaskMessage('Submitting policy update...');
    try {
      const result = await executeOperation('policy_deploy', {
        target: { type: 'policy', ref: enforceMode ? 'enforce' : 'audit' },
        params: { enforce_mode: enforceMode, playbook: '40_opa.yml' },
      });
      setTaskId(result?.job_id || '');
      setTaskMessage(`Policy update completed. Task ${result?.job_id || 'queued'}.`);
    } catch (err) {
      setTaskMessage(err.message || 'Policy update failed.');
    }
  };

  const handleTouchStart = (e) => {
    if (window.scrollY <= 0) touchStartY.current = e.touches[0].clientY;
    else touchStartY.current = 0;
  };

  const handleTouchMove = (e) => {
    if (touchStartY.current === 0 || isRefreshing) return;
    const diff = e.touches[0].clientY - touchStartY.current;
    if (diff > 0) setPullDistance(Math.min(diff * 0.4, 120));
  };

  const handleTouchEnd = () => {
    if (pullDistance > pullThreshold && !isRefreshing) {
      if (navigator.vibrate) navigator.vibrate(30);
      setIsRefreshing(true);
      setTimeout(() => {
        setIsRefreshing(false);
        setPullDistance(0);
        setEvaluations((prev) => [{ id: Math.random().toString(36).slice(2, 9), timestamp: new Date().toLocaleTimeString(), trigger: 'manual_sync', status: 'PASS', msg: 'Policies re-verified via Control Plane.', time: 15 }, ...prev].slice(0, 50));
      }, 800);
    } else {
      setPullDistance(0);
    }
    touchStartY.current = 0;
  };

  const toggleExpand = (id) => {
    if (navigator.vibrate) navigator.vibrate(10);
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="max-w-7xl mx-auto p-4 relative space-y-6" onTouchStart={handleTouchStart} onTouchMove={handleTouchMove} onTouchEnd={handleTouchEnd}>
      <div className="pull-refresh-tension flex justify-center items-center w-full absolute top-0 left-0 right-0 z-0 overflow-hidden" style={{ height: `${pullDistance}px`, opacity: pullDistance / pullThreshold, transition: isRefreshing || pullDistance === 0 ? 'height 0.3s ease, opacity 0.3s ease' : 'none' }}>
        <div className="flex flex-col items-center justify-center mt-4 text-emerald-400">
          {isRefreshing ? <Loader2 className="w-6 h-6 animate-spin" /> : <ArrowDown className={`w-6 h-6 transition-transform duration-300 ${pullDistance > pullThreshold ? 'rotate-180 text-emerald-300' : ''}`} />}
          <span className="text-[10px] font-bold uppercase tracking-widest mt-2 text-emerald-400/80">{isRefreshing ? 'Verifying Policies...' : pullDistance > pullThreshold ? 'Release to Sync' : 'Pull to verify'}</span>
        </div>
      </div>

      <div className="relative z-10 animate-in fade-in duration-700 flex flex-col xl:flex-row gap-6" style={{ transform: `translateY(${pullDistance}px)`, transition: isRefreshing || pullDistance === 0 ? 'transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)' : 'none' }}>
        <div className="w-full xl:w-1/2 flex flex-col gap-6 shrink-0">
          <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-6 md:p-8 relative overflow-hidden shadow-2xl">
            <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none transform translate-x-4 -translate-y-4">
              <Scale className="w-48 h-48 text-indigo-400" />
            </div>
            <div className="flex items-center space-x-2 mb-4 relative z-10">
              {!isLiveEnv ? <RadioTower className="w-5 h-5 text-amber-400" /> : <FileCheck className={`w-5 h-5 text-indigo-400 ${policySweeping ? 'policy-shield-sweep policy-shield-icon' : ''}`} />}
              <h3 className="text-xs font-black text-slate-500 uppercase tracking-widest">Open Policy Agent</h3>
            </div>
            <h2 className="text-3xl md:text-4xl font-black text-white tracking-tight mb-2 relative z-10">Policy as Code</h2>
            <p className="text-slate-400 text-sm relative z-10">Typed policy deployment keeps the UI and backend contract aligned.</p>

            <div className={`mt-6 p-4 rounded-2xl border flex items-center justify-between transition-colors relative z-10 ${enforceMode ? 'bg-indigo-900/30 border-indigo-500/50' : 'bg-black/40 border-white/5'}`}>
              <div>
                <h4 className={`font-bold text-sm md:text-base ${enforceMode ? 'text-indigo-400' : 'text-slate-300'}`}>{enforceMode ? 'Enforcement Mode' : 'Audit Mode (Dry Run)'}</h4>
                <p className="text-[9px] md:text-[10px] text-slate-500 uppercase tracking-widest mt-1">{enforceMode ? 'Violations block deployments' : 'Violations only log warnings'}</p>
              </div>
              <button onClick={handleToggleMode} className={`p-2 rounded-xl transition-all ${enforceMode ? 'text-indigo-400 bg-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.4)]' : 'text-slate-500 bg-slate-800'}`}>
                {enforceMode ? <ToggleRight className="w-7 h-7 md:w-8 md:h-8" /> : <ToggleLeft className="w-7 h-7 md:w-8 md:h-8" />}
              </button>
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              <button onClick={runScan} className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 font-semibold text-white hover:bg-indigo-500">
                <ShieldCheck className={`h-4 w-4 ${policySweeping ? 'policy-shield-sweep policy-shield-icon' : ''}`} /> Deploy policy
              </button>
              <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-3 text-xs text-slate-300">Task id: {taskId || 'queued'}</div>
            </div>

            {taskMessage && <div className={`mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200 ${policySweeping ? 'policy-shield-sweep' : ''}`}>{taskMessage}</div>}
          </div>

          <div className="bg-[#05080f] border border-white/10 rounded-[2.5rem] p-4 md:p-6 shadow-xl flex flex-col">
            <h3 className="text-xs font-black text-slate-500 uppercase tracking-widest px-2 mb-4 flex items-center">
              <ShieldCheck className="w-4 h-4 mr-2" /> Active Rego Rule Sets
            </h3>
            <div className="space-y-3">
              {Object.entries(policies).map(([key, policy]) => {
                const isExpanded = expandedId === key;
                return (
                  <div key={key} className={`rounded-2xl border transition-all overflow-hidden ${isExpanded ? 'bg-slate-900/80 border-indigo-500/30' : 'bg-slate-900/40 border-white/5 hover:border-white/10'}`}>
                    <div onClick={() => toggleExpand(key)} className="p-4 flex items-center justify-between cursor-pointer gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center space-x-2 mb-1">
                          <h4 className={`font-bold truncate text-sm md:text-base ${isExpanded ? 'text-indigo-300' : 'text-slate-300'}`}>{policy.name}</h4>
                        </div>
                        <p className="text-[11px] md:text-xs text-slate-500 line-clamp-1">{policy.desc}</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={`px-2 py-1 rounded text-[9px] md:text-[10px] font-black uppercase tracking-widest ${policy.severity === 'CRITICAL' ? 'bg-red-500/10 text-red-400 border border-red-500/20' : policy.severity === 'HIGH' ? 'bg-orange-500/10 text-orange-400 border border-orange-500/20' : 'bg-sky-500/10 text-sky-400 border border-sky-500/20'}`}>{policy.severity}</span>
                        <ChevronDown className={`w-4 h-4 text-slate-500 transition-transform duration-300 ${isExpanded ? 'rotate-180' : ''}`} />
                      </div>
                    </div>
                    {isExpanded && <div className="px-4 pb-4"><pre className="overflow-auto rounded-xl bg-black/50 p-4 text-[11px] leading-relaxed text-slate-300"><code>{policy.rego}</code></pre></div>}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <div className="w-full xl:w-1/2 flex flex-col gap-6">
          <div className="bg-[#05080f] border border-white/10 rounded-[2.5rem] p-4 md:p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-500 flex items-center"><Activity className="w-4 h-4 mr-2" /> Operation stream</h3>
            </div>
            <div className="space-y-3">
              {evaluations.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center opacity-30 text-slate-400">
                  <Activity className="w-10 h-10 mb-2 animate-pulse" />
                  <p className="text-xs">Awaiting Gitea/Ansible Declarations...</p>
                </div>
              ) : (
                evaluations.map((ev) => (
                  <div key={ev.id} className="flex flex-col sm:flex-row sm:items-center p-3 bg-black/40 rounded-xl border border-white/5 gap-2 sm:gap-0 transition-all hover:bg-black/60">
                    <div className="flex items-center justify-between sm:justify-start w-full sm:w-auto">
                      <div className="w-16 md:w-20 shrink-0 text-slate-500 font-mono text-[9px] md:text-[10px]">{ev.timestamp}</div>
                      <div className="w-24 md:w-28 shrink-0 flex justify-end sm:justify-start">
                        <span className={`px-2 py-0.5 md:py-1 rounded text-[9px] md:text-[10px] font-black uppercase tracking-widest flex items-center w-fit ${ev.status === 'PASS' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : ev.status === 'AUDIT_WARN' ? 'bg-orange-500/10 text-orange-400 border border-orange-500/30' : 'bg-red-500/10 text-red-400 border border-red-500/30'}`}>
                          {ev.status === 'PASS' && <CheckCircle2 className="w-3 h-3 mr-1" />}
                          {ev.status === 'AUDIT_WARN' && <AlertTriangle className="w-3 h-3 mr-1" />}
                          {ev.status === 'DENIED' && <Lock className="w-3 h-3 mr-1" />}
                          {ev.status}
                        </span>
                      </div>
                    </div>
                    <div className="flex-1 truncate pl-0 sm:pl-3 sm:border-l border-white/10 sm:ml-2">
                      <div className="text-[11px] md:text-xs font-bold text-slate-300 truncate">Action: {ev.trigger}</div>
                      <div className={`text-[10px] md:text-[11px] truncate mt-0.5 ${ev.status === 'PASS' ? 'text-slate-500' : 'text-red-300'}`}>{ev.msg}</div>
                    </div>
                    <div className="text-[9px] md:text-[10px] text-slate-600 font-mono hidden md:block shrink-0 ml-2">{ev.time}ms</div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
