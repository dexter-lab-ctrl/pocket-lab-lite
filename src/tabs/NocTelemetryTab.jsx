import React, { useState, useRef } from 'react';
import { Activity, HardDrive, MemoryStick, Server, Thermometer, Wifi, ArrowDown, Loader2, Cpu } from 'lucide-react';
import HealthEnginePanel from '../components/HealthEnginePanel';
import RuntimeObservabilityStatusPanel from '../components/RuntimeObservabilityStatusPanel';
import CountUpNumber from '../components/CountUpNumber.jsx';
import { useHealthEngine } from '../hooks/useHealthEngine';
import { useTelemetry } from '../hooks/useTelemetry';
import { useObservabilityStatus } from '../hooks/useObservabilityStatus';
import LiveEventPanel from '../components/LiveEventPanel.jsx';
import { SkeletonCards } from '../components/ui.jsx';

// Accept a `simpleMode` prop to rename headings for non‑technical users.
export default function NocTelemetryTab({ simpleMode = false }) {
  const { liveData: telemetry, isConnected, refresh: refreshTelemetry, status: telemetryStatus } = useTelemetry();
  const connectionStatus = isConnected ? 'online' : 'connecting';

  const [pullDistance, setPullDistance] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const touchStartY = useRef(0);
  const pullThreshold = 70;
  const { health, refresh: refreshHealthEngine, live: healthLive } = useHealthEngine(60000);
  const { snapshot: observabilityStatus, summary: observabilitySummary, isLoading: observabilityLoading, error: observabilityError, refresh: refreshObservabilityStatus } = useObservabilityStatus(60000);

  const refreshAll = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([refreshTelemetry(), refreshHealthEngine(), refreshObservabilityStatus()]);
    } finally {
      setIsRefreshing(false);
      setPullDistance(0);
    }
  };

  const handleTouchStart = (e) => {
    if (window.scrollY <= 0) {
      touchStartY.current = e.touches[0].clientY;
    } else {
      touchStartY.current = 0;
    }
  };

  const handleTouchMove = (e) => {
    if (touchStartY.current === 0 || isRefreshing) return;
    const diff = e.touches[0].clientY - touchStartY.current;
    if (diff > 0) {
      setPullDistance(Math.min(diff * 0.4, 120));
    }
  };

  const handleTouchEnd = () => {
    if (pullDistance > pullThreshold && !isRefreshing) {
      if (navigator.vibrate) navigator.vibrate(30);
      setIsRefreshing(true);
      refreshAll();
    } else {
      setPullDistance(0);
    }
    touchStartY.current = 0;
  };

  const tempVal = telemetry.cpu_temp_c > 0 ? telemetry.cpu_temp_c.toFixed(1) : '0.0';
  const isHot = telemetry.cpu_temp_c > 65.0;

  const getNodeDisplay = () => {
    if (connectionStatus === 'connecting') return { text: 'CONNECTING', color: 'text-amber-400', glow: 'shadow-[0_0_15px_rgba(251,191,36,0.2)]' };
    return { text: telemetryStatus?.isLive ? 'LIVE' : 'ONLINE', color: 'text-emerald-400', glow: 'shadow-[0_0_15px_rgba(52,211,153,0.2)]' };
  };

  const getNetworkDisplay = () => {
    if (telemetryStatus?.isLive || healthLive?.isLive) return { text: 'LIVE', icon: Wifi, color: 'text-emerald-400' };
    if (connectionStatus === 'connecting') return { text: 'CHECKING', icon: Wifi, color: 'text-amber-400' };
    return { text: 'SECURE', icon: Wifi, color: 'text-emerald-400' };
  };

  const node = getNodeDisplay();
  const net = getNetworkDisplay();
  const NetIcon = net.icon;

  // Determine heading for telemetry view.  In simple mode, replace
  // "Node Telemetry" with a more approachable "System Status" title.
  const telemetryHeading = simpleMode ? 'System Status' : 'Node Telemetry';

  return (
    <div
      className="max-w-7xl mx-auto p-4 relative"
      onTouchStart={handleTouchStart}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
    >

      {/* PULL TO REFRESH INDICATOR */}
      <div
        className="pull-refresh-tension flex justify-center items-center w-full absolute top-0 left-0 right-0 z-0 overflow-hidden"
        style={{
          height: `${pullDistance}px`,
          opacity: pullDistance / pullThreshold,
          transition: isRefreshing || pullDistance === 0 ? 'height 0.3s ease, opacity 0.3s ease' : 'none'
        }}
      >
        <div className="flex flex-col items-center justify-center mt-4 text-emerald-400">
          {isRefreshing ? (
            <Loader2 className="w-6 h-6 animate-spin" />
          ) : (
            <ArrowDown className={`w-6 h-6 transition-transform duration-300 ${pullDistance > pullThreshold ? 'rotate-180 text-emerald-300' : ''}`} />
          )}
          <span className="text-[10px] font-bold uppercase tracking-widest mt-2 text-emerald-400/80">
            {isRefreshing ? 'Reading live status...' : pullDistance > pullThreshold ? 'Release to check now' : 'Pull to refresh'}
          </span>
        </div>
      </div>

      {/* MAIN CONTENT WRAPPER */}
      <div
        className="relative z-10 animate-in fade-in duration-700 bg-[#020617]"
        style={{
          transform: `translateY(${pullDistance}px)`,
          transition: isRefreshing || pullDistance === 0 ? 'transform 0.3s cubic-bezier(0.2, 0.8, 0.2, 1)' : 'none'
        }}
      >
        {/* HEADER */}
        <div className="bg-slate-900/60 backdrop-blur-xl border border-white/10 rounded-[2.5rem] p-6 md:p-8 shadow-2xl mb-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 p-8 opacity-5 pointer-events-none transform translate-x-4 -translate-y-4">
            <Activity className="w-48 h-48 text-emerald-400" />
          </div>
          <div className="relative z-10 flex flex-col sm:flex-row items-center sm:justify-between gap-4 text-center sm:text-left">
            <div>
            <h2 className="text-3xl md:text-4xl font-black text-white tracking-tight mb-2">{telemetryHeading}</h2>
              <p className="text-slate-400 text-sm max-w-xl">{simpleMode ? 'See whether your Pocket Lab device has enough power, memory, and storage.' : <>Live hardware metrics streamed through Control API, Event Bus events, and Termux <code className="text-emerald-400">/proc</code> sensors.</>}</p>
            </div>
            <div className="flex flex-col items-center justify-center bg-black/40 px-6 py-4 rounded-3xl border border-white/5">
              <span className={`text-4xl font-black ${isHot ? 'text-red-400' : 'text-emerald-400'}`}>
                <CountUpNumber value={Number(tempVal)} decimals={1} suffix="°C" />
              </span>
              <div className="flex items-center mt-1 space-x-1 opacity-70">
                <Thermometer className="w-3 h-3 text-white" />
                <span className="text-[10px] font-bold uppercase tracking-widest text-white">{simpleMode ? 'Device Temp' : 'SoC Temp'}</span>
              </div>
            </div>
          </div>
        </div>

        {/* METRICS GRID - EXPANDED TO 3 COLUMNS FOR CPU USAGE */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

          {/* CPU Usage */}
          <div className="bg-[#05080f] border border-white/10 rounded-3xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-emerald-500/10 rounded-lg border border-emerald-500/20"><Cpu className="w-5 h-5 text-emerald-400" /></div>
                  <h3 className="font-bold text-white">{simpleMode ? 'Processor Use' : 'Compute Utilization'}</h3>
                </div>
                <span className="text-2xl font-black text-emerald-400"><CountUpNumber value={telemetry.cpu_usage_percent} suffix="%" /></span>
              </div>
              <div className="w-full h-3 bg-slate-900 rounded-full overflow-hidden border border-white/5">
                <div
                  className={`h-full transition-all duration-1000 ease-out relative bg-emerald-500`}
                  style={{ width: `${telemetry.cpu_usage_percent}%` }}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent to-white/30" />
                </div>
              </div>
            </div>
            <div className="flex justify-between mt-2 text-[10px] font-mono text-slate-500">
              <span>0%</span>
              <span>{simpleMode ? 'Normal Range' : 'Kernel Space'}</span>
              <span>100%</span>
            </div>
          </div>

          {/* {simpleMode ? 'Memory Use' : 'Memory Allocation'} */}
          <div className="bg-[#05080f] border border-white/10 rounded-3xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-blue-500/10 rounded-lg border border-blue-500/20"><MemoryStick className="w-5 h-5 text-blue-400" /></div>
                  <h3 className="font-bold text-white">{simpleMode ? 'Memory Use' : 'Memory Allocation'}</h3>
                </div>
                <span className="text-2xl font-black text-blue-400"><CountUpNumber value={telemetry.memory_usage_mb} /> <span className="text-sm">MB</span></span>
              </div>
              <div className="w-full h-3 bg-slate-900 rounded-full overflow-hidden border border-white/5">
                <div
                  className={`h-full transition-all duration-1000 ease-out relative bg-blue-500`}
                  style={{ width: `${Math.max(5, Math.min(100, (telemetry.memory_usage_mb / 8192) * 100))}%` }}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent to-white/30" />
                </div>
              </div>
            </div>
            <div className="flex justify-between mt-2 text-[10px] font-mono text-slate-500">
              <span>0 MB</span>
              <span>{simpleMode ? 'Used by Apps' : 'Native & PRoot Subsystems'}</span>
              <span>8192 MB+</span>
            </div>
          </div>

          {/* Storage Free Space */}
          <div className="bg-[#05080f] border border-white/10 rounded-3xl p-6 shadow-xl flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center space-x-3">
                  <div className="p-2 bg-purple-500/10 rounded-lg border border-purple-500/20"><HardDrive className="w-5 h-5 text-purple-400" /></div>
                  <h3 className="font-bold text-white">{simpleMode ? 'Free Storage' : 'Edge Storage'}</h3>
                </div>
                <span className="text-2xl font-black text-purple-400"><CountUpNumber value={telemetry.free_space_mb} /> <span className="text-sm">MB</span></span>
              </div>
              <div className="w-full h-3 bg-slate-900 rounded-full overflow-hidden border border-white/5">
                <div
                  className={`h-full transition-all duration-1000 ease-out relative bg-purple-500`}
                  style={{ width: `${Math.max(10, Math.min(100, (telemetry.free_space_mb / 256000) * 100))}%` }}
                >
                   <div className="absolute inset-0 bg-gradient-to-r from-transparent to-white/30" />
                </div>
              </div>
            </div>
             <div className="flex justify-between mt-2 text-[10px] font-mono text-slate-500">
              <span>Critical</span>
              <span>{simpleMode ? 'Available Space' : 'Available /var/storage'}</span>
              <span>Healthy</span>
            </div>
          </div>

        </div>

        <HealthEnginePanel health={health} onRefresh={refreshAll} simpleMode={simpleMode} liveStatus={healthLive} />

        <RuntimeObservabilityStatusPanel
          snapshot={observabilityStatus}
          summary={observabilitySummary}
          isLoading={observabilityLoading}
          error={observabilityError}
          onRefresh={refreshObservabilityStatus}
          simpleMode={simpleMode}
        />

        {/* INTELLIGENT NETWORK & SYSTEM STATUS */}
        <div className="grid grid-cols-2 gap-4 mt-4">
          <div className={`bg-slate-900/50 border border-white/5 rounded-3xl p-5 flex flex-col items-center justify-center text-center transition-colors duration-500 ${node.glow}`}>
            <Server className={`w-6 h-6 mb-2 ${node.color}`} />
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{simpleMode ? 'Device Status' : 'Node Status'}</span>
            <span className={`font-black mt-1 ${node.color}`}>{node.text}</span>
          </div>

          <div className="bg-slate-900/50 border border-white/5 rounded-3xl p-5 flex flex-col items-center justify-center text-center">
            <NetIcon className={`w-6 h-6 mb-2 ${net.color}`} />
            <span className="text-[10px] font-bold uppercase tracking-widest text-slate-400">{simpleMode ? 'Live Updates' : 'Event Bus Event Stream'}</span>
            <span className={`font-black mt-1 ${net.color}`}>{net.text}</span>
          </div>
        </div>

      </div>
      <LiveEventPanel
        simpleMode={simpleMode}
        title="System status live stream"
        description={simpleMode ? 'System health, device status, and service changes appear automatically.' : 'Health, telemetry, fleet, and sampler events stream from control plane as they are reported.'}
        subjectPrefixes={['pocketlab.events.telemetry.', 'pocketlab.events.health.', 'pocketlab.events.fleet.', 'pocketlab.events.live_status.']}
        maxItems={4}
        compact
      />

    </div>
  );
}
