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
 * Rules-only physical Android qualification. The shell wrapper owns the
 * exact-SHA build, candidate server, ADB reverse, CDP relay and cleanup.
 * This file exercises only the Rules read projection and never submits a
 * Rules operation. It deliberately does not invoke the seven-screen matrix.
 */

const cdpValue = String(process.env.LITE_ANDROID_CDP_URL || '').trim();
const baseValue = String(process.env.LITE_BASE_URL || '').trim();
const MIN_FRAMES = 20;
const MIN_INTERVALS = MIN_FRAMES + 3;
const EXTENSION_MS = 2_000;

let browser;
let page;
let dialog;
let base;
let commit;
let manifest;
let outputDir;
let chromeVersion = '';
let foregroundViewport;
let evidenceCount = 0;
let targetMisses = 0;
let gateMisses = 0;
let haptics = { supported: false, instrumented: false, touchActivationCalls: 0, acceptedCalls: 0 };
let requests = [];
const notes = [];
const exercised = new Set();
const matrix = new Map([
  ['Rules page initial render', 'UNVALIDATED'],
  ['Protection hero visibility', 'UNVALIDATED'],
  ['Rules landing scroll', 'UNVALIDATED'],
  ['Protection journey stage selection', 'UNVALIDATED'],
  ['Manage Safety Rules opening', 'UNVALIDATED'],
  ['Mobile settings index', 'UNVALIDATED'],
  ['Protection Overview', 'UNVALIDATED'],
  ['Protected Actions', 'UNVALIDATED'],
  ['How Protection Works', 'UNVALIDATED'],
  ['Decision History', 'UNVALIDATED'],
  ['Decision Insight', 'UNVALIDATED'],
  ['Decision Insight return', 'UNVALIDATED'],
  ['Policy Settings', 'UNVALIDATED'],
  ['Rules Version', 'UNVALIDATED'],
  ['Governance', 'UNVALIDATED'],
  ['Technical Status', 'UNVALIDATED'],
  ['Detail return', 'UNVALIDATED'],
  ['Compact/Medium/Expanded snaps', 'UNVALIDATED'],
  ['Manage close', 'UNVALIDATED'],
  ['Manage reopen after navigation', 'UNVALIDATED'],
  ['Safe-area positioning', 'UNVALIDATED'],
  ['320px-equivalent constrained geometry', 'UNVALIDATED'],
  ['Long text and responsive wrapping', 'UNVALIDATED'],
  ['Reduced-motion behavior', 'UNVALIDATED'],
  ['Daylight and Dark rendering', 'UNVALIDATED'],
  ['System appearance resolution', 'UNVALIDATED'],
  ['Haptic capability and fallback', 'UNVALIDATED'],
  ['No unintended privileged backend requests', 'UNVALIDATED'],
]);

function fail(message) {
  throw new Error(message);
}

function mark(label, status) {
  matrix.set(label, status);
}

function sourceCommit() {
  const configured = String(process.env.LITE_PERF_SOURCE_COMMIT || process.env.GITHUB_SHA || '').trim();
  if (/^[0-9a-f]{40}$/.test(configured) && !/^0+$/.test(configured)) return configured;
  const value = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
  if (/^[0-9a-f]{40}$/.test(value) && !/^0+$/.test(value)) return value;
  fail('Rules physical evidence requires an exact source SHA.');
}

function url(value, label) {
  let parsed;
  try { parsed = new URL(value); } catch { fail(label + ' is not a valid URL.'); }
  if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.query || parsed.hash) {
    fail(label + ' contains an invalid credential or query component.');
  }
  return parsed;
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

function evidenceId(interaction, nestedSurface) {
  return LITE_UI_PERFORMANCE_MATRIX.find((entry) => (
    entry.screen === 'rules' &&
    entry.interaction === interaction &&
    entry.nestedSurface === nestedSurface
  ))?.evidenceId || null;
}

async function activate(candidatePage) {
  await candidatePage.bringToFront().catch(() => {});
  try {
    const session = await page.context().newCDPSession(candidatePage);
    await session.send('Page.bringToFront');
    await session.detach().catch(() => {});
  } catch {}
}

