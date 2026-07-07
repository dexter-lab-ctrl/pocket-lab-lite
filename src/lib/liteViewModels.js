const UNSAFE_VIEW_MODEL_KEY_PATTERN = /token|secret|password|credential|api[_-]?key|apikey|hash|private[_-]?key|invite[_-]?token|bootstrap|command[_-]?payload|raw[_-]?(log|logs|path|evidence)|evidence[_-]?path|private[_-]?path|restic[_-]?password|vault|unseal|bearer|authorization|nats/i;
const UNSAFE_VIEW_MODEL_VALUE_PATTERN = /(bearer\s+[^\s]+|token=|password=|api[_-]?key=|secret=|authorization:\s*bearer|nats:\/\/[^\s/]+:[^\s@]+@|-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----)/i;
const MAX_DETAIL_ITEMS = 6;
const MAX_TECHNICAL_ITEMS = 8;

export const LITE_APP_CATALOG_VIEW_MODEL_VERSION = 'lite-app-catalog-s3-v1';

const LIVE_ACTION_STATUSES = new Set([
  'queued',
  'pending',
  'accepted',
  'running',
  'working',
  'executing',
  'waiting',
  'in_progress',
]);

const TERMINAL_ACTION_STATUSES = new Set([
  'ready',
  'succeeded',
  'success',
  'completed',
  'complete',
  'done',
  'verified',
  'failed',
  'failure',
  'error',
  'blocked',
  'paused',
  'cancelled',
  'canceled',
  'review',
  'needs_attention',
  'not_ready',
  'not_supported',
  'unsupported',
  'disabled',
]);

const ACTION_CATEGORY_ORDER = ['media', 'safety', 'recovery', 'setup', 'danger'];

function normalizeStatus(value = '') {
  return String(value || '').toLowerCase().replace(/[\s-]+/g, '_');
}

