import { QueryClient } from '@tanstack/react-query';

export const liteQueryKeys = {
  status: () => ['lite', 'status'],
  catalog: () => ['lite', 'catalog'],
  appActions: (appId = 'photoprism') => ['lite', 'app', String(appId || 'photoprism').toLowerCase(), 'actions'],
  fleet: () => ['lite', 'fleet'],
  device: (deviceId = '') => ['lite', 'fleet', 'device', String(deviceId || '')],
  deviceHistory: (deviceId = '', limit = 20, cursor = '') => ['lite', 'fleet', 'device-history', String(deviceId || ''), Number(limit || 20), String(cursor || 'first')],
  deviceRemovalAssessment: (deviceId = '') => ['lite', 'fleet', 'device-removal-assessment', String(deviceId || '')],
  domainRevisions: () => ['lite', 'revisions'],
  domainEvents: () => ['lite', 'events'],
  appLifecycle: () => ['lite', 'apps', 'lifecycle'],
  appActionHistory: (appId = 'photoprism', limit = 20, cursor = '') => ['lite', 'apps', String(appId || 'photoprism'), 'action-history', Number(limit || 20), String(cursor || 'first')],
  deviceRecoveryHistory: (deviceId = '', limit = 20, cursor = '') => ['lite', 'fleet', 'device-recovery-history', String(deviceId || ''), Number(limit || 20), String(cursor || 'first')],
  commandHistory: (entityType = '', entityId = '', limit = 20, cursor = '') => ['lite', 'commands', 'history', String(entityType || ''), String(entityId || ''), Number(limit || 20), String(cursor || 'first')],
  security: () => ['lite', 'security'],
  securityDetails: () => ['lite', 'security', 'details'],
  securityRunDetails: (runId = 'latest') => ['lite', 'security', 'details', String(runId || 'latest')],
  securityFreshness: () => ['lite', 'security', 'freshness'],
  securityProgress: () => ['lite', 'security', 'progress'],
  securityEvents: () => ['lite', 'security', 'events'],
  securityEvidenceSummary: (runId = 'latest') => ['lite', 'security', 'evidence-summary', String(runId || 'latest')],
  securityProfile: (profile = 'quick', appId = '') => ['lite', 'security', 'profile', String(profile || 'quick').toLowerCase(), String(appId || '').toLowerCase()],
  securityHistory: (limit = 20) => ['lite', 'security', 'history', Number(limit || 20)],
  securityHistoryPage: (limit = 20, cursor = '') => ['lite', 'security', 'history', Number(limit || 20), String(cursor || 'first')],
  recovery: () => ['lite', 'recovery'],
  recoverySummary: () => ['lite', 'recovery', 'summary'],
  recoveryDetails: () => ['lite', 'recovery', 'details'],
  recoveryHistory: () => ['lite', 'recovery', 'history'],
  recoveryHistoryPage: (limit = 10, cursor = '') => ['lite', 'recovery', 'history', Number(limit || 10), String(cursor || 'first')],
  recoveryOperations: (limit = 20, cursor = '') => ['lite', 'recovery', 'operations', Number(limit || 20), String(cursor || 'first')],
  resource: (path = 'unknown', ...parts) => ['lite', 'resource', String(path || 'unknown'), ...parts],
};

export const liteQueryPaths = {
  status: '/api/lite/status',
  catalog: '/api/lite/catalog',
  appActions: (appId = 'photoprism') => `/api/lite/apps/${encodeURIComponent(appId || 'photoprism')}/actions`,
  fleet: '/api/lite/fleet',
  device: (deviceId = '') => `/api/lite/devices/${encodeURIComponent(deviceId || '')}`,
  deviceHistory: (deviceId = '', limit = 20, cursor = '') => `/api/lite/devices/${encodeURIComponent(deviceId || '')}/history?limit=${encodeURIComponent(limit || 20)}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
  deviceRemovalAssessment: (deviceId = '') => `/api/lite/devices/${encodeURIComponent(deviceId || '')}/removal-assessment`,
  domainRevisions: '/api/lite/revisions',
  domainEvents: '/api/lite/events',
  appLifecycle: '/api/lite/apps/lifecycle',
  appActionHistory: (appId = 'photoprism', limit = 20, cursor = '') => `/api/lite/apps/${encodeURIComponent(appId || 'photoprism')}/action-history?limit=${encodeURIComponent(limit || 20)}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
  deviceRecoveryHistory: (deviceId = '', limit = 20, cursor = '') => `/api/lite/fleet/devices/${encodeURIComponent(deviceId || '')}/recovery-history?limit=${encodeURIComponent(limit || 20)}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
  commandHistory: (entityType = '', entityId = '', limit = 20, cursor = '') => `/api/lite/commands/history?limit=${encodeURIComponent(limit || 20)}${entityType ? `&entity_type=${encodeURIComponent(entityType)}` : ''}${entityId ? `&entity_id=${encodeURIComponent(entityId)}` : ''}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
  security: '/api/lite/security/summary',
  securityDetails: '/api/lite/security',
  securityFreshness: '/api/lite/security/freshness',
  securityProfile: (profile = 'quick', appId = '') => `/api/lite/security/profiles/${encodeURIComponent(profile || 'quick')}${String(profile || 'quick').toLowerCase() === 'app' && appId ? `?app_id=${encodeURIComponent(appId)}` : ''}`,
  securityHistory: (limit = 20, cursor = '') => `/api/lite/security/history?limit=${encodeURIComponent(limit || 20)}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
  securityProgress: '/api/lite/security/progress',
  securityEvents: '/api/lite/security/events',
  securityRunDetails: (runId = 'latest') => `/api/lite/security/details/${encodeURIComponent(runId || 'latest')}`,
  securityEvidenceSummary: (runId = 'latest') => `/api/lite/security/evidence/${encodeURIComponent(runId || 'latest')}/summary`,
  recovery: '/api/lite/recovery',
  recoverySummary: '/api/lite/recovery/summary',
  recoveryDetails: '/api/lite/recovery/details',
  recoveryOperations: (limit = 20, cursor = '') => `/api/lite/recovery/operations?limit=${encodeURIComponent(limit || 20)}${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`,
};

export function liteQueryRetry(failureCount, error) {
  const status = Number(error?.status || error?.payload?.status_code || 0);
  if (status >= 400 && status < 500) return false;
  return failureCount < 2;
}

export function liteQueryRetryDelay(attemptIndex) {
  return Math.min(1200 * 2 ** attemptIndex, 6000);
}

export function createLiteQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: liteQueryRetry,
        retryDelay: liteQueryRetryDelay,
        staleTime: 20_000,
        gcTime: 5 * 60_000,
        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
        refetchInterval: false,
        refetchIntervalInBackground: false,
        networkMode: 'online',
      },
      mutations: {
        retry: false,
        networkMode: 'online',
      },
    },
  });
}

export const liteQueryClient = createLiteQueryClient();