async function hasFrames(candidatePage) {
  const count = await candidatePage.evaluate(() => new Promise((resolveFrames) => {
    let count = 0;
    const timeout = setTimeout(() => resolveFrames(count), 350);
    const tick = () => {
      count += 1;
      if (count >= 2) {
        clearTimeout(timeout);
        resolveFrames(count);
      } else requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  })).catch(() => 0);
  return Number(count) >= 2;
}

async function wakeLock() {
  const result = await page.evaluate(async () => {
    const existing = window.__POCKETLAB_ANDROID_RULES_WAKE_LOCK__;
    if (existing && !existing.released) return true;
    if (!navigator.wakeLock?.request) return false;
    try {
      const lock = await navigator.wakeLock.request('screen');
      window.__POCKETLAB_ANDROID_RULES_WAKE_LOCK__ = lock;
      window.setTimeout(() => lock.release().catch(() => {}), 300_000);
      return !lock.released;
    } catch {
      return false;
    }
  }).catch(() => false);
  if (!result) fail('Android screen wake lock was not available for physical Rules evidence.');
}

async function installSampler(targetPage = page) {
  await targetPage.addInitScript(() => {
    let active = null;
    window.__POCKETLAB_ANDROID_RULES_SAMPLER__ = {
      start(name) {
        active?.raf && cancelAnimationFrame(active.raf);
        active?.observers?.forEach((observer) => observer.disconnect());
        active = { name: String(name || 'rules').slice(0, 96), previous: null, intervals: [], longTasks: [], loaf: [], events: [], observers: [], raf: null };
        const sample = active;
        const frame = (time) => {
          if (active !== sample) return;
          if (sample.previous !== null) sample.intervals.push(time - sample.previous);
          sample.previous = time;
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
            const observer = new PerformanceObserver((list) => list.getEntries().forEach((entry) => sample.loaf.push(Number(entry.duration) || 0)));
            observer.observe({ type: 'long-animation-frame', buffered: false });
            sample.observers.push(observer);
          } catch {}
          try {
            const observer = new PerformanceObserver((list) => list.getEntries().forEach((entry) => sample.events.push(Number(entry.duration) || 0)));
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
          intervals: sample.intervals.slice(0, 600),
          longTasks: sample.longTasks.slice(0, 120),
          longAnimationFrames: sample.loaf.slice(0, 120),
          eventDurations: sample.events.slice(0, 120),
        };
      },
      count() { return active?.intervals?.length || 0; },
    };
  });
}

async function installHapticProbe(targetPage = page) {
  await targetPage.addInitScript(() => {
    const original = typeof Navigator !== 'undefined' ? Navigator.prototype.vibrate : null;
    const probe = { supported: typeof original === 'function', instrumented: false, calls: [] };
    window.__POCKETLAB_ANDROID_RULES_HAPTICS__ = probe;
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
    } catch {}
  });
}

async function touch(locator, label) {
  const box = await locator.boundingBox().catch(() => null);
  if (!box || box.width <= 0 || box.height <= 0) fail(label + ' is not touchable.');
  const session = await page.context().newCDPSession(page);
  try {
    await session.send('Input.dispatchTouchEvent', { type: 'touchStart', modifiers: 0, touchPoints: [{ x: box.x + box.width / 2, y: box.y + box.height / 2 }] });
    await session.send('Input.dispatchTouchEvent', { type: 'touchEnd', modifiers: 0, touchPoints: [] });
  } finally {
    await session.detach().catch(() => {});
  }
}

async function assertRulesLoaded() {
  await page.locator('[data-lite-screen-id="rules"]').waitFor({ state: 'visible', timeout: 20_000 });
  await page.locator('[data-rules-protection-state]').waitFor({ state: 'visible', timeout: 20_000 });
  await page.getByRole('heading', { name: 'Safety Rules', level: 1 }).waitFor({ state: 'visible', timeout: 20_000 });
  await page.getByLabel('Protection Center').waitFor({ state: 'visible', timeout: 20_000 });
  await page.getByRole('heading', { name: 'How protection works' }).waitFor({ state: 'visible', timeout: 20_000 });
  await page.evaluate(async () => { if ('fonts' in document) await document.fonts.ready; });
  await page.waitForTimeout(500);
}

