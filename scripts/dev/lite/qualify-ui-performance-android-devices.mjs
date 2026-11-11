#!/usr/bin/env node

import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import {
  LITE_PERFORMANCE_INTERACTIONS,
  LITE_PERFORMANCE_SCHEMA_VERSION,
  sanitizeLitePerformanceName,
  summarizeLiteFrames,
} from '../../../src/performance/litePerformanceBudget.js';
import { LITE_UI_PERFORMANCE_MATRIX } from '../../../src/performance/litePerformanceMatrix.js';

/*
 * Devices-only physical Android qualification.
 *
 * This is intentionally a bounded sibling of the repository's Safety and
 * Rules qualifiers. It exercises only read-only Devices surfaces and reuses
 * the exact-SHA candidate, Android CDP identity, foreground RAF, wake-lock,
 * sampler, screenshot and evidence contracts. It never invokes an operation
 * endpoint and never runs the seven-screen Android matrix.
 */

const cdpValue = String(process.env.LITE_ANDROID_CDP_URL || '').trim();
const baseValue = String(process.env.LITE_BASE_URL || '').trim();
const browserBridge = String(process.env.POCKETLAB_HARNESS_BROWSER_BRIDGE || '').trim();
const browserBridgeEnabled = process.env.LITE_QUALIFICATION_BROWSER_BRIDGE === '1';
const MINIMUM_FRAME_COUNT = 20;
const MINIMUM_SAMPLER_INTERVAL_COUNT = MINIMUM_FRAME_COUNT + 3;
const MAX_MINIMUM_FRAME_EXTENSION_MS = 2_000;

let browser;
let page;
let context;
let base;
let commit;
let candidateManifest;
let androidChromeVersion = '';
let outputDir;
let hardGateFailures = 0;
let targetMisses = 0;
let evidenceCount = 0;
let hapticProbe = { supported: false, instrumented: false, touchActivationCalls: 0, acceptedCalls: 0 };
const exercisedInteractions = new Set();
const physicalNotes = [];
const unavailableSurfaces = [];
const requestFailures = [];

function fail(message) {
  throw new Error(message);
}

function exactSourceCommit() {
  const configured = String(process.env.LITE_PERF_SOURCE_COMMIT || process.env.GITHUB_SHA || '').trim();
  if (/^[0-9a-f]{40}$/.test(configured) && !/^0+$/.test(configured)) return configured;
  try {
    const value = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    if (/^[0-9a-f]{40}$/.test(value) && !/^0+$/.test(value)) return value;
  } catch {
    // Fail closed below.
  }
  fail('Devices physical evidence requires an exact 40-character source commit.');
}

function endpoint(value, label) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    fail(label + ' must be a valid URL.');
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) fail(label + ' must use http:// or https://.');
  if (parsed.username || parsed.password) fail(label + ' must not contain credentials.');
  return parsed;
}

async function jsonFetch(url, label) {
  let response;
  try {
    response = await fetch(url, { headers: { Accept: 'application/json' } });
  } catch (error) {
    fail(label + ' was not reachable: ' + (error?.message || error));
  }
  if (!response.ok) fail(label + ' returned HTTP ' + response.status + '.');
  try {
    return await response.json();
  } catch {
    fail(label + ' did not return valid JSON.');
  }
}

function matrixEvidence(interaction, nestedSurface) {
  return LITE_UI_PERFORMANCE_MATRIX.find((entry) => (
    entry.screen === 'devices'
    && entry.interaction === interaction
    && entry.nestedSurface === nestedSurface
  ))?.evidenceId || null;
}

async function firstVisible(locator, label) {
  const count = await locator.count().catch(() => 0);
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible().catch(() => false)) return candidate;
  }
  fail('Could not find visible ' + label + '.');
}

async function firstVisibleOrNull(locator) {
  const count = await locator.count().catch(() => 0);
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible().catch(() => false)) return candidate;
  }
  return null;
}

async function activate(candidatePage) {
  await candidatePage.bringToFront().catch(() => {});
  try {
    const session = await context.newCDPSession(candidatePage);
    await session.send('Page.bringToFront');
    await session.detach().catch(() => {});
  } catch {
    // Playwright activation remains the portable fallback.
  }
}

async function receivesAnimationFrames(candidatePage) {
  const frames = await candidatePage.evaluate(() => new Promise((resolveFrames) => {
    let count = 0;
    const timeout = setTimeout(() => resolveFrames(count), 350);
    const tick = () => {
      count += 1;
      if (count >= 2) {
        clearTimeout(timeout);
        resolveFrames(count);
      } else {
        requestAnimationFrame(tick);
      }
    };
    requestAnimationFrame(tick);
  })).catch(() => 0);
  return Number(frames) >= 2;
}

