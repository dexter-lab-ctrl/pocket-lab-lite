import { attachFreshSnapshotMeta, attachSavedHttpCacheMeta, isSafeLiteSnapshotPath, markLiteSnapshotBackendUnreachable, readLiteSnapshotAsync, writeLiteSnapshot } from './liteSafeSnapshots.js';
import {
  classifyLiteSafeReadResponse,
  createLiteSafeReadNonce,
  LITE_SAFE_READ_NONCE_HEADER,
} from './liteOfflineReadPolicy.js';

const API_BASE = (import.meta.env.VITE_POCKETLAB_API_BASE || '').replace(/\/$/, '');
const LITE_NOT_MODIFIED = '__liteNotModified';
const liteEtagByPath = new Map();

function normalizeEtag(value) {
  const etag = String(value || '').trim();
  return etag || '';
}

function rememberLiteEtag(path, value) {
  const etag = normalizeEtag(value);
  if (etag) liteEtagByPath.set(path, etag);
  return etag;
}

export function getLiteEtag(path) {
  return liteEtagByPath.get(path) || '';
}

export function isLiteNotModified(payload) {
  return Boolean(payload && payload[LITE_NOT_MODIFIED]);
}

function endpoint(path) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

function serviceWorkerControlsSameOriginRequest(path = '') {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false;
  if (!navigator.serviceWorker?.controller) return false;
  try {
    return new URL(endpoint(path), window.location.origin).origin === window.location.origin;
  } catch {
    return false;
  }
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

  if (method === 'GET' && safeSnapshot && typeof navigator !== 'undefined' && navigator.onLine === false) {
    markLiteSnapshotBackendUnreachable();
    const cached = await readLiteSnapshotAsync(path);
    if (cached) return cached;
    const error = new Error('Pocket Lab is not reachable. No saved state is available yet.');
    error.status = 0;
    error.payload = { status: 'offline', summary: 'Pocket Lab is not reachable. No saved state is available yet.' };
    throw error;
  }

  const conditionalEtagKey = options.conditionalEtagKey || path;
  const verifySafeReadSource = Boolean(safeSnapshot && serviceWorkerControlsSameOriginRequest(path));
  const safeReadNonce = verifySafeReadSource ? createLiteSafeReadNonce() : '';
  const requestHeaders = {
    Accept: 'application/json',
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(safeReadNonce ? { [LITE_SAFE_READ_NONCE_HEADER]: safeReadNonce } : {}),
    ...(options.headers || {}),
  };
  const knownEtag = normalizeEtag(options.ifNoneMatch || (options.conditional ? getLiteEtag(conditionalEtagKey) : ''));
  if (method === 'GET' && knownEtag && !requestHeaders['If-None-Match']) {
    requestHeaders['If-None-Match'] = knownEtag;
  }

  let response;
  try {
    response = await fetch(endpoint(path), {
    cache: 'no-store',
    ...options,
    headers: requestHeaders,
  });
  } catch (networkError) {
    if (safeSnapshot) {
      markLiteSnapshotBackendUnreachable();
      const cached = await readLiteSnapshotAsync(path);
      if (cached) return cached;
    }
    const error = new Error('Pocket Lab is not reachable. Saved state only.');
    error.status = 0;
    error.payload = { status: 'unreachable', summary: 'Pocket Lab is not reachable. Saved state only.', cause: networkError?.message || 'network_error' };
    throw error;
  }

  const responseEtag = rememberLiteEtag(conditionalEtagKey, response.headers?.get?.('ETag') || '');
  if (response.status === 304) {
    return {
      [LITE_NOT_MODIFIED]: true,
      status: 'not_modified',
      __liteEtag: responseEtag || knownEtag,
      __litePath: path,
    };
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
      markLiteSnapshotBackendUnreachable();
      const cached = await readLiteSnapshotAsync(path);
      if (cached) return cached;
    }
    const message = data?.message || data?.summary || data?.detail?.message || data?.detail?.summary || data?.detail || data?.error || response.statusText;
    const error = new Error(typeof message === 'string' ? message : 'Pocket Lab Lite action could not be completed.');
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  if (safeSnapshot) {
    const responseSource = classifyLiteSafeReadResponse({
      requestNonce: safeReadNonce,
      responseNonce: response.headers?.get?.(LITE_SAFE_READ_NONCE_HEADER) || '',
      serviceWorkerControlled: verifySafeReadSource,
    });
    if (responseSource === 'http-cache') {
      markLiteSnapshotBackendUnreachable();
      const durable = await readLiteSnapshotAsync(path);
      if (durable) return durable;
      return attachSavedHttpCacheMeta(path, data, {
        checkedAt: response.headers?.get?.('Date') || '',
      });
    }
    writeLiteSnapshot(path, data);
    return attachFreshSnapshotMeta(path, data);
  }

  return data;
}

