const BACKEND_LANGUAGE_REPLACEMENTS = Object.freeze([
  [/\bNATS(?:\/JetStream)?\b/gi, 'Pocket Lab connection'],
  [/\bJetStream\b/gi, 'Pocket Lab connection'],
  [/\bFastAPI\b/gi, 'Pocket Lab'],
  [/\bworker(?:s)?\b/gi, 'Pocket Lab service'],
  [/\bsupervisor(?:s)?\b/gi, 'recovery service'],
  [/\bprojection(?:s)?\b/gi, 'status information'],
  [/\bsnapshot(?:s)?\b/gi, 'saved information'],
  [/\bpolling\b/gi, 'refreshing'],
  [/\bpayload(?:s)?\b/gi, 'request details'],
  [/\bconsumer(?:s)?\b/gi, 'connection service'],
  [/\bdurable\b/gi, 'reliable'],
  [/\bendpoint(?:s)?\b/gi, 'service'],
  [/\bSQLite\b/gi, 'local records'],
  [/\bETag(?:s)?\b/gi, 'freshness marker'],
]);

export const LITE_DEFAULT_UI_FORBIDDEN_TERMS = Object.freeze([
  'nats',
  'jetstream',
  'fastapi',
  'worker picked it up',
  'backend-owned',
  'projection stale',
  'polling:',
  'etag',
  'sqlite',
  'command payload',
  'durable consumer',
]);

export function friendlyLiteText(value, fallback = '') {
  let text = String(value ?? '').trim();
  if (!text) return fallback;
  for (const [pattern, replacement] of BACKEND_LANGUAGE_REPLACEMENTS) {
    text = text.replace(pattern, replacement);
  }
  return text;
}

export function liteFreshnessPresentation({
  saved = false,
  stale = false,
  refreshing = false,
  lastUpdatedLabel = '',
  backendReachable = true,
} = {}) {
  const when = String(lastUpdatedLabel || '').trim();
  if (refreshing) {
    return { state: 'refreshing', label: 'Refreshing…', detail: 'Keeping the current view visible while Pocket Lab checks for updates.' };
  }
  if (saved || !backendReachable) {
    return {
      state: 'saved',
      label: when ? `Showing saved information · ${when}` : 'Showing saved information',
      detail: 'Reconnect to confirm the latest state.',
    };
  }
  if (stale) {
    return {
      state: 'stale',
      label: when ? `Last updated ${when}` : 'Information may be out of date',
      detail: 'Pocket Lab will refresh this when a current reading is available.',
    };
  }
  return {
    state: 'fresh',
    label: when ? `Updated ${when}` : 'Up to date',
    detail: 'Current Pocket Lab information.',
  };
}

export function normalizeTechnicalFacts(facts = []) {
  return (Array.isArray(facts) ? facts : [])
    .filter(Boolean)
    .map((item, index) => ({
      id: item.id || item.label || `fact-${index + 1}`,
      label: friendlyLiteText(item.label, 'Detail'),
      value: friendlyLiteText(item.value, 'Not reported'),
      note: friendlyLiteText(item.note, ''),
      tone: item.tone || 'neutral',
    }))
    .filter((item) => item.label && item.value);
}

export function normalizeTimelineItems(items = []) {
  return (Array.isArray(items) ? items : [])
    .filter(Boolean)
    .map((item, index) => ({
      id: item.id || item.event_id || item.created_at || `history-${index + 1}`,
      title: friendlyLiteText(item.title || item.label || item.summary, 'Pocket Lab update'),
      summary: friendlyLiteText(item.summary || item.description || item.detail, ''),
      time: item.time || item.created_at || item.updated_at || '',
      state: item.state || item.status || 'neutral',
    }));
}

export function actionOutcomePresentation(result = {}, {
  fallbackTitle = 'Action completed',
  fallbackSummary = 'Pocket Lab finished the requested action.',
} = {}) {
  const changed = result.changed ?? result.change_made;
  const protectedItems = Array.isArray(result.protected) ? result.protected : [];
  return {
    title: friendlyLiteText(result.title || result.headline, fallbackTitle),
    summary: friendlyLiteText(result.summary || result.message, fallbackSummary),
    whatChanged: friendlyLiteText(
      result.what_changed || (changed === false ? 'Nothing changed.' : changed === true ? 'The requested change was applied.' : ''),
      '',
    ),
    whatDidNotHappen: friendlyLiteText(result.what_did_not_happen || '', ''),
    protectedSummary: protectedItems.length
      ? protectedItems.map((item) => friendlyLiteText(item)).join(' · ')
      : friendlyLiteText(result.protected_summary || '', ''),
    nextAction: friendlyLiteText(result.next_action || result.nextAction || '', ''),
  };
}

export function confirmationPresentation({
  title,
  summary,
  will = [],
  willNot = [],
  reversible = '',
  availability = '',
} = {}) {
  return {
    title: friendlyLiteText(title, 'Confirm this change'),
    summary: friendlyLiteText(summary, 'Review what Pocket Lab will do before continuing.'),
    will: (Array.isArray(will) ? will : []).map((item) => friendlyLiteText(item)).filter(Boolean),
    willNot: (Array.isArray(willNot) ? willNot : []).map((item) => friendlyLiteText(item)).filter(Boolean),
    reversible: friendlyLiteText(reversible, ''),
    availability: friendlyLiteText(availability, ''),
  };
}

export function assertPlainLanguage(text = '') {
  const normalized = String(text || '').toLowerCase();
  return LITE_DEFAULT_UI_FORBIDDEN_TERMS.filter((term) => normalized.includes(term));
}
