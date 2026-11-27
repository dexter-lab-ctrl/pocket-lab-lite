#!/usr/bin/env node

import { chromium } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const cdpUrl = String(process.env.LITE_ANDROID_CDP_URL || 'http://127.0.0.1:19222').trim();
const baseUrl = String(process.env.LITE_BASE_URL || 'http://127.0.0.1:18765').trim();
const commit = String(process.env.LITE_PERF_SOURCE_COMMIT || '').trim().toLowerCase();
const bridge = String(process.env.POCKETLAB_HARNESS_BROWSER_BRIDGE || '').trim();
const outputDir = resolve(process.env.LITE_TRUSTED_LIFECYCLE_ANDROID_OUTPUT_DIR || '.pocketlab-dev/validation');
const qualificationId = 'pr662-trusted-lifecycle-android-ui';

let browser;
let context;
let page;
const interactions = [];
const lifecycleRequests = [];

function fail(message) {
  throw new Error(String(message));
}

function exactCommit() {
  if (!/^[0-9a-f]{40}$/.test(commit) || /^0+$/.test(commit)) fail('Trusted Lifecycle evidence requires an exact candidate SHA');
  return commit;
}

function localEndpoint(value, label, expectedPort) {
  let parsed;
  try { parsed = new URL(value); } catch { fail(`${label} is not a valid URL`); }
  if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || Number(parsed.port) !== expectedPort || parsed.username || parsed.password) {
    fail(`${label} must be loopback HTTP on port ${expectedPort}`);
  }
  return parsed;
}

async function proveManifest(expectedCommit) {
  const response = await page.goto(new URL('/__pocketlab_qualification__/candidate.json', baseUrl).toString(), {
    waitUntil: 'domcontentloaded', timeout: 30_000,
  });
  if (!response?.ok()) fail('Android candidate manifest was not reachable');
  const manifest = JSON.parse(await page.locator('body').innerText());
  const responseSha = response.headers()['x-pocket-lab-candidate-sha'] || '';
  if (manifest.source_commit !== expectedCommit || responseSha !== expectedCommit || manifest.sanitized !== true || manifest.trusted_lifecycle_ui_fixture !== true) {
    fail('Android lifecycle manifest did not prove the exact candidate SHA');
  }
  return {
    source_commit: manifest.source_commit,
    manifest_response_sha: responseSha,
    runtime_transport: manifest.runtime_transport,
    trusted_lifecycle_ui_fixture: true,
    sanitized: true,
  };
}

async function setTheme(theme) {
  await page.evaluate((value) => {
    const root = document.documentElement;
    root.setAttribute('data-lite-theme', value);
    root.setAttribute('data-pocketlab-lite-theme', value === 'dark' ? 'dark' : 'daylight');
    root.classList.toggle('theme-pocket-lite-dark', value === 'dark');
    root.classList.toggle('theme-pocket-lite-daylight', value === 'light');
    root.style.colorScheme = value;
  }, theme);
}

async function waitForSystemSurfaceToSettle() {
  const screen = page.locator('[data-system-health-page="true"]');
  await screen.waitFor({ state: 'visible', timeout: 30_000 });
  await page.evaluate(async () => {
    if ('fonts' in document) await document.fonts.ready;
  });
  const deadline = Date.now() + 15_000;
  let previous = '';
  let stableSamples = 0;
  while (Date.now() < deadline) {
    const signature = await screen.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      const busy = element.querySelectorAll('[aria-busy="true"], [data-loading="true"], [data-lite-loading-state="true"]').length;
      return [Math.round(rect.width), Math.round(rect.height), element.scrollHeight, (element.textContent || '').trim().length, busy].join(':');
    });
    const busy = Number(signature.split(':').at(-1) || '0');
    if (signature === previous && busy === 0) {
      stableSamples += 1;
      if (stableSamples >= 4) return;
    } else {
      stableSamples = 0;
      previous = signature;
    }
    await page.waitForTimeout(250);
  }
  fail('System Health surface did not settle before interaction');
}

