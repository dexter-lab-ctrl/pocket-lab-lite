#!/usr/bin/env node

import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import {
  LITE_PERFORMANCE_SCHEMA_VERSION,
  sanitizeLitePerformanceName,
  summarizeLiteFrames,
} from '../../../src/performance/litePerformanceBudget.js';
import { LITE_UI_PERFORMANCE_MATRIX } from '../../../src/performance/litePerformanceMatrix.js';

const cdpUrlValue = String(process.env.LITE_ANDROID_CDP_URL || '').trim();
const baseUrlValue = String(process.env.LITE_BASE_URL || '').trim();
const browserBridge = String(process.env.POCKETLAB_HARNESS_BROWSER_BRIDGE || '').trim();
const browserBridgeEnabled = process.env.LITE_QUALIFICATION_BROWSER_BRIDGE === '1';
const outputDir = resolve(process.env.LITE_ANDROID_APPS_OUTPUT_DIR || '.pocketlab-dev/performance');
const minimumFrameCount = 20;
const minimumSamplerIntervalCount = minimumFrameCount + 3;
const maxMinimumFrameExtensionMs = 2_000;
const candidatePagePath = '/?screen=catalog';

const gaps = [];
const reports = [];
let targetMisses = 0;
let gateFailures = 0;
let browser;
let page;
let candidatePages = [];
let candidateManifest;
let candidateManifestResponseHeaderVerified = false;
let candidatePageResponseHeaderVerified = false;
let candidatePageMetaVerified = false;
let androidChromeVersion = '';
let commit = '';

function fail(message) {
  throw new Error(message);
}

function gap(surface, reason, status = 'INCONCLUSIVE') {
  const entry = { surface, reason, status };
  gaps.push(entry);
  console.warn(`[ui-performance-android-apps] ${status} ${surface}: ${reason}`);
  return entry;
}

function exactSourceCommit() {
  const configured = String(process.env.LITE_PERF_SOURCE_COMMIT || process.env.GITHUB_SHA || '').trim();
  if (/^[0-9a-f]{40}$/.test(configured) && !/^0+$/.test(configured)) return configured;
  try {
    const value = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    if (/^[0-9a-f]{40}$/.test(value) && !/^0+$/.test(value)) return value;
  } catch {
    // Fall through to the fail-closed error below.
  }
  fail('UI performance evidence requires an exact 40-character source commit.');
}

function endpoint(value, label) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    fail(`${label} must be a valid URL.`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) fail(`${label} must use http:// or https://.`);
  if (parsed.username || parsed.password) fail(`${label} must not contain credentials.`);
  return parsed;
}

async function jsonFetch(url, label) {
  let response;
  try {
    response = await fetch(url, { headers: { Accept: 'application/json' } });
  } catch (error) {
    fail(`${label} was not reachable: ${error?.message || error}`);
  }
  if (!response.ok) fail(`${label} returned HTTP ${response.status}.`);
  try {
    return await response.json();
  } catch {
    fail(`${label} did not return valid JSON.`);
  }
}

async function validateCdpIdentity(cdp) {
  const version = await jsonFetch(new URL('/json/version', cdp).toString(), 'Android CDP version endpoint');
  if (version['Android-Package'] !== 'com.android.chrome') {
    fail('The CDP endpoint did not identify com.android.chrome.');
  }
  const websocket = new URL(version.webSocketDebuggerUrl || '');
  if (!['127.0.0.1', 'localhost'].includes(websocket.hostname) || Number(websocket.port) !== Number(cdp.port)) {
    fail(`The CDP websocket did not remain on the WSL-local endpoint: ${version.webSocketDebuggerUrl}`);
  }
  return {
    package: version['Android-Package'],
    browser: String(version.Browser || '').trim(),
    protocol: String(version['Protocol-Version'] || '').trim(),
    websocket_local: true,
  };
}

function matrixEvidence(screen, interaction, nestedSurface) {
  return LITE_UI_PERFORMANCE_MATRIX.find((entry) => (
    entry.screen === screen
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
  fail(`Could not find visible ${label}.`);
}

async function firstVisibleOrNull(locator) {
  const count = await locator.count().catch(() => 0);
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible().catch(() => false)) return candidate;
  }
  return null;
}

