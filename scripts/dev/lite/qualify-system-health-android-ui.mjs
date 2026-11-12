#!/usr/bin/env node

import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { basename, resolve } from 'node:path';

const cdpUrl = String(process.env.LITE_ANDROID_CDP_URL || 'http://127.0.0.1:19222').trim();
const baseUrl = String(process.env.LITE_BASE_URL || 'http://127.0.0.1:18765').trim();
const commit = String(process.env.LITE_PERF_SOURCE_COMMIT || '').trim().toLowerCase();
const bridge = String(process.env.POCKETLAB_HARNESS_BROWSER_BRIDGE || '').trim();
const outputDir = resolve(process.env.LITE_SYSTEM_HEALTH_ANDROID_OUTPUT_DIR || '.pocketlab-dev/validation/pr649-system-health-android-ui');

let browser;
let page;
let context;
const requests = [];
const responses = [];
const requestFailures = [];

function fail(message) {
  throw new Error(String(message));
}

function localEndpoint(value, label, expectedPort) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    fail(`${label} is not a valid URL`);
  }
  if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || Number(parsed.port) !== expectedPort || parsed.username || parsed.password) {
    fail(`${label} must be loopback HTTP on port ${expectedPort}`);
  }
  return parsed;
}

function exactCommit() {
  if (!/^[0-9a-f]{40}$/.test(commit) || /^0+$/.test(commit)) fail('Android System Health UI evidence requires an exact candidate SHA');
  return commit;
}

function safePath(url) {
  try {
    const parsed = new URL(url);
    return parsed.pathname;
  } catch {
    return '[invalid-url]';
  }
}

async function waitForSystemHealth() {
  await page.locator('[data-system-health-page="true"]').waitFor({ state: 'visible', timeout: 30_000 });
  await page.locator('[data-health-incident]').first().waitFor({ state: 'visible', timeout: 30_000 });
  await page.getByRole('heading', { name: 'Active Problems', exact: true }).waitFor({ state: 'visible', timeout: 10_000 });
}

async function proveManifest(expectedCommit) {
  const response = await page.goto(new URL('/__pocketlab_qualification__/candidate.json', baseUrl).toString(), {
    waitUntil: 'domcontentloaded',
    timeout: 30_000,
  });
  if (!response?.ok()) fail('Android candidate manifest was not reachable');
  const manifest = JSON.parse(await page.locator('body').innerText());
  if (manifest.source_commit !== expectedCommit || manifest.sanitized !== true || manifest.runtime_transport !== 'ssh_loopback_to_isolated_phone_candidate') {
    fail('Android candidate manifest did not prove the isolated exact-SHA runtime');
  }
  if (response.headers()['x-pocket-lab-candidate-sha'] !== expectedCommit) fail('Android manifest response SHA header was incorrect');
  return { source_commit: manifest.source_commit, runtime_transport: manifest.runtime_transport, sanitized: true };
}