async function main() {
  const expectedCommit = exactCommit();
  const cdp = localEndpoint(cdpUrl, 'LITE_ANDROID_CDP_URL', 19222);
  localEndpoint(baseUrl, 'LITE_BASE_URL', 18765);
  if (bridge.length < 32 || bridge.length > 128 || /[\r\n]/.test(bridge)) fail('A short-lived browser bridge is required');
  await mkdir(outputDir, { recursive: true, mode: 0o700 });

  const version = await (await fetch(new URL('/json/version', cdp))).json();
  if (version['Android-Package'] !== 'com.android.chrome' || version['Protocol-Version'] !== '1.3') fail('CDP endpoint is not Android Chrome Protocol 1.3');
  const websocket = new URL(version.webSocketDebuggerUrl);
  if (!['127.0.0.1', 'localhost'].includes(websocket.hostname) || Number(websocket.port) !== 19222) fail('CDP websocket is not looped back through the WSL relay');

  browser = await chromium.connectOverCDP(cdp.toString());
  const contexts = browser.contexts();
  if (!contexts.length) fail('Android Chrome exposed no browser context');
  context = contexts[0];
  await context.setExtraHTTPHeaders({ 'X-Pocket-Lab-Qualification-Bridge': bridge });
  const origin = new URL(baseUrl).origin;
  const candidates = context.pages().filter((item) => item.url().startsWith(origin));
  page = candidates[candidates.length - 1] || await context.newPage();
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith('/api/lite/lifecycle/')) lifecycleRequests.push({ method: request.method(), path: url.pathname });
  });

  await page.bringToFront().catch(() => {});
  await page.goto(new URL('/?pocketlab_qualification_bootstrap=1', baseUrl).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.evaluate(async () => {
    const registrations = await navigator.serviceWorker?.getRegistrations?.() || [];
    await Promise.all(registrations.map((registration) => registration.unregister()));
    if ('caches' in window) await Promise.all((await caches.keys()).map((name) => caches.delete(name)));
  });
  const identity = await proveManifest(expectedCommit);
  const landing = await page.goto(new URL('/?screen=system-health', baseUrl).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  const pageHeaderSha = landing?.headers()['x-pocket-lab-candidate-sha'] || '';
  const pageMetaSha = await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content') || '';
  if (!landing?.ok() || pageHeaderSha !== expectedCommit || pageMetaSha !== expectedCommit) fail('Android lifecycle page did not prove the exact candidate SHA');
  await waitForSystemSurfaceToSettle();
  interactions.push('system_entry');

  const manageButton = page.getByRole('button', { name: 'Manage System Health', exact: true });
  await manageButton.scrollIntoViewIfNeeded({ timeout: 15_000 });
  const manageDebug = await manageButton.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const center = { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
    const hit = document.elementFromPoint(center.x, center.y);
    const style = window.getComputedStyle(element);
    return {
      rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) },
      viewport: { width: window.innerWidth, height: window.innerHeight, scrollY: window.scrollY },
      pointerEvents: style.pointerEvents,
      visibility: style.visibility,
      opacity: style.opacity,
      hit: hit ? { tag: hit.tagName, className: String(hit.className || '').slice(0, 160), text: String(hit.textContent || '').trim().slice(0, 120) } : null,
    };
  });
  console.log(`[trusted-lifecycle-android-ui] manage_debug ${JSON.stringify(manageDebug)}`);
  await page.screenshot({ path: resolve(outputDir, 'trusted-lifecycle-before-manage.png'), fullPage: false });
  await manageButton.click();
  const dialog = page.getByRole('dialog', { name: /System Health Manage/i });
  await dialog.waitFor({ state: 'visible', timeout: 10_000 });
  interactions.push('manage_open');
  const lifecycleSummaryResponsePromise = page.waitForResponse(
    response => response.url().includes('/api/lite/lifecycle/summary'),
    { timeout: 20_000 },
  ).catch(() => null);
  await dialog.getByRole('button', { name: 'Updates & protection', exact: true }).click();
  const lifecycleSummaryResponse = await lifecycleSummaryResponsePromise;
  if (!lifecycleSummaryResponse) fail('Trusted Lifecycle summary response was not observed');
  let lifecycleSummaryPayload = {};
  try { lifecycleSummaryPayload = await lifecycleSummaryResponse.json(); } catch { lifecycleSummaryPayload = {}; }
  if (!lifecycleSummaryResponse.ok()) {
    fail(`Trusted Lifecycle summary was unavailable (${lifecycleSummaryResponse.status()})`);
  }
  const selectedWorkspace = dialog.locator('[data-home-settings-selected="updates-protection"]');
  await selectedWorkspace.waitFor({ state: 'visible', timeout: 10_000 });
  const detail = selectedWorkspace.locator('.lite-home-settings-detail[aria-label="Updates & protection"]');
  await detail.waitFor({ state: 'visible', timeout: 10_000 });
  const panel = detail.locator('section.lite-system-health-manage-section[aria-label="Updates & protection"]');
  if (!await panel.count()) {
    fail(`Trusted Lifecycle content was unavailable (schema=${String(lifecycleSummaryPayload.schema_version || 'unknown')}, owner=${String(lifecycleSummaryPayload.owner_authority || 'unknown')})`);
  }
  await panel.waitFor({ state: 'visible', timeout: 10_000 });
  await panel.getByRole('heading', { name: 'Updates & protection', exact: true }).waitFor({ state: 'visible' });
  interactions.push('updates_protection_entry');

  const verification = panel.locator('details').filter({ hasText: 'View verification details' }).first();
  await verification.locator('summary').click();
  await verification.locator('.lite-action-row, p, .lite-system-health-detail-block').first().waitFor({ state: 'visible', timeout: 5_000 });
  await verification.locator('summary').click();
  interactions.push('verification_details_open_close');

  await panel.getByText('Impact not confirmed', { exact: true }).waitFor({ state: 'visible' });
  interactions.push('change_impact_review');

  const reviewButtons = panel.getByRole('button', { name: /^Review (Recommended|Security updates only|Notify me)$/ });
  if (await reviewButtons.count()) {
    const reviewButton = reviewButtons.first();
    await reviewButton.click();
    const reviewGroup = panel.getByRole('group', { name: 'Review proposed change' });
    await reviewGroup.waitFor({ state: 'visible', timeout: 10_000 });
    await reviewGroup.getByRole('button', { name: 'Cancel', exact: true }).click();
    await reviewGroup.waitFor({ state: 'hidden', timeout: 5_000 });
    interactions.push('preference_review_cancel');
  } else {
    const pause = panel.getByRole('button', { name: 'Pause new standing consent', exact: true });
    if (await pause.count()) {
      await pause.click();
      const reviewGroup = panel.getByRole('group', { name: 'Review proposed change' });
      await reviewGroup.waitFor({ state: 'visible', timeout: 10_000 });
      await reviewGroup.getByRole('button', { name: 'Cancel', exact: true }).click();
      await reviewGroup.waitFor({ state: 'hidden', timeout: 5_000 });
      interactions.push('preference_pause_review_cancel');
    } else {
      fail('Trusted Lifecycle exposed no safe preference review control');
    }
  }

  for (const summary of ['Review capability contracts', 'Verification history', 'Recent permission changes']) {
    const details = panel.locator('details').filter({ hasText: summary }).first();
    await details.locator('summary').click();
    await details.locator('summary').click();
    interactions.push(summary.toLowerCase().replaceAll(' ', '_') + '_open_close');
  }

  const scrollSurface = dialog.locator('.lite-overlay-scroll').first();
  await scrollSurface.evaluate(async (element) => {
    element.scrollTop = Math.min(element.scrollHeight, 480);
    await new Promise((resolve) => requestAnimationFrame(() => resolve()));
    element.scrollTop = 0;
  });
  interactions.push('nested_mobile_scroll');

  for (const theme of ['light', 'dark']) {
    await setTheme(theme);
    await page.screenshot({ path: resolve(outputDir, `trusted-lifecycle-${theme}.png`), fullPage: false });
    interactions.push(`theme_${theme}`);
  }

  await page.keyboard.press('Escape');
  await dialog.waitFor({ state: 'hidden', timeout: 10_000 });
  interactions.push('manage_close');

  const unsafeWrites = lifecycleRequests.filter((item) => item.method !== 'GET' && !(
    item.method === 'POST' && (item.path === '/api/lite/lifecycle/preferences/review' || item.path === '/api/lite/lifecycle/boundary/review')
  ));
  if (unsafeWrites.length) fail('Trusted Lifecycle physical lane attempted a mutation outside review endpoints');
  const evidence = {
    status: 'PASS',
    qualification_surface: 'physical_android_chrome_trusted_lifecycle_ui',
    candidate_sha: expectedCommit,
    candidate_identity: {
      ...identity,
      rendered_page_response_sha: pageHeaderSha,
      rendered_page_meta_sha: pageMetaSha,
      manifest_sanitized: true,
    },
    browser: { android_package: 'com.android.chrome', protocol_version: '1.3', standard_user: true, localhost_cdp: true },
    interactions,
    interaction_count: interactions.length,
    lifecycle_requests: lifecycleRequests.map((item) => ({ method: item.method, path: item.path })),
    unsafe_writes: [],
    screenshots: ['trusted-lifecycle-light.png', 'trusted-lifecycle-dark.png'],
    backend_mode: 'isolated_candidate_ui_fixture',
    live_backend_summary: false,
    human_owner_boundary_preserved: true,
    destructive_actions: false,
    sanitized: true,
  };
  await writeFile(resolve(outputDir, `${qualificationId}-${expectedCommit.slice(0, 12)}.json`), `${JSON.stringify(evidence, null, 2)}\n`, { encoding: 'utf8', mode: 0o600 });
  console.log(`[trusted-lifecycle-android-ui] PASS ${interactions.length} safe interactions`);
}

try {
  await main();
} catch (error) {
  console.error(`[trusted-lifecycle-android-ui] ERROR ${String(error?.message || error).slice(0, 2000)}`);
  process.exitCode = 1;
} finally {
  if (page) await page.close().catch(() => {});
  if (browser) await browser.close().catch(() => {});
}
