import { useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { liteQueryKeys } from '../lib/liteQueryClient.js';

export const LITE_BROWSER_ACTION_QUEUE_DISABLED = true;

export const liteMutationInvalidations = {
  import_photos: [liteQueryKeys.appActions('photoprism')],
  connect_photos: [liteQueryKeys.appActions('photoprism')],
  check_app: [liteQueryKeys.appActions('photoprism')],
  repair_app: [liteQueryKeys.appActions('photoprism')],
  update_app: [liteQueryKeys.appActions('photoprism')],
  backup_app: [liteQueryKeys.recovery(), liteQueryKeys.appActions('photoprism')],
  backup_to_storage: [liteQueryKeys.recovery(), liteQueryKeys.appActions('photoprism')],
  preview_restore: [liteQueryKeys.recovery(), liteQueryKeys.appActions('photoprism')],
  install_app: [liteQueryKeys.catalog(), liteQueryKeys.appActions('photoprism')],
  remove_app: [liteQueryKeys.catalog(), liteQueryKeys.appActions('photoprism')],
  security_check: [liteQueryKeys.security()],
  recovery_backup: [liteQueryKeys.recovery(), liteQueryKeys.appActions('photoprism')],
  restart_agent: [liteQueryKeys.fleet(), liteQueryKeys.status()],
  add_device: [liteQueryKeys.fleet(), liteQueryKeys.status()],
};

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
