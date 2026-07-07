import { useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { liteQueryKeys } from '../lib/liteQueryClient.js';
import { getLiteDeviceMutationInvalidations } from '../lib/liteViewModels.js';

export const LITE_BROWSER_ACTION_QUEUE_DISABLED = true;

export const liteMutationInvalidations = {
  import_photos: [liteQueryKeys.appActions('photoprism')],
  connect_photos: [liteQueryKeys.appActions('photoprism')],
  check_app: [liteQueryKeys.appActions('photoprism')],
  repair_app: [liteQueryKeys.appActions('photoprism')],
  update_app: [liteQueryKeys.appActions('photoprism')],
  backup_app: [liteQueryKeys.appActions('photoprism')],
  backup_to_storage: [liteQueryKeys.appActions('photoprism')],
  preview_restore: [liteQueryKeys.appActions('photoprism')],
  install_app: [liteQueryKeys.catalog(), liteQueryKeys.appActions('photoprism')],
  remove_app: [liteQueryKeys.catalog(), liteQueryKeys.appActions('photoprism')],
  security_check: [liteQueryKeys.security()],
  recovery_backup: [liteQueryKeys.recovery(), liteQueryKeys.appActions('photoprism')],
  restart_agent: [liteQueryKeys.fleet(), liteQueryKeys.status()],
  add_device: [liteQueryKeys.fleet(), liteQueryKeys.status()],
  remove_device: [liteQueryKeys.fleet(), liteQueryKeys.status()],
  refresh_remote_access: [liteQueryKeys.fleet()],
};

function normalizeActionId(actionId = '') {
  return String(actionId || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function actionResultHint(payload = {}, names = []) {
  return names.some((name) => payload?.[name] === true || payload?.hints?.[name] === true || payload?.changed?.[name] === true);
}

function uniqueQueryKeys(keys = []) {
  const seen = new Set();
  return keys.filter((key) => {
    if (!key) return false;
    const marker = JSON.stringify(key);
    if (seen.has(marker)) return false;
    seen.add(marker);
    return true;
  });
}

export function getLiteAppActionInvalidations(appId = 'photoprism', actionId = '', result = {}) {
  const normalizedAppId = String(appId || 'photoprism').toLowerCase();
  const normalizedActionId = normalizeActionId(actionId || result?.action_id || result?.actionId);
  const keys = [liteQueryKeys.appActions(normalizedAppId)];

  const routeOrCatalogChanged = actionResultHint(result, [
    'catalog_changed',
    'app_changed',
    'route_changed',
    'route_readiness_changed',
    'openability_changed',
    'open_url_changed',
    'lifecycle_changed',
  ]);
  const mediaSummaryChanged = actionResultHint(result, ['media_changed', 'storage_changed', 'mapping_changed', 'import_state_changed']);
  const recoverySummaryChanged = actionResultHint(result, ['recovery_changed', 'backup_changed', 'restore_preview_changed']);

  if (
    routeOrCatalogChanged
    || ['install_app', 'remove_app', 'repair_app'].includes(normalizedActionId)
    || (['connect_photos', 'import_photos'].includes(normalizedActionId) && (mediaSummaryChanged || result?.accepted || result?.queued))
    || (normalizedActionId === 'check_app' && actionResultHint(result, ['security_changed', 'safety_changed']))
  ) {
    keys.push(liteQueryKeys.catalog());
  }

  if (
    recoverySummaryChanged
    || ['backup_app', 'backup_to_storage', 'preview_restore'].includes(normalizedActionId)
  ) {
    keys.push(liteQueryKeys.recovery());
  }

  return uniqueQueryKeys(keys);
}


export function getLiteDeviceActionInvalidations(actionId = '', result = {}) {
  return uniqueQueryKeys(getLiteDeviceMutationInvalidations(actionId, result));
}

export function isAcceptedLiteMutationResponse(payload) {
  const status = String(payload?.status || payload?.state || '').toLowerCase();
  return Boolean(
    payload?.accepted === true
    || payload?.queued === true
    || payload?.job_id
    || payload?.command_id
    || ['accepted', 'queued', 'running', 'started', 'already_connected'].includes(status)
  );
}

export async function invalidateLiteQueries(queryClient, invalidate = []) {
  const keys = Array.isArray(invalidate) ? invalidate : [invalidate];
  await Promise.all(keys.filter(Boolean).map((queryKey) => queryClient.invalidateQueries({ queryKey })));
}

export function useLiteMutation({ mutationFn, invalidate = [], invalidateForAction, onSuccess, ...options } = {}) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn,
    retry: false,
    ...options,
    onSuccess: async (data, variables, context) => {
      if (isAcceptedLiteMutationResponse(data)) {
        const dynamicInvalidations = typeof invalidateForAction === 'function'
          ? invalidateForAction(variables, data)
          : [];
        await invalidateLiteQueries(queryClient, [...invalidate, ...dynamicInvalidations]);
      }
      if (onSuccess) await onSuccess(data, variables, context);
    },
  });

  const run = useCallback((variables) => mutation.mutateAsync(variables), [mutation]);

  return {
    ...mutation,
    run,
  };
}
