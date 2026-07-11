import React, { useEffect, useMemo, useState } from 'react';
import { executeOperation } from '../lib/operations';
import { Workflow, Server, RefreshCw, ShieldCheck, Copy, KeyRound } from 'lucide-react';
import { AdvancedDetails } from '../components/SimpleModeControls.jsx';
import { redactTechnicalText } from '../lib/simpleLabels';
import { useControlPlaneStatus, productionWriteBlockedMessage } from '../hooks/useControlPlaneStatus.js';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import { SkeletonCards } from '../components/ui.jsx';

// Accept a `simpleMode` prop. When enabled, this component renames
// headings and buttons for a non‑technical audience (e.g. 'Add Device').
export default function FleetScalingTab({ simpleMode = false }) {
  const [nodes, setNodes] = useState([]);
  const [agents, setAgents] = useState([]);
  const [agentCommands, setAgentCommands] = useState([]);
  const [selectedRole, setSelectedRole] = useState('compute');
  const [hostname, setHostname] = useState('');
  const [apiInputValue, setApiInputValue] = useState('tskey-api-');
  const [isSavingKey, setIsSavingKey] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [ztpCommand, setZtpCommand] = useState('');
  const [joinPayload, setJoinPayload] = useState(null);
  const [pendingJoin, setPendingJoin] = useState(null);
  const [copied, setCopied] = useState(false);
  const [logs, setLogs] = useState('');
  const { status: controlPlane } = useControlPlaneStatus();
  const isLiveEnv = controlPlane.ready;
  const [isRefreshingAgents, setIsRefreshingAgents] = useState(false);
  const [handshakeStage, setHandshakeStage] = useState('idle');

  // Dynamic labels for simple experience mode.  When simpleMode is true,
  // these strings replace technical terminology with more approachable
  // alternatives.  They are defined here to avoid inline conditional
  // expressions throughout the JSX below.
  const tagline = simpleMode ? 'My Devices' : 'Fleet scaling';
  const headingTitle = simpleMode ? 'Add Device' : 'Device Fleet Onboarding';
  const generateButtonLabel = simpleMode ? 'Add Device' : 'Generate Device Invite';


  const fetchFleet = async () => {
    try {
      const res = await fetch('/api/fleet.json');
      const data = await res.json();
      setNodes(Array.isArray(data) ? data : []);
    } catch {
      setNodes([
        { id: 'worker1', name: 'pixel-edge-01', role: 'Mesh Node', ip: '100.101.50.2', status: 'active', isCurrent: false },
        { id: 'worker2', name: 'samsung-nfs', role: 'Mesh Storage Node', ip: '100.101.50.3', status: 'active', isCurrent: false },
      ]);
    }
  };

  const fetchAgents = async () => {
    try {
      const res = await fetch('/api/fleet/agents');
      const data = await res.json();
      setAgents(Array.isArray(data.agents) ? data.agents : []);
      const commandResponses = await Promise.all((data.agents || []).slice(0, 5).map(async (agent) => {
        try {
          const nodeId = agent.node_id || agent.id;
          const cmdRes = await fetch(`/api/fleet/agents/${encodeURIComponent(nodeId)}/commands?limit=5`);
          const cmdData = await cmdRes.json();
          return cmdData.commands || [];
        } catch { return []; }
      }));
      setAgentCommands(commandResponses.flat());
    } catch {
      setAgents([]);
      setAgentCommands([]);
    }
  };

  const refreshAgents = async () => {
    setIsRefreshingAgents(true);
    try {
      const res = await fetch('/api/fleet/agents/broadcast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'health.check' }),
      });
      if (!res.ok) throw new Error('Fleet broadcast rejected');
      setLogs((prev) => prev + (simpleMode ? 'Asked devices to check in.\n' : '[device-fleet] Device health check requested.\n'));
      setTimeout(() => { fetchFleet(); fetchAgents(); }, 1500);
    } catch (err) {
      setLogs((prev) => prev + (simpleMode ? 'Could not ask devices to check in.\n' : `[ERROR] ${err.message || 'Failed to broadcast node command.'}\n`));
    } finally {
      setIsRefreshingAgents(false);
    }
  };

  const requestAgentCheck = async (nodeId) => {
    try {
      const res = await fetch(`/api/fleet/agents/${encodeURIComponent(nodeId)}/commands`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'health.check' }),
      });
      if (!res.ok) throw new Error('Device command rejected');
      setLogs((prev) => prev + (simpleMode ? 'Device check requested.\n' : `[device-fleet] Health check requested for ${nodeId}.\n`));
      setTimeout(fetchAgents, 1500);
    } catch (err) {
      setLogs((prev) => prev + (simpleMode ? 'Device check could not be requested.\n' : `[ERROR] ${err.message || 'Failed to queue device command.'}\n`));
    }
  };

  useEffect(() => {
    fetchFleet();
    fetchAgents();
    const timer = setInterval(() => { fetchFleet(); fetchAgents(); }, 15000);
    return () => clearInterval(timer);
  }, []);

  const controlPlaneName = useMemo(() => {
    const current = nodes.find((n) => n.isCurrent);
    return current?.name || 'pocket-lab';
  }, [nodes]);

  const handleSaveApiKey = async () => {
    if (!apiInputValue.startsWith('tskey-api-')) return alert("Key must start with 'tskey-api-'");
    setIsSavingKey(true);
    try {
      if (!isLiveEnv) {
        setLogs((prev) => prev + productionWriteBlockedMessage(simpleMode) + '\n');
        return;
      }
      await executeOperation('rotate_secret', { target: { type: 'secret', ref: 'tailscale' }, params: { target: 'tailscale', value: apiInputValue } });
      setLogs((prev) => prev + (simpleMode ? 'Network key saved.\n' : '[identity-access] Network credential update requested.\n'));
    } finally {
      setIsSavingKey(false);
    }
  };

  const handleGenerateZTP = async () => {
    setIsGenerating(true);
    setHandshakeStage('invite');
    setLogs(simpleMode ? 'Preparing device invite...\n' : '[*] Preparing device invite...\n');
    try {
      if (!isLiveEnv) {
        const message = productionWriteBlockedMessage(simpleMode);
        setJoinPayload(null);
        setPendingJoin(null);
        setZtpCommand('');
        setLogs((prev) => prev + message + '\n');
        setHandshakeStage('idle');
        return;
      }
      const result = await executeOperation('fleet_join', {
        target: { type: 'fleet', ref: selectedRole },
        params: { role: selectedRole, hostname: hostname || `pocket-${selectedRole}` },
      });
      const artifact = result?.artifacts || {};
      setJoinPayload({ role: artifact.role || selectedRole, token: artifact.token, hostname: artifact.hostname || hostname || `pocket-${selectedRole}` });
      setPendingJoin(artifact.pending_state || null);
      setLogs((prev) => prev + (simpleMode ? 'Device invite created.\n' : '[device-fleet] Device invite created through the control plane.\n'));
      setHandshakeStage('connected');
      window.setTimeout(() => setHandshakeStage('idle'), 1600);
    } catch (err) {
      setLogs((prev) => prev + (simpleMode ? `Needs attention: ${redactTechnicalText(err.message || 'Failed to create device invite.')}\n` : `[ERROR] ${err.message || 'Failed to create join payload.'}\n`));
    } finally {
      setIsGenerating(false);
    }
  };

  const copyToClipboard = async () => {
    const text = ztpCommand || JSON.stringify(joinPayload || {}, null, 2);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-4 space-y-6 animate-in fade-in duration-700">
      <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-8 shadow-2xl relative overflow-hidden">
        <div className="absolute top-0 right-0 p-8 opacity-10 pointer-events-none transform translate-x-4 -translate-y-4">
          <Workflow className="w-48 h-48 text-emerald-400" />
        </div>

        <div className="relative z-10 flex flex-col gap-6">
          <div>
            <div className="flex items-center gap-2 text-slate-400 text-xs font-black uppercase tracking-widest">
              <Server className="h-4 w-4" /> {tagline}
            </div>
            <h2 className="mt-2 text-4xl font-black text-white tracking-tight">{headingTitle}</h2>
            <p className="mt-2 text-sm text-slate-400 max-w-2xl">
              {simpleMode ? 'Add a phone, tablet, server, or storage device using a guided invite. Advanced network settings are hidden unless needed.' : 'No shell payload editor. Generate a governed device invite and copy the output for provisioning.'}
            </p>
          </div>

          <AdvancedDetails simpleMode={simpleMode} title="Device invite settings">
            <div className="grid gap-3 md:grid-cols-3">
              <label className="block">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Role</span>
                <select value={selectedRole} onChange={(e) => setSelectedRole(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white">
                  <option value="compute">compute</option>
                  <option value="storage">storage</option>
                  <option value="control">control</option>
                </select>
              </label>
              <label className="block">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Hostname</span>
                <input value={hostname} onChange={(e) => setHostname(e.target.value)} placeholder="pocket-node-01" className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white" />
              </label>
              <label className="block">
                <span className="text-[10px] font-black uppercase tracking-widest text-slate-500">Tailscale API key</span>
                <input value={apiInputValue} onChange={(e) => setApiInputValue(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-sm text-white" />
              </label>
            </div>
          </AdvancedDetails>


          <div className={`device-handshake device-handshake-${handshakeStage}`}>
            <div className="device-handshake-dot" />
            <div className="device-handshake-line" />
            <div className="device-handshake-card">
              <span>{simpleMode ? 'Invite generated' : 'Device invite generated'}</span>
              <strong>{handshakeStage === 'connected' ? (simpleMode ? 'Device connected' : 'mesh handshake ready') : (simpleMode ? 'Waiting for device' : 'pending node')}</strong>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button onClick={handleSaveApiKey} disabled={isSavingKey} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-5 py-3 font-semibold text-slate-200 hover:bg-black/30 disabled:opacity-50">
              <KeyRound className="h-4 w-4" /> {simpleMode ? 'Save Network Key' : 'Save API Key'}
            </button>
            <button onClick={handleGenerateZTP} disabled={isGenerating} className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-3 font-semibold text-white hover:bg-emerald-500 disabled:opacity-50">
              {isGenerating ? <RefreshCw className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
              {generateButtonLabel}
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="bg-[#05080f] border border-white/10 rounded-[2rem] p-6 shadow-xl">
          <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'Device Invite' : 'Join artifact'}</h3>
          <pre className="mt-4 min-h-40 overflow-auto rounded-2xl border border-white/10 bg-black/30 p-4 text-[11px] text-slate-300">
{joinPayload ? (simpleMode ? `Invite ready for ${joinPayload.hostname || 'new device'}. Use Copy Invite when setting up the device.` : JSON.stringify(joinPayload, null, 2)) : (simpleMode ? 'No device invite created yet.' : 'No device invite generated yet.')}
          </pre>
          {ztpCommand && !simpleMode && (
            <div className="mt-4 text-xs text-slate-400 break-all">{ztpCommand}</div>
          )}
          {pendingJoin && (
            <div className="mt-4 rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-xs text-amber-100">
              Pending node: {pendingJoin.name} · heartbeat state: {pendingJoin.enrollment_state}
            </div>
          )}
          <button onClick={copyToClipboard} className="mt-4 inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:bg-black/30">
            <Copy className="h-4 w-4" /> {copied ? 'Copied' : (simpleMode ? 'Copy Invite' : 'Copy Invite Details')}
          </button>
        </div>

        <div className="bg-[#05080f] border border-white/10 rounded-[2rem] p-6 shadow-xl">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-500">{simpleMode ? 'My Devices' : 'Fleet overview'}</h3>
            <button onClick={refreshAgents} disabled={isRefreshingAgents} className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-black/30 disabled:opacity-50">
              <RefreshCw className={`h-3.5 w-3.5 ${isRefreshingAgents ? 'animate-spin' : ''}`} /> {simpleMode ? 'Check Devices' : 'Broadcast health.check'}
            </button>
          </div>
          <div className="mt-4 space-y-3">
            {nodes.length === 0 ? <SkeletonCards count={2} simpleMode={simpleMode} className="fleet-skeletons" /> : null}
            {nodes.map((node) => (
              <div key={node.id || node.name} className={`rounded-2xl border border-white/10 bg-black/20 p-4 ${pendingJoin && (pendingJoin.name === node.name || pendingJoin.hostname === node.name) ? 'device-handshake-card device-handshake-connected' : ''}`}>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-semibold text-white">{node.name}</div>
                    <div className="text-xs text-slate-400">{simpleMode ? node.role : `${node.role} · ${node.ip || 'n/a'} · ${node.source || 'static'}`}</div>
                    {node.last_seen_at && <div className="mt-1 text-[10px] text-slate-500">{simpleMode ? 'Last seen' : 'last_seen_at'}: {node.last_seen_at}</div>}
                  </div>
                  <span className="text-[10px] uppercase tracking-widest text-slate-400">{node.status}</span>
                </div>
              </div>
            ))}
          </div>
          <AdvancedDetails simpleMode={simpleMode} title={simpleMode ? 'Connected device agents' : 'event-backed fleet agents'}>
            <div className="space-y-3">
              {agents.length === 0 && <div className="text-sm text-slate-400">{simpleMode ? 'No live device agents have checked in yet.' : 'No event-backed fleet agents have checked in yet.'}</div>}
              {agents.map((agent) => (
                <div key={agent.node_id || agent.id} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-semibold text-white">{agent.name || agent.hostname || agent.node_id}</div>
                      <div className="text-xs text-slate-400">{agent.role} · {agent.agent_version} · {agent.status}</div>
                    </div>
                    <button onClick={() => requestAgentCheck(agent.node_id || agent.id)} className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-black/30">
                      {simpleMode ? 'Check' : 'health.check'}
                    </button>
                  </div>
                  {agent.telemetry && <div className="mt-2 text-[10px] text-slate-500">CPU {agent.telemetry.cpu_usage_percent ?? '—'}% · Temp {agent.telemetry.cpu_temp_c ?? '—'}°C · Free {agent.telemetry.free_space_mb ?? '—'} MB</div>}
                </div>
              ))}
            </div>
          </AdvancedDetails>
          {agentCommands.length > 0 && (
            <AdvancedDetails simpleMode={simpleMode} title={simpleMode ? 'Recent device checks' : 'Recent node command results'}>
              <pre className="rounded-2xl border border-white/10 bg-black/20 p-4 text-[11px] text-slate-300 whitespace-pre-wrap">{JSON.stringify(agentCommands.slice(0, 10), null, 2)}</pre>
            </AdvancedDetails>
          )}
          {logs && <pre className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-[11px] text-slate-300 whitespace-pre-wrap">{logs}</pre>}
        </div>
      </div>
      <LiveEventPanel
        simpleMode={simpleMode}
        title="Device activity"
        description="Device invites, joins, and background fleet operations update here."
        subjectPrefixes={['pocketlab.events.fleet.', 'pocketlab.events.operation.']}
        maxItems={4}
        compact
      />

    </div>
  );
}
