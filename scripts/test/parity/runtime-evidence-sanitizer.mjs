const PRIVATE_IDENTITY_MARKER = '[private-identity]';

const COMMON_UI_WORDS = new Set([
  'access', 'account', 'app', 'backup', 'checking', 'control', 'device',
  'home', 'identity', 'lite', 'online', 'pocket', 'private', 'protected',
  'ready', 'recovery', 'review', 'rules', 'safety', 'security', 'server',
  'status', 'storage', 'system', 'termux', 'workspace',
]);

export function escapeRuntimeEvidenceRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function safeSensitiveCandidate(value) {
  const candidate = String(value || '').trim();
  if (!candidate || candidate.includes(PRIVATE_IDENTITY_MARKER)) return '';
  if (candidate.length < 4 || candidate.length > 256) return '';

  const normalized = candidate.toLowerCase();
  if (COMMON_UI_WORDS.has(normalized)) return '';

  const alphaOnly = /^[A-Za-z]+$/.test(candidate);
  if (alphaOnly && candidate.length < 6) return '';

  return candidate;
}

function replaceTokenBounded(value, candidate) {
  const escaped = escapeRuntimeEvidenceRegExp(candidate);
  const tokenLike = /^[A-Za-z0-9]+$/.test(candidate);
  if (!tokenLike) {
    return value.replace(
      new RegExp(escaped, 'gi'),
      PRIVATE_IDENTITY_MARKER,
    );
  }

  const pattern = new RegExp(
    `(^|[^A-Za-z0-9])${escaped}(?=$|[^A-Za-z0-9])`,
    'gi',
  );
  return value.replace(pattern, `$1${PRIVATE_IDENTITY_MARKER}`);
}

export function sanitizeRuntimeEvidenceText(value, sensitiveValues = []) {
  let sanitized = String(value || '');
  if (!sanitized || sanitized.includes(PRIVATE_IDENTITY_MARKER)) {
    // Existing markers are preserved and never recursively redacted.
    return sanitized;
  }

  const candidates = [...new Set(
    sensitiveValues
      .map(safeSensitiveCandidate)
      .filter(Boolean),
  )].sort((left, right) => right.length - left.length);

  for (const candidate of candidates) {
    sanitized = replaceTokenBounded(sanitized, candidate);
  }

  return sanitized
    .replace(/-----BEGIN [A-Z ]*PRIVATE KEY-----/gi, '[redacted-key]')
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]{12,}/gi, 'Bearer [redacted]')
    .replace(/\b(password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s,]+/gi, '$1=[redacted]')
    .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, PRIVATE_IDENTITY_MARKER)
    .replace(/\b(?:10|127|169\.254|172\.(?:1[6-9]|2\d|3[01])|192\.168|100)\.(?:\d{1,3}\.){2}\d{1,3}\b/g, '[private-address]')
    .replace(/[A-Za-z0-9.-]+\.ts\.net\b/gi, '[tailnet-host]')
    .replace(/\/data\/data\/com\.termux\/files\/(?:home|usr)(?:\/[^\s]*)?/gi, '[private-path]')
    .replace(/\/home\/[^/\s]+\/[^\s]*/g, '[private-path]')
    .replace(/((?:nats|https?):\/\/)[^\s/@]+:[^\s@]+@/gi, '$1[redacted]@')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 12_000);
}