async function waitForCatalog() {
  await page.locator('[data-lite-screen-id="catalog"]').waitFor({ state: 'visible', timeout: 20_000 });
  await page.evaluate(async () => {
    if ('fonts' in document) await document.fonts.ready;
  });
  // Performance-mode Apps Manage intentionally mounts its body after a bounded
  // delay. Let that source-owned boundary settle before inspecting disclosures.
  await page.waitForTimeout(1_100);
  await page.locator('[data-lite-sw-update-ready="true"]').evaluateAll((nodes) => {
    nodes.forEach((node) => node.remove());
  }).catch(() => {});
}

async function requireWakeLock() {
  const result = await page.evaluate(async () => {
    const existing = window.__POCKETLAB_ANDROID_APPS_WAKE_LOCK__;
    if (existing && !existing.released) return { supported: true, acquired: true };
    if (!navigator.wakeLock?.request) return { supported: false, acquired: false };
    try {
      const lock = await navigator.wakeLock.request('screen');
      window.__POCKETLAB_ANDROID_APPS_WAKE_LOCK__ = lock;
      window.setTimeout(() => lock.release().catch(() => {}), 300_000);
      return { supported: true, acquired: !lock.released };
    } catch {
      return { supported: true, acquired: false };
    }
  }).catch(() => ({ supported: false, acquired: false }));
  if (!result.acquired) fail('Android screen wake lock could not be acquired for physical Apps evidence.');
}