async function requireScreenWakeLock() {
  const result = await page.evaluate(async () => {
    const existing = window.__POCKETLAB_ANDROID_DEVICES_WAKE_LOCK__;
    if (existing && !existing.released) return true;
    if (!navigator.wakeLock?.request) return false;
    try {
      const lock = await navigator.wakeLock.request('screen');
      window.__POCKETLAB_ANDROID_DEVICES_WAKE_LOCK__ = lock;
      window.setTimeout(() => lock.release().catch(() => {}), 300_000);
      return !lock.released;
    } catch {
      return false;
    }
  }).catch(() => false);
  if (!result) fail('Android screen wake lock could not be acquired; physical Devices frame evidence would be throttled.');
}

function samplerBootstrap() {
  let active = null;
  window.__POCKETLAB_ANDROID_DEVICES_SAMPLER__ = {
    start(name) {
      active?.raf && cancelAnimationFrame(active.raf);
      active?.observers?.forEach((observer) => observer.disconnect());
      active = {
        name: String(name || 'devices').slice(0, 96),
        previous: null,
        intervals: [],
        longTasks: [],
        longAnimationFrames: [],
        eventDurations: [],
        observers: [],
        raf: null,
      };
      const sample = active;
      const frame = (timestamp) => {
        if (active !== sample) return;
        if (sample.previous !== null) sample.intervals.push(timestamp - sample.previous);
        sample.previous = timestamp;
        sample.raf = requestAnimationFrame(frame);
      };
      sample.raf = requestAnimationFrame(frame);
      if ('PerformanceObserver' in window) {
        try {
          const observer = new PerformanceObserver((list) => list.getEntries().forEach((entry) => sample.longTasks.push(Number(entry.duration) || 0)));
          observer.observe({ entryTypes: ['longtask'] });
          sample.observers.push(observer);
        } catch {}
        try {
          const observer = new PerformanceObserver((list) => list.getEntries().forEach((entry) => sample.longAnimationFrames.push(Number(entry.duration) || 0)));
          observer.observe({ type: 'long-animation-frame', buffered: false });
          sample.observers.push(observer);
        } catch {}
        try {
          const observer = new PerformanceObserver((list) => list.getEntries().forEach((entry) => sample.eventDurations.push(Number(entry.duration) || 0)));
          observer.observe({ type: 'event', buffered: false, durationThreshold: 16 });
          sample.observers.push(observer);
        } catch {}
      }
    },
    stop() {
      if (!active) return null;
      const sample = active;
      active = null;
      if (sample.raf) cancelAnimationFrame(sample.raf);
      sample.observers.forEach((observer) => observer.disconnect());
      return {
        interaction: sample.name,
        intervals: sample.intervals.slice(0, 600),
        longTasks: sample.longTasks.slice(0, 120),
        longAnimationFrames: sample.longAnimationFrames.slice(0, 120),
        eventDurations: sample.eventDurations.slice(0, 120),
      };
    },
    count() { return active?.intervals?.length || 0; },
  };
}

function hapticProbeBootstrap() {
  const original = typeof Navigator !== 'undefined' ? Navigator.prototype.vibrate : null;
  const probe = { supported: typeof original === 'function', instrumented: false, calls: [] };
  window.__POCKETLAB_ANDROID_DEVICES_HAPTICS__ = probe;
  if (!probe.supported) return;
  try {
    Object.defineProperty(Navigator.prototype, 'vibrate', {
      configurable: true,
      value(pattern) {
        let accepted = false;
        try { accepted = Boolean(original.call(this, pattern)); } catch {}
        probe.calls.push({ accepted, pattern: Array.isArray(pattern) ? pattern.slice(0, 8) : pattern });
        return accepted;
      },
    });
    probe.instrumented = true;
  } catch {
    // Capability remains useful even if the optional hook is unavailable.
  }
}

async function touch(locator, label) {
  await locator.scrollIntoViewIfNeeded().catch(() => {});
  const box = await locator.boundingBox().catch(() => null);
  if (!box || box.width <= 0 || box.height <= 0) fail(label + ' is not touchable.');
  const session = await context.newCDPSession(page);
  try {
    const x = box.x + box.width / 2;
    const y = box.y + box.height / 2;
    await Promise.all([
      session.send('Input.dispatchTouchEvent', {
        type: 'touchStart', modifiers: 0, touchPoints: [{ x, y }],
      }),
      session.send('Input.dispatchTouchEvent', {
        type: 'touchEnd', modifiers: 0, touchPoints: [],
      }),
    ]);
  } finally {
    await session.detach().catch(() => {});
  }
}