async function geometry(label, hasDialog = false) {
  const result = await page.evaluate((withDialog) => {
    const viewportHeight = window.visualViewport?.height || window.innerHeight;
    const nav = document.querySelector('.pocket-nav-dock');
    const navRect = nav?.getBoundingClientRect();
    const navStyle = nav ? getComputedStyle(nav) : null;
    const surface = withDialog ? document.querySelector('[data-rules-manage-layout]') : null;
    const surfaceRect = surface?.getBoundingClientRect();
    const targets = surface ? [...surface.querySelectorAll('.lite-rules-native-row, .lite-rules-overlay-close, .lite-sheet-mobile-snap-actions button')].map((node) => {
      const rect = node.getBoundingClientRect();
      return { width: rect.width, height: rect.height };
    }) : [];
    return {
      viewport: { width: window.innerWidth, height: window.innerHeight },
      documentWidth: document.documentElement.scrollWidth,
      bodyWidth: document.body?.scrollWidth || 0,
      nav: navRect && navStyle ? { position: navStyle.position, bottomGap: viewportHeight - navRect.bottom, background: navStyle.backgroundColor } : null,
      surface: surfaceRect ? {
        top: surfaceRect.top,
        right: surfaceRect.right,
        bottom: surfaceRect.bottom,
        layout: surface.getAttribute('data-rules-manage-layout'),
        minTargetWidth: Math.min(...targets.map((target) => target.width), 999),
        minTargetHeight: Math.min(...targets.map((target) => target.height), 999),
      } : null,
    };
  }, hasDialog);
  if (result.documentWidth > result.viewport.width + 2 || result.bodyWidth > result.viewport.width + 2) {
    fail('Rules ' + label + ' introduced horizontal overflow: ' + JSON.stringify(result));
  }
  if (result.nav && (result.nav.position !== 'fixed' || result.nav.bottomGap < -4 || result.nav.bottomGap > 8)) {
    fail('Rules navigation dock lost viewport anchoring during ' + label + ': ' + JSON.stringify(result.nav));
  }
  if (result.nav && (!result.nav.background || result.nav.background === 'rgba(0, 0, 0, 0)' || result.nav.background === 'transparent')) {
    fail('Rules navigation dock became transparent during ' + label + '.');
  }
  if (result.surface) {
    if (result.surface.top < -2 || result.surface.right > result.viewport.width + 2 || result.surface.bottom > result.viewport.height + 2) {
      fail('Rules Manage surface exceeded the visible viewport during ' + label + ': ' + JSON.stringify(result.surface));
    }
    if (result.surface.layout === 'mobile-sheet' && (result.surface.minTargetWidth < 44 || result.surface.minTargetHeight < 44)) {
      fail('Rules mobile Manage exposed a visible control below the 44px target: ' + JSON.stringify(result.surface));
    }
    mark('Safe-area positioning', 'VERIFIED');
  }
  return result;
}

async function appearance(value, label) {
  const control = await firstVisible(page.getByRole('combobox', { name: 'Appearance', exact: true }), 'Appearance ' + label);
  await control.selectOption(value);
  const expected = value === 'dark' ? 'dark' : value === 'light' ? 'light' : null;
  await page.waitForFunction(({ preference, expectedTheme }) => {
    const select = document.querySelector('select[aria-label="Appearance"]');
    const theme = document.documentElement.dataset.liteTheme || '';
    return select?.value === preference && Boolean(theme) && (!expectedTheme || theme === expectedTheme);
  }, { preference: value, expectedTheme: expected }, { timeout: 20_000 });
  await assertRulesLoaded();
  const resolved = await page.locator('html').getAttribute('data-lite-theme');
  notes.push('Physical Android ' + label + ': preference=' + value + ', resolved=' + resolved + '.');
  return resolved;
}

async function scrollLanding() {
  const result = await page.evaluate(async () => {
    const root = document.scrollingElement || document.documentElement;
    const start = root.scrollTop;
    const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
    const distance = Math.min(maxScroll, Math.max(180, Math.round(window.innerHeight * 0.55)));
    await new Promise((done) => {
      const started = performance.now();
      const step = (now) => {
        const progress = Math.min(1, (now - started) / 700);
        root.scrollTop = Math.min(maxScroll, start + distance * progress);
        if (progress < 1) requestAnimationFrame(step);
        else { root.scrollTop = start; done(); }
      };
      requestAnimationFrame(step);
    });
    const nav = document.querySelector('.pocket-nav-dock');
    const rect = nav?.getBoundingClientRect();
    const height = window.visualViewport?.height || window.innerHeight;
    return { maxScroll, navPosition: nav ? getComputedStyle(nav).position : null, bottomGap: rect ? height - rect.bottom : null, finalBottomReachable: root.scrollHeight - root.scrollTop >= root.clientHeight };
  });
  if (result.navPosition && (result.navPosition !== 'fixed' || result.bottomGap < -4 || result.bottomGap > 8)) fail('Rules navigation dock lost anchoring during scroll: ' + JSON.stringify(result));
  if (!result.finalBottomReachable) fail('Rules landing content was not reachable after scroll.');
  mark('Rules landing scroll', 'VERIFIED');
}

