import React, { useState, useEffect, useRef } from 'react';
import { Search, Filter, Play, Pause, AlertTriangle, AlertCircle, Info, Activity, Clock, AlignLeft, Download, ChevronDown } from 'lucide-react';
import { queryLogs } from '../lib/operations.js';

export default function LogExplorerTab() {
  const [logs, setLogs] = useState([]);
  const [isLive, setIsLive] = useState(true);
  const [searchQuery, setSearchQuery] = useState('{job="varlogs"}');

  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [showSeverityDropdown, setShowSeverityDropdown] = useState(false);
  const [timeRange, setTimeRange] = useState('15m');
  const [queryMeta, setQueryMeta] = useState(null);

  const logsEndRef = useRef(null);
  const previousLogIdsRef = useRef(new Set());
  const [newLogIds, setNewLogIds] = useState(new Set());

  // HTML-PROOF ENVIRONMENT DETECTION
  const [isLiveEnv, setIsLiveEnv] = useState(false);
  useEffect(() => {
    fetch('/ready')
      .then(res => res.text())
      .then(text => {
        try { const payload = JSON.parse(text); setIsLiveEnv(payload.status === 'ready' || payload.ready === true); }
        catch { setIsLiveEnv(false); }
      })
      .catch(() => setIsLiveEnv(false));
  }, []);

  useEffect(() => {
    let interval;

    if (!isLiveEnv && isLive) {
      setLogs([{ id: 'control-plane-degraded', timestamp: new Date().toISOString(), level: 'WARN', service: 'control-plane', message: 'control plane is not ready. Log streaming is paused; simulator logs are disabled in production mode.' }]);
      setQueryMeta(null);

    } else if (isLiveEnv && isLive) {
      // --- PRODUCTION MODE (Control API-owned log query API) ---
      const fetchLokiLogs = async () => {
        try {
          let query = searchQuery;
          if (severityFilter !== 'ALL') {
            query = `${searchQuery} |~ "(?i)${severityFilter}"`;
          }

          const data = await queryLogs({ query, limit: 100 });

          const parsedLogs = [];
          if (data.data && data.data.result) {
            data.data.result.forEach(stream => {
              stream.values.forEach(val => {
                parsedLogs.push({
                  id: val[0],
                  timestamp: new Date(parseInt(val[0]) / 1000000).toISOString(),
                  level: val[1].toUpperCase().includes('ERROR') ? 'ERROR' : val[1].toUpperCase().includes('WARN') ? 'WARN' : 'INFO',
                  service: stream.stream.job || 'syslog',
                  message: val[1],
                });
              });
            });
          }
          parsedLogs.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
          setLogs(parsedLogs);
          setQueryMeta(data.meta || null);
        } catch (err) {
          setLogs([{ id: 'err', timestamp: new Date().toISOString(), level: 'ERROR', service: 'system', message: 'Connecting to Pocket Lab Control API log query API. Live log data may be unavailable until the control plane and log pipeline are ready.' }]);
          setQueryMeta(null);
        }
      };

      fetchLokiLogs();
      interval = setInterval(fetchLokiLogs, 3000);
    }

    return () => clearInterval(interval);
  }, [isLive, isLiveEnv, searchQuery, severityFilter]);


  useEffect(() => {
    const currentIds = new Set(logs.slice(-3).map((log) => String(log.id)));
    const fresh = [...currentIds].filter((id) => !previousLogIdsRef.current.has(id));
    previousLogIdsRef.current = new Set(logs.map((log) => String(log.id)));
    if (fresh.length > 0) {
      setNewLogIds(new Set(fresh.slice(-3)));
      const timeout = window.setTimeout(() => setNewLogIds(new Set()), 520);
      return () => window.clearTimeout(timeout);
    }
    return undefined;
  }, [logs]);

  useEffect(() => {
    if (isLive && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, isLive]);

  const displayedLogs = logs.filter((log) => {
    if (!isLiveEnv && severityFilter !== 'ALL' && log.level !== severityFilter) return false;
    if (!isLiveEnv && searchQuery !== '{job="varlogs"}') {
      const needle = searchQuery.replace(/[^a-zA-Z0-9_-]/g, '').toLowerCase();
      if (needle && !log.message.toLowerCase().includes(needle) && !log.service.toLowerCase().includes(needle)) return false;
    }
    return true;
  });

  const handleExport = () => {
    const logText = displayedLogs.map(l => `[${l.timestamp}] [${l.level}] [${l.service}] ${l.message}`).join('\n');
    const blob = new Blob([logText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `pocket_lab_logs_${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const getLevelColor = (level) => {
    switch (level) {
      case 'ERROR': return 'text-red-400 bg-red-500/10 border-red-500/30';
      case 'WARN': return 'text-orange-400 bg-orange-500/10 border-orange-500/30';
      default: return 'text-blue-400 bg-blue-500/10 border-blue-500/30';
    }
  };

  const getLevelIcon = (level) => {
    switch (level) {
      case 'ERROR': return <AlertCircle className="w-3 h-3 mr-1 inline" />;
      case 'WARN': return <AlertTriangle className="w-3 h-3 mr-1 inline" />;
      default: return <Info className="w-3 h-3 mr-1 inline" />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto p-4 animate-in fade-in duration-700 flex flex-col h-[85vh] gap-4">

      {/* HEADER & SEARCH MODULE */}
      <div className="bg-slate-900/80 backdrop-blur-xl border border-white/10 rounded-3xl p-5 shadow-2xl shrink-0 z-20">
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 mb-4">
          <div className="flex items-center space-x-3 w-full md:w-auto">
            <div className={`p-2.5 rounded-xl border ${!isLiveEnv ? 'bg-orange-500/20 border-orange-500/30' : 'bg-indigo-500/20 border-indigo-500/30'}`}>
              <AlignLeft className={`w-6 h-6 ${!isLiveEnv ? 'text-orange-400' : 'text-indigo-400'}`} />
            </div>
            <div>
              <h2 className="text-xl font-black text-white tracking-tight flex items-center">
                Activity & Evidence <span className={`ml-2 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-widest ${!isLiveEnv ? 'border-orange-400/30 bg-orange-500/15 text-orange-200' : 'border-indigo-400/30 bg-indigo-500/15 text-indigo-200'}`}>{!isLiveEnv ? 'Degraded' : 'Control API'}</span>
              </h2>
              <p className="text-slate-400 text-xs flex items-center mt-0.5">
                <span className={`w-2 h-2 rounded-full mr-1.5 ${!isLiveEnv ? 'bg-orange-500 animate-pulse' : 'bg-green-500 animate-pulse'}`}></span>
                {!isLiveEnv ? 'Control Plane Degraded' : 'Control API Log Query Stream'}
              </p>
            </div>
          </div>

          <div className="flex-1 w-full flex items-center relative">
            <div className="absolute left-4 text-slate-500 font-mono text-sm">Query</div>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className={`pocket-input w-full pl-16 pr-4 font-mono ${!isLiveEnv ? 'text-orange-300 focus:border-orange-400/60' : 'text-emerald-300 focus:border-indigo-300/60'}`}
              placeholder='{job="varlogs"}'
            />
            <button className={`absolute right-2 rounded-xl p-2 text-white transition-colors ${!isLiveEnv ? 'bg-orange-600 hover:bg-orange-500' : 'bg-indigo-600 hover:bg-indigo-500'}`}>
               <Search className="w-4 h-4" />
            </button>
          </div>
        </div>

        {queryMeta && (
          <div className="rounded-xl border border-white/10 bg-black/20 px-4 py-2 text-[11px] text-slate-400">
            {queryMeta.matched_count ?? 0} matches · {queryMeta.query_time_ms ?? 0} ms
          </div>
        )}

        <div className="flex flex-wrap items-end justify-between gap-2">
          <div className="flex space-x-2">
            <button
              onClick={() => setIsLive(!isLive)}
              className={`flex items-center px-4 py-2 rounded-lg text-xs font-bold transition-all border ${isLive ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-slate-800 text-slate-400 border-slate-700 hover:text-white'}`}
            >
              {isLive ? <Pause className="w-3 h-3 mr-2" /> : <Play className="w-3 h-3 mr-2" />}
              {isLive ? 'Pause Stream' : 'Resume Live'}
            </button>

            <button
              onClick={() => setTimeRange(prev => prev === '15m' ? '1h' : prev === '1h' ? '24h' : '15m')}
              className="flex items-center px-4 py-2 rounded-lg text-xs font-bold bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 transition-all"
            >
               <Clock className="w-3 h-3 mr-2" /> Last {timeRange}
            </button>

            <div className="relative">
              <button
                onClick={() => setShowSeverityDropdown(!showSeverityDropdown)}
                className={`flex items-center px-4 py-2 rounded-lg text-xs font-bold transition-all border ${severityFilter !== 'ALL' ? 'bg-indigo-500/20 border-indigo-500/50 text-indigo-300' : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'}`}
              >
                 <Filter className="w-3 h-3 mr-2" />
                 {severityFilter === 'ALL' ? 'Filter Severity' : `Severity: ${severityFilter}`}
                 <ChevronDown className="w-3 h-3 ml-2" />
              </button>

              {showSeverityDropdown && (
                <div className="absolute top-full left-0 mt-2 w-48 bg-[#05080f] border border-slate-700 rounded-xl shadow-2xl overflow-hidden z-50">
                  {['ALL', 'INFO', 'WARN', 'ERROR'].map(level => (
                    <button
                      key={level}
                      onClick={() => { setSeverityFilter(level); setShowSeverityDropdown(false); }}
                      className={`w-full text-left px-4 py-3 text-xs font-bold hover:bg-white/10 transition-colors ${severityFilter === level ? 'bg-indigo-600/20 text-indigo-400' : 'text-slate-300'}`}
                    >
                      {level === 'ALL' ? 'Show All Logs' : `${level} Only`}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* LOG STREAM DISPLAY */}
      <div className="bg-[#020617] border border-white/10 rounded-3xl overflow-hidden shadow-[inset_0_0_50px_rgba(0,0,0,0.8)] flex flex-col flex-1 relative z-10">
         <div className="bg-black/80 px-4 py-3 border-b border-white/5 flex items-center justify-between z-10">
            <div className="flex items-center space-x-4">
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest w-32 hidden md:block">Timestamp</span>
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest w-24">Level</span>
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest w-36 hidden md:block">Service</span>
              <span className="text-xs font-bold text-slate-400 uppercase tracking-widest">Message</span>
            </div>

            <button
              onClick={handleExport}
              className="flex items-center space-x-2 text-slate-400 hover:text-white bg-white/5 hover:bg-white/10 px-3 py-1.5 rounded-lg transition-colors text-xs font-bold"
            >
              <Download className="w-4 h-4" /> <span className="hidden md:inline">Export</span>
            </button>
         </div>

         <div className="flex-1 overflow-y-auto p-2 scrollbar-thin scrollbar-thumb-slate-700 font-mono text-[11px] lg:text-xs">
           {displayedLogs.length === 0 ? (
             <div className="h-full flex flex-col items-center justify-center opacity-30 text-slate-400">
               <Activity className="w-10 h-10 mb-2 animate-pulse" />
               <p>No logs match the current filter criteria.</p>
             </div>
           ) : (
             displayedLogs.map((log, index) => {
               const isNewLog = newLogIds.has(String(log.id));
               return (
               <div key={`${log.id}-${index}`} className={`flex flex-col md:flex-row items-start md:items-center p-2 hover:bg-white/5 rounded-lg group transition-colors cursor-pointer border-b border-white/5 md:border-transparent ${isNewLog ? 'log-stream-row-new' : ''}`}>
                 <span className={`text-slate-500 w-32 shrink-0 mb-1 md:mb-0 hidden md:block ${isNewLog ? 'log-timestamp-highlight' : ''}`}>
                   {log.timestamp.includes('T') ? log.timestamp.split('T')[1].replace('Z', '') : log.timestamp}
                 </span>

                 <div className="w-24 shrink-0 mb-1 md:mb-0">
                   <span className={`px-2 py-0.5 rounded border ${getLevelColor(log.level)} font-bold flex items-center w-fit ${isNewLog ? 'log-severity-pop' : ''}`}>
                     {getLevelIcon(log.level)} {log.level}
                   </span>
                 </div>

                 <span className={`w-36 shrink-0 truncate pr-2 mb-1 md:mb-0 hidden md:block ${!isLiveEnv ? 'text-orange-300' : 'text-indigo-300'}`}>
                   [{log.service}]
                 </span>

                 <span className={`flex-1 break-all ${log.level === 'ERROR' ? 'text-red-200' : 'text-slate-300'}`}>
                   <span className="md:hidden text-slate-500 mr-2">{log.timestamp.includes('T') ? log.timestamp.split('T')[1].substring(0,8) : ''}</span>
                   <span className="md:hidden text-indigo-300 mr-2">[{log.service}]</span>
                   {log.message}
                 </span>
               </div>
               );
             })
           )}
           <div ref={logsEndRef} />
         </div>
      </div>

    </div>
  );
}