async function receivesAnimationFrames(candidatePage) {
  const frames = await candidatePage.evaluate(() => new Promise((resolve) => {
    let count = 0;
    const timeout = setTimeout(() => resolve(count), 350);
    const tick = () => {
      count += 1;
      if (count >= 2) {
        clearTimeout(timeout);
        resolve(count);
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  })).catch(() => 0);
  return Number(frames) >= 2;
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

async function proveCandidatePage(candidatePage, targetUrl) {
  const response = await candidatePage.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  if (!response?.ok()) fail(`Candidate page did not load: ${targetUrl}`);
  candidatePageResponseHeaderVerified = response.headers()['x-pocket-lab-candidate-sha'] === commit;
  if (!candidatePageResponseHeaderVerified) fail('The rendered Apps page response header did not prove the exact candidate SHA.');
  const meta = await candidatePage.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content').catch(() => null);
  candidatePageMetaVerified = meta === commit;
  if (!candidatePageMetaVerified) fail('The rendered Apps page did not expose the exact candidate SHA.');
}

async function installSampler() {
  await page.evaluate(() => {
    let active = null;
    window.__POCKETLAB_ANDROID_APPS_SAMPLER__ = {
      start(name) {
        if (active?.raf) cancelAnimationFrame(active.raf);
        active?.observers?.forEach((observer) => observer.disconnect());
        window.__POCKETLAB_LITE_PERF__?.resetSummary?.();
        const sample = {
          name: String(name || 'apps-interaction').slice(0, 96),
          previous: null,
          intervals: [],
          longTasks: [],
          longAnimationFrames: [],
          eventDurations: [],
          observers: [],
          raf: null,
        };
        active = sample;
        const frame = (timestamp) => {
          if (active !== sample) return;
          if (sample.previous !== null) sample.intervals.push(timestamp - sample.previous);
          sample.previous = timestamp;
          sample.raf = requestAnimationFrame(frame);
        };
        sample.raf = requestAnimationFrame(frame);
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
        const react = window.__POCKETLAB_LITE_PERF__?.readSummary?.() || null;
        return {
          interaction: sample.name,
          intervals: sample.intervals.slice(0, 600),
          longTasks: sample.longTasks.slice(0, 120),
          longAnimationFrames: sample.longAnimationFrames.slice(0, 120),
          eventDurations: sample.eventDurations.slice(0, 120),
          react,
        };
      },
      count() {
        return active?.intervals?.length || 0;
      },
    };
  });
}

function summarizeReact(raw) {
  const commits = raw?.commits && typeof raw.commits === 'object' ? Object.values(raw.commits) : [];
  if (!commits.length) {
    return {
      react_profile_available: false,
      react_commit_count: 0,
      react_commit_p95_ms: null,
      react_commit_max_ms: null,
      react_commit_target_met: null,
      react_commit_gate_passed: null,
    };
  }
  const p95 = Math.max(...commits.map((item) => Number(item?.p95_commit_ms || 0)));
  const max = Math.max(...commits.map((item) => Number(item?.max_commit_ms || 0)));
  const count = commits.reduce((total, item) => total + Number(item?.commit_count || 0), 0);
  return {
    react_profile_available: true,
    react_commit_count: count,
    react_commit_p95_ms: p95,
    react_commit_max_ms: max,
    react_commit_target_met: commits.every((item) => item?.target_met === true),
    react_commit_gate_passed: commits.every((item) => item?.gate_passed === true),
  };
}

async function capture(name, target = page) {
  const path = resolve(outputDir, `android-apps-${sanitizeLitePerformanceName(name)}.png`);
  await target.screenshot({ path, animations: 'disabled' });
  console.log(`[ui-performance-android-apps] screenshot ${sanitizeLitePerformanceName(name)}: ${path}`);
  return path;
}

async function measure({ interaction, scope, surface, action, evidenceId = null, settleMs = 420 }) {
  const evidenceInteraction = sanitizeLitePerformanceName(`android-cdp-apps:${scope}:${interaction}`);
  await page.evaluate((name) => window.__POCKETLAB_ANDROID_APPS_SAMPLER__?.start(name), evidenceInteraction);
  const started = Date.now();
  let actionError;
  try {
    await action();
    if (settleMs > 0) await page.waitForTimeout(settleMs);
  } catch (error) {
    actionError = error;
  }
  const extensionDeadline = Date.now() + maxMinimumFrameExtensionMs;
  while (Date.now() < extensionDeadline) {
    const frameCount = await page.evaluate(
      () => window.__POCKETLAB_ANDROID_APPS_SAMPLER__?.count?.() || 0,
    ).catch(() => 0);
    if (frameCount >= minimumSamplerIntervalCount) break;
    await page.waitForTimeout(50);
  }
  const raw = await page.evaluate(() => window.__POCKETLAB_ANDROID_APPS_SAMPLER__?.stop?.() || null);
  if (actionError) throw actionError;
  if (!raw) fail(`Android Apps frame sampler returned no evidence for ${interaction} (${scope}).`);
  const summary = summarizeLiteFrames(raw.intervals || [], {
    longTasks: raw.longTasks || [],
    longAnimationFrames: raw.longAnimationFrames || [],
    eventDurations: raw.eventDurations || [],
    warmupFrames: 3,
  });
  if (summary.frame_count < minimumFrameCount) {
    fail(`${interaction} (${scope}) produced only ${summary.frame_count} measured frames; at least ${minimumFrameCount} are required.`);
  }
  const react = summarizeReact(raw.react);
  const viewport = page.viewportSize();
  const report = {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    interaction: evidenceInteraction,
    performance_evidence_id: evidenceId ? sanitizeLitePerformanceName(evidenceId) : null,
    phase4_interaction: interaction,
    interaction_scope: scope,
    interaction_surface: surface,
    mode: 'live',
    qualification_surface: 'android-cdp-apps-only',
    browser_project: 'android-cdp-apps-only',
    rendering_surface: 'physical-android-chrome',
    android_chrome_version: androidChromeVersion,
    android_package: 'com.android.chrome',
    device_identity: 'pocketlab-owned-android-device-redacted',
    source_commit: commit,
    candidate_manifest_verified: true,
    candidate_manifest_source_commit: candidateManifest.source_commit,
    candidate_manifest_schema_version: candidateManifest.schema_version,
    candidate_manifest_response_header_verified: candidateManifestResponseHeaderVerified,
    candidate_page_response_header_verified: candidatePageResponseHeaderVerified,
    candidate_page_meta_verified: candidatePageMetaVerified,
    cdp_identity_verified: true,
    device_serial_verified: process.env.LITE_ANDROID_CDP_DEVICE_IDENTITY_VERIFIED === '1',
    windows_bridge_identity_verified: process.env.LITE_ANDROID_CDP_BRIDGE_IDENTITY_VERIFIED === '1',
    candidate_reverse_verified: process.env.LITE_ANDROID_CANDIDATE_REVERSE_VERIFIED === '1',
    sanitized: true,
    viewport: viewport ? { width: viewport.width, height: viewport.height } : null,
    action_latency_ms: Date.now() - started,
    input_to_frame_timing: 'not separately exposed by Android CDP; action latency and frame intervals recorded',
    ...summary,
    ...react,
  };
  const fileName = `ui-performance-android-cdp-apps-${sanitizeLitePerformanceName(scope)}-${sanitizeLitePerformanceName(interaction)}.json`;
  await writeFile(resolve(outputDir, fileName), JSON.stringify(report, null, 2) + '\n', 'utf8');
  reports.push(report);
  if (report.gate_passed !== true) gateFailures += 1;
  if (report.target_met !== true) targetMisses += 1;
  if (report.react_profile_available && report.react_commit_gate_passed !== true) gateFailures += 1;
  console.log(
    `[ui-performance-android-apps] ${report.gate_passed ? report.target_met ? 'TARGET-PASS' : 'TARGET-MISS' : 'FAIL'} ${interaction} (${scope}): p95=${report.p95_frame_ms}ms smooth=${report.target_smooth_frame_ratio} latency=${report.action_latency_ms}ms`,
  );
  return report;
}

async function applyTheme(theme, colorScheme) {
  await page.emulateMedia({ colorScheme, reducedMotion: 'no-preference' });
  await page.evaluate((value) => localStorage.setItem('pocketlab:appearance', value), theme);
  await page.goto(new URL(candidatePagePath, new URL(baseUrlValue).origin).toString(), {
    waitUntil: 'domcontentloaded',
    timeout: 30_000,
  });
  await requireWakeLock();
  await waitForCatalog();
  await installSampler();
  return page.evaluate(() => ({
    theme: document.documentElement.dataset.liteTheme || '',
    colorScheme: getComputedStyle(document.documentElement).colorScheme || '',
    reducedMotion: window.matchMedia('(prefers-reduced-motion: reduce)').matches,
  }));
}

async function visibleManageDialog() {
  return firstVisible(page.getByRole('dialog', { name: /Manage /i }), 'Apps Manage dialog');
}

async function checkCatalogLanding() {
  const screen = page.locator('[data-lite-screen-id="catalog"]');
  const cards = screen.locator('.lite-catalog-app-card');
  const count = await cards.count();
  if (!count) {
    gap('Apps landing', 'The live runtime exposed no app cards; authenticated or prepared catalog projection may be unavailable.');
    return { cardCount: 0, appNames: [] };
  }
  const appNames = [];
  let genericCount = 0;
  for (let index = 0; index < count; index += 1) {
    const card = cards.nth(index);
    if (!await card.isVisible().catch(() => false)) continue;
    const heading = (await card.getByRole('heading').first().innerText().catch(() => ''))
      .replace(/[^a-zA-Z0-9 ._-]/g, '')
      .trim()
      .slice(0, 80);
    if (heading) appNames.push(heading);
    if (!/photoprism/i.test(heading)) genericCount += 1;
    const open = card.getByRole('button', { name: 'Open', exact: true });
    const manage = card.getByRole('button', { name: 'Manage', exact: true });
    if (!await open.isVisible().catch(() => false) || !await manage.isVisible().catch(() => false)) {
      fail(`Apps card ${heading || index} did not expose both Open and Manage controls.`);
    }
    const boxes = await card.locator('.lite-catalog-actions > button').evaluateAll((nodes) => nodes.map((node) => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom };
    }));
    if (boxes.length >= 2) {
      const separated = boxes[1].top >= boxes[0].bottom + 4 || boxes[1].left >= boxes[0].right + 4;
      if (!separated) fail(`Apps card ${heading || index} has overlapping Open/Manage controls.`);
    }
  }
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 2);
  if (!overflow) fail('Apps landing has horizontal overflow on the physical Android viewport.');
  if (!appNames.some((name) => /photoprism/i.test(name))) gap('PhotoPrism card', 'The live catalog did not expose a PhotoPrism card.');
  if (!genericCount) gap('Generic second app card', 'The live catalog did not expose a generic second app; mocked coverage remains authoritative for capability isolation.');
  await capture('landing-system', screen);
  return { cardCount: appNames.length, appNames };
}

