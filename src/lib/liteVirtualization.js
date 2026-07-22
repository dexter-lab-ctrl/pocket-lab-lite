export const LITE_VIRTUALIZATION_SCHEMA_VERSION = 1;
export const LITE_VIRTUAL_SCROLL_STATE_LIMIT = 24;

export const LITE_VIRTUALIZATION_THRESHOLDS = Object.freeze({
  default: Object.freeze({ enter: 40, exit: 32, compactEnter: 32, compactExit: 26 }),
  securityHistory: Object.freeze({ enter: 36, exit: 28, compactEnter: 30, compactExit: 24 }),
  recoveryHistory: Object.freeze({ enter: 24, exit: 18, compactEnter: 22, compactExit: 16 }),
  appActionHistory: Object.freeze({ enter: 30, exit: 22, compactEnter: 26, compactExit: 20 }),
  devices: Object.freeze({ enter: 72, exit: 56, compactEnter: 56, compactExit: 44 }),
});

const STABLE_ID_FIELDS = Object.freeze([
  'run_id',
  'backup_id',
  'restore_id',
  'operation_id',
  'command_id',
  'device_id',
  'snapshot_id',
  'finding_id',
  'receipt_id',
  'id',
]);

const scrollState = new Map();

function finiteInteger(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.max(0, Math.floor(parsed)) : fallback;
}

