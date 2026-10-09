import React from 'react';
import { Camera, RefreshCw, Square } from 'lucide-react';
import { useLiteQuery } from '../../hooks/useLiteQuery.js';
import { liteApi } from '../../lib/liteApi.js';
import { LiteButton } from '../LiteUi.jsx';

const COLLECTIONS = [
  { id: 'camera', label: 'Camera' },
  { id: 'pictures', label: 'Pictures' },
  { id: 'videos', label: 'Videos' },
];

function isLive(status) {
  return ['queued', 'planning', 'waiting_for_credentials', 'starting', 'transferring', 'cancelling']
    .includes(String(status || '').toLowerCase());
}

const GUIDANCE = {
  source_offline: 'Reconnect this device and wait for a fresh heartbeat.',
  source_capabilities_stale: 'Wait for the device to report fresh photo backup capabilities.',
  rclone_unavailable: 'Use Repair photo backup to install or verify tools on this device.',
  rclone_repair_in_progress: 'The device is repairing photo backup tools. Check the latest update.',
  photo_storage_access_missing: 'Allow photo and video access in Android settings, then refresh.',
  photoprism_not_running: 'Open Apps and check PhotoPrism on the Server Phone.',
  photoprism_unreachable: 'Check PhotoPrism health and its local connection on the Server Phone.',
  secure_route_unavailable: 'Check remote access in Devices before retrying.',
  webdav_probe_failed: 'Check the PhotoPrism HTTPS route and retry when it is reachable.',
  webdav_auth_failed: 'A protected upload credential was rejected. Retry after checking PhotoPrism.',
  destination_identity_mismatch: 'Destination storage changed. Verify the original drive on the Server Phone; do not force a backup.',
  destination_storage_unavailable: 'Check the Server Phone storage mount and permissions.',
  destination_read_only: 'The backup destination is not writable. Check Server Phone storage.',
  storage_below_planning_reserve: 'Free up destination space without deleting existing backups.',
  storage_below_hard_reserve: 'Server Phone storage is critically low. Free up space before trying again.',
  storage_reservation_conflict: 'Another device is using the photo backup destination. Retry when it finishes.',
  credential_expired: 'The previous one-time credential expired. Start a new backup when ready.',
  credential_revocation_pending: 'Credential revocation is pending. Check the connection before retrying.',
};

function safeDate(value) {
  const date = typeof value === 'string' ? new Date(value) : null;
  return date && Number.isFinite(date.getTime()) ? date.toLocaleString() : 'Not available';
}

function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!Number.isFinite(bytes) || bytes <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let amount = bytes;
  let index = 0;
  while (amount >= 1024 && index < units.length - 1) {
    amount /= 1024;
    index += 1;
  }
  return `${amount >= 10 || index === 0 ? amount.toFixed(0) : amount.toFixed(1)} ${units[index]}`;
}