async function waitForDevices() {
  await page.locator('[data-lite-screen-id="devices"]').waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('.lite-devices-list-area').waitFor({ state: 'visible', timeout: 20_000 });
  await page.waitForFunction(() => {
    const area = document.querySelector('.lite-devices-list-area');
    const cards = document.querySelectorAll('.lite-device-library-card').length;
    const state = document.querySelector('.lite-devices-list-area .pocket-state-surface');
    return area?.getAttribute('aria-busy') === 'false' && (cards > 0 || Boolean(state));
  }, undefined, { timeout: 30_000 });
  await page.evaluate(async () => {
    if ('fonts' in document) await document.fonts.ready;
  });
  await page.waitForTimeout(500);
}

async function proveCandidate() {
  await page.goto(new URL('/?pocketlab_qualification_bootstrap=1', base).toString(), {
    waitUntil: 'domcontentloaded', timeout: 30_000,
  });
  await requireScreenWakeLock();
  await page.evaluate(async () => {
    const registrations = await navigator.serviceWorker?.getRegistrations?.() || [];
    await Promise.all(registrations.map((registration) => registration.unregister()));
    if ('caches' in window) {
      const names = await caches.keys();
      await Promise.all(names.map((name) => caches.delete(name)));
    }
  });

  const manifestResponse = await page.goto(new URL('/__pocketlab_qualification__/candidate.json', base).toString(), {
    waitUntil: 'domcontentloaded', timeout: 30_000,
  });
  if (!manifestResponse?.ok()) fail('The Android base URL did not expose the exact-SHA candidate manifest.');
  try {
    candidateManifest = JSON.parse(await page.locator('body').innerText());
  } catch {
    fail('The Android candidate manifest was not valid JSON.');
  }
  if (candidateManifest?.source_commit !== commit || candidateManifest?.sanitized !== true) {
    fail('The Android Devices candidate manifest source SHA or sanitization marker is invalid.');
  }
  if (manifestResponse.headers()['x-pocket-lab-candidate-sha'] !== commit) {
    fail('The Android candidate manifest response header did not prove the exact commit.');
  }

  const response = await page.goto(new URL('/?screen=devices', base).toString(), {
    waitUntil: 'domcontentloaded', timeout: 30_000,
  });
  if (!response?.ok()) fail('The Android Devices candidate page did not load.');
  if (response.headers()['x-pocket-lab-candidate-sha'] !== commit) {
    fail('The Android Devices rendered page response header did not prove the exact commit.');
  }
  if (await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content') !== commit) {
    fail('The Android Devices rendered page metadata did not prove the exact commit.');
  }
  await requireScreenWakeLock();
}

async function assertNoOverflow(label) {
  const geometry = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    documentWidth: document.documentElement.scrollWidth,
    bodyWidth: document.body?.scrollWidth || 0,
    viewportHeight: window.innerHeight,
  }));
  if (geometry.documentWidth > geometry.viewportWidth + 2 || geometry.bodyWidth > geometry.viewportWidth + 2) {
    fail(label + ' introduced horizontal overflow: ' + JSON.stringify(geometry));
  }
  return geometry;
}

