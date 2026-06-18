import React, { useEffect, useRef, useState } from 'react';
import { Activity, CheckCircle2, RefreshCw, ShieldAlert, X } from 'lucide-react';
import { useExperienceMode } from '../context/ExperienceModeContext.jsx';
import { usePocketLabEvents } from '../hooks/usePocketLabEvents.js';
import { useOnlineStatus } from '../hooks/useOnlineStatus.js';
import { eventTone, formatEventTime, friendlyEvent } from '../lib/pocketLabEvents.js';
import { enterpriseDisplayText, enterpriseSubjectLabel } from '../lib/enterpriseLabels.js';
import { animatedEventClass, animatedEventStatus, eventIdentity } from '../lib/eventMotion.js';
import { ProgressiveDisclosure, StandardList, StandardListItem, StateSurface, StatusBadge } from './ui.jsx';

function toneIcon(tone) {
  if (tone === 'success') return CheckCircle2;
  if (tone === 'warning' || tone === 'danger') return ShieldAlert;
  return Activity;
}

export default function ActivityDrawer() {
  const { experienceMode } = useExperienceMode();
  const simpleMode = experienceMode === 'simple';
  const online = useOnlineStatus();
  const [open, setOpen] = useState(false);
  const { events, connection, isLive, refreshEvents } = usePocketLabEvents({
    subjectPrefixes: ['pocketlab.events.', 'pocketlab.audit.'],
    limit: 20,
    pollFallbackMs: 7000,
  });

  const [pulseKeys, setPulseKeys] = useState(() => new Set());
  const previousKeysRef = useRef(new Set());
  const visible = events.slice(0, 8);

  useEffect(() => {
    const keys = new Set(visible.map(eventIdentity));
    const newKeys = [...keys].filter((key) => !previousKeysRef.current.has(key));
    if (newKeys.length > 0 && previousKeysRef.current.size > 0) {
      setPulseKeys((current) => new Set([...current, ...newKeys]));
      const timeout = window.setTimeout(() => {
        setPulseKeys((current) => {
          const next = new Set(current);
          newKeys.forEach((key) => next.delete(key));
          return next;
        });
      }, 320);
      previousKeysRef.current = keys;
      return () => window.clearTimeout(timeout);
    }
    previousKeysRef.current = keys;
    return undefined;
  }, [visible]);
  const status = !online ? 'offline' : isLive ? 'healthy' : 'degraded';
  const label = !online ? (simpleMode ? 'Offline' : 'Offline cache') : isLive ? (simpleMode ? 'Live' : 'Live events') : (simpleMode ? 'Checking' : connection.mode === 'polling' ? 'Polling' : connection.state);

  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="activity-drawer-button" aria-label="Open recent Pocket Lab activity">
        <Activity className="h-5 w-5" />
        <span className="hidden sm:inline">{simpleMode ? 'Activity' : 'Activity'}</span>
        <StatusBadge status={status === 'offline' ? 'degraded' : status} className="scale-90">{label}</StatusBadge>
      </button>

      {open && <div className="activity-drawer-backdrop" onClick={() => setOpen(false)} aria-hidden="true" />}

      <aside className={`activity-drawer ${open ? 'activity-drawer-open' : ''}`} aria-hidden={!open} aria-label="Recent Pocket Lab activity">
        <div className="flex items-start justify-between gap-3 border-b border-white/10 p-5">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.2em] text-cyan-200/80">{simpleMode ? 'Recent activity' : 'Activity stream'}</p>
            <h2 className="mt-1 text-xl font-black text-white">{simpleMode ? 'What Pocket Lab is doing' : 'Pocket Lab activity'}</h2>
            <p className="mt-1 text-sm leading-6 text-slate-400">{simpleMode ? 'Installs, updates, backups, device invites, and safety checks appear here.' : 'Control-plane activity, approvals, execution progress, and audit records are summarized here.'}</p>
          </div>
          <button type="button" onClick={() => setOpen(false)} className="rounded-2xl border border-white/10 bg-white/5 p-2 text-slate-200 hover:bg-white/10" aria-label="Close activity drawer"><X className="h-5 w-5" /></button>
        </div>

        <div className="space-y-4 overflow-y-auto p-5">
          {!online && (
            <StateSurface
              tone="offline"
              title={simpleMode ? 'You are offline' : 'Browser is offline'}
              description={simpleMode ? 'Pocket Lab will show cached information where possible. Actions that change your environment are paused until the connection returns.' : 'Live event streaming and write flows are paused. The UI can still show cached state where available.'}
            />
          )}

          {online && !isLive && (
            <StateSurface
              tone="degraded"
              title={simpleMode ? 'Live updates are reconnecting' : 'Activity stream degraded'}
              description={simpleMode ? 'Pocket Lab is checking periodically until live updates return.' : `Connection mode: ${connection.mode}. ${connection.error || 'Recent event polling is active.'}`}
            />
          )}

          <div className="flex items-center justify-between gap-3">
            <StatusBadge status={status === 'offline' ? 'degraded' : status}>{label}</StatusBadge>
            <button type="button" onClick={refreshEvents} className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-white/10"><RefreshCw className="h-4 w-4" /> Refresh</button>
          </div>

          {visible.length === 0 ? (
            <StateSurface
              tone="empty"
              title={simpleMode ? 'No recent activity yet' : 'No matching activity yet'}
              description={simpleMode ? 'Start an install, update, backup, or safety check and progress will appear here.' : 'Waiting for live or recent control-plane activity.'}
            />
          ) : (
            <StandardList title={simpleMode ? 'Recent activity' : 'Recent activity records'} description={simpleMode ? 'Newest Pocket Lab updates are listed first.' : 'A normalized activity list using the shared Pocket Lab list pattern.'}>
              {visible.map((event) => {
                const tone = eventTone(event);
                const Icon = toneIcon(tone);
                const friendly = friendlyEvent(event, simpleMode);
                const eventId = eventIdentity(event);
                const fallbackStatus = tone === 'success' ? 'succeeded' : tone === 'warning' ? 'degraded' : tone === 'danger' ? 'failed' : 'running';
                return (
                  <StandardListItem
                    key={eventId}
                    icon={Icon}
                    title={friendly.title}
                    description={friendly.detail}
                    status={animatedEventStatus(event, fallbackStatus)}
                    simpleMode={simpleMode}
                    className={animatedEventClass(event, pulseKeys.has(eventId))}
                    metadata={[{ label: 'Time', value: formatEventTime(event) }]}
                  >
                    {!simpleMode && (
                      <ProgressiveDisclosure title="Advanced activity evidence">
                        <div className="space-y-2">
                          <div>Activity channel: <span className="break-all font-mono">{enterpriseSubjectLabel(event.subject || event.type)}</span></div>
                          <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-2xl bg-black/25 p-3 font-mono text-[11px]">{enterpriseDisplayText(JSON.stringify(event, null, 2))}</pre>
                        </div>
                      </ProgressiveDisclosure>
                    )}
                  </StandardListItem>
                );
              })}
            </StandardList>
          )}
        </div>
      </aside>
    </>
  );
}