async function checkThemeAndMotion() {
  const themes = [];
  for (const [theme, colorScheme] of [['light', 'light'], ['dark', 'dark'], ['system', 'dark']]) {
    const resolved = await applyTheme(theme, colorScheme);
    themes.push({ requested: theme, ...resolved });
    await checkCatalogLanding();
    await capture(`landing-${theme}`, page.locator('[data-lite-screen-id="catalog"]'));
  }
  const reduced = await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
  const reducedMotion = await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  if (!reducedMotion) gap('Reduced motion', 'Android Chrome did not expose the requested prefers-reduced-motion media state.');
  return { themes, reducedMotion, reducedMotionMediaApplied: Boolean(reduced) || reducedMotion };
}

async function checkTabsAndDisclosures(manage) {
  const tabs = manage.getByRole('tab');
  const tabCount = await tabs.count();
  if (tabCount < 2) {
    gap('Apps Manage section tabs', 'The live PhotoPrism projection exposed fewer than two action sections.');
  } else {
    const selectedCount = await tabs.evaluateAll((nodes) => nodes.filter((node) => node.getAttribute('aria-selected') === 'true').length);
    if (selectedCount !== 1) fail(`Apps Manage tablist exposed ${selectedCount} selected tabs instead of one.`);
    const firstTab = tabs.nth(0);
    const secondTab = tabs.nth(1);
    await firstTab.focus();
    await page.keyboard.press('End');
    if (await tabs.nth(tabCount - 1).getAttribute('aria-selected') !== 'true') fail('Apps Manage End keyboard navigation did not select the last tab.');
    await page.keyboard.press('Home');
    if (await firstTab.getAttribute('aria-selected') !== 'true') fail('Apps Manage Home keyboard navigation did not select the first tab.');
    await measure({
      interaction: 'section-switch',
      scope: 'catalog-photoprism-manage',
      surface: 'PhotoPrism Manage action sections',
      evidenceId: matrixEvidence('catalog', 'section-switch', 'PhotoPrism Manage / action sections'),
      action: async () => {
        await secondTab.click();
        if (await secondTab.getAttribute('aria-selected') !== 'true') fail('Apps Manage section switch did not select the requested tab.');
      },
      settleMs: 480,
    });
    await firstTab.click();
    await page.waitForTimeout(260);
  }

  const disclosures = [
    ['Photo backup guide', manage.getByText('How photo backup works', { exact: true }).locator('..').locator('..').locator('details').first()],
    ['Other action notices', manage.locator('details.lite-catalog-premium-action-notices').first()],
    ['Storage and device details', manage.locator('details.lite-catalog-premium-storage-details').first()],
  ];
  const disclosureResults = [];
  for (const [label, disclosure] of disclosures) {
    if (!await disclosure.count()) {
      gap(label, 'The current backend projection did not expose this disclosure.');
      continue;
    }
    const summary = disclosure.locator('summary').first();
    if (!await summary.isVisible().catch(() => false)) {
      gap(label, 'The disclosure exists but is not visible in the current action section.');
      continue;
    }
    await measure({
      interaction: 'disclosure-open',
      scope: sanitizeLitePerformanceName(label),
      surface: label,
      action: async () => {
        await summary.click();
        if (await disclosure.getAttribute('open') === null) fail(`${label} did not open with its native summary control.`);
      },
      settleMs: 220,
    });
    disclosureResults.push({ label, open: true });
    await measure({
      interaction: 'disclosure-close',
      scope: sanitizeLitePerformanceName(label),
      surface: label,
      action: async () => {
        await summary.click();
        if (await disclosure.getAttribute('open') !== null) fail(`${label} did not close with its native summary control.`);
      },
      settleMs: 220,
    });
  }
  return { tabCount, disclosureResults };
}

