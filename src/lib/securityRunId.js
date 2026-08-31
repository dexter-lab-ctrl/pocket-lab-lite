export const SECURITY_RUN_ID_MAX_LENGTH = 120;

// Backend Security run IDs are opaque correlation identifiers. They may carry
// case-sensitive timestamp or entropy segments, so only remove transport
// whitespace and apply the existing bounded UI-storage limit.
export function sanitizeSecurityRunId(value = '', fallback = '') {
  return String(value || fallback).trim().slice(0, SECURITY_RUN_ID_MAX_LENGTH);
}
