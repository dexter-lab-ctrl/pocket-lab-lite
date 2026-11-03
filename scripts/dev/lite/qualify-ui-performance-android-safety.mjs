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
 * Safety-only physical qualification.
 *
 * This is deliberately a sibling of the established Apps/Access qualifiers.
 * It uses the same exact-SHA candidate, Android CDP bridge, foreground RAF
 * gate, wake-lock policy, sampler, evidence schema and absolute thresholds.
 * It never submits a scan or invokes a backend mutation.
 */

const cdpUrlValue = String(process.env.LITE_ANDROID_CDP_URL || '').trim();
const baseUrlValue = String(process.env.LITE_BASE_URL || '').trim();
const browserBridge = String(process.env.POCKETLAB_HARNESS_BROWSER_BRIDGE || '').trim();
const browserBridgeEnabled = process.env.LITE_QUALIFICATION_BROWSER_BRIDGE === '1';
const anonymousReadOnly = process.env.LITE_ANDROID_SAFETY_ANONYMOUS_READ_ONLY === '1';
const MINIMUM_FRAME_COUNT = 20;
const MINIMUM_SAMPLER_INTERVAL_COUNT = MINIMUM_FRAME_COUNT + 3;
const MAX_MINIMUM_FRAME_EXTENSION_MS = 2_000;

let browser;
let page;
let candidateManifest;
let androidChromeVersion = '';
let commit = '';
let outputDir;
let base;
let hardGateFailures = 0;
let targetMisses = 0;
let evidenceCount = 0;
let hapticProbe = {
  supported: false,
  instrumented: false,
  touchActivationCalls: 0,
  acceptedCalls: 0,
};
const exercisedInteractions = new Set();
const physicalNotes = [];
let nestedFindingStatus = 'UNVALIDATED';

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
  fail('Safety physical evidence requires an exact 40-character source commit.');
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
    entry.screen === 'security'
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

async function activateCandidate(candidatePage) {
  await candidatePage.bringToFront().catch(() => {});
  try {
    const session = await page.context().newCDPSession(candidatePage);
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
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  })).catch(() => 0);
  return Number(frames) >= 2;
}

async function requireScreenWakeLock() {
  const result = await page.evaluate(async () => {
    const existing = window.__POCKETLAB_ANDROID_SAFETY_WAKE_LOCK__;
    if (existing && !existing.released) return { supported: true, acquired: true };
    if (!navigator.wakeLock?.request) return { supported: false, acquired: false };
    try {
      const lock = await navigator.wakeLock.request('screen');
      window.__POCKETLAB_ANDROID_SAFETY_WAKE_LOCK__ = lock;
      window.setTimeout(() => lock.release().catch(() => {}), 300_000);
      return { supported: true, acquired: !lock.released };
    } catch {
      return { supported: true, acquired: false };
    }
  }).catch(() => ({ supported: false, acquired: false }));
  if (!result.acquired) fail('Android screen wake lock could not be acquired; physical Safety frame evidence would be throttled.');
}

async function proveForegroundCandidate(candidatePage) {
  const proof = await candidatePage.evaluate(async () => {
    const response = await fetch('/?pocketlab_qualification_sha_probe=1', {
      cache: 'no-store',
      credentials: 'same-origin',
    });
    return {
      ok: response.ok,
      responseHeader: response.headers.get('x-pocket-lab-candidate-sha'),
      meta: document.querySelector('meta[name="pocketlab-candidate-sha"]')?.getAttribute('content') || null,
    };
  }).catch(() => null);
  if (!proof?.ok || proof.responseHeader !== commit || proof.meta !== commit) {
    fail('The Android foreground Safety candidate did not prove the exact source SHA.');
  }
  await requireScreenWakeLock();
}