function isObject(value) {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function snapshotMeta(payload) {
  return isObject(payload?.__liteSnapshot) ? payload.__liteSnapshot : null;
}

function withSnapshotMeta(input, output) {
  if (!isObject(output)) return output;
  const meta = snapshotMeta(input);
  return meta && !output.__liteSnapshot ? { ...output, __liteSnapshot: meta } : output;
}

function safeString(value = '', fallback = '') {
  const next = String(value || fallback || '').trim();
  if (!next) return '';
  return UNSAFE_VIEW_MODEL_VALUE_PATTERN.test(next) ? '[hidden]' : next.slice(0, 500);
}

function safeList(items, fallback = []) {
  const values = Array.isArray(items) ? items : fallback;
  return values
    .filter(Boolean)
    .map((item) => safeString(item))
    .filter((item) => item && item !== '[hidden]')
    .slice(0, MAX_DETAIL_ITEMS);
}

function safeTechnicalList(items) {
  return safeList(items, []).slice(0, MAX_TECHNICAL_ITEMS);
}

function copySafeKeys(source = {}, keys = []) {
  if (!isObject(source)) return {};
  return keys.reduce((safe, key) => {
    if (UNSAFE_VIEW_MODEL_KEY_PATTERN.test(key)) return safe;
    const value = source[key];
    if (value !== undefined && value !== null) safe[key] = value;
    return safe;
  }, {});
}

function actionCategory(actionId = '', action = {}) {
  const category = String(action?.category || '').replace('app_setup', 'setup');
  if (category) return category;
  if (['connect_photos', 'import_photos'].includes(actionId)) return 'media';
  if (actionId === 'check_app') return 'safety';
  if (['backup_app', 'preview_restore', 'backup_to_storage', 'repair_app'].includes(actionId)) return 'recovery';
  if (['install_app', 'update_app'].includes(actionId)) return 'setup';
  if (actionId === 'remove_app') return 'danger';
  if (['open', 'open_full_screen'].includes(actionId)) return 'access';
  return 'setup';
}

function normalizeProgress(progress = null) {
  if (!isObject(progress)) return null;
  return copySafeKeys(progress, [
    'running',
    'status',
    'state',
    'phase',
    'step',
    'percent',
    'indeterminate',
    'synthetic',
    'updated_at',
  ]);
}

function normalizeResult(result = null) {
  if (!isObject(result)) return null;
  return copySafeKeys(result, [
    'status',
    'summary',
    'message',
    'receipt_id',
    'backend_only',
    'action_id',
    'started_at',
    'completed_at',
    'updated_at',
  ]);
}

function normalizeTroubleshooting(troubleshooting = null) {
  if (!isObject(troubleshooting)) return null;
  return copySafeKeys(troubleshooting, [
    'available',
    'saved',
    'backend_only',
    'debug_only',
    'status',
    'summary',
    'receipt_id',
    'updated_at',
  ]);
}

function normalizeActionDetails(details = null, fallback = {}) {
  if (!isObject(details)) return null;
  const saved = isObject(details.saved_for_troubleshooting)
    ? normalizeTroubleshooting(details.saved_for_troubleshooting)
    : null;
  return {
    title: safeString(details.title, fallback.label || fallback.id || 'Action details'),
    status: normalizeStatus(details.status || fallback.status || 'ready'),
    summary: safeString(details.summary || fallback.summary || ''),
    what_happened: safeList(details.what_happened),
    what_changed: safeList(details.what_changed),
    what_needs_attention: safeList(details.what_needs_attention),
    what_did_not_happen: safeList(details.what_did_not_happen),
    what_would_happen_after_confirmation: safeList(details.what_would_happen_after_confirmation),
    what_will_not_happen_by_default: safeList(details.what_will_not_happen_by_default),
    saved_for_troubleshooting: saved || { backend_only: true, saved: false, summary: 'Backend troubleshooting stays protected.' },
    next_step: safeString(details.next_step || details.next_step_summary || ''),
    last_result: safeString(details.last_result || fallback.last_result || ''),
    first_ran_at: details.first_ran_at || fallback.first_ran_at || null,
    last_ran_at: details.last_ran_at || fallback.last_ran_at || null,
    run_count: Number(details.run_count || fallback.run_count || 0),
    has_run_evidence: Boolean(details.has_run_evidence || fallback.receipt_id || fallback.evidence_ref || saved?.saved),
    technical_details: safeTechnicalList(details.technical_details),
    status_checks: Array.isArray(details.status_checks) ? details.status_checks.slice(0, 6).map((item) => copySafeKeys(item, ['id', 'label', 'status', 'summary'])) : [],
  };
}

export function isLiteAppActionLive(action = {}) {
  if (!isObject(action)) return false;
  const progress = action.progress || {};
  const values = [
    action.status,
    action.state,
    action.phase,
    progress.status,
    progress.state,
    progress.phase,
    action.result?.status,
  ].map(normalizeStatus);
  const live = Boolean(action.running || action.operation_running || progress.running)
    || values.some((value) => LIVE_ACTION_STATUSES.has(value));
  const terminal = values.some((value) => TERMINAL_ACTION_STATUSES.has(value));
  return Boolean(live && !terminal);
}

export function normalizeLiteAppAction(action = {}, actionId = '') {
  if (!isObject(action)) return null;
  const id = safeString(action.id || action.action_id || actionId);
  if (!id) return null;
  const normalized = {
    id,
    action_id: id,
    app_id: safeString(action.app_id || 'photoprism'),
    label: safeString(action.label || id.replace(/_/g, ' ')),
    category: actionCategory(id, action),
    category_label: safeString(action.category_label || ''),
    summary: safeString(action.summary || action.description || ''),
    enabled: action.enabled !== false,
    disabled_reason: safeString(action.disabled_reason || action.reason || ''),
    status: normalizeStatus(action.status || action.state || 'ready'),
    risk: safeString(action.risk || ''),
    confirmation_required: Boolean(action.confirmation_required),
    destructive: Boolean(action.destructive),
    execution_owner: safeString(action.execution_owner || ''),
    progress: normalizeProgress(action.progress),
    result: normalizeResult(action.result || action.latest_result),
    latest_result: normalizeResult(action.latest_result),
    details: normalizeActionDetails(action.details, action),
    troubleshooting: normalizeTroubleshooting(action.troubleshooting),
    last_result: safeString(action.last_result || action.result?.summary || ''),
    first_ran_at: action.first_ran_at || action.first_run_at || null,
    last_ran_at: action.last_ran_at || action.last_run_at || action.updated_at || null,
    run_count: Number(action.run_count || 0),
    receipt_id: safeString(action.receipt_id || action.result?.receipt_id || ''),
    evidence_ref: safeString(action.evidence_ref || ''),
  };
  normalized.live = isLiteAppActionLive(normalized);
  return normalized;
}

function collectActions(payload = {}) {
  const actions = {};
  if (isObject(payload.actions)) {
    Object.entries(payload.actions).forEach(([actionId, action]) => {
      const normalized = normalizeLiteAppAction({ id: actionId, ...(action || {}) }, actionId);
      if (normalized) actions[normalized.id] = normalized;
    });
  }
  if (Array.isArray(payload.action_list)) {
    payload.action_list.forEach((action) => {
      const actionId = action?.id || action?.action_id;
      const normalized = normalizeLiteAppAction({ ...(actions[actionId] || {}), ...(action || {}), id: actionId }, actionId);
      if (normalized) actions[normalized.id] = normalized;
    });
  }
  if (isObject(payload.latest_results)) {
    Object.entries(payload.latest_results).forEach(([actionId, result]) => {
      const base = actions[actionId] || normalizeLiteAppAction({ id: actionId }, actionId);
      if (base) {
        base.result = { ...(base.result || {}), ...(normalizeResult(result) || {}) };
        base.latest_result = normalizeResult(result);
        actions[actionId] = base;
      }
    });
  }
  if (isObject(payload.latest_troubleshooting_records)) {
    Object.entries(payload.latest_troubleshooting_records).forEach(([actionId, record]) => {
      const base = actions[actionId] || normalizeLiteAppAction({ id: actionId }, actionId);
      if (base) {
        base.troubleshooting = normalizeTroubleshooting(record) || base.troubleshooting;
        actions[actionId] = base;
      }
    });
  }
  return actions;
}

function groupActions(actions = {}) {
  const grouped = new Map();
  Object.values(actions).forEach((action) => {
    const category = action.category || 'setup';
    if (category === 'access') return;
    if (!grouped.has(category)) grouped.set(category, { id: category, actions: [] });
    grouped.get(category).actions.push(action);
  });
  return ACTION_CATEGORY_ORDER.map((category) => grouped.get(category)).filter(Boolean);
}

function normalizeMediaSummary(media = null) {
  if (!isObject(media)) return null;
  return {
    status: normalizeStatus(media.status || media.state || ''),
    summary: safeString(media.summary || ''),
    operation_running: Boolean(media.operation_running),
    mapping_count: Number(media.mapping_count || 0),
    last_imported_at: media.last_imported_at || null,
    last_import: isObject(media.last_import)
      ? {
        status: normalizeStatus(media.last_import.status || media.last_import.phase || ''),
        phase: normalizeStatus(media.last_import.phase || media.last_import.status || ''),
        summary: safeString(media.last_import.summary || ''),
        completed_at: media.last_import.completed_at || null,
        progress: normalizeProgress(media.last_import.progress),
      }
      : null,
  };
}

export function selectPhotoPrismActionsView(payload = {}) {
  if (payload?.view_model === 'photoprism-actions-s3-v1') return payload;
  const actions = collectActions(payload || {});
  const actionList = Object.values(actions);
  const latestResults = actionList.reduce((items, action) => {
    if (action.latest_result || action.result) items[action.id] = action.latest_result || action.result;
    return items;
  }, {});
  const latestTroubleshooting = actionList.reduce((items, action) => {
    if (action.troubleshooting) items[action.id] = action.troubleshooting;
    return items;
  }, {});
  const output = {
    view_model: 'photoprism-actions-s3-v1',
    version: LITE_APP_CATALOG_VIEW_MODEL_VERSION,
    app_id: safeString(payload?.app_id || 'photoprism'),
    app_label: safeString(payload?.app_label || payload?.name || 'PhotoPrism'),
    status: normalizeStatus(payload?.status || 'ready'),
    actions,
    action_list: actionList,
    action_groups: groupActions(actions),
    latest_results: latestResults,
    latest_troubleshooting_records: latestTroubleshooting,
    media: normalizeMediaSummary(payload?.media),
    updated_at: payload?.updated_at || payload?.checked_at || null,
    checked_at: payload?.checked_at || payload?.updated_at || null,
    live_action_ids: actionList.filter(isLiteAppActionLive).map((action) => action.id),
  };
  return withSnapshotMeta(payload, output);
}

function safeStorageMappings(storage = {}) {
  const mappings = Array.isArray(storage?.mappings) ? storage.mappings : [];
  return mappings.slice(0, 12).map((mapping) => copySafeKeys(mapping, [
    'mapping_id',
    'id',
    'label',
    'source_label',
    'mode_label',
    'mode',
    'target',
    'status',
    'source_type',
    'device_id',
    'device_name',
    'created_at',
    'updated_at',
  ]));
}

function selectLifecycleActions(actions = {}) {
  if (!isObject(actions)) return {};
  return Object.entries(actions).reduce((selected, [actionId, action]) => {
    const normalized = normalizeLiteAppAction({ id: actionId, ...(action || {}) }, actionId);
    if (normalized) selected[actionId] = normalized;
    return selected;
  }, {});
}

function selectLifecycleSummary(lifecycle = {}) {
  if (!isObject(lifecycle)) return null;
  return {
    status: normalizeStatus(lifecycle.status || lifecycle.state || 'checking'),
    summary: safeString(lifecycle.summary || ''),
    checked_at: lifecycle.checked_at || lifecycle.updated_at || null,
    updated_at: lifecycle.updated_at || lifecycle.checked_at || null,
    storage: isObject(lifecycle.storage) ? copySafeKeys(lifecycle.storage, ['status', 'summary', 'mapping_count']) : {},
    security: isObject(lifecycle.security) ? copySafeKeys(lifecycle.security, ['status', 'summary', 'updated_at', 'last_checked_at']) : {},
    backup: isObject(lifecycle.backup) ? copySafeKeys(lifecycle.backup, ['status', 'summary', 'target_available', 'target_device_id', 'target_id', 'updated_at']) : {},
    update: isObject(lifecycle.update) ? copySafeKeys(lifecycle.update, ['status', 'summary', 'readiness_status', 'pending', 'updated_at']) : {},
    media: normalizeMediaSummary(lifecycle.media) || {},
    attention: Array.isArray(lifecycle.attention)
      ? lifecycle.attention.slice(0, 4).map((item) => copySafeKeys(item, ['id', 'title', 'summary', 'status']))
      : [],
    actions: selectLifecycleActions(lifecycle.actions),
  };
}

export function selectLiteCatalogAppSummary(app = {}) {
  const storage = isObject(app.storage) ? app.storage : {};
  const lifecycle = selectLifecycleSummary(app.lifecycle);
  const access = isObject(app.access) ? app.access : {};
  const runtime = isObject(app.runtime) ? app.runtime : {};
  const actions = isObject(app.actions) ? app.actions : {};
  return {
    id: safeString(app.id || 'photoprism'),
    name: safeString(app.name || app.label || 'PhotoPrism'),
    label: safeString(app.label || app.name || 'PhotoPrism'),
    category: safeString(app.category || 'Photos'),
    summary: safeString(app.summary || ''),
    status: normalizeStatus(app.status || app.health || app.install_state || 'unknown'),
    health: normalizeStatus(app.health || runtime.health || ''),
    installed: Boolean(app.installed || app.install_state === 'installed' || app.status === 'ready'),
    install_state: normalizeStatus(app.install_state || ''),
    actions: copySafeKeys(actions, ['open', 'install', 'remove', 'retry']),
    access: copySafeKeys(access, ['route_ready', 'open_url', 'route', 'url', 'message', 'https_ready', 'open']),
    runtime: copySafeKeys(runtime, ['route', 'url', 'health', 'process', 'status', 'checked_at']),
    target: isObject(app.target)
      ? {
        default_node_id: safeString(app.target.default_node_id || ''),
        supported_roles: Array.isArray(app.target.supported_roles) ? app.target.supported_roles.slice(0, 4) : [],
        eligible_devices: Array.isArray(app.target.eligible_devices)
          ? app.target.eligible_devices.slice(0, 4).map((device) => copySafeKeys(device, ['id', 'name', 'role', 'status']))
          : [],
      }
      : {},
    host_device_name: safeString(app.host_device_name || app.device_label || ''),
    storage: {
      summary: safeString(storage.summary || ''),
      mapping_count: Number(storage.mapping_count || safeStorageMappings(storage).length || 0),
      mappings: safeStorageMappings(storage),
    },
    media: normalizeMediaSummary(app.media) || {},
    security_profile: isObject(app.security_profile) ? copySafeKeys(app.security_profile, ['status', 'label', 'summary', 'updated_at']) : {},
    backup_profile: isObject(app.backup_profile) ? copySafeKeys(app.backup_profile, ['status', 'label', 'summary', 'media', 'updated_at']) : {},
    device_relationships: isObject(app.device_relationships) ? copySafeKeys(app.device_relationships, ['storage_devices_available', 'app_host_id', 'app_host_label']) : {},
    available_device_capabilities: isObject(app.available_device_capabilities) ? copySafeKeys(app.available_device_capabilities, ['media_storage']) : {},
    storage_devices: Array.isArray(app.storage_devices)
      ? app.storage_devices.slice(0, 6).map((device) => copySafeKeys(device, ['id', 'name', 'role', 'ready', 'status']))
      : [],
    lifecycle,
    last_operation: isObject(app.last_operation) ? copySafeKeys(app.last_operation, ['status', 'summary', 'updated_at', 'completed_at']) : null,
    progress: normalizeProgress(app.progress),
    updated_at: app.updated_at || app.checked_at || runtime.checked_at || null,
    checked_at: app.checked_at || app.updated_at || runtime.checked_at || null,
    health_chips: [
      { id: 'route', label: access.route_ready ? 'Route ready' : 'Route checking', status: access.route_ready ? 'ready' : 'checking' },
      { id: 'photos', label: storage.mapping_count || safeStorageMappings(storage).length ? 'Photos connected' : 'Photos not connected', status: storage.mapping_count || safeStorageMappings(storage).length ? 'ready' : 'checking' },
      { id: 'safety', label: app.security_profile?.label || lifecycle?.security?.summary || 'Check app', status: normalizeStatus(app.security_profile?.status || lifecycle?.security?.status || 'checking') },
      { id: 'backup', label: app.backup_profile?.label || lifecycle?.backup?.summary || 'Backup ready', status: normalizeStatus(app.backup_profile?.status || lifecycle?.backup?.status || 'checking') },
    ],
  };
}

export function selectCatalogSummaryView(payload = {}) {
  if (payload?.view_model === 'catalog-summary-s3-v1') return payload;
  const sourceApps = Array.isArray(payload?.apps) ? payload.apps : Array.isArray(payload?.items) ? payload.items : [];
  const apps = sourceApps.map(selectLiteCatalogAppSummary);
  const output = {
    view_model: 'catalog-summary-s3-v1',
    version: LITE_APP_CATALOG_VIEW_MODEL_VERSION,
    status: normalizeStatus(payload?.status || 'healthy'),
    count: Number(payload?.count || apps.length || 0),
    apps,
    items: apps,
    access: isObject(payload?.access) ? copySafeKeys(payload.access, ['https_ready', 'route_ready', 'open', 'message', 'updated_at']) : {},
    updated_at: payload?.updated_at || payload?.checked_at || null,
    checked_at: payload?.checked_at || payload?.updated_at || null,
  };
  return withSnapshotMeta(payload, output);
}

export function isLiteAppActionsViewLive(payload = {}) {
  if (!payload) return false;
  if (Array.isArray(payload.live_action_ids) && payload.live_action_ids.length > 0) return true;
  const actions = collectActions(payload);
  const actionLive = Object.values(actions).some(isLiteAppActionLive);
  const media = payload.media || {};
  return Boolean(actionLive || media.operation_running || isLiteAppActionLive(media.last_import || {}));
}

export function selectPhotoPrismManageView({ catalog, appActions, recoverySummary = null, securitySummary = null } = {}) {
  const catalogView = selectCatalogSummaryView(catalog || {});
  const actionsView = selectPhotoPrismActionsView(appActions || {});
  const photoprism = catalogView.apps.find((app) => app.id === 'photoprism') || catalogView.apps[0] || null;
  return {
    view_model: 'photoprism-manage-s3-v1',
    version: LITE_APP_CATALOG_VIEW_MODEL_VERSION,
    app: photoprism,
    action_groups: actionsView.action_groups,
    actions: actionsView.actions,
    live_action_ids: actionsView.live_action_ids,
    active_live_action: actionsView.live_action_ids[0] ? actionsView.actions[actionsView.live_action_ids[0]] : null,
    media: actionsView.media || photoprism?.media || null,
    recovery: recoverySummary ? copySafeKeys(recoverySummary, ['status', 'summary', 'updated_at']) : photoprism?.lifecycle?.backup || null,
    security: securitySummary ? copySafeKeys(securitySummary, ['status', 'summary', 'updated_at']) : photoprism?.lifecycle?.security || null,
    updated_at: actionsView.updated_at || catalogView.updated_at || null,
  };
}