export default function DevicePhotoBackup({ deviceId }) {
  const [selected, setSelected] = React.useState(['camera', 'pictures', 'videos']);
  const [actionState, setActionState] = React.useState({ busy: false, error: '', message: '' });
  const query = useLiteQuery({
    queryKey: ['lite', 'photo-backup', deviceId],
    path: `/api/lite/devices/${encodeURIComponent(deviceId || '')}/photo-backup`,
    queryFn: () => liteApi.photoBackup(deviceId),
    enabled: Boolean(deviceId),
    staleTime: 15_000,
    refetchInterval: (queryState) => {
      const status = queryState?.state?.data?.latest_backup?.status;
      return isLive(status) || ['installing', 'verifying'].includes(queryState?.state?.data?.tool_repair?.status) ? 5_000 : 30_000;
    },
    refetchOnWindowFocus: false,
  });

  const data = query.data || {};
  const latest = data.latest_backup || {};
  const toolRepair = data.tool_repair || {};
  const repairing = ['installing', 'verifying'].includes(toolRepair.status);
  const live = isLive(latest.status);
  const progress = latest.progress || {};
  const blockers = Array.isArray(data.blockers) ? data.blockers : [];
  const canStart = Boolean(data.backup_admissible ?? data.ready) && Boolean(selected.length && !live && !repairing && !actionState.busy && !query.error);
  const canRepair = blockers.includes('rclone_unavailable') && !repairing && !live && !actionState.busy && !query.error;
  const diagnostics = Array.isArray(data.diagnostics) ? data.diagnostics.filter((entry) => entry && typeof entry.reason_code === 'string') : [];
  const hasStatus = Boolean(query.data && !query.error);
  const storage = data.storage && typeof data.storage === 'object' ? data.storage : null;

  async function run(action) {
    setActionState({ busy: true, error: '', message: '' });
    try {
      if (action === 'start') {
        await liteApi.startPhotoBackup(deviceId, { collections: selected });
      } else if (action === 'cancel') {
        await liteApi.cancelPhotoBackup(deviceId, {});
      } else if (action === 'repair') {
        await liteApi.repairPhotoBackup(deviceId);
      }
      await query.refresh();
      setActionState({ busy: false, error: '', message: action === 'start' ? 'Backup request sent. Waiting for device acknowledgement.' : action === 'cancel' ? 'Stop requested. Waiting for the device to confirm.' : 'Repair request sent. The device will report its outcome.' });
    } catch (error) {
      setActionState({ busy: false, error: error?.message || 'Pocket Lab could not update photo backup.' });
      return;
    }
  }

  return (
    <section className="lite-device-photo-backup" aria-label="Photo backup">
      <div className="lite-device-photo-backup-head">
        <span className="lite-device-photo-backup-icon"><Camera className="h-4 w-4" /></span>
        <div>
          <span>Photo backup</span>
          <strong>{live ? 'Backing up photos' : repairing ? 'Repairing tools' : !hasStatus ? 'Status unavailable' : data.ready ? 'Ready' : blockers.some((code) => code.startsWith('storage_')) ? 'Waiting for space' : 'Needs attention'}</strong>
          <p>{data.summary || 'Pocket Lab is checking photo backup readiness.'}</p>
        </div>
      </div>

      <div className="lite-device-photo-backup-note" role="group" aria-label="Current backup readiness">
        <strong>Current readiness</strong>
        <p>{hasStatus ? (data.backup_admissible ? 'Ready to start a new backup.' : 'New backup is blocked until the conditions below are resolved.') : 'Current readiness could not be confirmed.'}</p>
        <small>Checked: {safeDate(data.checked_at)}</small>
        {diagnostics.length ? (
          <ul aria-label="Backup readiness checks">
            {diagnostics.map((entry, index) => (
              <li key={`${entry.reason_code}-${index}`}>
                {GUIDANCE[entry.reason_code] || 'This check needs attention on the device or Server Phone.'}
                {entry.remediation_category ? ` (Area: ${String(entry.remediation_category).replaceAll('_', ' ')})` : ''}
              </li>
            ))}
          </ul>
        ) : null}
        {data.webdav_authenticated === null ? <small>WebDAV access is checked with a temporary credential when a backup starts.</small> : null}
      </div>

      {toolRepair.status && !['unknown', 'not_requested'].includes(toolRepair.status) ? (
        <p className="lite-device-photo-backup-note" role="status" aria-live="polite">
          Photo backup tools: {repairing ? 'repair in progress' : toolRepair.status.replaceAll('_', ' ')}.
          {toolRepair.reason_code ? ` Reason: ${toolRepair.reason_code.replaceAll('_', ' ')}.` : ''}
          {repairing ? ' You can continue using the device while Pocket Lab checks the tools.' : ''}
        </p>
      ) : null}
      {latest.summary && !live ? (
        <p className="lite-device-photo-backup-note" role="status">
          Latest backup outcome: {latest.summary}
        </p>
      ) : null}
      {storage ? (
        <div className="lite-device-photo-backup-note" role="group" aria-label="Server Phone destination storage">
          <strong>Server Phone destination</strong>
          <p>Free: {formatBytes(storage.free_bytes)} · Hard reserve: {formatBytes(storage.hard_reserve_bytes)} · Planning reserve: {formatBytes(storage.planning_reserve_bytes)} · Safe upload budget: {formatBytes(storage.safe_upload_budget_bytes)}</p>
          <small>At least 10% remains protected; new transfers plan around 15% free space or 2 GiB, whichever is greater.</small>
          {storage.status !== 'ready' ? <p role="status">Storage status: {String(storage.reason_code || storage.status || 'unavailable').replaceAll('_', ' ')}. New transfers are blocked when storage cannot be verified.</p> : null}
        </div>
      ) : null}
      {Array.isArray(data.destinations) && data.destinations.length ? (
        <div className="lite-device-photo-backup-note" role="group" aria-label="Photo backup destinations">
          <strong>Backup destination</strong>
          <p>{data.destinations.find((item) => item.destination_id === data.selected_destination_id)?.display_name || 'Configured PhotoPrism destination'}</p>
          {data.destinations.some((item) => !item.supported) ? (
            <details><summary>Other storage options</summary>
              <ul>{data.destinations.filter((item) => !item.supported).map((item) => (
                <li key={item.destination_id}>{item.display_name} — not supported on this setup</li>
              ))}</ul>
            </details>
          ) : null}
        </div>
      ) : null}
      {latest.backup_id ? (
        <div className="lite-device-photo-backup-note" role="group" aria-label="Latest backup details">
          <strong>Latest backup</strong>
          <p>Outcome: {String(latest.status || 'unknown').replaceAll('_', ' ')} · Started: {safeDate(latest.started_at)} · Updated: {safeDate(latest.updated_at)}</p>
          <p>{Number(latest.items_transferred || 0)} copied · {Number(latest.items_skipped || 0)} already backed up · {Number(latest.items_remaining || 0)} remaining</p>
          {latest.retryable ? <small>Retry is available when current readiness checks pass.</small> : null}
          {latest.reason_code && GUIDANCE[latest.reason_code] ? <p>{GUIDANCE[latest.reason_code]}</p> : null}
          {latest.credential_revoke_status === 'pending' ? <p role="status">Credential revocation is pending. Do not assume access has been revoked yet.</p> : null}
        </div>
      ) : null}
      {latest.oversized_items > 0 ? (
        <p className="lite-device-photo-backup-note" role="status">
          {latest.oversized_items} large item(s) could not fit in the protected backup budget. Smaller eligible files can still be copied.
        </p>
      ) : null}
      {data.photo_storage_access === false || blockers.includes('photo_storage_access_missing') ? (
        <p className="lite-device-photo-backup-note" role="note">
          Allow photo access on this device, then return here. Pocket Lab will not repeatedly open Android permission prompts.
        </p>
      ) : null}

      {query.error ? (
        <p className="lite-device-photo-backup-error" role="alert">
          Photo backup status is temporarily unavailable. Device details remain available; try again when the connection is ready.
        </p>
      ) : null}

      <fieldset className="lite-device-photo-backup-collections" disabled={live || repairing || actionState.busy}>
        <legend>Photo collections</legend>
        {COLLECTIONS.map((collection) => {
          const available = !Array.isArray(data.collections) || data.collections.includes(collection.id);
          const checked = selected.includes(collection.id);
          return (
            <label key={collection.id} className={!available ? 'is-disabled' : ''}>
              <input
                type="checkbox"
                checked={checked}
                disabled={!available || live || actionState.busy}
                onChange={(event) => {
                  setSelected((current) => (
                    event.target.checked
                      ? [...new Set([...current, collection.id])]
                      : current.filter((item) => item !== collection.id)
                  ));
                }}
              />
              <span>{collection.label}</span>
            </label>
          );
        })}
      </fieldset>

      {live ? (
        <div className="lite-device-photo-backup-progress" aria-live="polite">
          <div>
            <span>{progress.step || 'Backing up photos.'}</span>
            <strong>{Math.max(0, Math.min(100, Number(progress.percent || 0)))}%</strong>
          </div>
          <progress aria-label="Photo backup progress" max="100" value={Math.max(0, Math.min(100, Number(progress.percent || 0)))} />
          <small>
            {Number(latest.items_transferred || 0)} backed up · {Number(latest.items_skipped || 0)} already safe
            {Number(latest.items_remaining || 0) ? ` · ${latest.items_remaining} waiting` : ''}
          </small>
        </div>
      ) : null}

      {latest.status === 'partial_storage_limit' ? (
        <p className="lite-device-photo-backup-note" role="status">
          Backup stopped before Pocket Lab's protected Server Phone reserve. Completed files were kept; Retry will continue with the remaining {Number(latest.items_remaining || 0)} item{Number(latest.items_remaining || 0) === 1 ? '' : 's'}
          {Number(latest.bytes_remaining || 0) > 0 ? ` (${formatBytes(latest.bytes_remaining)})` : ''}. Pocket Lab keeps at least 10% of Server Phone storage free.
        </p>
      ) : null}

      {!live && latest.photo_processing_state === 'processing' ? (
        <p className="lite-device-photo-backup-note" role="status">
          Transfer complete. PhotoPrism is processing the new media in the background.
        </p>
      ) : null}

      {!live && latest.status === 'completed' && Number(latest.items_total || 0) === 0 ? (
        <p className="lite-device-photo-backup-note" role="status">
          Nothing new to back up from the selected photo folders.
        </p>
      ) : null}

      {data.ready && Number(data?.storage?.hard_reserve_fraction || 0) >= 0.1 ? (
        <small className="lite-device-photo-backup-transfer">
          Storage protection: at least 10% of Server Phone space stays free.
        </small>
      ) : null}

      {latest.bytes_transferred ? (
        <small className="lite-device-photo-backup-transfer">
          {formatBytes(latest.bytes_transferred)} transferred in the latest run.
        </small>
      ) : null}

      {actionState.message ? <p className="lite-device-photo-backup-note" role="status">{actionState.message}</p> : null}
      {actionState.error ? <p className="lite-device-photo-backup-error" role="alert">{actionState.error}</p> : null}

      <div className="lite-device-photo-backup-actions" role="group" aria-label="Photo backup actions">
        <LiteButton tone="secondary" disabled={actionState.busy || !deviceId} onClick={() => query.refresh()}>
          <RefreshCw className="h-4 w-4" /> Check status
        </LiteButton>
        {canRepair ? (
          <LiteButton tone="secondary" disabled={actionState.busy || repairing} onClick={() => run('repair')}>
            <RefreshCw className="h-4 w-4" />
            Repair photo backup
          </LiteButton>
        ) : null}
        {live ? (
          <LiteButton tone="secondary" disabled={actionState.busy} onClick={() => run('cancel')}>
            <Square className="h-4 w-4" />
            Stop backup
          </LiteButton>
        ) : (
          <LiteButton tone="primary" disabled={!canStart} onClick={() => run('start')}>
            <Camera className="h-4 w-4" />
            {latest.retryable && canStart ? 'Retry' : 'Back up photos'}
          </LiteButton>
        )}
      </div>
    </section>
  );
}