async function installSampler() {
  await page.addInitScript(() => {
    let active = null;
    window.__POCKETLAB_ANDROID_SAFETY_FRAME_SAMPLER__ = {
      start(name) {
        active?.raf && cancelAnimationFrame(active.raf);
        active?.observers?.forEach((observer) => observer.disconnect());
        active = {
          name: String(name || 'safety-interaction').slice(0, 96),
          previous: null,
          intervals: [],
          longTasks: [],
          longAnimationFrames: [],
          eventDurations: [],
          observers: [],
          raf: null,
        };
        const sample = active;
        const tick = (timestamp) => {
          if (active !== sample) return;
          if (sample.previous !== null) sample.intervals.push(timestamp - sample.previous);
          sample.previous = timestamp;
          sample.raf = requestAnimationFrame(tick);
        };
        sample.raf = requestAnimationFrame(tick);
        if ('PerformanceObserver' in window) {
          try {
            const observer = new PerformanceObserver((list) => {
              list.getEntries().forEach((entry) => sample.longTasks.push(Number(entry.duration) || 0));
            });
            observer.observe({ entryTypes: ['longtask'] });
            sample.observers.push(observer);
          } catch {}
          try {
            const observer = new PerformanceObserver((list) => {
              list.getEntries().forEach((entry) => sample.longAnimationFrames.push(Number(entry.duration) || 0));
            });
            observer.observe({ type: 'long-animation-frame', buffered: false });
            sample.observers.push(observer);
          } catch {}
          try {
            const observer = new PerformanceObserver((list) => {
              list.getEntries().forEach((entry) => sample.eventDurations.push(Number(entry.duration) || 0));
            });
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
      count() {
        return active?.intervals?.length || 0;
      },
    };
  });
}

async function installHapticProbe() {
  await page.addInitScript(() => {
    const original = typeof Navigator !== 'undefined' ? Navigator.prototype.vibrate : null;
    const probe = {
      supported: typeof original === 'function',
      instrumented: false,
      calls: [],
    };
    window.__POCKETLAB_ANDROID_SAFETY_HAPTIC_PROBE__ = probe;
    if (!probe.supported) return;
    try {
      Object.defineProperty(Navigator.prototype, 'vibrate', {
        configurable: true,
        value(pattern) {
          let accepted = false;
          try {
            accepted = Boolean(original.call(this, pattern));
          } catch {
            accepted = false;
          }
          probe.calls.push({
            pattern: Array.isArray(pattern) ? pattern.slice(0, 12) : pattern,
            accepted,
          });
          return accepted;
        },
      });
      probe.instrumented = true;
    } catch {
      // The support result remains useful even if this optional observer is
      // blocked by the browser's Navigator implementation.
    }
  });
}

async function qualifyRealDeviceHaptics(manageButton) {
  const before = await page.evaluate(() => {
    const probe = window.__POCKETLAB_ANDROID_SAFETY_HAPTIC_PROBE__;
    return {
      supported: probe?.supported === true,
      instrumented: probe?.instrumented === true,
      count: Array.isArray(probe?.calls) ? probe.calls.length : 0,
    };
  });
  await dispatchAndroidTouch(manageButton, 'Manage Safety haptic probe');
  const dialog = await firstVisible(page.getByRole('dialog', { name: 'Manage Safety' }), 'Manage Safety haptic probe dialog');
  const close = await firstVisible(dialog.getByRole('button', { name: 'Close security details' }), 'Close Manage Safety haptic probe');
  await dispatchAndroidTouch(close, 'Close Manage Safety haptic probe');
  await dialog.waitFor({ state: 'hidden', timeout: 20_000 });
  const after = await page.evaluate(() => {
    const probe = window.__POCKETLAB_ANDROID_SAFETY_HAPTIC_PROBE__;
    const calls = Array.isArray(probe?.calls) ? probe.calls : [];
    return {
      supported: probe?.supported === true,
      instrumented: probe?.instrumented === true,
      calls: calls.slice(-4),
    };
  });
  const calls = after.calls.slice(Math.max(0, before.count));
  hapticProbe = {
    supported: after.supported,
    instrumented: after.instrumented,
    touchActivationCalls: calls.length,
    acceptedCalls: calls.filter((call) => call?.accepted === true).length,
  };
  if (!hapticProbe.supported) {
    physicalNotes.push('Android Chrome did not expose navigator.vibrate; real-device haptics were not available.');
  } else if (!hapticProbe.instrumented) {
    physicalNotes.push('Android Chrome exposed navigator.vibrate, but the optional observation hook was unavailable.');
  } else if (hapticProbe.acceptedCalls > 0) {
    physicalNotes.push('Android Chrome accepted vibration requests from real touch activation of Safety controls.');
  } else {
    physicalNotes.push('Android Chrome exposed navigator.vibrate, but no vibration request was observed for the touch probe.');
  }
}

async function dispatchAndroidTouch(locator, label) {
  const box = await locator.boundingBox().catch(() => null);
  if (!box || box.width <= 0 || box.height <= 0) fail(label + ' did not expose a touchable bounding box.');
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  const session = await page.context().newCDPSession(page);
  try {
    // Match Playwright's raw Android touchscreen implementation: the browser
    // receives a real CDP touch sequence, not a DOM click or mouse event.
    await Promise.all([
      session.send('Input.dispatchTouchEvent', {
        type: 'touchStart',
        modifiers: 0,
        touchPoints: [{ x, y }],
      }),
      session.send('Input.dispatchTouchEvent', {
        type: 'touchEnd',
        modifiers: 0,
        touchPoints: [],
      }),
    ]);
  } finally {
    await session.detach().catch(() => {});
  }
}

async function waitForSafety() {
  await page.locator('[data-lite-screen-id="security"]').waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('[data-safety-native-page="true"]').waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('[data-safety-native-hero="true"]').waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('[data-safety-native-destinations="true"]').waitFor({ state: 'visible', timeout: 20_000 });
  await page.evaluate(async () => {
    if ('fonts' in document) await document.fonts.ready;
  });
  await page.waitForTimeout(500);
}

async function gotoSafety() {
  const target = new URL('/?screen=security', base);
  const response = await page.goto(target.toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  if (!response?.ok()) fail('The physical Android Safety candidate did not load.');
  if (response.headers()['x-pocket-lab-candidate-sha'] !== commit) {
    fail('The physical Android Safety page response header did not prove the exact source SHA.');
  }
  if (await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content') !== commit) {
    fail('The physical Android Safety page metadata did not prove the exact source SHA.');
  }
  await requireScreenWakeLock();
  await waitForSafety();
}

async function assertDock(label) {
  const state = await page.evaluate(() => {
    const nav = document.querySelector('.pocket-nav-dock');
    if (!nav) return { present: false };
    const rect = nav.getBoundingClientRect();
    const viewportHeight = window.visualViewport?.height || window.innerHeight;
    const computed = getComputedStyle(nav);
    return {
      present: true,
      position: computed.position,
      top: rect.top,
      bottomGap: viewportHeight - rect.bottom,
      height: rect.height,
      viewportHeight,
      background: computed.backgroundColor,
      zIndex: computed.zIndex,
      visible: rect.width > 0 && rect.height > 0,
    };
  });
  if (!state.present || !state.visible) fail('Safety dock was not visible during ' + label + '.');
  if (state.position !== 'fixed' || state.bottomGap < -4 || state.bottomGap > 8) {
    fail('Safety dock was not anchored to the visible viewport during ' + label + ': ' + JSON.stringify(state));
  }
  if (!state.background || state.background === 'rgba(0, 0, 0, 0)' || state.background === 'transparent') {
    fail('Safety dock did not expose an opaque background during ' + label + '.');
  }
  return state;
}

async function scrollSafety() {
  const result = await page.evaluate(async () => {
    const root = document.scrollingElement || document.documentElement;
    const startTop = root.scrollTop;
    const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
    const distance = Math.min(maxScroll, Math.max(180, Math.round(window.innerHeight * 0.55)));
    let observed = null;
    await new Promise((resolveScroll) => {
      const started = performance.now();
      const step = (now) => {
        const progress = Math.min(1, (now - started) / 700);
        root.scrollTop = Math.min(maxScroll, startTop + distance * progress);
        if (progress >= 0.85 && !observed) {
          const nav = document.querySelector('.pocket-nav-dock');
          const rect = nav?.getBoundingClientRect();
          const viewportHeight = window.visualViewport?.height || window.innerHeight;
          observed = nav && rect ? {
            bottomGap: viewportHeight - rect.bottom,
            position: getComputedStyle(nav).position,
            background: getComputedStyle(nav).backgroundColor,
          } : null;
        }
        if (progress < 1) requestAnimationFrame(step);
        else {
          root.scrollTop = startTop;
          resolveScroll();
        }
      };
      requestAnimationFrame(step);
    });
    return {
      maxScroll,
      observed,
      finalScrollTop: root.scrollTop,
      finalBottomReachable: root.scrollHeight - root.scrollTop >= root.clientHeight,
    };
  });
  if (result.maxScroll <= 0) physicalNotes.push('Safety landing content did not require scrolling on the physical viewport.');
  if (!result.observed || result.observed.position !== 'fixed' || result.observed.bottomGap < -4 || result.observed.bottomGap > 8) {
    fail('Safety dock lost bottom anchoring during scroll: ' + JSON.stringify(result));
  }
  if (!result.observed.background || result.observed.background === 'rgba(0, 0, 0, 0)') {
    fail('Safety dock became transparent during scroll.');
  }
  if (result.finalBottomReachable !== true) fail('Safety page final content was not reachable above the dock.');
}

async function measure({ interaction, scope, surface, action, settleMs = 440, evidenceId = null }) {
  if (!LITE_PERFORMANCE_INTERACTIONS.includes(interaction)) {
    fail('Unknown Safety interaction id: ' + interaction);
  }
  await page.evaluate((name) => window.__POCKETLAB_ANDROID_SAFETY_FRAME_SAMPLER__?.start(name), 'android-cdp:safety:' + interaction + ':' + scope);
  await action();
  if (settleMs > 0) await page.waitForTimeout(settleMs);
  const extensionDeadline = Date.now() + MAX_MINIMUM_FRAME_EXTENSION_MS;
  while (Date.now() < extensionDeadline) {
    const count = await page.evaluate(() => window.__POCKETLAB_ANDROID_SAFETY_FRAME_SAMPLER__?.count?.() || 0).catch(() => 0);
    if (count >= MINIMUM_SAMPLER_INTERVAL_COUNT) break;
    await page.waitForTimeout(50);
  }
  const raw = await page.evaluate(() => window.__POCKETLAB_ANDROID_SAFETY_FRAME_SAMPLER__?.stop?.() || null);
  if (!raw) fail('Safety frame sampler returned no evidence for ' + scope + '.');
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
    interaction: 'android-cdp:safety:' + interaction + ':' + scope,
    performance_evidence_id: evidenceId,
    phase4_interaction: interaction,
    interaction_scope: scope,
    interaction_surface: surface,
    mode: 'live',
    qualification_surface: 'android-cdp',
    browser_project: 'android-cdp-safety-only',
    rendering_surface: 'physical-android-chrome',
    qualification_scope: 'safety',
    android_chrome_version: androidChromeVersion,
    android_package: 'com.android.chrome',
    source_commit: commit,
    candidate_manifest_verified: true,
    candidate_manifest_source_commit: candidateManifest.source_commit,
    candidate_manifest_schema_version: candidateManifest.schema_version,
    candidate_manifest_response_header_verified: true,
    candidate_page_response_header_verified: true,
    candidate_page_meta_verified: true,
    android_cdp_identity_verified: true,
    android_candidate_reverse_verified: process.env.LITE_ANDROID_CANDIDATE_REVERSE_VERIFIED === '1',
    sanitized: true,
    viewport,
    ...summary,
  };
  const fileName = 'ui-performance-android-safety-' + sanitizeLitePerformanceName(scope) + '-' + sanitizeLitePerformanceName(interaction) + '.json';
  await writeFile(resolve(outputDir, fileName), JSON.stringify(report, null, 2) + '\n', 'utf8');
  exercisedInteractions.add(interaction);
  evidenceCount += 1;
  if (!report.gate_passed) hardGateFailures += 1;
  if (!report.target_met) targetMisses += 1;
  const status = report.target_met ? 'TARGET-PASS' : report.gate_passed ? 'TARGET-MISS' : 'GATE-MISS';
  console.log('[ui-performance-android-safety] ' + status + ' ' + interaction + ' (' + scope + '): p95=' + report.p95_frame_ms + 'ms smooth=' + report.target_smooth_frame_ratio);
}

async function capture(name, target = page) {
  const path = resolve(outputDir, 'android-safety-' + sanitizeLitePerformanceName(name) + '.png');
  await target.screenshot({ path, animations: 'disabled' });
  console.log('[ui-performance-android-safety] screenshot ' + name + ': ' + path);
}

const MANAGE_SECTIONS = [
  { label: 'Overview', region: 'Overview' },
  { label: 'Checks', region: 'Checks' },
  { label: 'Changes', region: 'Changes' },
  { label: 'Issues', region: 'Issues' },
  { label: 'Coverage', region: 'Coverage' },
  { label: 'Check path', region: 'Check path' },
  { label: 'Evidence', region: 'Evidence' },
  { label: 'History', region: 'History' },
  { label: 'Technical details', region: 'Technical details' },
];

async function returnToManageIndex(dialog) {
  const back = dialog.getByRole('button', { name: 'Back to Manage Safety' });
  if (await back.isVisible().catch(() => false)) {
    await back.click();
    await dialog.locator('[data-safety-manage-view="index"]').waitFor({ state: 'visible', timeout: 20_000 });
  }
}

async function selectManageSection(dialog, section) {
  const row = dialog.locator('.lite-safety-native-nav-row[aria-label="Open ' + section.label + ' in Manage Safety"]');
  await row.click();
  if (await row.getAttribute('aria-current') !== 'page') {
    fail('Safety Manage did not select ' + section.label + '.');
  }
  await dialog.getByRole('region', { name: section.region }).waitFor({ state: 'visible', timeout: 20_000 });
}

async function main() {
  if (anonymousReadOnly && (browserBridgeEnabled || browserBridge)) {
    fail('Anonymous Safety qualification cannot receive a browser bridge or qualification marker.');
  }
  if (!anonymousReadOnly && browserBridgeEnabled !== Boolean(browserBridge)) {
    fail('Synthetic Android browser qualification requires an explicit browser bridge and LITE_QUALIFICATION_BROWSER_BRIDGE=1.');
  }
  commit = exactSourceCommit();
  outputDir = resolve(process.env.LITE_ANDROID_SAFETY_OUTPUT_DIR || '.pocketlab-dev/performance/android-safety-' + commit);
  await mkdir(outputDir, { recursive: true });
  const cdp = endpoint(cdpUrlValue, 'LITE_ANDROID_CDP_URL');
  base = endpoint(baseUrlValue, 'LITE_BASE_URL');
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
  const context = contexts[0];
  if (browserBridge) await context.setExtraHTTPHeaders({ 'X-Pocket-Lab-Qualification-Bridge': browserBridge });
  const candidateOrigin = base.origin;
  const existingCandidatePages = context.pages().filter((candidatePage) => candidatePage.url().startsWith(candidateOrigin));
  page = await context.newPage();
  const candidatePages = [page, ...existingCandidatePages.filter((candidatePage) => candidatePage !== page)];

  await activateCandidate(page);
  await installHapticProbe();
  await page.goto(new URL('/?pocketlab_qualification_bootstrap=1', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await requireScreenWakeLock();
  await page.evaluate(async () => {
    const registrations = await navigator.serviceWorker?.getRegistrations?.() || [];
    await Promise.all(registrations.map((registration) => registration.unregister()));
    if ('caches' in window) {
      const names = await caches.keys();
      await Promise.all(names.map((name) => caches.delete(name)));
    }
  });

  const manifestResponse = await page.goto(new URL('/__pocketlab_qualification__/candidate.json', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  if (!manifestResponse?.ok()) fail('The Android base URL did not expose the exact-SHA candidate manifest.');
  try {
    candidateManifest = JSON.parse(await page.locator('body').innerText());
  } catch {
    fail('The Android candidate manifest was not valid JSON.');
  }
  if (candidateManifest?.source_commit !== commit || candidateManifest?.sanitized !== true) {
    fail('The Android Safety candidate manifest source SHA does not match the requested exact commit.');
  }
  if (manifestResponse.headers()['x-pocket-lab-candidate-sha'] !== commit) {
    fail('The Android Safety candidate manifest response header did not prove the exact commit.');
  }

  const candidatePageResponse = await page.goto(new URL('/?screen=security', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  if (!candidatePageResponse?.ok()) fail('The Android Safety candidate page did not load.');
  if (candidatePageResponse.headers()['x-pocket-lab-candidate-sha'] !== commit) {
    fail('The Android Safety rendered page response header did not prove the exact commit.');
  }
  if (await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content') !== commit) {
    fail('The Android Safety rendered page metadata did not prove the exact commit.');
  }

  let foregroundReady = false;
  for (const candidatePage of candidatePages) {
    page = candidatePage;
    await activateCandidate(candidatePage);
    await proveForegroundCandidate(candidatePage);
    foregroundReady = await receivesAnimationFrames(candidatePage);
    for (let attempt = 0; !foregroundReady && attempt < 2; attempt += 1) {
      await activateCandidate(candidatePage);
      await candidatePage.reload({ waitUntil: 'domcontentloaded', timeout: 30_000 }).catch(() => {});
      await proveForegroundCandidate(candidatePage);
      foregroundReady = await receivesAnimationFrames(candidatePage);
    }
    if (foregroundReady) break;
  }
  if (!foregroundReady) fail('Android Safety candidate did not deliver foreground animation frames.');
  await Promise.all(candidatePages.filter((candidatePage) => candidatePage !== page).map((candidatePage) => candidatePage.close().catch(() => {})));

  await installSampler();
  if (anonymousReadOnly) {
    physicalNotes.push('Explicit anonymous read-only Safety projection; no harness bridge or write-capable authority was used.');
  }
  await gotoSafety();
  const hero = page.locator('[data-safety-native-hero="true"]');
  const destinations = page.locator('[data-safety-native-destinations="true"]');
  const manageButton = await firstVisible(page.getByRole('button', { name: 'Manage Security details' }), 'Manage Safety');
  await qualifyRealDeviceHaptics(manageButton);
  await measure({
    interaction: 'screen-steady',
    scope: 'safety-landing',
    surface: 'Safety landing hero, reported state, score and destinations',
    action: async () => {
      await hero.waitFor({ state: 'visible' });
      await destinations.waitFor({ state: 'visible' });
      await assertDock('Safety landing');
    },
    settleMs: 720,
  });
  await capture('landing');

  await measure({
    interaction: 'list-scroll',
    scope: 'safety-landing-scroll-dock',
    surface: 'Safety landing scroll containment and dock anchoring',
    action: async () => { await scrollSafety(); },
    settleMs: 480,
  });

  await measure({
    interaction: 'manage-open',
    scope: 'safety-manage-open',
    surface: 'Safety Manage opening',
    action: async () => {
      await manageButton.click();
      await page.getByRole('dialog', { name: 'Manage Safety' }).waitFor({ state: 'visible', timeout: 20_000 });
    },
    settleMs: 520,
  });
  const dialog = await firstVisible(page.getByRole('dialog', { name: 'Manage Safety' }), 'Manage Safety dialog');
  await measure({
    interaction: 'screen-steady',
    scope: 'safety-manage-index',
    surface: 'Safety Manage grouped native index',
    action: async () => {
      await dialog.locator('[data-safety-manage-view="index"]').waitFor({ state: 'visible', timeout: 20_000 });
      await assertDock('Safety Manage index');
    },
    settleMs: 520,
  });
  await capture('manage-index', dialog);

  for (const section of MANAGE_SECTIONS) {
    await returnToManageIndex(dialog);
    await measure({
      interaction: 'section-switch',
      scope: 'safety-manage-' + sanitizeLitePerformanceName(section.label),
      surface: 'Safety Manage / ' + section.label,
      evidenceId: section.label === 'History'
        ? matrixEvidence('history-open', 'Security Manage / history details')
        : null,
      action: async () => { await selectManageSection(dialog, section); },
      settleMs: 520,
    });
    if (section.label === 'History') await capture('manage-history', dialog);
  }

  await returnToManageIndex(dialog);
  await selectManageSection(dialog, { label: 'Checks', region: 'Checks' });
  const profileTab = await firstVisibleOrNull(dialog.getByRole('tab', { name: 'Full Scan', exact: true }));
  if (profileTab) {
    await measure({
      interaction: 'section-switch',
      scope: 'safety-profile-view',
      surface: 'Safety Manage read-only profile view selection',
      action: async () => {
        await profileTab.click();
        if (await profileTab.getAttribute('aria-selected') !== 'true') fail('Full Scan profile view did not become selected.');
        const quick = dialog.getByRole('tab', { name: 'Quick Scan', exact: true });
        await quick.click();
        if (await quick.getAttribute('aria-selected') !== 'true') fail('Quick Scan profile view did not restore.');
      },
      settleMs: 420,
    });
  } else {
    physicalNotes.push('Safety profile view tabs were not exposed by the physical projection.');
  }

  await returnToManageIndex(dialog);
  await measure({
    interaction: 'section-switch',
    scope: 'safety-repeated-controlled-navigation',
    surface: 'Safety Manage repeated controlled read-only navigation',
    action: async () => {
      await selectManageSection(dialog, { label: 'Checks', region: 'Checks' });
      await returnToManageIndex(dialog);
      await selectManageSection(dialog, { label: 'History', region: 'History' });
      await returnToManageIndex(dialog);
    },
    settleMs: 520,
  });

  await returnToManageIndex(dialog);
  await selectManageSection(dialog, { label: 'Issues', region: 'Issues' });
  const findingTrigger = await firstVisibleOrNull(dialog.locator('.lite-finding-detail-trigger'));
  if (findingTrigger) {
    nestedFindingStatus = 'VERIFIED';
    await measure({
      interaction: 'nested-detail-open',
      scope: 'safety-finding-details',
      surface: 'Safety Manage / read-only finding details',
      evidenceId: matrixEvidence('finding-detail-open', 'Security Manage / finding details'),
      action: async () => {
        await findingTrigger.click();
        await page.locator('.lite-security-detail-layer').waitFor({ state: 'visible', timeout: 20_000 });
      },
      settleMs: 520,
    });
    await capture('finding-details');
    await measure({
      interaction: 'nested-detail-close',
      scope: 'safety-finding-details-return',
      surface: 'Safety finding details / return to Manage',
      action: async () => {
        const close = page.locator('.lite-security-detail-layer').getByRole('button', { name: 'Close finding details' }).first();
        await close.click();
        await page.locator('.lite-security-detail-layer').waitFor({ state: 'hidden', timeout: 20_000 });
      },
      settleMs: 420,
    });
  } else {
    nestedFindingStatus = 'NOT_APPLICABLE';
    physicalNotes.push('No reported Safety finding was present in the candidate projection; nested finding details were not applicable.');
  }

  const closeButton = await firstVisible(dialog.getByRole('button', { name: 'Close security details' }), 'Close Manage Safety');
  await measure({
    interaction: 'manage-close',
    scope: 'safety-manage-close',
    surface: 'Safety Manage close and focus return boundary',
    action: async () => {
      await closeButton.click();
      await dialog.waitFor({ state: 'hidden', timeout: 20_000 });
      await page.getByRole('button', { name: 'Manage Security details' }).waitFor({ state: 'visible' });
      await assertDock('Safety after Manage close');
    },
    settleMs: 440,
  });

  await measure({
    interaction: 'manage-open',
    scope: 'safety-manage-reopen-after-navigation',
    surface: 'Safety Manage reopen after returning to the Safety landing',
    action: async () => {
      await page.getByRole('button', { name: 'Manage Security details' }).click();
      await page.getByRole('dialog', { name: 'Manage Safety' }).waitFor({ state: 'visible', timeout: 20_000 });
    },
    settleMs: 520,
  });
  const reopenedDialog = page.getByRole('dialog', { name: 'Manage Safety' });
  await capture('manage-reopened', reopenedDialog);
  await firstVisible(reopenedDialog.getByRole('button', { name: 'Close security details' }), 'Close reopened Manage Safety').then((button) => button.click());
  await reopenedDialog.waitFor({ state: 'hidden', timeout: 20_000 });
  await assertDock('Safety final landing');
  await capture('final-landing');

  const requiredInteractions = ['screen-steady', 'list-scroll', 'manage-open', 'manage-close', 'section-switch'];
  const missing = requiredInteractions.filter((interaction) => !exercisedInteractions.has(interaction));
  if (missing.length) fail('Safety-only physical qualification missed interaction ids: ' + missing.join(', '));

  const summary = {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    status: hardGateFailures ? 'gate_miss' : targetMisses ? 'target_miss' : 'qualified',
    qualification_scope: 'safety',
    source_commit: commit,
    android_chrome_version: androidChromeVersion,
    android_package: 'com.android.chrome',
    evidence_count: evidenceCount,
    target_misses: targetMisses,
    hard_gate_misses: hardGateFailures,
    nested_finding_details: nestedFindingStatus,
    haptics: hapticProbe,
    physical_notes: physicalNotes,
    sanitized: true,
  };
  await writeFile(resolve(outputDir, 'android-safety-summary.json'), JSON.stringify(summary, null, 2) + '\n', 'utf8');
  console.log('[ui-performance-android-safety] captured ' + evidenceCount + ' Safety-only physical evidence samples.');
  if (hardGateFailures || targetMisses) {
    if (hardGateFailures) console.error('[ui-performance-android-safety] ' + hardGateFailures + ' sample(s) exceeded the hard render gate.');
    if (targetMisses) console.error('[ui-performance-android-safety] ' + targetMisses + ' sample(s) missed the 60 FPS production target.');
    process.exitCode = 1;
  }
}

main()
  .catch((error) => {
    console.error('[ui-performance-android-safety] ERROR: ' + (error?.message || error));
    process.exitCode = 1;
  })
  .finally(async () => {
    await page?.close().catch(() => {});
    await browser?.close().catch(() => {});
  });
