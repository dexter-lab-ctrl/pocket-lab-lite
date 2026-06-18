const JSON_HEADERS = { 'Content-Type': 'application/json' };

export function controlPlaneErrorMessage(data, fallback = 'Control plane request failed') {
  const text = String(data?.detail || data?.error || data?.message || fallback);
  if (/nats|jetstream|worker|control plane|unavailable|required/i.test(text)) {
    return `${text} Control plane production mode does not allow local fallback execution.`;
  }
  return text;
}

export async function parseJsonResponse(res) {
  const text = await res.text();
  if (text.trim().startsWith('<!DOCTYPE html') || text.includes('<html')) {
    throw new Error('HTML fallback detected');
  }
  try {
    return JSON.parse(text || '{}');
  } catch {
    throw new Error('Invalid JSON response');
  }
}

export async function fetchJson(path, options = {}) {
  const res = await fetch(path, {
    cache: 'no-store',
    headers: { Accept: 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const data = await parseJsonResponse(res);
  return { res, data };
}

async function fetchOperationStatus(jobId) {
  const statusPaths = [`/api/operations/${jobId}/status`, `/api/operations/${jobId}`];
  let lastError;
  for (const path of statusPaths) {
    try {
      const { res, data } = await fetchJson(path);
      if (!res.ok) {
        lastError = new Error(data?.error || 'Operation status unavailable');
        continue;
      }
      return data;
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error('Operation status unavailable');
}

async function pollOperation(jobId, timeoutMs = 30000, intervalMs = 750) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const data = await fetchOperationStatus(jobId);
    if (['succeeded', 'failed', 'canceled'].includes(data.status)) {
      return data;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error('Timed out waiting for operation');
}

export async function executeOperation(operation, {
  target = { type: 'repo', ref: '' },
  params = {},
  dryRun = false,
  wait = true,
} = {}) {
  const { res, data } = await fetchJson('/api/operations/execute', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ operation, target, params, dry_run: dryRun }),
  });
  if (!res.ok && res.status !== 202) {
    throw new Error(controlPlaneErrorMessage(data, `Operation ${operation} rejected`));
  }
  const jobId = data.job_id;
  if (!jobId || wait === false) {
    return data;
  }
  return pollOperation(jobId);
}


export async function executeOperationQueued(operation, {
  target = { type: 'repo', ref: '' },
  params = {},
  dryRun = false,
} = {}) {
  return executeOperation(operation, { target, params, dryRun, wait: false });
}

export async function previewOperation(operation, {
  target = { type: 'repo', ref: '' },
  params = {},
} = {}) {
  const { res, data } = await fetchJson('/api/operations/preview', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({ operation, target, params }),
  });
  if (!res.ok) {
    throw new Error(controlPlaneErrorMessage(data, `Preview for ${operation} rejected`));
  }
  return data;
}

export async function fetchOperation(jobId) {
  return fetchOperationStatus(jobId);
}


export async function refreshCatalog() {
  const { res, data } = await fetchJson('/api/catalog/refresh', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    throw new Error(controlPlaneErrorMessage(data, 'Catalog refresh rejected'));
  }
  return data;
}

export async function fetchReleaseWorkflow() {
  const { data } = await fetchJson('/api/release/workflow');
  return data;
}

export async function fetchReleaseUpdateStatus() {
  const { data } = await fetchJson('/api/release/self-update/status');
  return data;
}

export async function checkReleaseUpdate() {
  const { res, data } = await fetchJson('/api/release/self-update/check', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    throw new Error(controlPlaneErrorMessage(data, 'Release update check rejected'));
  }
  return data;
}

export async function applyReleaseUpdate() {
  const { res, data } = await fetchJson('/api/release/self-update/apply', {
    method: 'POST',
    headers: JSON_HEADERS,
    body: JSON.stringify({}),
  });
  if (!res.ok) {
    throw new Error(controlPlaneErrorMessage(data, 'Release update apply rejected'));
  }
  return data;
}


export async function queryLogs({ query = '{job="varlogs"}', limit = 100 } = {}) {
  const encodedQuery = encodeURIComponent(query);
  const safeLimit = Math.max(1, Math.min(100, Number(limit) || 20));
  const { res, data } = await fetchJson(`/api/logs/query?query=${encodedQuery}&limit=${safeLimit}`);
  if (!res.ok) {
    throw new Error(controlPlaneErrorMessage(data, 'Log query rejected'));
  }
  return data;
}