async function checkNestedDetails(manage) {
  const workflow = manage.getByRole('region', { name: 'Photo workflow' });
  const detailsButton = await firstVisibleOrNull(workflow.getByRole('button', { name: 'View details', exact: true }));
  if (!detailsButton) {
    gap('Nested Action Details', 'The live Photo workflow did not expose a read-only View details control.');
    return { available: false };
  }
  let nested;
  await measure({
    interaction: 'nested-detail-open',
    scope: 'catalog-photoprism-action-details',
    surface: 'PhotoPrism Manage Action Details',
    evidenceId: matrixEvidence('catalog', 'nested-detail-open', 'PhotoPrism Manage / action details'),
    action: async () => {
      await detailsButton.click();
      nested = await firstVisible(page.locator('.lite-details-overlay-layer .lite-details-panel'), 'nested Action Details panel');
    },
    settleMs: 480,
  });
  await capture('nested-action-details', nested);
  const nestedScroll = nested.locator('.lite-apps-premium-details-scroll').first();
  const nestedScrollState = await nestedScroll.evaluate((element) => ({
    scrollHeight: element.scrollHeight,
    clientHeight: element.clientHeight,
    scrollTop: element.scrollTop,
  })).catch(() => null);
  if (nestedScrollState && nestedScrollState.scrollHeight > nestedScrollState.clientHeight + 2) {
    await measure({
      interaction: 'nested-scroll',
      scope: 'catalog-photoprism-action-details',
      surface: 'Nested Action Details scroll container',
      action: async () => {
        await nestedScroll.evaluate((element) => {
          element.scrollTop = Math.min(element.scrollHeight - element.clientHeight, Math.max(120, element.clientHeight * 0.6));
        });
        const position = await nestedScroll.evaluate((element) => element.scrollTop);
        if (position <= 0) fail('Nested Action Details did not retain an independent scroll position.');
      },
      settleMs: 220,
    });
  } else {
    gap('Nested Action Details scroll containment', 'The current details projection was shorter than the physical viewport.');
  }
  await measure({
    interaction: 'nested-detail-close',
    scope: 'catalog-photoprism-action-details',
    surface: 'PhotoPrism Manage Action Details',
    action: async () => {
      await page.keyboard.press('Escape');
      await nested.waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => null);
      if (await page.locator('.lite-details-overlay-layer .lite-details-panel:visible').count()) fail('Nested Action Details did not close with Escape.');
      if (!await manage.isVisible()) fail('Manage did not remain visible after closing nested Action Details.');
    },
    settleMs: 360,
  });
  return { available: true, scroll: nestedScrollState };
}