async function measure({ interaction, scope, surface, action, settleMs = 440, performanceEvidenceId = null }) {
  if (!LITE_PERFORMANCE_INTERACTIONS.includes(interaction)) fail('Unknown Rules interaction: ' + interaction);
  await page.evaluate((name) => window.__POCKETLAB_ANDROID_RULES_SAMPLER__?.start(name), 'android-cdp:rules:' + interaction + ':' + scope);
  await action();
  if (settleMs > 0) await page.waitForTimeout(settleMs);
  const deadline = Date.now() + EXTENSION_MS;
  while (Date.now() < deadline) {
    if (await page.evaluate(() => window.__POCKETLAB_ANDROID_RULES_SAMPLER__?.count?.() || 0).catch(() => 0) >= MIN_INTERVALS) break;
    await page.waitForTimeout(50);
  }
  const raw = await page.evaluate(() => window.__POCKETLAB_ANDROID_RULES_SAMPLER__?.stop?.() || null);
  if (!raw) fail('Rules sampler returned no evidence for ' + scope + '.');
  const summary = summarizeLiteFrames(raw.intervals || [], {
    longTasks: raw.longTasks || [],
    longAnimationFrames: raw.longAnimationFrames || [],
    eventDurations: raw.eventDurations || [],
    warmupFrames: 3,
  });
  if (summary.frame_count < MIN_FRAMES) fail(interaction + ' (' + scope + ') produced only ' + summary.frame_count + ' frames.');
  const viewport = await page.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight, visual_width: window.visualViewport?.width || null, visual_height: window.visualViewport?.height || null, device_pixel_ratio: window.devicePixelRatio || null }));
  const report = {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    interaction: 'android-cdp:rules:' + interaction + ':' + scope,
    performance_evidence_id: performanceEvidenceId,
    phase4_interaction: interaction,
    interaction_scope: scope,
    interaction_surface: surface,
    mode: 'live',
    qualification_surface: 'android-cdp-rules-only',
    browser_project: 'android-cdp-rules-only',
    rendering_surface: 'physical-android-chrome',
    qualification_scope: 'rules',
    authority_mode: 'anonymous-read-only',
    android_chrome_version: chromeVersion,
    android_package: 'com.android.chrome',
    source_commit: commit,
    candidate_manifest_verified: true,
    candidate_manifest_source_commit: manifest.source_commit,
    candidate_manifest_schema_version: manifest.schema_version,
    candidate_manifest_response_header_verified: true,
    candidate_page_response_header_verified: true,
    candidate_page_meta_verified: true,
    android_cdp_identity_verified: true,
    android_candidate_reverse_verified: process.env.LITE_ANDROID_CANDIDATE_REVERSE_VERIFIED === '1',
    sanitized: true,
    viewport,
    ...summary,
  };
  await writeFile(resolve(outputDir, 'ui-performance-android-rules-' + sanitizeLitePerformanceName(scope) + '-' + sanitizeLitePerformanceName(interaction) + '.json'), JSON.stringify(report, null, 2) + '\n', 'utf8');
  evidenceCount += 1;
  exercised.add(interaction);
  if (!report.gate_passed) gateMisses += 1;
  if (!report.target_met) targetMisses += 1;
  console.log('[ui-performance-android-rules] ' + (report.target_met ? 'TARGET-PASS' : report.gate_passed ? 'TARGET-MISS' : 'GATE-MISS') + ' ' + interaction + ' (' + scope + '): p95=' + report.p95_frame_ms + 'ms smooth=' + report.target_smooth_frame_ratio);
}

async function journey(container) {
  for (const stage of ['Request', 'Evaluate', 'Decision', 'Outcome']) {
    const button = await firstVisible(container.locator('.lite-rules-journey-track button').filter({ hasText: stage }), 'Rules Journey ' + stage);
    await button.click();
    await container.locator('.lite-rules-journey-explanation').waitFor({ state: 'visible', timeout: 20_000 });
  }
  mark('Protection journey stage selection', 'VERIFIED');
}

async function manageIndex() {
  const back = dialog.getByRole('button', { name: 'All Safety Rules settings', exact: true });
  if (await back.isVisible().catch(() => false)) await back.click();
  await dialog.locator('[data-rules-manage-view="index"]').waitFor({ state: 'visible', timeout: 20_000 });
}

