import { attachFreshSnapshotMeta, isSafeLiteSnapshotPath, readLiteSnapshot, writeLiteSnapshot } from './liteSafeSnapshots.js';

const API_BASE = (import.meta.env.VITE_POCKETLAB_API_BASE || '').replace(/\/$/, '');

function endpoint(path) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

async function readJson(path, options = {}) {
  const method = String(options.method || 'GET').toUpperCase();
  const safeSnapshot = method === 'GET' && isSafeLiteSnapshotPath(path);

  if (method !== 'GET' && typeof navigator !== 'undefined' && navigator.onLine === false) {
    const error = new Error('Pocket Lab is not reachable. Reconnect to continue.');
    error.status = 0;
    error.payload = { status: 'offline', summary: 'Pocket Lab is not reachable. Reconnect to continue.' };
    throw error;
  }

  let response;
  try {
    response = await fetch(endpoint(path), {
    cache: 'no-store',
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  } catch (networkError) {
    if (safeSnapshot) {
      const cached = readLiteSnapshot(path);
      if (cached) return cached;
    }
    const error = new Error('Pocket Lab is not reachable. Saved state only.');
    error.status = 0;
    error.payload = { status: 'unreachable', summary: 'Pocket Lab is not reachable. Saved state only.', cause: networkError?.message || 'network_error' };
    throw error;
  }

  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_error) {
    data = { summary: 'Pocket Lab Lite returned a response that could not be read.' };
  }

  if (!response.ok) {
    if (safeSnapshot) {
      const cached = readLiteSnapshot(path);
      if (cached) return cached;
    }
    const message = data?.summary || data?.detail?.summary || data?.detail || data?.error || response.statusText;
    const error = new Error(typeof message === 'string' ? message : 'Pocket Lab Lite action could not be completed.');
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  if (safeSnapshot) {
    writeLiteSnapshot(path, data);
    return attachFreshSnapshotMeta(path, data);
  }

  return data;
}

function postJson(path, body = {}) {
  return readJson(path, { method: 'POST', body: JSON.stringify(body) });
}

function safeGet(path) {
  const loader = () => readJson(path);
  loader.safeSnapshotPath = path;
  return loader;
}

export const liteApi = {
  status: safeGet('/api/lite/status'),
  catalog: safeGet('/api/lite/catalog'),
  appLifecycle: () => readJson('/api/lite/apps/lifecycle'),
  appLifecycleProfile: (appId = 'photoprism') => readJson(`/api/lite/apps/lifecycle/${encodeURIComponent(appId)}`),
  appActions: Object.assign((appId = 'photoprism') => {
    const path = `/api/lite/apps/${encodeURIComponent(appId)}/actions`;
    return readJson(path);
  }, { safeSnapshotPath: '/api/lite/apps/photoprism/actions' }),
  appEvidence: (appId = 'photoprism') => readJson(`/api/lite/apps/${encodeURIComponent(appId)}/evidence`),
  appBackupStatus: (appId = 'photoprism') => readJson(`/api/lite/apps/${encodeURIComponent(appId)}/backup`),
  appBackups: (appId = 'photoprism') => readJson(`/api/lite/apps/${encodeURIComponent(appId)}/backups`),
  appBackupReceipt: (appId = 'photoprism', backupId = 'latest') => readJson(`/api/lite/apps/${encodeURIComponent(appId)}/backups/${encodeURIComponent(backupId || 'latest')}/receipt`),
  appUpdateStatus: (appId = 'photoprism') => readJson(`/api/lite/apps/${encodeURIComponent(appId)}/update`),
  appUpdateReceipt: (appId = 'photoprism', operationId = 'latest') => readJson(`/api/lite/apps/${encodeURIComponent(appId)}/update/receipts/${encodeURIComponent(operationId || 'latest')}`),
  applyAppUpdate: (appId = 'photoprism', payload = {}) => postJson(`/api/lite/apps/${encodeURIComponent(appId)}/update/apply`, payload),
  runAppAction: (appId = 'photoprism', actionId, payload = {}) => postJson(`/api/lite/apps/${encodeURIComponent(appId)}/actions/${encodeURIComponent(actionId || '')}`, payload),
  identity: () => readJson('/api/lite/identity'),
  security: safeGet('/api/lite/security'),
  securityApps: () => readJson('/api/lite/security/apps'),
  securityApp: (appId = 'photoprism') => readJson(`/api/lite/security/apps/${encodeURIComponent(appId)}`),
  checkSecurityApp: (appId = 'photoprism', payload = {}) => postJson(`/api/lite/security/apps/${encodeURIComponent(appId)}/check`, payload),
  fleet: safeGet('/api/lite/fleet'),
  policy: () => readJson('/api/lite/policy'),
  recovery: safeGet('/api/lite/recovery'),
  recoveryApps: () => readJson('/api/lite/recovery/apps'),
  recoveryBackupTargets: () => readJson('/api/lite/recovery/backup-targets'),
  recoveryAppBackupTargets: (appId = 'photoprism') => readJson(`/api/lite/recovery/apps/${encodeURIComponent(appId)}/backup-targets`),
  backupAppToStorage: (appId = 'photoprism', payload = {}) => postJson(`/api/lite/apps/${encodeURIComponent(appId)}/backup/storage-device`, payload),
  recoveryApp: (appId = 'photoprism') => readJson(`/api/lite/recovery/apps/${encodeURIComponent(appId)}`),
  backupApp: (appId = 'photoprism', payload = {}) => postJson(`/api/lite/apps/${encodeURIComponent(appId)}/backup`, payload),
  previewAppRestore: (appId = 'photoprism', payload = {}) => postJson(`/api/lite/apps/${encodeURIComponent(appId)}/restore/preview`, payload),
  appRestorePreview: (appId = 'photoprism', previewId = 'latest') => readJson(`/api/lite/apps/${encodeURIComponent(appId)}/restore/previews/${encodeURIComponent(previewId || 'latest')}`),
  restoreApp: (appId = 'photoprism', payload = {}) => postJson(`/api/lite/recovery/apps/${encodeURIComponent(appId)}/restore`, payload),
  recoveryBackups: () => readJson('/api/lite/recovery/backups'),
  recoveryBackup: (backupId = 'latest') => readJson(`/api/lite/recovery/backups/${encodeURIComponent(backupId)}`),
  recoveryReceipt: (backupId = 'latest') => readJson(`/api/lite/recovery/receipts/${encodeURIComponent(backupId)}`),
  installApp: (appId, options = {}) => postJson('/api/lite/catalog/install', { app_id: appId, ...options }),
  photoprismStoragePreview: () => readJson('/api/lite/apps/photoprism/storage-preview'),
  photoprismStorageMappings: () => readJson('/api/lite/apps/photoprism/storage-mappings'),
  connectPhotoPrismStorage: (payload = {}) => postJson('/api/lite/apps/photoprism/storage-mappings', payload),
  disconnectPhotoPrismStorage: (mappingId) => readJson(`/api/lite/apps/photoprism/storage-mappings/${encodeURIComponent(mappingId || '')}`, { method: 'DELETE' }),
  rotateIdentity: (target, options = {}) => postJson('/api/lite/identity/rotate', { target, ...options }),
  runSecurityScan: (scope = 'local', options = {}) => postJson('/api/lite/security/check', { scope, ...options }),
  securityRun: (runId) => readJson(`/api/lite/security/runs/${encodeURIComponent(runId || '')}`),
  securityEvidence: (runId) => readJson(`/api/lite/security/evidence/${encodeURIComponent(runId || '')}`),
  addDevice: (payload = {}) => postJson('/api/lite/fleet/add-device', payload),
  removeDevice: (deviceId, payload = {}) => postJson('/api/lite/fleet/remove-device', {
    device_id: deviceId,
    confirm: true,
    ...payload,
  }),
  restartDeviceAgent: (deviceId, payload = {}) => postJson(`/api/lite/fleet/devices/${encodeURIComponent(deviceId)}/restart-agent`, payload),
  restartDeviceAgentStatus: (deviceId, commandId) => readJson(`/api/lite/fleet/devices/${encodeURIComponent(deviceId)}/restart-agent/status?command_id=${encodeURIComponent(commandId || '')}`),
  applyPolicy: (payload = {}) => postJson('/api/lite/policy/apply', payload),
  backupNow: (payload = {}) => postJson('/api/lite/recovery/backup', payload),
  verifyBackup: (backupId = 'latest', payload = {}) => postJson(`/api/lite/recovery/backups/${encodeURIComponent(backupId || 'latest')}/verify`, payload),
  previewRestore: (payload = {}) => postJson('/api/lite/recovery/restore/preview', payload),
  restorePreview: (previewId) => readJson(`/api/lite/recovery/restore/previews/${encodeURIComponent(previewId || '')}`),
  restoreBackup: (payload = {}) => postJson('/api/lite/recovery/restore', payload),
};

export function formatLiteTime(value) {
  if (!value) return 'Not available yet';
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value));
  } catch (_error) {
    return String(value);
  }
}

export function actionReference(payload) {
  return payload?.job_id || payload?.command_id || payload?.execution_id || payload?.reference || null;
}