async function checkMobileSnap(manage) {
  const layout = await manage.getAttribute('data-lite-apps-manage-layout');
  const snap = manage.locator('[data-lite-sheet-snap]').first();
  if (!await snap.count()) {
    gap('Mobile sheet snap', `Android rendered ${layout || 'desktop'} Manage geometry; mobile snap is covered by the Dev-PC geometry gate.`);
    return { mobile: false };
  }
  const initial = await snap.getAttribute('data-lite-sheet-snap');
  if (initial !== 'medium') fail(`Apps Manage reopened with unexpected initial snap state: ${initial}`);
  const expand = snap.getByRole('button', { name: 'Expand', exact: true });
  const compact = snap.getByRole('button', { name: 'Compact', exact: true });
  const grip = snap.getByRole('button', { name: /Resize sheet, currently/ });
  await measure({
    interaction: 'mobile-snap-expanded',
    scope: 'catalog-manage-mobile-sheet',
    surface: 'Apps Manage mobile sheet',
    action: async () => {
      await expand.click();
      if (await snap.getAttribute('data-lite-sheet-snap') !== 'expanded') fail('Expand did not reach the expanded snap state.');
    },
    settleMs: 320,
  });
  await measure({
    interaction: 'mobile-snap-medium',
    scope: 'catalog-manage-mobile-sheet',
    surface: 'Apps Manage mobile sheet',
    action: async () => {
      await compact.click();
      if (await snap.getAttribute('data-lite-sheet-snap') !== 'medium') fail('Compact did not return from expanded to medium.');
    },
    settleMs: 320,
  });
  await measure({
    interaction: 'mobile-snap-compact',
    scope: 'catalog-manage-mobile-sheet',
    surface: 'Apps Manage mobile sheet',
    action: async () => {
      await compact.click();
      if (await snap.getAttribute('data-lite-sheet-snap') !== 'compact') fail('Compact did not reach the compact snap state.');
    },
    settleMs: 320,
  });
  await grip.focus();
  await page.keyboard.press('End');
  if (await snap.getAttribute('data-lite-sheet-snap') !== 'expanded') fail('Keyboard End did not reach expanded.');
  await page.waitForTimeout(300);
  const rect = await grip.boundingBox();
  if (!rect) fail('Mobile sheet grip had no physical bounding box.');
  await measure({
    interaction: 'mobile-grip-drag',
    scope: 'catalog-manage-mobile-sheet',
    surface: 'Apps Manage mobile sheet grip',
    action: async () => {
      await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2);
      await page.mouse.down();
      await page.mouse.move(rect.x + rect.width / 2, rect.y + rect.height / 2 + 260, { steps: 8 });
      await page.mouse.up();
      if (await snap.getAttribute('data-lite-sheet-snap') === 'expanded') fail('Physical CDP grip drag did not contract the sheet.');
    },
    settleMs: 360,
  });
  const scroll = snap.locator('.lite-catalog-manage-scroll').first();
  const scrollMetrics = await scroll.evaluate((element) => ({ scrollHeight: element.scrollHeight, clientHeight: element.clientHeight }));
  if (scrollMetrics.scrollHeight > scrollMetrics.clientHeight + 2) {
    await measure({
      interaction: 'nested-scroll',
      scope: 'catalog-manage-mobile-sheet',
      surface: 'Apps Manage internal scroll',
      action: async () => {
        await scroll.evaluate((element) => {
          element.scrollTop = Math.min(element.scrollHeight - element.clientHeight, Math.max(120, element.clientHeight * 0.6));
        });
        if (await scroll.evaluate((element) => element.scrollTop) <= 0) fail('Apps Manage internal scroll did not move.');
      },
      settleMs: 220,
    });
  } else {
    gap('Apps Manage internal scroll', 'The current Manage projection did not exceed the physical viewport.');
  }
  return { mobile: true, initial, final: await snap.getAttribute('data-lite-sheet-snap') };
}