async function main() {
  const expectedCommit = exactCommit();
  const cdp = localEndpoint(cdpUrl, 'LITE_ANDROID_CDP_URL', 19222);
  const base = localEndpoint(baseUrl, 'LITE_BASE_URL', 18765);
  if (bridge.length < 32 || bridge.length > 128 || /[\r\n]/.test(bridge)) fail('A short-lived browser bridge is required');
  await mkdir(outputDir, { recursive: true, mode: 0o700 });

  const version = await (await fetch(new URL('/json/version', cdp))).json();
  if (version['Android-Package'] !== 'com.android.chrome' || version['Protocol-Version'] !== '1.3') {
    fail('CDP endpoint is not the expected Android Chrome Protocol 1.3 target');
  }
  const websocket = new URL(version.webSocketDebuggerUrl);
  if (!['127.0.0.1', 'localhost'].includes(websocket.hostname) || Number(websocket.port) !== 19222) {
    fail('CDP websocket is not looped back through the WSL relay');
  }

  browser = await chromium.connectOverCDP(cdp.toString());
  const contexts = browser.contexts();
  if (!contexts.length) fail('Android Chrome exposed no browser context');
  context = contexts[0];
  await context.setExtraHTTPHeaders({ 'X-Pocket-Lab-Qualification-Bridge': bridge });
  page = await context.newPage();
  page.on('request', (request) => {
    const path = safePath(request.url());
    if (path.startsWith('/api/lite/system-health/')) requests.push({ method: request.method(), path });
  });
  page.on('response', (response) => {
    const path = safePath(response.url());
    if (!path.startsWith('/api/lite/system-health/')) return;
    const headers = response.headers();
    responses.push({ method: response.request().method(), path, status: response.status(), candidate_sha: headers['x-pocket-lab-candidate-sha'] || '' });
  });
  page.on('requestfailed', (request) => {
    const path = safePath(request.url());
    if (path.startsWith('/api/lite/')) requestFailures.push({ method: request.method(), path, failure: 'request_failed' });
  });

  await page.goto(new URL('/?pocketlab_qualification_bootstrap=1', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.evaluate(async () => {
    const registrations = await navigator.serviceWorker?.getRegistrations?.() || [];
    await Promise.all(registrations.map((registration) => registration.unregister()));
    if ('caches' in window) {
      const names = await caches.keys();
      await Promise.all(names.map((name) => caches.delete(name)));
    }
  });
  const manifest = await proveManifest(expectedCommit);
  const landing = await page.goto(new URL('/?screen=system-health', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  if (!landing?.ok() || landing.headers()['x-pocket-lab-candidate-sha'] !== expectedCommit) fail('Android System Health page did not prove the exact candidate SHA');
  if (await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content') !== expectedCommit) fail('Android System Health metadata did not prove the exact candidate SHA');
  await waitForSystemHealth();
  await page.screenshot({ path: resolve(outputDir, 'system-health-landing.png'), fullPage: true });

  const incident = page.locator('[data-health-incident]').first();
  const incidentId = await incident.getAttribute('data-health-incident');
  if (!/^health-[0-9a-f]{24}$/.test(String(incidentId || ''))) fail('Android System Health did not expose a generation-bound incident');
  await incident.getByRole('button', { name: 'Diagnose & Fix', exact: true }).click();
  const dialog = page.getByRole('dialog');
  await dialog.waitFor({ state: 'visible', timeout: 10_000 });
  await Promise.all([
    page.waitForResponse((response) => response.request().method() === 'POST' && safePath(response.url()) === `/api/lite/system-health/incidents/${incidentId}/diagnose` && response.status() === 200, { timeout: 30_000 }),
    dialog.getByRole('button', { name: 'Check cause', exact: true }).click(),
  ]);
  const fixButton = dialog.getByRole('button', { name: /^Fix/ });
  await fixButton.waitFor({ state: 'visible', timeout: 10_000 });
  if (!(await fixButton.isDisabled())) fail('System Health Fix action was not disabled');
  await page.screenshot({ path: resolve(outputDir, 'system-health-diagnosis.png'), fullPage: true });

  const forbiddenWrites = requests.filter((item) => item.method === 'POST' && (item.path.endsWith('/repair') || item.path.endsWith('/preflight')));
  if (forbiddenWrites.length) fail('Android System Health UI attempted an unauthorized repair or preflight write');
  if (requestFailures.length) fail('Android System Health API request failed');
  const apiResponsesHaveCandidate = responses.length > 0 && responses.every((item) => item.candidate_sha === expectedCommit);
  if (!apiResponsesHaveCandidate) fail('Android System Health API responses did not carry the exact candidate identity');

  await dialog.getByRole('button', { name: 'Close Home details', exact: true }).click();
  await page.goto(new URL('/?screen=home', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator('[data-lite-screen-id="home"]').waitFor({ state: 'visible', timeout: 30_000 });
  await page.screenshot({ path: resolve(outputDir, 'home-system-health-summary.png'), fullPage: true });

  const evidence = {
    status: 'PASS',
    qualification_surface: 'physical_android_chrome_system_health_ui',
    candidate_sha: expectedCommit,
    android_chrome: { browser: String(version.Browser || ''), protocol_version: String(version['Protocol-Version'] || ''), package: String(version['Android-Package'] || ''), websocket_loopback: true },
    candidate_manifest: manifest,
    candidate_api_backend_verified: true,
    system_health: { landing: true, active_incident: incidentId, diagnosis_post_status: 200, manage_open: true, fix_disabled: true, repair_execution: false, preflight_execution: false, home_return: true },
    api_response_count: responses.length,
    api_response_paths: [...new Set(responses.map((item) => item.path))].sort(),
    screenshots: ['system-health-landing.png', 'system-health-diagnosis.png', 'home-system-health-summary.png'],
    sanitized: true,
  };
  const evidencePath = resolve(outputDir, `pr649-system-health-android-ui-${expectedCommit.slice(0, 12)}.json`);
  await writeFile(evidencePath, `${JSON.stringify(evidence, null, 2)}\n`, { encoding: 'utf8', mode: 0o600 });
  console.log(JSON.stringify({ status: 'PASS', evidence: basename(evidencePath), candidate_sha: expectedCommit, android_chrome: evidence.android_chrome, system_health: evidence.system_health }, null, 2));
}

try {
  await main();
} catch (error) {
  console.error(`[system-health-android-ui] ERROR ${String(error?.message || error).slice(0, 320)}`);
  process.exitCode = 1;
} finally {
  if (page) await page.close().catch(() => {});
  if (browser) await browser.close().catch(() => {});
}