function postJson(path, body = {}) {
  return readJson(path, { method: 'POST', body: JSON.stringify(body) });
}

function putJson(path, body = {}) {
  return readJson(path, { method: 'PUT', body: JSON.stringify(body) });
}

function safeGet(path) {
  const loader = () => readJson(path);
  loader.safeSnapshotPath = path;
  return loader;
}

function conditionalGet(path) {
  const loader = () => readJson(path, { conditional: true, conditionalEtagKey: path });
  loader.safeSnapshotPath = path;
  return loader;
}

function conditionalRead(path) {
  return readJson(path, { conditional: true, conditionalEtagKey: path });
}

export const liteApi = {
  status: safeGet('/api/lite/status'),
  lifecycleDiagnosticsChallenge: () => readJson('/api/lite/diagnostics/frontend-lifecycle/challenge'),
  recordLifecycleDiagnostics: (challengeId, report = {}) => postJson('/api/lite/diagnostics/frontend-lifecycle', { challenge_id: challengeId, report }),
  catalog: safeGet('/api/lite/catalog'),
  appLifecycle: conditionalGet('/api/lite/apps/lifecycle'),
  appLifecycleProfile: (appId = 'photoprism') => readJson(`/api/lite/apps/lifecycle/${encodeURIComponent(appId)}`),
  appActionHistory: (appId = 'photoprism', limit = 20, cursor = '') => {
    const query = new URLSearchParams({ limit: String(limit || 20) });
    if (cursor) query.set('cursor', cursor);
    return conditionalRead(`/api/lite/apps/${encodeURIComponent(appId)}/action-history?${query.toString()}`);
  },
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
  security: conditionalGet('/api/lite/security/summary'),
  securitySummary: conditionalGet('/api/lite/security/summary'),
  securityDetails: safeGet('/api/lite/security'),
  securityFreshness: conditionalGet('/api/lite/security/freshness'),
  securityProfile: (profile = 'quick', appId = '') => {
    const query = String(profile || 'quick').toLowerCase() === 'app' && appId
      ? `?app_id=${encodeURIComponent(appId)}`
      : '';
    return conditionalRead(`/api/lite/security/profiles/${encodeURIComponent(profile || 'quick')}${query}`);
  },
  securityHistory: (limit = 20, cursor = '') => {
    const query = new URLSearchParams({ limit: String(limit || 20) });
    if (cursor) query.set('cursor', cursor);
    return conditionalRead(`/api/lite/security/history?${query.toString()}`);
  },
  securityProgress: () => conditionalRead('/api/lite/security/progress'),
  securityRunDetails: (runId) => conditionalRead(`/api/lite/security/details/${encodeURIComponent(runId || '')}`),
  securityEvidenceSummary: (runId) => conditionalRead(`/api/lite/security/evidence/${encodeURIComponent(runId || '')}/summary`),
  securityApps: () => readJson('/api/lite/security/apps'),
  securityApp: (appId = 'photoprism') => readJson(`/api/lite/security/apps/${encodeURIComponent(appId)}`),
  checkSecurityApp: (appId = 'photoprism', payload = {}) => postJson(`/api/lite/security/apps/${encodeURIComponent(appId)}/check`, payload),
  fleet: conditionalGet('/api/lite/fleet'),
  device: (deviceId) => conditionalRead(`/api/lite/devices/${encodeURIComponent(deviceId || '')}`),
  deviceHealth: (deviceId) => conditionalRead(`/api/lite/devices/${encodeURIComponent(deviceId || '')}/health`),
  deviceHealthHistory: (deviceId, limit = 20, cursor = '') => {
    const query = new URLSearchParams({ limit: String(limit || 20) });
    if (cursor) query.set('cursor', cursor);
    return conditionalRead(`/api/lite/devices/${encodeURIComponent(deviceId || '')}/health/history?${query.toString()}`);
  },
  fleetHealthSummary: () => conditionalRead('/api/lite/fleet/health-summary'),
  deviceHistory: (deviceId, limit = 20, cursor = '') => {
    const query = new URLSearchParams({ limit: String(limit || 20) });
    if (cursor) query.set('cursor', cursor);
    return conditionalRead(`/api/lite/devices/${encodeURIComponent(deviceId || '')}/history?${query.toString()}`);
  },
  deviceRemovalAssessment: (deviceId) => conditionalRead(`/api/lite/devices/${encodeURIComponent(deviceId || '')}/removal-assessment`),
  revokeDeviceInvite: (inviteId, payload = {}) => postJson(`/api/lite/fleet/invites/${encodeURIComponent(inviteId || '')}/revoke`, payload),
  updateDeviceDisplayModel: (deviceId, consumerModelName = '', expectedProfileRevision = null, expectedConsumerModelName = null) => putJson(`/api/lite/fleet/devices/${encodeURIComponent(deviceId || '')}/display-model`, {
    consumer_model_name: consumerModelName || null,
    expected_profile_revision: Number.isFinite(Number(expectedProfileRevision)) ? Number(expectedProfileRevision) : null,
    expected_consumer_model_name: expectedConsumerModelName == null ? null : String(expectedConsumerModelName || ''),
  }),
  domainRevisions: conditionalGet('/api/lite/revisions'),
  deviceRecoveryHistory: (deviceId, limit = 20, cursor = '') => {
    const query = new URLSearchParams({ limit: String(limit || 20) });
    if (cursor) query.set('cursor', cursor);
    return conditionalRead(`/api/lite/fleet/devices/${encodeURIComponent(deviceId || '')}/recovery-history?${query.toString()}`);
  },
  commandHistory: ({ entityType = '', entityId = '', limit = 20, cursor = '' } = {}) => {
    const query = new URLSearchParams({ limit: String(limit || 20) });
    if (entityType) query.set('entity_type', entityType);
    if (entityId) query.set('entity_id', entityId);
    if (cursor) query.set('cursor', cursor);
    return conditionalRead(`/api/lite/commands/history?${query.toString()}`);
  },
  policy: () => readJson('/api/lite/policy'),
  recovery: safeGet('/api/lite/recovery'),
  recoverySummary: conditionalGet('/api/lite/recovery/summary'),
  recoveryDetails: conditionalGet('/api/lite/recovery/details'),
  recoveryOperations: (limit = 20, cursor = '') => {
    const query = new URLSearchParams({ limit: String(limit || 20) });
    if (cursor) query.set('cursor', cursor);
    return conditionalRead(`/api/lite/recovery/operations?${query.toString()}`);
  },
  databaseRecovery: safeGet('/api/lite/recovery/database'),
  recoveryMaintenance: safeGet('/api/lite/recovery/maintenance'),
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
  recoveryHistory: (limit = 10, cursor = '') => {
    const query = new URLSearchParams({ limit: String(limit || 10) });
    if (cursor) query.set('cursor', cursor);
    return readJson(`/api/lite/recovery/backups?${query.toString()}`);
  },
  recoveryBackup: (backupId = 'latest') => readJson(`/api/lite/recovery/backups/${encodeURIComponent(backupId)}`),
  recoveryReceipt: (backupId = 'latest') => readJson(`/api/lite/recovery/receipts/${encodeURIComponent(backupId)}`),
  installApp: (appId, options = {}) => postJson('/api/lite/catalog/install', { app_id: appId, ...options }),
  photoprismStoragePreview: () => readJson('/api/lite/apps/photoprism/storage-preview'),
  photoprismStorageMappings: () => readJson('/api/lite/apps/photoprism/storage-mappings'),
  connectPhotoPrismStorage: (payload = {}) => postJson('/api/lite/apps/photoprism/storage-mappings', payload),
  disconnectPhotoPrismStorage: (mappingId) => readJson(`/api/lite/apps/photoprism/storage-mappings/${encodeURIComponent(mappingId || '')}`, { method: 'DELETE' }),
  rotateIdentity: (target, options = {}) => postJson('/api/lite/identity/rotate', { target, ...options }),
  runSecurityScan: (scope = 'local', options = {}) => postJson('/api/lite/security/check', { scope, profile: 'quick', ...options }),
  securityRun: (runId) => readJson(`/api/lite/security/runs/${encodeURIComponent(runId || '')}`),
  securityEvidence: (runId) => conditionalRead(`/api/lite/security/evidence/${encodeURIComponent(runId || '')}/summary`),
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
  backupDatabase: (payload = {}) => postJson('/api/lite/recovery/database/backup', payload),
  databaseBackups: () => readJson('/api/lite/recovery/database/backups'),
  databaseBackup: (backupId = 'latest') => readJson(`/api/lite/recovery/database/backups/${encodeURIComponent(backupId || 'latest')}`),
  verifyDatabaseBackup: (backupId = 'latest') => postJson(`/api/lite/recovery/database/backups/${encodeURIComponent(backupId || 'latest')}/verify`, {}),
  previewDatabaseRestore: (backupId = 'latest') => postJson(`/api/lite/recovery/database/backups/${encodeURIComponent(backupId || 'latest')}/preview`, {}),
  databaseRestorePreview: (previewId) => readJson(`/api/lite/recovery/database/restore/previews/${encodeURIComponent(previewId || '')}`),
  restoreDatabase: (backupId, payload = {}) => postJson(`/api/lite/recovery/database/backups/${encodeURIComponent(backupId || '')}/restore`, payload),
  databaseRestoreRun: (restoreId) => readJson(`/api/lite/recovery/database/restore/${encodeURIComponent(restoreId || '')}`),
  runSecurityRetention: (payload = {}) => postJson('/api/lite/recovery/maintenance/retention', payload),
  runWalCheckpoint: (payload = {}) => postJson('/api/lite/recovery/maintenance/checkpoint', payload),
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