async function measure({ interaction, scope, surface, action, settleMs = 450, evidenceId = null, restartSamplerAfterAction = false }) {
  if (!LITE_PERFORMANCE_INTERACTIONS.includes(interaction)) fail('Unknown Devices interaction id: ' + interaction);
  const samplerName = 'android-cdp:devices:' + interaction + ':' + scope;
  await page.evaluate((name) => window.__POCKETLAB_ANDROID_DEVICES_SAMPLER__?.start(name), samplerName);
  await action();
  if (restartSamplerAfterAction) {
    await page.evaluate(samplerBootstrap);
    await page.evaluate((name) => window.__POCKETLAB_ANDROID_DEVICES_SAMPLER__?.start(name), samplerName);
  }
  if (settleMs > 0) await page.waitForTimeout(settleMs);
  const deadline = Date.now() + MAX_MINIMUM_FRAME_EXTENSION_MS;
  while (Date.now() < deadline) {
    const count = await page.evaluate(() => window.__POCKETLAB_ANDROID_DEVICES_SAMPLER__?.count?.() || 0).catch(() => 0);
    if (count >= MINIMUM_SAMPLER_INTERVAL_COUNT) break;
    await page.waitForTimeout(50);
  }
  const raw = await page.evaluate(() => window.__POCKETLAB_ANDROID_DEVICES_SAMPLER__?.stop?.() || null);
  if (!raw) fail('Devices frame sampler returned no evidence for ' + scope + '.');
  const summary = summarizeLiteFrames(raw.intervals || [], {
    longTasks: raw.longTasks || [],
    longAnimationFrames: raw.longAnimationFrames || [],
    eventDurations: raw.eventDurations || [],
    warmupFrames: 3,
  });
  if (summary.frame_count < MINIMUM_FRAME_COUNT) {
    fail(interaction + ' (' + scope + ') produced only ' + summary.frame_count + ' measured frames; at least ' + MINIMUM_FRAME_COUNT + ' are required.');
  }
  const viewport = await page.evaluate(() => ({
    width: window.innerWidth,
    height: window.innerHeight,
    visual_width: window.visualViewport?.width || null,
    visual_height: window.visualViewport?.height || null,
    device_pixel_ratio: window.devicePixelRatio || null,
  }));
  const report = {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    evidence_type: 'android-devices-only-interaction',
    interaction: 'android-cdp:devices:' + interaction + ':' + scope,
    phase4_interaction: interaction,
    interaction_scope: scope,
    interaction_surface: surface,
    performance_evidence_id: evidenceId,
    mode: 'live',
    qualification_surface: 'android-cdp-devices-only',
    browser_project: 'android-cdp-devices-only',
    rendering_surface: 'physical-android-chrome',
    qualification_scope: 'devices',
    android_chrome_version: androidChromeVersion,
    android_package: 'com.android.chrome',
    source_commit: commit,
    candidate_manifest_verified: true,
    candidate_manifest_source_commit: candidateManifest.source_commit,
    candidate_manifest_schema_version: candidateManifest.schema_version,
    candidate_manifest_response_header_verified: true,
    candidate_page_response_header_verified: true,
    candidate_page_meta_verified: true,
    android_cdp_identity_verified: process.env.LITE_ANDROID_CDP_DEVICE_IDENTITY_VERIFIED === '1'
      && process.env.LITE_ANDROID_CDP_BRIDGE_IDENTITY_VERIFIED === '1',
    android_candidate_reverse_verified: process.env.LITE_ANDROID_CANDIDATE_REVERSE_VERIFIED === '1',
    sanitized: true,
    viewport,
    raw_intervals_ms: raw.intervals || [],
    raw_long_tasks_ms: raw.longTasks || [],
    raw_long_animation_frames_ms: raw.longAnimationFrames || [],
    raw_event_durations_ms: raw.eventDurations || [],
    ...summary,
  };
  const fileName = 'ui-performance-android-devices-'
    + sanitizeLitePerformanceName(scope) + '-' + sanitizeLitePerformanceName(interaction) + '.json';
  await writeFile(resolve(outputDir, fileName), JSON.stringify(report, null, 2) + '\n', 'utf8');
  exercisedInteractions.add(interaction);
  evidenceCount += 1;
  if (!report.gate_passed) hardGateFailures += 1;
  if (!report.target_met) targetMisses += 1;
  const status = report.target_met ? 'TARGET-PASS' : report.gate_passed ? 'TARGET-MISS' : 'GATE-MISS';
  console.log('[ui-performance-android-devices] ' + status + ' ' + interaction + ' (' + scope + '): p95=' + report.p95_frame_ms + 'ms smooth=' + report.target_smooth_frame_ratio);
}

async function capture(name, target = page) {
  const path = resolve(outputDir, 'android-devices-' + sanitizeLitePerformanceName(name) + '.png');
  const masks = [
    target.locator('.lite-device-library-name h3'),
    target.locator('.lite-device-details-panel-head h3'),
    target.locator('.lite-device-relationship-node span'),
    target.locator('.lite-remote-access-facts'),
  ];
  await target.screenshot({ path, animations: 'disabled', mask: masks });
  console.log('[ui-performance-android-devices] screenshot ' + name + ': ' + path);
}

async function openManage() {
  const manage = await firstVisibleOrNull(page.locator('.lite-device-card-peer .lite-device-library-manage'))
    || await firstVisible(page.locator('.lite-device-library-manage'), 'Devices Manage action');
  await touch(manage, 'Devices Manage action');
  const dialog = page.getByRole('dialog', { name: /Manage / }).first();
  await dialog.waitFor({ state: 'visible', timeout: 20_000 });
  await dialog.locator('.lite-device-details-panel').waitFor({ state: 'visible', timeout: 20_000 }).catch(() => {});
  return { dialog, manage };
}

async function closeManage(dialog, manage) {
  const close = await firstVisible(dialog.getByRole('button', { name: 'Close device details' }), 'Close Devices Manage');
  await close.click();
  await dialog.waitFor({ state: 'hidden', timeout: 20_000 });
  await manage.focus().catch(() => {});
  const expected = await manage.getAttribute('aria-label');
  const active = await page.evaluate(() => document.activeElement?.getAttribute('aria-label') || '');
  if (active !== expected) {
    physicalNotes.push('Manage close returned to the card action, but Android did not expose the expected active-element label.');
  }
}

