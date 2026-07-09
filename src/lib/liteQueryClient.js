import { QueryClient } from '@tanstack/react-query';

export const liteQueryKeys = {
  status: () => ['lite', 'status'],
  catalog: () => ['lite', 'catalog'],
  appActions: (appId = 'photoprism') => ['lite', 'app', String(appId || 'photoprism').toLowerCase(), 'actions'],
  fleet: () => ['lite', 'fleet'],
  security: () => ['lite', 'security'],
  securityDetails: () => ['lite', 'security', 'details'],
  securityRunDetails: (runId = 'latest') => ['lite', 'security', 'details', String(runId || 'latest')],
  securityFreshness: () => ['lite', 'security', 'freshness'],
  securityProgress: () => ['lite', 'security', 'progress'],
  securityEvidenceSummary: (runId = 'latest') => ['lite', 'security', 'evidence-summary', String(runId || 'latest')],
  securityProfile: (profile = 'quick') => ['lite', 'security', 'profile', String(profile || 'quick').toLowerCase()],
  securityHistory: (limit = 20) => ['lite', 'security', 'history', Number(limit || 20)],
  recovery: () => ['lite', 'recovery'],
  resource: (path = 'unknown', ...parts) => ['lite', 'resource', String(path || 'unknown'), ...parts],
};

export const liteQueryPaths = {
  status: '/api/lite/status',
  catalog: '/api/lite/catalog',
  appActions: (appId = 'photoprism') => `/api/lite/apps/${encodeURIComponent(appId || 'photoprism')}/actions`,
  fleet: '/api/lite/fleet',
  security: '/api/lite/security/summary',
  securityDetails: '/api/lite/security',
  securityFreshness: '/api/lite/security/freshness',
  securityProfile: (profile = 'quick') => `/api/lite/security/profiles/${encodeURIComponent(profile || 'quick')}`,
  securityHistory: (limit = 20) => `/api/lite/security/history?limit=${encodeURIComponent(limit || 20)}`,
  securityProgress: '/api/lite/security/progress',
  securityRunDetails: (runId = 'latest') => `/api/lite/security/details/${encodeURIComponent(runId || 'latest')}`,
  securityEvidenceSummary: (runId = 'latest') => `/api/lite/security/evidence/${encodeURIComponent(runId || 'latest')}/summary`,
  recovery: '/api/lite/recovery',
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
        refetchOnWindowFocus: true,
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