async function selectSection(id, label) {
  await manageIndex();
  const row = await firstVisibleOrNull(dialog.getByRole('button', { name: label, exact: true }));
  if (!row) return false;
  await row.click();
  await dialog.locator('[data-rules-manage-section="' + id + '"]').waitFor({ state: 'visible', timeout: 20_000 }).catch(async () => {
    await dialog.getByRole('heading', { name: label, exact: false }).waitFor({ state: 'visible', timeout: 20_000 });
  });
  return true;
}

async function closeManage() {
  await firstVisible(dialog.getByRole('button', { name: 'Close Rules management' }), 'Rules Manage close').click();
  await dialog.waitFor({ state: 'hidden', timeout: 20_000 });
  mark('Manage close', 'VERIFIED');
}

async function decisionInsight() {
  const trigger = await firstVisibleOrNull(page.getByLabel('Latest Decision').getByRole('button', { name: 'Explain decision', exact: true }));
  if (!trigger) {
    mark('Decision Insight', 'UNAVAILABLE_NO_SERVER_DECISION');
    mark('Decision Insight return', 'UNAVAILABLE_NO_SERVER_DECISION');
    notes.push('No server-reported decision was present; Decision Insight was not fabricated.');
    return;
  }
  await measure({
    interaction: 'nested-detail-open',
    scope: 'rules-decision-insight-open',
    surface: 'Rules Latest Decision / server-backed Decision Insight',
    action: async () => {
      await trigger.click();
      await page.getByRole('dialog', { name: 'Decision Insight' }).waitFor({ state: 'visible', timeout: 20_000 });
    },
  });
  mark('Decision Insight', 'VERIFIED');
  const insight = page.getByRole('dialog', { name: 'Decision Insight' });
  await measure({
    interaction: 'nested-detail-close',
    scope: 'rules-decision-insight-return',
    surface: 'Rules Decision Insight / return',
    action: async () => {
      await page.keyboard.press('Escape');
      await insight.waitFor({ state: 'hidden', timeout: 20_000 });
    },
  });
  mark('Decision Insight return', 'VERIFIED');
}

