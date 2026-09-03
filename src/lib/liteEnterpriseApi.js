const API_BASE = (import.meta.env.VITE_POCKETLAB_API_BASE || '').replace(/\/$/, '');

function endpoint(path) {
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`;
}

function csrfCookie() {
  if (typeof document === 'undefined') return '';
  for (const name of ['__Host-pocketlab_csrf', 'pocketlab_csrf']) {
    const prefix = `${encodeURIComponent(name)}=`;
    const match = String(document.cookie || '').split(';').map((item) => item.trim()).find((item) => item.startsWith(prefix));
    if (match) return decodeURIComponent(match.slice(prefix.length));
  }
  return '';
}

async function request(path, { method = 'GET', body } = {}) {
  const upper = String(method).toUpperCase();
  if (upper !== 'GET' && typeof navigator !== 'undefined' && navigator.onLine === false) {
    const error = new Error('Pocket Lab is not reachable. Reconnect before changing Identity or Rules.');
    error.status = 0;
    error.payload = { status: 'offline', summary: 'Pocket Lab is not reachable. Reconnect before changing Identity or Rules.' };
    throw error;
  }
  let response;
  try {
    response = await fetch(endpoint(path), {
      method: upper,
      credentials: 'same-origin',
      cache: 'no-store',
      headers: {
        Accept: 'application/json',
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(upper === 'GET' ? {} : csrfCookie() ? { 'X-Pocket-Lab-CSRF': csrfCookie() } : {}),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
  } catch (networkError) {
    const error = new Error('Pocket Lab is not reachable. Identity and Rules authority cannot be refreshed.');
    error.status = 0;
    error.payload = { status: 'unreachable', summary: 'Pocket Lab is not reachable. Identity and Rules authority cannot be refreshed.' };
    error.cause = networkError;
    throw error;
  }
  const text = await response.text();
  let payload = {};
  try { payload = text ? JSON.parse(text) : {}; }
  catch (_error) { payload = { summary: 'Pocket Lab returned a response that could not be read.' }; }
  if (!response.ok) {
    const message = payload?.detail?.message || payload?.detail?.summary || payload?.message || payload?.summary || response.statusText || 'Pocket Lab could not complete this request.';
    const error = new Error(typeof message === 'string' ? message : 'Pocket Lab could not complete this request.');
    error.status = response.status;
    error.payload = payload;
    throw error;
  }
  return payload;
}

const get = (path) => request(path);
const post = (path, body = {}) => request(path, { method: 'POST', body });
const put = (path, body = {}) => request(path, { method: 'PUT', body });
const del = (path) => request(path, { method: 'DELETE' });

export const liteEnterpriseApi = {
  identitySelf: () => get('/api/lite/enterprise/identity/self'),
  access: () => get('/api/lite/enterprise/access'),
  identity: () => get('/api/lite/enterprise/identity'),
  modePreview: (enabled) => get(`/api/lite/enterprise/identity/mode/preview?enabled=${enabled ? 'true' : 'false'}`),
  setMode: (enabled) => put('/api/lite/enterprise/identity/mode', { enabled: Boolean(enabled) }),
  members: () => get('/api/lite/enterprise/identity/members'),
  updateMember: (humanId, payload) => put(`/api/lite/enterprise/identity/members/${encodeURIComponent(humanId || '')}`, payload),
  people: () => get('/api/lite/enterprise/identity/people'),
  person: (humanId) => get(`/api/lite/enterprise/identity/people/${encodeURIComponent(humanId || '')}`),
  createPerson: (payload) => post('/api/lite/enterprise/identity/people', payload),
  personPasskeyOptions: (humanId) => post(`/api/lite/enterprise/identity/people/${encodeURIComponent(humanId || '')}/passkey/options`, {}),
  verifyPersonPasskey: (humanId, payload) => post(`/api/lite/enterprise/identity/people/${encodeURIComponent(humanId || '')}/passkey/verify`, payload),
  suspendPerson: (humanId) => post(`/api/lite/enterprise/identity/people/${encodeURIComponent(humanId || '')}/suspend`, {}),
  reactivatePerson: (humanId) => post(`/api/lite/enterprise/identity/people/${encodeURIComponent(humanId || '')}/reactivate`, {}),
  resetPersonAccess: (humanId) => post(`/api/lite/enterprise/identity/people/${encodeURIComponent(humanId || '')}/reset-access`, {}),
  removePerson: (humanId) => del(`/api/lite/enterprise/identity/people/${encodeURIComponent(humanId || '')}`),
  enrollmentStatus: () => get('/api/lite/enterprise/identity/enrollment/status'),
  passkeyLoginOptions: (username = '') => post('/api/lite/enterprise/identity/passkeys/login/options', { username }),
  verifyPasskeyLogin: (payload) => post('/api/lite/enterprise/identity/passkeys/login/verify', payload),

  ruleTemplates: () => get('/api/lite/enterprise/rules/templates'),
  ruleRevisions: () => get('/api/lite/enterprise/rules/revisions'),
  ruleRevision: (revisionId) => get(`/api/lite/enterprise/rules/revisions/${encodeURIComponent(revisionId || '')}`),
  createRuleRevision: (payload) => post('/api/lite/enterprise/rules/revisions', payload),
  compareRuleRevisions: (left, right) => get(`/api/lite/enterprise/rules/revisions/${encodeURIComponent(left || '')}/compare/${encodeURIComponent(right || '')}`),
  activateRuleRevision: (revisionId) => post('/api/lite/enterprise/rules/activations', { revision_id: revisionId }),
  resolveRuleActivation: (operationId) => post(`/api/lite/enterprise/rules/activations/${encodeURIComponent(operationId || '')}/resolve`, {}),
  ruleActivation: (operationId) => get(`/api/lite/enterprise/rules/activations/${encodeURIComponent(operationId || '')}`),
  rollbackRules: () => post('/api/lite/enterprise/rules/rollbacks', {}),
  rulesHealth: () => get('/api/lite/enterprise/rules/health'),
  rulesAnalysis: (revisionId = '') => get(`/api/lite/enterprise/rules/analysis${revisionId ? `?revision_id=${encodeURIComponent(revisionId)}` : ''}`),
  rulesDecisions: (query = '') => get(`/api/lite/enterprise/rules/decisions${query ? `?${query}` : ''}`),
  rulesDecision: (decisionId) => get(`/api/lite/enterprise/rules/decisions/${encodeURIComponent(decisionId || '')}`),
  simulateRule: (payload) => post('/api/lite/enterprise/rules/simulations', payload),
  approvals: () => get('/api/lite/enterprise/rules/approvals'),
  approval: (approvalId) => get(`/api/lite/enterprise/rules/approvals/${encodeURIComponent(approvalId || '')}`),
  transitionApproval: (approvalId, action) => post(`/api/lite/enterprise/rules/approvals/${encodeURIComponent(approvalId || '')}`, { action }),
  exceptions: () => get('/api/lite/enterprise/rules/exceptions'),
  createException: (payload) => post('/api/lite/enterprise/rules/exceptions', payload),
  revokeException: (exceptionId) => post(`/api/lite/enterprise/rules/exceptions/${encodeURIComponent(exceptionId || '')}/revoke`, {}),
};

export default liteEnterpriseApi;