async function qualifyApps() {
  const cdp = endpoint(cdpUrlValue, 'LITE_ANDROID_CDP_URL');
  const base = endpoint(baseUrlValue, 'LITE_BASE_URL');
  commit = exactSourceCommit();
  if (browserBridgeEnabled !== Boolean(browserBridge)) {
    fail('Synthetic browser bridge settings are inconsistent; no implicit Owner authority is allowed.');
  }
  const cdpIdentity = await validateCdpIdentity(cdp);
  androidChromeVersion = cdpIdentity.browser;
  await mkdir(outputDir, { recursive: true });

  browser = await chromium.connectOverCDP(cdp.toString());
  androidChromeVersion ||= String(browser.version() || '').trim();
  if (!androidChromeVersion) fail('Android Chrome did not expose a browser version over CDP.');
  const contexts = browser.contexts();
  if (!contexts.length) fail('Android Chrome did not expose a browser context over CDP.');
  const context = contexts[0];
  if (browserBridge) await context.setExtraHTTPHeaders({ 'X-Pocket-Lab-Qualification-Bridge': browserBridge });

  const origin = new URL(base.origin);
  const existing = context.pages().filter((candidate) => candidate.url().startsWith(origin.origin));
  page = existing[existing.length - 1] || await context.newPage();
  candidatePages = [...new Set([...existing, page])];
  await activateCandidate(page);
  await page.addInitScript(() => {
    const style = document.createElement('style');
    style.textContent = '[data-lite-sw-update-ready="true"] { display: none !important; }';
    (document.head || document.documentElement)?.appendChild(style);
  });

  await page.goto(new URL('/?pocketlab_qualification_bootstrap=1', origin).toString(), {
    waitUntil: 'domcontentloaded',
    timeout: 30_000,
  });
  await requireWakeLock();
  await page.evaluate(async () => {
    const registrations = await navigator.serviceWorker?.getRegistrations?.() || [];
    await Promise.all(registrations.map((registration) => registration.unregister()));
    if ('caches' in window) {
      const names = await caches.keys();
      await Promise.all(names.map((name) => caches.delete(name)));
    }
  });

  const manifestResponse = await page.goto(new URL('/__pocketlab_qualification__/candidate.json', base).toString(), {
    waitUntil: 'domcontentloaded',
    timeout: 30_000,
  });
  if (!manifestResponse?.ok()) fail('Android did not expose the candidate manifest.');
  candidateManifestResponseHeaderVerified = manifestResponse.headers()['x-pocket-lab-candidate-sha'] === commit;
  if (!candidateManifestResponseHeaderVerified) fail('Candidate manifest response header SHA mismatch.');
  try {
    candidateManifest = JSON.parse(await page.locator('body').innerText());
  } catch {
    fail('Candidate manifest was not valid JSON.');
  }
  if (
    candidateManifest?.source_commit !== commit
    || candidateManifest?.sanitized !== true
    || candidateManifest?.browser_secret_persisted !== false
    || candidateManifest?.qualification_surface !== 'devpc_candidate_loopback'
    || candidateManifest?.runtime_transport !== 'ssh_loopback_to_server_phone_caddy'
  ) {
    fail('Candidate manifest failed the exact-SHA, sanitized, loopback runtime contract.');
  }

  await proveCandidatePage(page, new URL(candidatePagePath, base).toString());
  let foregroundReady = await receivesAnimationFrames(page);
  for (let attempt = 0; !foregroundReady && attempt < 2; attempt += 1) {
    await activateCandidate(page);
    await page.reload({ waitUntil: 'domcontentloaded', timeout: 30_000 }).catch(() => {});
    await requireWakeLock();
    foregroundReady = await receivesAnimationFrames(page);
  }
  if (!foregroundReady) fail('Android candidate target did not deliver foreground animation frames.');
  await Promise.all(candidatePages.filter((candidate) => candidate !== page).map((candidate) => candidate.close().catch(() => {})));

  const themeEvidence = await checkThemeAndMotion();
  const landing = await checkCatalogLanding();
  if (!landing.cardCount) return { cdpIdentity, themeEvidence, landing };

  const cards = page.locator('.lite-catalog-app-card');
  const firstCard = await firstVisible(cards, 'first Apps card');
  const manageButton = await firstVisible(firstCard.getByRole('button', { name: 'Manage', exact: true }), 'Apps Manage button');
  let manage;
  await measure({
    interaction: 'manage-open',
    scope: 'catalog-photoprism-manage',
    surface: 'Apps Manage overlay',
    action: async () => {
      await manageButton.click();
      manage = await visibleManageDialog();
    },
    settleMs: 720,
  });
  if (!manage) manage = await visibleManageDialog();
  const closeButton = await firstVisible(manage.getByRole('button', { name: 'Close app actions', exact: true }), 'Apps Manage close button');
  if (!await closeButton.isVisible()) fail('Apps Manage close button was not visible.');
  await checkTabsAndDisclosures(manage);
  await checkNestedDetails(manage);
  await checkMobileSnap(manage);
  await measure({
    interaction: 'manage-close',
    scope: 'catalog-photoprism-manage',
    surface: 'Apps Manage overlay',
    action: async () => {
      await closeButton.click();
      await manage.waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => null);
      if (await page.getByRole('dialog', { name: /Manage /i }).count()) fail('Apps Manage did not close explicitly.');
      if (await manageButton.evaluate((node) => document.activeElement === node).catch(() => false) !== true) {
        gap('Apps Manage focus return', 'The physical browser did not report focus return to the opener after explicit close.');
      }
    },
    settleMs: 420,
  });

  // Reopen on the same page to prove the repaired close/reopen lifecycle does
  // not retain the previous mobile snap state.
  await manageButton.click();
  manage = await visibleManageDialog();
  const reopenedSnap = await manage.locator('[data-lite-sheet-snap]').first().getAttribute('data-lite-sheet-snap').catch(() => null);
  if (reopenedSnap && reopenedSnap !== 'medium') fail(`Apps Manage reopened at ${reopenedSnap} instead of medium.`);
  await capture('manage-reopened', manage);
  await manage.getByRole('button', { name: 'Close app actions', exact: true }).click();

  await writeFile(resolve(outputDir, 'android-apps-ui-contract.json'), JSON.stringify({
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    evidence_type: 'android-apps-only-ui-contract',
    qualification_surface: 'android-cdp-apps-only',
    source_commit: commit,
    candidate_manifest: {
      source_commit: candidateManifest.source_commit,
      schema_version: candidateManifest.schema_version,
      sanitized: candidateManifest.sanitized,
      runtime_transport: candidateManifest.runtime_transport,
    },
    cdp_identity: cdpIdentity,
    device_identity: 'pocketlab-owned-android-device-redacted',
    candidate_identity: {
      manifest_response_header_verified: candidateManifestResponseHeaderVerified,
      page_response_header_verified: candidatePageResponseHeaderVerified,
      page_meta_verified: candidatePageMetaVerified,
    },
    theme_evidence: themeEvidence,
    landing,
    reports: reports.map((report) => ({
      interaction: report.phase4_interaction,
      scope: report.interaction_scope,
      target_met: report.target_met,
      gate_passed: report.gate_passed,
      p95_frame_ms: report.p95_frame_ms,
      action_latency_ms: report.action_latency_ms,
    })),
    gaps,
    desktop_geometry: 'covered by Dev-PC mocked geometry and accessibility gates; not substituted with a synthetic Android viewport.',
    authenticated_owner: browserBridgeEnabled ? 'scoped bridge supplied by caller' : 'not requested; no Owner bypass used',
    sanitized: true,
  }, null, 2) + '\n', 'utf8');

  return { cdpIdentity, themeEvidence, landing };
}

async function closeCandidatePages() {
  await Promise.all(candidatePages.map((candidate) => candidate.close().catch(() => {})));
  if (browser) await browser.close().catch(() => {});
}

try {
  await qualifyApps();
} catch (error) {
  console.error(`[ui-performance-android-apps] ERROR: ${error?.message || error}`);
  process.exitCode = 1;
} finally {
  await closeCandidatePages();
}

if (!process.exitCode) {
  if (gateFailures) {
    console.error(`[ui-performance-android-apps] ${gateFailures} hard performance gate failure(s); thresholds were not changed.`);
    process.exitCode = 1;
  } else if (gaps.length) {
    console.warn(`[ui-performance-android-apps] ${reports.length} Apps samples passed the hard render gate; ${gaps.length} physical coverage gap(s) remain INCONCLUSIVE.`);
    process.exitCode = 2;
  } else {
    console.log(`[ui-performance-android-apps] Apps-only physical qualification passed with ${reports.length} measured samples.`);
  }
}