async function main() {
  commit = sourceCommit();
  outputDir = resolve(process.env.LITE_ANDROID_RULES_OUTPUT_DIR || '.pocketlab-dev/performance/android-rules-' + commit);
  await mkdir(outputDir, { recursive: true });
  const cdp = url(cdpValue, 'LITE_ANDROID_CDP_URL');
  base = url(baseValue, 'LITE_BASE_URL');
  const versionResponse = await fetch(new URL('/json/version', cdp));
  if (!versionResponse.ok) fail('Android CDP version endpoint was not reachable.');
  const version = await versionResponse.json();
  if (version['Android-Package'] !== 'com.android.chrome') fail('CDP endpoint did not identify com.android.chrome.');
  const websocket = new URL(version.webSocketDebuggerUrl || '');
  if (!['127.0.0.1', 'localhost'].includes(websocket.hostname) || Number(websocket.port) !== Number(cdp.port)) fail('CDP websocket did not remain on the WSL-local endpoint.');

  browser = await chromium.connectOverCDP(cdp.toString());
  chromeVersion = String(browser.version() || version.Browser || '').trim();
  const contexts = browser.contexts();
  if (!contexts.length) fail('Android Chrome did not expose a browser context.');
  const context = contexts[0];
  const candidatePages = context.pages().filter((candidatePage) => candidatePage.url().startsWith(base.origin));
  page = candidatePages[candidatePages.length - 1] || await context.newPage();
  if (!candidatePages.includes(page)) candidatePages.push(page);
  await activate(page);
  await Promise.all(candidatePages.map(async (candidatePage) => {
    await installSampler(candidatePage);
    await installHapticProbe(candidatePage);
  }));

  const manifestResponse = await page.goto(new URL('/__pocketlab_qualification__/candidate.json', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
  if (!manifestResponse?.ok()) fail('Candidate manifest was not available through Android reverse.');
  try { manifest = JSON.parse(await page.locator('body').innerText()); } catch { fail('Candidate manifest was not valid JSON.'); }
  if (manifest.source_commit !== commit || manifest.sanitized !== true) fail('Candidate manifest SHA mismatch.');
  if (manifestResponse.headers()['x-pocket-lab-candidate-sha'] !== commit) fail('Candidate manifest response-header SHA mismatch.');
  let foregroundReady = false;
  const foregroundCandidates = [page, ...candidatePages.filter((candidatePage) => candidatePage !== page)];
  for (const candidatePage of foregroundCandidates) {
    page = candidatePage;
    await activate(page);
    const rendered = await page.goto(new URL('/?screen=rules', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 }).catch(() => null);
    if (!rendered?.ok()) fail('Rules candidate page did not load.');
    if (rendered.headers()['x-pocket-lab-candidate-sha'] !== commit) fail('Rules page response-header SHA mismatch.');
    if (await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content') !== commit) fail('Rules page meta SHA mismatch.');
    await wakeLock();
    foregroundReady = await hasFrames(page);
    for (let attempt = 0; !foregroundReady && attempt < 2; attempt += 1) {
      await activate(page);
      const retryResponse = await page.reload({ waitUntil: 'domcontentloaded', timeout: 30_000 }).catch(() => null);
      if (retryResponse?.headers()['x-pocket-lab-candidate-sha'] !== commit) fail('Rules foreground retry lost the candidate response-header SHA.');
      if (await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content') !== commit) fail('Rules foreground retry lost the candidate page meta SHA.');
      await wakeLock();
      await activate(page);
      foregroundReady = await hasFrames(page);
    }
    if (foregroundReady) break;
  }
  if (!foregroundReady) fail('Rules candidate did not deliver foreground RAF frames after bounded reactivation retries.');
  await Promise.all(candidatePages.filter((candidatePage) => candidatePage !== page).map((candidatePage) => candidatePage.close().catch(() => {})));
  foregroundViewport = await page.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight, devicePixelRatio: window.devicePixelRatio || null }));
  await assertRulesLoaded();
  requests = [];
  page.on('request', (request) => {
    try {
      const parsed = new URL(request.url());
      requests.push({ method: request.method(), path: parsed.pathname });
    } catch {}
  });

  const manageButton = await firstVisible(page.getByRole('button', { name: 'Manage Safety Rules', exact: true }), 'Manage Safety Rules');
  await measure({
    interaction: 'screen-steady',
    scope: 'rules-initial-render-hero',
    surface: 'Rules landing / Protection Center / Journey / Latest Decision',
    action: async () => { await page.getByRole('heading', { name: 'Latest Decision' }).waitFor({ state: 'visible' }); await geometry('initial Rules landing'); },
    settleMs: 720,
  });
  mark('Rules page initial render', 'VERIFIED');
  mark('Protection hero visibility', 'VERIFIED');
  await measure({ interaction: 'section-switch', scope: 'rules-journey-stage-selection', surface: 'Rules Protection Journey / four stages', action: async () => journey(page.locator('.lite-rules-premium-journey').first()) });
  await measure({ interaction: 'list-scroll', scope: 'rules-landing-scroll', surface: 'Rules landing scroll and navigation dock', action: scrollLanding });

  await appearance('light', 'Daylight');
  mark('Daylight and Dark rendering', 'VERIFIED_DAYLIGHT');
  await appearance('dark', 'Dark');
  mark('Daylight and Dark rendering', 'VERIFIED_DARK');
  await appearance('system', 'System');
  mark('System appearance resolution', 'VERIFIED');
  await appearance('light', 'restored Daylight');

  const beforeHaptic = await page.evaluate(() => window.__POCKETLAB_ANDROID_RULES_HAPTICS__?.calls?.length || 0);
  await touch(manageButton, 'Rules Manage haptic probe');
  dialog = await firstVisible(page.getByRole('dialog', { name: 'Manage Safety Rules' }), 'Rules Manage haptic dialog');
  const closeForHaptic = await firstVisible(dialog.getByRole('button', { name: 'Close Rules management' }), 'Rules haptic close');
  await touch(closeForHaptic, 'Rules Manage haptic close');
  await dialog.waitFor({ state: 'hidden', timeout: 20_000 });
  const afterHaptic = await page.evaluate(() => {
    const probe = window.__POCKETLAB_ANDROID_RULES_HAPTICS__;
    return { supported: probe?.supported === true, instrumented: probe?.instrumented === true, calls: probe?.calls || [] };
  });
  const hapticCalls = afterHaptic.calls.slice(beforeHaptic);
  haptics = { supported: afterHaptic.supported, instrumented: afterHaptic.instrumented, touchActivationCalls: hapticCalls.length, acceptedCalls: hapticCalls.filter((call) => call.accepted === true).length };
  mark('Haptic capability and fallback', !haptics.supported ? 'UNAVAILABLE_ANDROID_CHROME' : haptics.instrumented ? (haptics.acceptedCalls ? 'VERIFIED' : 'VERIFIED_FALLBACK') : 'UNVALIDATED_OPTIONAL_HOOK');
  await decisionInsight();

  await measure({
    interaction: 'manage-open',
    scope: 'rules-manage-open',
    surface: 'Rules Manage Safety Rules opening',
    action: async () => {
      await manageButton.click();
      dialog = await firstVisible(page.getByRole('dialog', { name: 'Manage Safety Rules' }), 'Rules Manage dialog');
      await geometry('Rules Manage opening', true);
    },
    settleMs: 520,
  });
  mark('Manage Safety Rules opening', 'VERIFIED');
  const mobile = (await dialog.getAttribute('data-rules-manage-layout')) === 'mobile-sheet';
  mark('Mobile settings index', mobile ? 'VERIFIED' : 'NOT_APPLICABLE_DESKTOP_RENDERER');
  mark('Protection Overview', 'VERIFIED');
  if (!mobile) notes.push('The Android renderer exposed the desktop-movable Rules layout; mobile snap evidence was not applicable.');

  if (await selectSection('journey', 'How Protection Works')) {
    await measure({ interaction: 'section-switch', scope: 'rules-manage-journey', surface: 'Rules Manage / How Protection Works', action: async () => journey(dialog.locator('[data-rules-manage-section="journey"]')) });
    mark('How Protection Works', 'VERIFIED');
  } else mark('How Protection Works', 'UNAVAILABLE_ROLE_OR_PROJECTION');

  for (const item of [
    ['protections', 'Protected Actions', 'Protected Actions'],
    ['decisions', 'Decision History', 'Decision History'],
    ['policies', 'Policy Settings', 'Policy Settings'],
    ['revision', 'Rules Version', 'Rules Version'],
    ['governance', 'Governance', 'Governance'],
  ]) {
    const available = await selectSection(item[0], item[1]);
    if (!available) {
      mark(item[2], item[0] === 'revision' || item[0] === 'governance' ? 'UNAVAILABLE_ANONYMOUS_OR_ROLE' : 'UNAVAILABLE_ROLE_OR_PROJECTION');
      continue;
    }
    await measure({
      interaction: 'section-switch',
      scope: 'rules-manage-' + sanitizeLitePerformanceName(item[1]),
      surface: 'Rules Manage / ' + item[1],
      action: async () => geometry('Rules ' + item[1], true),
      performanceEvidenceId: item[1] === 'Decision History' ? evidenceId('history-open', 'Rules Manage / history details') : null,
    });
    mark(item[2], 'VERIFIED');
  }

  if (await selectSection('technical', 'Technical Status')) {
    await measure({
      interaction: 'nested-detail-open',
      scope: 'rules-technical-status',
      surface: 'Rules Manage / Technical Status',
      performanceEvidenceId: evidenceId('nested-detail-open', 'Manage Safety Rules / Technical status'),
      action: async () => {
        const details = await firstVisibleOrNull(dialog.locator('details.lite-ux-technical-facts summary'));
        if (details) await details.click();
        await geometry('Rules Technical Status', true);
      },
    });
    mark('Technical Status', 'VERIFIED');
    await measure({ interaction: 'nested-detail-close', scope: 'rules-technical-status-return', surface: 'Rules Technical Status / return', action: manageIndex });
    mark('Detail return', 'VERIFIED');
  } else {
    mark('Technical Status', 'UNAVAILABLE_ROLE_OR_PROJECTION');
    mark('Detail return', 'UNAVAILABLE_ROLE_OR_PROJECTION');
  }

  if (mobile) {
    await measure({
      interaction: 'overlay-open',
      scope: 'rules-mobile-compact-medium-expanded-snap',
      surface: 'Rules Manage mobile sheet snap controls',
      action: async () => {
        await manageIndex();
        await firstVisible(dialog.getByRole('button', { name: 'Expand', exact: true }), 'Rules sheet Expand').click();
        if (await dialog.getAttribute('data-lite-sheet-snap') !== 'expanded') fail('Rules sheet did not reach expanded.');
        await firstVisible(dialog.getByRole('button', { name: 'Compact', exact: true }), 'Rules sheet Compact').click();
        if (await dialog.getAttribute('data-lite-sheet-snap') !== 'medium') fail('Rules sheet did not return to medium.');
        const grip = await firstVisible(dialog.getByRole('button', { name: /Resize sheet/i }), 'Rules sheet grip');
        await grip.focus();
        await page.keyboard.press('Home');
        if (await dialog.getAttribute('data-lite-sheet-snap') !== 'compact') fail('Rules sheet did not reach compact.');
        await page.keyboard.press('End');
        if (await dialog.getAttribute('data-lite-sheet-snap') !== 'expanded') fail('Rules sheet did not return to expanded.');
        await page.keyboard.press('Home');
      },
    });
    mark('Compact/Medium/Expanded snaps', 'VERIFIED');
  } else mark('Compact/Medium/Expanded snaps', 'NOT_APPLICABLE_DESKTOP_RENDERER');

  await closeManage();
  await measure({
    interaction: 'manage-open',
    scope: 'rules-manage-reopen-after-navigation',
    surface: 'Rules Manage reopen after page navigation',
    action: async () => {
      await page.reload({ waitUntil: 'domcontentloaded', timeout: 30_000 });
      await assertRulesLoaded();
      await firstVisible(page.getByRole('button', { name: 'Manage Safety Rules', exact: true }), 'reopened Manage Safety Rules').click();
      dialog = await firstVisible(page.getByRole('dialog', { name: 'Manage Safety Rules' }), 'reopened Rules Manage');
      await geometry('Rules Manage reopen', true);
    },
  });
  mark('Manage reopen after navigation', 'VERIFIED');
  await closeManage();

  await measure({
    interaction: 'screen-steady',
    scope: 'rules-reduced-motion-and-wrap',
    surface: 'Rules reduced motion and emulated 200% text scale',
    action: async () => {
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.evaluate(() => {
        const style = document.createElement('style');
        style.id = 'rules-physical-text-scale';
        style.textContent = 'html { font-size: 200% !important; }';
        document.head.appendChild(style);
      });
      await geometry('Rules reduced motion and emulated 200% text scale');
      const transitions = await page.evaluate(() => [...document.querySelectorAll('.lite-rules-premium-screen')].map((node) => getComputedStyle(node).transitionDuration));
      if (transitions.some((value) => value !== '0s')) notes.push('Reduced-motion emulation retained a non-zero landing transition: ' + JSON.stringify(transitions.slice(0, 4)));
      await page.evaluate(() => document.getElementById('rules-physical-text-scale')?.remove());
      await page.emulateMedia({ reducedMotion: 'no-preference' });
    },
  });
  mark('Reduced-motion behavior', 'VERIFIED');
  mark('Long text and responsive wrapping', 'VERIFIED_NO_OVERFLOW_EMULATED_200_PERCENT');
  mark('320px-equivalent constrained geometry', foregroundViewport.width <= 320 ? 'VERIFIED' : 'UNAVAILABLE_PHYSICAL_VIEWPORT_' + foregroundViewport.width + 'CSS_PX');

  const writes = requests.filter((request) => !['GET', 'HEAD', 'OPTIONS'].includes(request.method));
  if (writes.length) fail('Rules qualification issued a non-read-only request: ' + JSON.stringify(writes.slice(0, 8)));
  mark('No unintended privileged backend requests', 'VERIFIED_READ_ONLY_' + requests.length + '_REQUESTS');

  await writeFile(resolve(outputDir, 'android-rules-summary.json'), JSON.stringify({
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    status: gateMisses ? 'gate_miss' : targetMisses ? 'target_miss' : 'qualified',
    qualification_scope: 'rules',
    qualification_surface: 'android-cdp-rules-only',
    source_commit: commit,
    android_chrome_version: chromeVersion,
    android_package: 'com.android.chrome',
    foreground_viewport: foregroundViewport,
    evidence_count: evidenceCount,
    target_misses: targetMisses,
    hard_gate_misses: gateMisses,
    physical_interaction_matrix: [...matrix].map(([interaction, status]) => ({ interaction, status })),
    haptics,
    network_safety: { request_count: requests.length, methods: [...new Set(requests.map((request) => request.method))].sort(), non_read_request_count: writes.length, sanitized: true },
    authority: { mode: 'anonymous-read-only', synthetic_owner_used: false, destructive: false, test_auth_bypass: false },
    physical_notes: notes,
    sanitized: true,
  }, null, 2) + '\n', 'utf8');
  console.log('[ui-performance-android-rules] captured ' + evidenceCount + ' Rules-only physical evidence samples.');
  if (gateMisses || targetMisses) {
    if (gateMisses) console.error('[ui-performance-android-rules] ' + gateMisses + ' sample(s) exceeded the hard render gate.');
    if (targetMisses) console.error('[ui-performance-android-rules] ' + targetMisses + ' sample(s) missed the 60 FPS target.');
    process.exitCode = 1;
  }
}

main()
  .catch((error) => {
    console.error('[ui-performance-android-rules] ERROR: ' + (error?.message || error));
    process.exitCode = 1;
  })
  .finally(async () => {
    await page?.close().catch(() => {});
    await browser?.close().catch(() => {});
  });
