export const LITE_XSTATE_WORKFLOW_ONLY = true;
export const LITE_XSTATE_NO_BROWSER_ACTION_QUEUE = true;
export const LITE_XSTATE_NO_OPTIMISTIC_SUCCESS = true;

export function isBackendReachable(context = {}) {
  return context.backendReachable !== false && context.savedStateOnly !== true;
}

export function isSavedStateOnly(context = {}) {
  return context.savedStateOnly === true || context.backendReachable === false;
}

export function requiresConfirmation(context = {}) {
  return context.confirmationRequired === true || context.destructive === true || ['remove_app', 'restore'].includes(String(context.actionId || '').toLowerCase());
}

export function acceptedReference(payload = {}) {
  return payload.command_id || payload.operation_id || payload.job_id || payload.run_id || payload.backup_id || payload.preview_id || payload.reference || null;
}

export function friendlyFlowError(error, fallback = 'Reconnect to continue.') {
  const value = error?.payload?.summary || error?.payload?.detail?.summary || error?.message || fallback;
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}

export function writeBlockedReason({ backendReachable = true, savedStateOnly = false, disabledReason = '' } = {}) {
  if (savedStateOnly) return 'Saved state only. Reconnect to continue.';
  if (backendReachable === false) return 'Pocket Lab is not reachable.';
  return disabledReason || '';
}