async function scrollDocument() {
  const result = await page.evaluate(async () => {
    const root = document.scrollingElement || document.documentElement;
    const start = root.scrollTop;
    const max = Math.max(0, root.scrollHeight - root.clientHeight);
    root.scrollTop = Math.min(max, Math.max(180, Math.round(window.innerHeight * 0.55)));
    await new Promise((resolveScroll) => requestAnimationFrame(() => requestAnimationFrame(resolveScroll)));
    const observed = root.scrollTop;
    root.scrollTop = start;
    return { max, observed, restored: root.scrollTop === start };
  });
  if (result.max <= 0) physicalNotes.push('Devices inventory did not require document scrolling on the physical viewport.');
  if (!result.restored) fail('Devices inventory scroll did not restore its starting position.');
}

async function scrollManage(dialog) {
  const result = await dialog.evaluate(async (element) => {
    const start = element.scrollTop;
    const max = Math.max(0, element.scrollHeight - element.clientHeight);
    element.scrollTop = Math.min(max, Math.max(120, Math.round(element.clientHeight * 0.55)));
    await new Promise((resolveScroll) => requestAnimationFrame(() => requestAnimationFrame(resolveScroll)));
    const observed = element.scrollTop;
    element.scrollTop = start;
    return { max, observed, restored: element.scrollTop === start };
  });
  if (result.max <= 0) physicalNotes.push('Devices Manage content did not require scrolling on the physical viewport.');
  if (!result.restored) fail('Devices Manage scroll did not restore its starting position.');
}

async function chooseSection(dialog, label) {
  let button = await firstVisibleOrNull(dialog.getByRole('button', { name: label, exact: true }));
  if (!button) {
    const back = await firstVisibleOrNull(dialog.getByRole('button', { name: 'Back to all device settings', exact: true }));
    if (back) {
      await back.click();
      await dialog.locator('[data-manage-view="index"]').waitFor({ state: 'visible', timeout: 20_000 });
      button = await firstVisibleOrNull(dialog.getByRole('button', { name: label, exact: true }));
    }
  }
  if (!button) return false;
  await button.click();
  await page.locator('[data-active-device-section="' + label.toLowerCase() + '"]').waitFor({ state: 'visible', timeout: 20_000 });
  return true;
}

async function expectText(locator, expected) {
  await locator.waitFor({ state: 'visible', timeout: 20_000 });
  const actual = (await locator.innerText()).trim();
  if (actual.toLowerCase() !== expected.toLowerCase()) fail('Expected ' + expected + ' but observed ' + actual + '.');
}

async function qualifyThemes() {
  const control = await firstVisibleOrNull(page.getByRole('combobox', { name: 'Appearance', exact: true }));
  if (!control) {
    unavailableSurfaces.push('Devices theme switching / Appearance control');
    return;
  }
  const original = await control.inputValue().catch(() => 'system');
  await measure({
    interaction: 'screen-steady',
    scope: 'devices-themes-light-dark-system',
    surface: 'Devices Light, Dark and System theme resolution',
    action: async () => {
      for (const preference of ['light', 'dark', 'system']) {
        await control.selectOption(preference);
        await page.waitForFunction((value) => {
          const select = document.querySelector('select[aria-label="Appearance"]');
          return select?.value === value && Boolean(document.documentElement.dataset.liteTheme);
        }, preference, { timeout: 20_000 });
        await assertNoOverflow('Devices ' + preference + ' appearance');
        await capture('theme-' + preference);
      }
      await control.selectOption(['system', 'light', 'dark'].includes(original) ? original : 'system');
    },
    settleMs: 520,
  });
}

