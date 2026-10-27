import React, { useMemo, useState } from 'react';
import { CheckCircle2, HardDrive, MapPin, RefreshCw, ShieldCheck } from 'lucide-react';
import { formatLiteTime } from '../../lib/liteApi.js';
import { LiteButton, StatusBadge } from '../LiteUi.jsx';

function statusLabel(location = {}) {
  if (location.status === 'ready') return 'Ready';
  if (location.status === 'available') return 'Available';
  if (location.status === 'low_space') return 'Low space';
  if (location.status === 'read_only') return 'Read-only';
  if (['missing', 'unavailable', 'permission_required', 'repository_invalid', 'repository_missing'].includes(location.status)) return 'Unavailable';
  return location.status === 'checking' ? 'Checking' : 'Unknown';
}

function statusTone(location = {}) {
  if (location.status === 'ready') return 'healthy';
  if (location.status === 'available') return 'neutral';
  if (location.status === 'checking') return 'checking';
  return 'review';
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!bytes) return '';
  if (bytes >= 1024 ** 3) return `${(bytes / (1024 ** 3)).toFixed(bytes >= 10 * 1024 ** 3 ? 0 : 1)} GB free`;
  return `${Math.max(1, Math.round(bytes / (1024 ** 2)))} MB free`;
}

export default function RecoveryBackupLocation({
  locations = {},
  disabled = false,
  busy = '',
  onDiscover,
  onSelect,
  onForget,
}) {
  const [expanded, setExpanded] = useState(false);
  const registered = Array.isArray(locations?.locations) ? locations.locations : [];
  const candidates = Array.isArray(locations?.candidates) ? locations.candidates : [];
  const selected = locations?.selected_location || registered.find((item) => item.is_selected) || null;
  const choices = useMemo(() => registered.filter((item) => item.location_id), [registered]);
  const canChange = !disabled && !busy;
  const selectedReady = Boolean(selected && selected.status === 'ready'
    && selected.ready !== false && selected.available !== false);

  return (
    <section className="lite-recovery-manage-subsection" aria-labelledby="recovery-backup-location-heading" data-recovery-backup-location="true">
      <div className="lite-recovery-location-head">
        <div>
          <strong id="recovery-backup-location-heading">Backup location</strong>
          <p>Select a backend-approved protected destination for encrypted backups.</p>
        </div>
        <StatusBadge status={statusTone(selected)}>{statusLabel(selected || {})}</StatusBadge>
      </div>

      <div className="lite-recovery-location-current">
        <div className="lite-recovery-location-icon" aria-hidden="true"><ShieldCheck className="h-5 w-5" /></div>
        <div>
          <strong>{selected?.display_name || 'Pocket Lab private backup folder'}</strong>
          <span>{selectedReady && selected?.repository_present ? 'Encrypted repository ready for backup' : selected?.repository_present ? 'Repository found · check readiness before writing' : 'Repository not yet confirmed ready'}</span>
          <small>{formatBytes(selected?.free_bytes) || (selected?.last_checked_at ? `Checked ${formatLiteTime(selected.last_checked_at)}` : 'Storage health is being checked.')}</small>
        </div>
        <LiteButton tone="secondary" onClick={() => setExpanded((value) => !value)} disabled={!canChange} ariaLabel="Change backup location">
          {expanded ? 'Done' : 'Change'}
        </LiteButton>
      </div>

      {expanded ? (
        <div className="lite-recovery-location-picker" role="group" aria-label="Available backup locations">
          <p className="lite-recovery-location-picker-note">Choose a protected writable folder. Raw browser paths and Android media folders are not accepted.</p>
          <div className="lite-recovery-location-choice-list">
            {choices.map((location) => {
              const selectedChoice = location.location_id === selected?.location_id;
              const unavailable = location.available === false;
              return (
                <div key={location.location_id} className={`lite-recovery-location-choice${selectedChoice ? ' is-selected' : ''}`}>
                  <button
                    type="button"
                    onClick={() => onSelect?.(location.location_id)}
                    disabled={!canChange || unavailable || selectedChoice}
                    aria-pressed={selectedChoice}
                  >
                    {selectedChoice ? <CheckCircle2 className="h-4 w-4" aria-hidden="true" /> : <HardDrive className="h-4 w-4" aria-hidden="true" />}
                    <span><strong>{location.display_name}</strong><small>{location.repository_present ? 'Encrypted repository ready' : location.reason_code === 'will_create' ? 'Will be created when selected' : 'Protected Pocket Lab location'}</small></span>
                  </button>
                  <StatusBadge status={statusTone(location)}>{statusLabel(location)}</StatusBadge>
                  {!location.is_default && onForget ? <LiteButton tone="secondary" onClick={() => onForget(location.location_id)} disabled={!canChange || selectedChoice}>Forget</LiteButton> : null}
                </div>
              );
            })}
          </div>

          {candidates.length ? (
            <div className="lite-recovery-location-candidates">
              <strong>Available storage candidates</strong>
              {candidates.map((candidate) => (
                <div key={candidate.candidate_id} className="lite-recovery-location-choice">
                  <span><MapPin className="h-4 w-4" aria-hidden="true" /><strong>{candidate.display_name}</strong><small>{candidate.available === false ? 'Unavailable right now' : 'Discover and add this location'}</small></span>
                  <LiteButton tone="secondary" onClick={() => onDiscover?.(candidate.candidate_id)} disabled={!canChange || candidate.available === false || busy === `location-discover:${candidate.candidate_id}`}>
                    {busy === `location-discover:${candidate.candidate_id}` ? <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" /> : 'Add'}
                  </LiteButton>
                </div>
              ))}
            </div>
          ) : null}

          <p className="lite-recovery-location-picker-footnote">The Android system folder picker is not available in this PWA. Locations are backend-approved. Forgetting a location removes its registration; it does not claim to delete physical backup files.</p>
        </div>
      ) : null}
    </section>
  );
}