function safeToken(value = '') {
  return String(value ?? '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._:-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 120);
}

function stableIdToken(value = '') {
  const raw = String(value ?? '').trim().slice(0, 240);
  if (!raw) return '';
  const readable = safeToken(raw).slice(0, 48) || 'id';
  return `${hashText(raw)}-${readable}`;
}

function hashText(value = '') {
  let hash = 2166136261;
  const text = String(value || '');
  for (let index = 0; index < text.length; index += 1) {
    hash ^= text.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

function fallbackFingerprint(item = {}, domain = 'row') {
  const object = item && typeof item === 'object' ? item : { value: item };
  const parts = [
    domain,
    object.title,
    object.label,
    object.summary,
    object.status,
    object.profile,
    object.completed_at,
    object.updated_at,
    object.created_at,
    object.started_at,
    object.name,
    object.role,
  ].map((value) => String(value ?? '').slice(0, 180));
  return `${safeToken(domain) || 'row'}-fallback-${hashText(parts.join('|'))}`;
}

export function liteVirtualThreshold(domain = 'default', compact = false) {
  const policy = LITE_VIRTUALIZATION_THRESHOLDS[domain] || LITE_VIRTUALIZATION_THRESHOLDS.default;
  return compact
    ? { enter: policy.compactEnter, exit: policy.compactExit }
    : { enter: policy.enter, exit: policy.exit };
}

export function selectLiteVirtualMode({
  count = 0,
  domain = 'default',
  compact = false,
  previousMode = false,
  disabled = false,
} = {}) {
  if (disabled) return false;
  const safeCount = finiteInteger(count);
  const threshold = liteVirtualThreshold(domain, compact);
  if (previousMode) return safeCount > threshold.exit;
  return safeCount >= threshold.enter;
}

export function liteStableRowKey(item, { domain = 'row', getKey } = {}) {
  if (typeof getKey === 'function') {
    const custom = stableIdToken(getKey(item));
    if (custom) return `${safeToken(domain) || 'row'}:custom:${custom}`;
  }
  const object = item && typeof item === 'object' ? item : null;
  if (object) {
    for (const field of STABLE_ID_FIELDS) {
      const value = stableIdToken(object[field]);
      if (value) return `${safeToken(domain) || 'row'}:${field}:${value}`;
    }
  }
  return fallbackFingerprint(item, domain);
}

export function normalizeLiteVirtualRows(items = [], { domain = 'row', getKey } = {}) {
  const rows = [];
  const keys = [];
  const seen = new Set();
  const fallbackOccurrences = new Map();
  let duplicateCount = 0;
  let fallbackCount = 0;
  let fallbackCollisionCount = 0;

  (Array.isArray(items) ? items : []).forEach((item) => {
    const baseKey = liteStableRowKey(item, { domain, getKey });
    const fallback = baseKey.includes(':fallback-') || baseKey.includes('-fallback-');
    if (fallback) {
      fallbackCount += 1;
      const occurrence = fallbackOccurrences.get(baseKey) || 0;
      fallbackOccurrences.set(baseKey, occurrence + 1);
      const key = occurrence ? `${baseKey}:occurrence-${occurrence + 1}` : baseKey;
      if (occurrence) fallbackCollisionCount += 1;
      seen.add(key);
      rows.push(item);
      keys.push(key);
      return;
    }
    if (seen.has(baseKey)) {
      duplicateCount += 1;
      return;
    }
    seen.add(baseKey);
    rows.push(item);
    keys.push(baseKey);
  });

  return {
    rows,
    keys,
    duplicateCount,
    fallbackCount,
    fallbackCollisionCount,
  };
}

export function mergeLiteCursorPages(pages = [], {
  domain = 'history',
  getRows = (page) => page?.history || page?.items || page?.backups || [],
  getKey,
} = {}) {
  const merged = [];
  (Array.isArray(pages) ? pages : []).forEach((page) => {
    const pageRows = getRows(page);
    if (Array.isArray(pageRows)) merged.push(...pageRows);
  });
  return normalizeLiteVirtualRows(merged, { domain, getKey });
}

export function createLiteCursorRequestGuard() {
  const active = new Set();
  return {
    begin(cursor = 'first') {
      const key = safeToken(cursor || 'first');
      if (active.has(key)) return false;
      active.add(key);
      return true;
    },
    finish(cursor = 'first') {
      active.delete(safeToken(cursor || 'first'));
    },
    clear() {
      active.clear();
    },
    size() {
      return active.size;
    },
  };
}

export function liteVirtualScrollKey(domain = 'list', datasetKey = 'default') {
  return `${safeToken(domain) || 'list'}::${safeToken(datasetKey) || 'default'}`;
}

export function readLiteVirtualScrollState(domain = 'list', datasetKey = 'default') {
  const key = liteVirtualScrollKey(domain, datasetKey);
  const record = scrollState.get(key);
  if (!record) return 0;
  record.touchedAt = Date.now();
  return finiteInteger(record.offset);
}

export function saveLiteVirtualScrollState(domain = 'list', datasetKey = 'default', offset = 0) {
  const key = liteVirtualScrollKey(domain, datasetKey);
  scrollState.set(key, { offset: finiteInteger(offset), touchedAt: Date.now() });
  if (scrollState.size > LITE_VIRTUAL_SCROLL_STATE_LIMIT) {
    const oldest = [...scrollState.entries()]
      .sort((left, right) => left[1].touchedAt - right[1].touchedAt)
      .slice(0, scrollState.size - LITE_VIRTUAL_SCROLL_STATE_LIMIT);
    oldest.forEach(([oldKey]) => scrollState.delete(oldKey));
  }
  return key;
}

export function clearLiteVirtualScrollState(domain = '', datasetKey = '') {
  if (!domain && !datasetKey) {
    scrollState.clear();
    return;
  }
  scrollState.delete(liteVirtualScrollKey(domain, datasetKey));
}

export function liteVirtualizationDiagnostics({
  domain = 'list',
  enabled = false,
  loadedCount = 0,
  hasMore = false,
  savedState = false,
  duplicateCount = 0,
  fallbackCount = 0,
  fallbackCollisionCount = 0,
} = {}) {
  return {
    schema_version: LITE_VIRTUALIZATION_SCHEMA_VERSION,
    domain: safeToken(domain) || 'list',
    virtualization_enabled: Boolean(enabled),
    loaded_row_count: finiteInteger(loadedCount),
    next_page_available: Boolean(hasMore && !savedState),
    saved_state: Boolean(savedState),
    duplicate_row_count: finiteInteger(duplicateCount),
    fallback_key_count: finiteInteger(fallbackCount),
    fallback_collision_count: finiteInteger(fallbackCollisionCount),
  };
}
