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
  const [actionState, setActionState] = React.useState({ busy: false, error: '' });
  const query = useLiteQuery({
    queryKey: ['lite', 'photo-backup', deviceId],
    path: `/api/lite/devices/${encodeURIComponent(deviceId || '')}/photo-backup`,
    queryFn: () => liteApi.photoBackup(deviceId),
    enabled: Boolean(deviceId),
    staleTime: 15_000,
    refetchInterval: (queryState) => {
      const status = queryState?.state?.data?.latest_backup?.status;
      return isLive(status) ? 5_000 : 30_000;
    },
    refetchOnWindowFocus: false,
  });

  const data = query.data || {};
  const latest = data.latest_backup || {};
  const live = isLive(latest.status);
  const progress = latest.progress || {};
  const blockers = Array.isArray(data.blockers) ? data.blockers : [];
  const canStart = Boolean(data.ready && selected.length && !live && !actionState.busy);
  const canRepair = blockers.includes('rclone_unavailable') && !actionState.busy;

  async function run(action) {
    setActionState({ busy: true, error: '' });
    try {
      if (action === 'start') {
        await liteApi.startPhotoBackup(deviceId, { collections: selected });
      } else if (action === 'cancel') {
        await liteApi.cancelPhotoBackup(deviceId, {});
      } else if (action === 'repair') {
        await liteApi.repairPhotoBackup(deviceId);
      }
      await query.refresh();
    } catch (error) {
      setActionState({ busy: false, error: error?.message || 'Pocket Lab could not update photo backup.' });
      return;
    }
    setActionState({ busy: false, error: '' });
  }

  return (
    <section className="lite-device-photo-backup" aria-label="Photo backup">
      <div className="lite-device-photo-backup-head">
        <span className="lite-device-photo-backup-icon"><Camera className="h-4 w-4" /></span>
        <div>
          <span>Photo backup</span>
          <strong>{live ? 'Backing up photos' : data.ready ? 'Ready' : 'Needs attention'}</strong>
          <p>{latest.summary || data.summary || 'Pocket Lab is checking photo backup readiness.'}</p>
        </div>
      </div>

      {!data.photo_storage_access ? (
        <p className="lite-device-photo-backup-note" role="note">
          Allow photo access on this device, then return here. Pocket Lab will not repeatedly open Android permission prompts.
        </p>
      ) : null}

      <div className="lite-device-photo-backup-collections" aria-label="Photo collections">
        {COLLECTIONS.map((collection) => {
          const available = !Array.isArray(data.collections) || !data.collections.length || data.collections.includes(collection.id);
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
      </div>

      {live ? (
        <div className="lite-device-photo-backup-progress" aria-live="polite">
          <div>
            <span>{progress.step || 'Backing up photos.'}</span>
            <strong>{Math.max(0, Math.min(100, Number(progress.percent || 0)))}%</strong>
          </div>
          <progress max="100" value={Math.max(0, Math.min(100, Number(progress.percent || 0)))} />
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

      {actionState.error ? <p className="lite-device-photo-backup-error" role="alert">{actionState.error}</p> : null}

      <div className="lite-device-photo-backup-actions">
        {canRepair ? (
          <LiteButton tone="secondary" disabled={actionState.busy} onClick={() => run('repair')}>
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
            {latest.retryable ? 'Retry' : 'Back up photos'}
          </LiteButton>
        )}
      </div>
    </section>
  );
}
