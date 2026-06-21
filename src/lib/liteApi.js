const API_BASE = (import.meta.env.VITE_POCKETLAB_API_BASE || '').replace(/\/$/, '');

function endpoint(path) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

async function readJson(path, options = {}) {
  const response = await fetch(endpoint(path), {
    cache: 'no-store',
    headers: {
      Accept: 'application/json',
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });

  const text = await response.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_error) {
    data = { summary: 'Pocket Lab Lite returned a response that could not be read.' };
  }

  if (!response.ok) {
    const message = data?.summary || data?.detail?.summary || data?.detail || data?.error || response.statusText;
    const error = new Error(typeof message === 'string' ? message : 'Pocket Lab Lite action could not be completed.');
    error.status = response.status;
    error.payload = data;
    throw error;
  }

  return data;
}

function postJson(path, body = {}) {
  return readJson(path, { method: 'POST', body: JSON.stringify(body) });
}

export const liteApi = {
  status: () => readJson('/api/lite/status'),
  catalog: () => readJson('/api/lite/catalog'),
  identity: () => readJson('/api/lite/identity'),
  security: () => readJson('/api/lite/security'),
  fleet: () => readJson('/api/lite/fleet'),
  policy: () => readJson('/api/lite/policy'),
  recovery: () => readJson('/api/lite/recovery'),
  installApp: (appId, options = {}) => postJson('/api/lite/catalog/install', { app_id: appId, ...options }),
  rotateIdentity: (target, options = {}) => postJson('/api/lite/identity/rotate', { target, ...options }),
  runSecurityScan: (scope = 'local') => postJson('/api/lite/security/scan', { scope }),
  addDevice: (payload = {}) => postJson('/api/lite/fleet/add-device', payload),
  removeDevice: (deviceId, payload = {}) => postJson('/api/lite/fleet/remove-device', {
    device_id: deviceId,
    confirm: true,
    ...payload,
  }),
  restartDeviceAgent: (deviceId, payload = {}) => postJson(`/api/lite/fleet/devices/${encodeURIComponent(deviceId)}/restart-agent`, payload),
  applyPolicy: (payload = {}) => postJson('/api/lite/policy/apply', payload),
  backupNow: (payload = {}) => postJson('/api/lite/recovery/backup', payload),
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
