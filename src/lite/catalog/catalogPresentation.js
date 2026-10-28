// The catalog is a read-only presentation of backend-projected state.
// Buckets must never turn an unknown health/route into a healthy claim.
export function catalogStateBucket(app = {}) {
  const state = String(app?.status || app?.lifecycle?.status || app?.runtime?.status || '').toLowerCase().replace(/[\s-]+/g, '_');
  const health = String(app?.health || app?.runtime?.health || '').toLowerCase();
  const route = app?.access || {};
  if (app?.installed === false || ['not_installed', 'available', 'install_available', 'uninstalled'].includes(state)) return 'not_installed';
  if (['installing', 'queued', 'starting', 'updating', 'removing', 'preparing', 'waiting'].includes(state)) return 'working';
  if (['failed', 'error', 'blocked', 'needs_attention', 'installed_stopped', 'installed_degraded', 'unavailable', 'stopped', 'unhealthy', 'state_conflict'].includes(state)
    || ['unhealthy', 'failed', 'error'].includes(health) || route.route_ready === false || route.https_ready === false || app?.runtime?.state_conflict === true) return 'attention';
  if (route.route_ready === true && route.open !== false
    && (app?.installed === true || ['ready', 'running', 'installed', 'installed_running', 'healthy'].includes(state))) return 'ready';
  return 'unknown';
}

export function sortCatalogApps(items) {
  return (Array.isArray(items) ? [...items] : []).filter((item) => item && typeof item === 'object')
    .sort((left, right) => String(left.name || left.title || left.id || '').localeCompare(String(right.name || right.title || right.id || ''))
      || String(left.id || '').localeCompare(String(right.id || '')));
}
export function filterCatalogApps(items, query, bucket = 'all') {
  const needle = String(query || '').trim().toLocaleLowerCase();
  return sortCatalogApps(items).filter((item) =>
    (bucket === 'all' || catalogStateBucket(item) === bucket)
    && (!needle || [item.name, item.title, item.id, item.description].some((value) => String(value || '').toLocaleLowerCase().includes(needle))));
}

/** Display a status summary only when it adds information beyond the app description. */
export function distinctCatalogStatusSummary(description, statusSummary) {
  const summary = String(statusSummary || '').trim();
  if (!summary) return '';
  const normalize = (value) => String(value || '').trim().replace(/\\s+/g, ' ').replace(/[.!?]+$/, '').toLocaleLowerCase();
  return normalize(description) === normalize(summary) ? '' : summary;
}