async function main() {
  if (browserBridgeEnabled !== Boolean(browserBridge)) {
    fail('Synthetic Android browser qualification requires an explicit browser bridge and LITE_QUALIFICATION_BROWSER_BRIDGE=1.');
  }
  commit = exactSourceCommit();
  outputDir = resolve(process.env.LITE_ANDROID_DEVICES_OUTPUT_DIR || '.pocketlab-dev/performance/android-devices-' + commit);
  await mkdir(outputDir, { recursive: true });
  const cdp = endpoint(cdpValue, 'LITE_ANDROID_CDP_URL');
  base = endpoint(baseValue, 'LITE_BASE_URL');
  const version = await jsonFetch(new URL('/json/version', cdp).toString(), 'Android CDP version endpoint');
  if (version['Android-Package'] !== 'com.android.chrome') fail('The CDP endpoint did not identify com.android.chrome.');
  const websocket = new URL(version.webSocketDebuggerUrl || '');
  if (!['127.0.0.1', 'localhost'].includes(websocket.hostname) || Number(websocket.port) !== Number(cdp.port)) {
    fail('The CDP websocket did not remain on the WSL-local endpoint.');
  }

  browser = await chromium.connectOverCDP(cdp.toString());
  androidChromeVersion = String(browser.version() || version.Browser || '').trim();
  const contexts = browser.contexts();
  if (!contexts.length) fail('Android Chrome did not expose a browser context over CDP.');
  context = contexts[0];
  if (browserBridge) await context.setExtraHTTPHeaders({ 'X-Pocket-Lab-Qualification-Bridge': browserBridge });
  const candidateOrigin = base.origin;
  const existingCandidatePages = context.pages().filter((candidatePage) => candidatePage.url().startsWith(candidateOrigin));
  page = existingCandidatePages[existingCandidatePages.length - 1] || await context.newPage();
  const candidatePages = [...new Set([...existingCandidatePages, page])];
  page.on('requestfailed', (request) => {
    if (!request.url().includes('/api/lite/')) return;
    try {
      requestFailures.push({
        method: request.method(),
        path: new URL(request.url()).pathname,
        failure: String(request.failure()?.errorText || 'request_failed').slice(0, 120),
      });
    } catch {
      requestFailures.push({ method: request.method(), path: '/api/lite/*', failure: 'request_failed' });
    }
  });

  let foregroundReady = false;
  const foregroundCandidates = [page, ...candidatePages.filter((candidatePage) => candidatePage !== page)];
  for (const candidatePage of foregroundCandidates) {
    page = candidatePage;
    await activate(page);
    await proveCandidate();
    foregroundReady = await receivesAnimationFrames(page);
    for (let attempt = 0; !foregroundReady && attempt < 2; attempt += 1) {
      await activate(page);
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 30_000 }).catch(() => {});
      await requireScreenWakeLock();
      await activate(page);
      foregroundReady = await receivesAnimationFrames(page);
    }
    if (foregroundReady) break;
  }
  if (!foregroundReady) fail('Android Devices candidate did not deliver foreground animation frames.');
  await Promise.all(candidatePages.filter((candidatePage) => candidatePage !== page).map((candidatePage) => candidatePage.close().catch(() => {})));
  await page.addInitScript(samplerBootstrap);
  await page.addInitScript(hapticProbeBootstrap);
  await page.evaluate(samplerBootstrap);
  await page.evaluate(hapticProbeBootstrap);
  await requireScreenWakeLock();

  await waitForDevices();
  await assertNoOverflow('Devices initial render');
  await measure({
    interaction: 'screen-navigation',
    scope: 'devices-initial-navigation',
    surface: 'Devices initial navigation and candidate render',
    action: async () => {
      const response = await page.goto(new URL('/?screen=devices', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
      if (response?.headers()['x-pocket-lab-candidate-sha'] !== commit) fail('Devices navigation response SHA changed during qualification.');
      await waitForDevices();
    },
    settleMs: 620,
    restartSamplerAfterAction: true,
  });
  await measure({
    interaction: 'screen-steady',
    scope: 'devices-inventory-initial-render',
    surface: 'Devices inventory, fleet metrics and card rendering',
    action: async () => {
      await waitForDevices();
      await assertNoOverflow('Devices inventory');
    },
    settleMs: 720,
  });
  await capture('overview');

  await measure({
    interaction: 'list-scroll',
    scope: 'devices-inventory-scroll',
    surface: 'Devices inventory scrolling and scroll containment',
    action: scrollDocument,
    settleMs: 420,
  });

  const search = await firstVisibleOrNull(page.getByRole('searchbox', { name: 'Search devices' }));
  const cards = page.locator('.lite-device-library-card');
  const firstName = await cards.first().locator('h3').innerText().catch(() => '');
  if (!search || !firstName) {
    unavailableSurfaces.push('Devices search/filter interaction / no searchable device card was projected');
  } else {
    await measure({
      interaction: 'screen-navigation',
      scope: 'devices-search-filter',
      surface: 'Devices search and state filter controls',
      action: async () => {
        await search.fill(firstName.slice(0, Math.min(12, firstName.length)));
        await page.waitForTimeout(180);
        if (await cards.count() < 1) fail('Devices search did not retain the matching device.');
        await search.fill('');
        const filter = page.getByRole('combobox', { name: 'Filter devices' });
        await filter.selectOption('connected').catch(() => {});
        await filter.selectOption('all').catch(() => {});
        await assertNoOverflow('Devices search/filter');
      },
      settleMs: 420,
    });
  }

  const opened = await openManage();
  const dialog = opened.dialog;
  const manage = opened.manage;
  await measure({
    interaction: 'manage-open',
    scope: 'devices-manage-open',
    surface: 'Device Manage opening from the inventory card',
    action: async () => {
      await dialog.waitFor({ state: 'visible', timeout: 20_000 });
      await assertNoOverflow('Devices Manage');
    },
    settleMs: 620,
  });
  await capture('manage-overview', dialog);

  const sectionLabels = ['Overview', 'Connection', 'Health', 'Roles', 'Services', 'Backup', 'History', 'Technical'];
  const availableSections = [];
  await measure({
    interaction: 'section-switch',
    scope: 'devices-manage-sections',
    surface: 'Device Manage Overview, Connection, Health, Roles, Services, Backup, History and Technical sections',
    action: async () => {
      for (const label of sectionLabels) {
        const available = await chooseSection(dialog, label);
        if (!available) {
          unavailableSurfaces.push('Device Manage / ' + label + ' (not exposed for the selected device)');
          continue;
        }
        availableSections.push(label);
        await capture('manage-' + label.toLowerCase(), dialog);
      }
    },
    settleMs: 520,
  });
  for (const required of ['Overview', 'Connection', 'Health', 'Services', 'History', 'Technical']) {
    if (!availableSections.includes(required)) fail('Device Manage ' + required + ' was not exposed.');
  }

  await measure({
    interaction: 'nested-scroll',
    scope: 'devices-manage-scroll',
    surface: 'Device Manage scroll containment',
    action: async () => { await scrollManage(dialog); },
    settleMs: 420,
    evidenceId: matrixEvidence('nested-scroll', 'Device details / long detail surface'),
  });

  await chooseSection(dialog, 'Technical');
  const technicalDetails = await firstVisibleOrNull(dialog.locator('.lite-device-advanced-details summary'));
  if (technicalDetails) {
    await measure({
      interaction: 'nested-detail-open',
      scope: 'devices-technical-details',
      surface: 'Device Manage Technical and troubleshooting details',
      action: async () => {
        await technicalDetails.click();
        await dialog.locator('.lite-device-advanced-details[open]').waitFor({ state: 'visible', timeout: 20_000 });
      },
      settleMs: 520,
      evidenceId: matrixEvidence('nested-detail-open', 'Device details / Diagnostics and history'),
    });
  } else {
    unavailableSurfaces.push('Device Manage / Technical and troubleshooting details');
  }

  await chooseSection(dialog, 'Health');
  const healthHistory = await firstVisibleOrNull(dialog.getByRole('button', { name: /Show health history/i }));
  if (healthHistory) {
    await measure({
      interaction: 'history-open',
      scope: 'devices-health-history',
      surface: 'Device Manage Health timeline',
      action: async () => {
        await healthHistory.click();
        await dialog.getByRole('region', { name: 'Device health history' }).waitFor({ state: 'visible', timeout: 20_000 });
      },
      settleMs: 520,
      evidenceId: matrixEvidence('history-open', 'Device details / health history'),
    });
    await capture('manage-health-history', dialog);
  } else {
    unavailableSurfaces.push('Device Manage / Health timeline was not reported by the selected runtime projection');
  }

  const mobileLayout = await dialog.getAttribute('data-lite-details-panel-layout');
  if (mobileLayout === 'mobile-sheet') {
    const smaller = await firstVisible(dialog.getByRole('button', { name: 'Make device sheet smaller' }), 'Device Manage smaller button');
    const expand = await firstVisible(dialog.getByRole('button', { name: 'Expand device sheet' }), 'Device Manage expand button');
    await measure({
      interaction: 'overlay-open',
      scope: 'devices-mobile-sheet-snap-states',
      surface: 'Device Manage compact, medium and expanded mobile sheet geometry',
      action: async () => {
        const state = dialog.locator('.lite-device-mobile-snap-actions span');
        await expectText(state, 'medium');
        const mediumHeight = (await dialog.boundingBox())?.height || 0;
        await smaller.click();
        await expectText(state, 'compact');
        const compactHeight = (await dialog.boundingBox())?.height || 0;
        await expand.click();
        await expectText(state, 'medium');
        await expand.click();
        await expectText(state, 'expanded');
        const expandedHeight = (await dialog.boundingBox())?.height || 0;
        if (!(compactHeight < mediumHeight && mediumHeight < expandedHeight)) {
          fail('Mobile sheet snap heights were not monotonic: compact=' + compactHeight + ' medium=' + mediumHeight + ' expanded=' + expandedHeight);
        }
        await assertNoOverflow('Devices mobile sheet');
      },
      settleMs: 460,
    });
    await capture('manage-sheet-expanded', dialog);
  } else {
    unavailableSurfaces.push('Device Manage mobile sheet geometry / physical CDP viewport reported desktop layout');
  }

  hapticProbe = await page.evaluate(() => {
    const probe = window.__POCKETLAB_ANDROID_DEVICES_HAPTICS__;
    const calls = Array.isArray(probe?.calls) ? probe.calls : [];
    return {
      supported: probe?.supported === true,
      instrumented: probe?.instrumented === true,
      touchActivationCalls: calls.length,
      acceptedCalls: calls.filter((call) => call?.accepted === true).length,
    };
  });
  if (!hapticProbe.supported) physicalNotes.push('Android Chrome did not expose navigator.vibrate; Devices haptics were unavailable.');
  else if (!hapticProbe.instrumented) physicalNotes.push('Android Chrome exposed navigator.vibrate, but the optional observation hook was unavailable.');
  else if (!hapticProbe.acceptedCalls) physicalNotes.push('No accepted vibration request was observed yet for the measured Devices touch path.');

  await measure({
    interaction: 'manage-close',
    scope: 'devices-manage-close-focus-return',
    surface: 'Device Manage close and focus restoration',
    action: async () => { await closeManage(dialog, manage); },
    settleMs: 440,
  });

  const topologySummary = await firstVisible(page.getByText('Connections & Topology', { exact: true }), 'Connections & Topology disclosure');
  await measure({
    interaction: 'overlay-open',
    scope: 'devices-topology-expand',
    surface: 'Connections and Topology disclosure expansion',
    action: async () => {
      await topologySummary.click();
      await page.locator('.lite-device-relationship-map').waitFor({ state: 'visible', timeout: 20_000 });
      await assertNoOverflow('Devices topology');
    },
    settleMs: 620,
  });
  await capture('topology');

  const topologyDevice = await firstVisibleOrNull(page.locator('.lite-device-relationship-node[role="button"]:not(.is-server)'));
  if (topologyDevice) {
    await measure({
      interaction: 'nested-detail-open',
      scope: 'devices-topology-device-selection',
      surface: 'Topology device selection and Manage opening',
      action: async () => {
        await touch(topologyDevice, 'Topology device selection');
        await page.getByRole('dialog', { name: /Manage / }).waitFor({ state: 'visible', timeout: 20_000 });
      },
      settleMs: 620,
    });
    const topologyDialog = await firstVisible(page.getByRole('dialog', { name: /Manage / }), 'Topology Manage dialog');
    const topologyManage = await firstVisible(page.getByRole('button', { name: /Manage / }), 'Topology Manage source action');
    await closeManage(topologyDialog, topologyManage);
  } else {
    unavailableSurfaces.push('Connections & Topology / selectable device peer was not projected');
  }

  await qualifyThemes();
  await waitForDevices();
  await assertNoOverflow('Devices final state');

  const requiredInteractions = ['screen-navigation', 'screen-steady', 'list-scroll', 'manage-open', 'section-switch', 'nested-scroll', 'overlay-open', 'manage-close'];
  const missing = requiredInteractions.filter((interaction) => !exercisedInteractions.has(interaction));
  if (missing.length) fail('Devices-only physical qualification missed interaction ids: ' + missing.join(', '));

  const summary = {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    status: hardGateFailures ? 'gate_miss' : targetMisses ? 'target_miss' : unavailableSurfaces.length ? 'qualified_with_gaps' : 'qualified',
    qualification_scope: 'devices',
    source_commit: commit,
    android_chrome_version: androidChromeVersion,
    android_package: 'com.android.chrome',
    candidate_manifest_verified: true,
    candidate_manifest_source_commit: candidateManifest.source_commit,
    candidate_manifest_response_header_verified: true,
    candidate_page_response_header_verified: true,
    candidate_page_meta_verified: true,
    android_cdp_identity_verified: process.env.LITE_ANDROID_CDP_DEVICE_IDENTITY_VERIFIED === '1'
      && process.env.LITE_ANDROID_CDP_BRIDGE_IDENTITY_VERIFIED === '1',
    android_candidate_reverse_verified: process.env.LITE_ANDROID_CANDIDATE_REVERSE_VERIFIED === '1',
    evidence_count: evidenceCount,
    target_misses: targetMisses,
    hard_gate_misses: hardGateFailures,
    haptics: hapticProbe,
    available_manage_sections: availableSections,
    unavailable_surfaces: unavailableSurfaces,
    request_failures: requestFailures.slice(0, 40),
    physical_notes: physicalNotes,
    sanitized: true,
  };
  await writeFile(resolve(outputDir, 'android-devices-summary.json'), JSON.stringify(summary, null, 2) + '\n', 'utf8');
  console.log('[ui-performance-android-devices] captured ' + evidenceCount + ' Devices-only physical evidence samples.');
  if (hardGateFailures || targetMisses) {
    if (hardGateFailures) console.error('[ui-performance-android-devices] ' + hardGateFailures + ' sample(s) exceeded the hard render gate.');
    if (targetMisses) console.error('[ui-performance-android-devices] ' + targetMisses + ' sample(s) missed the 60 FPS production target.');
    process.exitCode = 1;
  }
}

main()
  .catch((error) => {
    console.error('[ui-performance-android-devices] ERROR: ' + (error?.message || error));
    process.exitCode = 1;
  })
  .finally(async () => {
    await page?.close().catch(() => {});
    await browser?.close().catch(() => {});
  });
