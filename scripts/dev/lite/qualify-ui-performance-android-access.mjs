import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdir, rm, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import {
  LITE_PERFORMANCE_INTERACTIONS,
  LITE_PERFORMANCE_SCHEMA_VERSION,
  sanitizeLitePerformanceName,
  summarizeLiteFrames,
} from '../../../src/performance/litePerformanceBudget.js';

/*
 * Access-only physical qualification.
 *
 * This deliberately owns a smaller interaction set than the historical
 * seven-screen qualifier. It reuses the same CDP bridge, candidate manifest,
 * browser-bridge header, wake-lock policy, frame sampler, evidence schema and
 * absolute target/gate calculations. The broad all-screen qualifier remains
 * in qualify-ui-performance-android-cdp.mjs unchanged.
 */

const cdpUrl = String(process.env.LITE_ANDROID_CDP_URL || '').trim();
const baseUrl = String(process.env.LITE_BASE_URL || '').trim();
const browserBridge = String(process.env.POCKETLAB_HARNESS_BROWSER_BRIDGE || '').trim();
const browserBridgeEnabled = process.env.LITE_QUALIFICATION_BROWSER_BRIDGE === '1';
const outputDir = resolve('.pocketlab-dev/performance');
const MINIMUM_FRAME_COUNT = 20;
const MINIMUM_SAMPLER_INTERVAL_COUNT = MINIMUM_FRAME_COUNT + 3;
const MAX_MINIMUM_FRAME_EXTENSION_MS = 2_000;

function fail(message) {
  console.error(`[ui-performance-android-access] ${message}`);
  process.exit(1);
}

if (browserBridgeEnabled !== Boolean(browserBridge)) {
  fail('Synthetic Android browser qualification requires an explicit browser bridge and LITE_QUALIFICATION_BROWSER_BRIDGE=1.');
}

function sourceCommit() {
  const configured = String(process.env.LITE_PERF_SOURCE_COMMIT || process.env.GITHUB_SHA || '').trim();
  if (/^[0-9a-f]{40}$/.test(configured)) return configured;
  try {
    const value = execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
    if (/^[0-9a-f]{40}$/.test(value) && !/^0+$/.test(value)) return value;
  } catch {
    // Fail closed below.
  }
  fail('Access physical evidence requires an exact 40-character source commit.');
}

function validateEndpoint(value, label) {
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

const commit = sourceCommit();
const base = validateEndpoint(baseUrl, 'LITE_BASE_URL');
validateEndpoint(cdpUrl, 'LITE_ANDROID_CDP_URL');
await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });

const browser = await chromium.connectOverCDP(cdpUrl);
const androidChromeVersion = String(browser.version() || '').trim();
if (!androidChromeVersion) fail('Android Chrome did not expose a browser version over CDP.');
const contexts = browser.contexts();
if (!contexts.length) fail('Android Chrome did not expose a browser context over CDP.');
const context = contexts[0];
if (browserBridge) await context.setExtraHTTPHeaders({ 'X-Pocket-Lab-Qualification-Bridge': browserBridge });

const candidateOrigin = base.origin;
const existingCandidatePages = context.pages().filter((candidatePage) => candidatePage.url().startsWith(candidateOrigin));
// Do not reuse a candidate-origin tab from an earlier interrupted run. A
// stale service worker or background renderer can expose the right URL while
// serving an older document and can also fail the authoritative foreground
// animation gate. The newly-created page is the only initial measurement
// target; older candidate-origin tabs are closed after the fresh target proves
// its exact SHA and foreground state.
let page = await context.newPage();
const candidatePages = [page, ...existingCandidatePages.filter((candidatePage) => candidatePage !== page)];

async function activateCandidatePage(candidatePage = page) {
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
        return;
      }
      requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  })).catch(() => 0);
  return Number(frames) >= 2;
}

async function acquireScreenWakeLock() {
  return page.evaluate(async () => {
    const existing = window.__POCKETLAB_ANDROID_WAKE_LOCK__;
    if (existing && !existing.released) return { supported: true, acquired: true };
    if (!navigator.wakeLock?.request) return { supported: false, acquired: false };
    try {
      const lock = await navigator.wakeLock.request('screen');
      window.__POCKETLAB_ANDROID_WAKE_LOCK__ = lock;
      window.setTimeout(() => lock.release().catch(() => {}), 300_000);
      return { supported: true, acquired: !lock.released };
    } catch {
      return { supported: true, acquired: false };
    }
  });
}

async function requireScreenWakeLock() {
  const result = await acquireScreenWakeLock();
  if (!result.acquired) fail('Android screen wake lock could not be acquired; physical frame evidence would be throttled.');
}

await activateCandidatePage();
await page.goto(new URL('/?pocketlab_qualification_bootstrap=1', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
await requireScreenWakeLock();
await page.evaluate(async () => {
  const registrations = await navigator.serviceWorker?.getRegistrations?.() || [];
  await Promise.all(registrations.map((registration) => registration.unregister()));
  if ('caches' in window) {
    const cacheNames = await caches.keys();
    await Promise.all(cacheNames.map((cacheName) => caches.delete(cacheName)));
  }
});

const manifestResponse = await page.goto(new URL('/__pocketlab_qualification__/candidate.json', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
if (!manifestResponse?.ok()) fail('The Android base URL did not expose the exact-SHA candidate manifest.');
let candidateManifest;
try {
  candidateManifest = JSON.parse(await page.locator('body').innerText());
} catch {
  fail('The Android candidate manifest was not valid JSON.');
}
if (candidateManifest?.source_commit !== commit || candidateManifest?.sanitized !== true) {
  fail('The Android Access candidate manifest source SHA does not match the requested exact commit.');
}
if (manifestResponse.headers()['x-pocket-lab-candidate-sha'] !== commit) {
  fail('The Android Access candidate manifest response header did not prove the exact commit.');
}

const candidatePageResponse = await page.goto(new URL('/?screen=identity', base).toString(), { waitUntil: 'domcontentloaded', timeout: 30_000 });
if (!candidatePageResponse?.ok()) fail('The Android Access candidate page did not load.');
if (candidatePageResponse.headers()['x-pocket-lab-candidate-sha'] !== commit) {
  fail('The Android Access rendered page response header did not prove the exact commit.');
}
if (await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content') !== commit) {
  fail('The Android Access rendered page metadata did not prove the exact commit.');
}

async function proveForegroundCandidate(candidatePage) {
  const proof = await candidatePage.evaluate(async () => {
    const response = await fetch('/?pocketlab_qualification_sha_probe=1', { cache: 'no-store', credentials: 'same-origin' });
    return {
      ok: response.ok,
      responseHeader: response.headers.get('x-pocket-lab-candidate-sha'),
      meta: document.querySelector('meta[name="pocketlab-candidate-sha"]')?.getAttribute('content') || null,
    };
  }).catch(() => null);
  if (!proof?.ok || proof.responseHeader !== commit || proof.meta !== commit) {
    fail('The Android foreground Access candidate did not prove the exact source SHA.');
  }
  await requireScreenWakeLock();
}

let foregroundReady = false;
for (const candidatePage of [page, ...candidatePages.filter((candidatePage) => candidatePage !== page)]) {
  page = candidatePage;
  await activateCandidatePage(candidatePage);
  await proveForegroundCandidate(candidatePage);
  foregroundReady = await receivesAnimationFrames(candidatePage);
  for (let attempt = 0; !foregroundReady && attempt < 2; attempt += 1) {
    // Android Chrome can report the CDP target as active before its renderer
    // has resumed foreground animation delivery. Re-activate and reload only
    // this candidate target, then repeat the exact-SHA proof and wake-lock
    // acquisition before accepting a physical frame gate.
    await activateCandidatePage(candidatePage);
    await candidatePage.reload({ waitUntil: 'domcontentloaded', timeout: 30_000 }).catch(() => {});
    await proveForegroundCandidate(candidatePage);
    await activateCandidatePage(candidatePage);
    foregroundReady = await receivesAnimationFrames(candidatePage);
  }
  if (foregroundReady) break;
}
if (!foregroundReady) fail('Android Access candidate did not deliver foreground animation frames.');
await Promise.all(candidatePages.filter((candidatePage) => candidatePage !== page).map((candidatePage) => candidatePage.close().catch(() => {})));

await page.addInitScript(() => {
  let active = null;
  window.__POCKETLAB_ANDROID_FRAME_SAMPLER__ = {
    start(name) {
      active?.raf && cancelAnimationFrame(active.raf);
      active?.observers?.forEach((observer) => observer.disconnect());
      const sample = { name: String(name || 'interaction').slice(0, 96), previous: null, intervals: [], longTasks: [], longAnimationFrames: [], eventDurations: [], observers: [], raf: null };
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
          const observer = new PerformanceObserver((list) => list.getEntries().forEach((entry) => sample.longTasks.push(Number(entry.duration) || 0)));
          observer.observe({ entryTypes: ['longtask'] }); sample.observers.push(observer);
        } catch {}
        try {
          const observer = new PerformanceObserver((list) => list.getEntries().forEach((entry) => sample.longAnimationFrames.push(Number(entry.duration) || 0)));
          observer.observe({ type: 'long-animation-frame', buffered: false }); sample.observers.push(observer);
        } catch {}
        try {
          const observer = new PerformanceObserver((list) => list.getEntries().forEach((entry) => sample.eventDurations.push(Number(entry.duration) || 0)));
          observer.observe({ type: 'event', buffered: false, durationThreshold: 16 }); sample.observers.push(observer);
        } catch {}
      }
    },
    stop() {
      if (!active) return null;
      const sample = active;
      active = null;
      if (sample.raf) cancelAnimationFrame(sample.raf);
      sample.observers.forEach((observer) => observer.disconnect());
      return { interaction: sample.name, intervals: sample.intervals.slice(0, 600), longTasks: sample.longTasks.slice(0, 120), longAnimationFrames: sample.longAnimationFrames.slice(0, 120), eventDurations: sample.eventDurations.slice(0, 120) };
    },
    count() { return active?.intervals?.length || 0; },
  };
});

let failures = 0;
let targetMisses = 0;
let evidenceCount = 0;
const exercisedInteractions = new Set();
const physicalNotes = [];

async function firstVisible(locator, label) {
  const count = await locator.count().catch(() => 0);
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible().catch(() => false)) return candidate;
  }
  fail(`Could not find visible ${label}.`);
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
      visible: rect.width > 0 && rect.height > 0,
    };
  });
  if (!state.present || !state.visible) fail(`Access dock was not visible during ${label}.`);
  if (state.position !== 'fixed' || state.bottomGap < -4 || state.bottomGap > 64) {
    fail(`Access dock was not anchored to the visible viewport during ${label}: ${JSON.stringify(state)}`);
  }
  return state;
}

async function waitForScreen(screenId) {
  await page.locator(`[data-lite-screen-id="${screenId}"]`).waitFor({ state: 'visible', timeout: 20_000 });
  await page.evaluate(async () => { if ('fonts' in document) await document.fonts.ready; });
  await page.waitForTimeout(500);
}

async function gotoScreen(screenId) {
  const target = new URL(base.href);
  target.searchParams.set('screen', screenId);
  await page.goto(target.href, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await requireScreenWakeLock();
  await waitForScreen(screenId);
}

async function exerciseScroll() {
  await page.evaluate(async () => {
    const root = document.scrollingElement || document.documentElement;
    const startTop = root.scrollTop;
    const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
    const distance = Math.min(maxScroll, Math.max(180, Math.round(window.innerHeight * 0.55)));
    await new Promise((resolveScroll) => {
      const started = performance.now();
      const step = (now) => {
        const progress = Math.min(1, (now - started) / 700);
        root.scrollTop = Math.min(maxScroll, startTop + distance * ((1 - Math.cos(progress * Math.PI * 2)) / 2));
        if (progress < 1) requestAnimationFrame(step); else { root.scrollTop = startTop; resolveScroll(); }
      };
      requestAnimationFrame(step);
    });
  });
}

async function measure({ interaction, scope, surface, action, settleMs = 440, evidenceId = null }) {
  if (!LITE_PERFORMANCE_INTERACTIONS.includes(interaction)) fail(`Unknown Access interaction id: ${interaction}`);
  await page.evaluate((name) => window.__POCKETLAB_ANDROID_FRAME_SAMPLER__?.start(name), `android-cdp:access:${interaction}:${scope}`);
  await action();
  if (settleMs > 0) await page.waitForTimeout(settleMs);
  const extensionDeadline = Date.now() + MAX_MINIMUM_FRAME_EXTENSION_MS;
  while (Date.now() < extensionDeadline) {
    const count = await page.evaluate(() => window.__POCKETLAB_ANDROID_FRAME_SAMPLER__?.count?.() || 0).catch(() => 0);
    if (count >= MINIMUM_SAMPLER_INTERVAL_COUNT) break;
    await page.waitForTimeout(50);
  }
  const raw = await page.evaluate(() => window.__POCKETLAB_ANDROID_FRAME_SAMPLER__?.stop?.() || null);
  if (!raw) fail(`Access frame sampler returned no evidence for ${scope}.`);
  const summary = summarizeLiteFrames(raw.intervals || [], { longTasks: raw.longTasks || [], longAnimationFrames: raw.longAnimationFrames || [], eventDurations: raw.eventDurations || [], warmupFrames: 3 });
  if (summary.frame_count < MINIMUM_FRAME_COUNT) fail(`${interaction} (${scope}) produced only ${summary.frame_count} measured frames; at least ${MINIMUM_FRAME_COUNT} are required.`);
  const viewport = await page.evaluate(() => ({ width: window.innerWidth, height: window.innerHeight, visual_width: window.visualViewport?.width || null, visual_height: window.visualViewport?.height || null }));
  const report = {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    interaction: `android-cdp:access:${interaction}:${scope}`,
    performance_evidence_id: evidenceId,
    phase4_interaction: interaction,
    interaction_scope: scope,
    interaction_surface: surface,
    mode: 'live',
    qualification_surface: 'android-cdp',
    browser_project: 'android-cdp-access-only',
    rendering_surface: 'physical-android-chrome',
    qualification_scope: 'access',
    android_chrome_version: androidChromeVersion,
    android_package: 'com.android.chrome',
    source_commit: commit,
    candidate_manifest_verified: true,
    candidate_manifest_source_commit: candidateManifest.source_commit,
    candidate_manifest_schema_version: candidateManifest.schema_version,
    candidate_manifest_response_header_verified: true,
    candidate_page_response_header_verified: true,
    candidate_page_meta_verified: true,
    sanitized: true,
    viewport,
    ...summary,
  };
  const fileName = `ui-performance-android-access-${sanitizeLitePerformanceName(scope)}-${sanitizeLitePerformanceName(interaction)}.json`;
  await writeFile(resolve(outputDir, fileName), `${JSON.stringify(report, null, 2)}\n`, 'utf8');
  exercisedInteractions.add(interaction);
  evidenceCount += 1;
  if (!report.gate_passed) failures += 1;
  if (!report.target_met) targetMisses += 1;
  const status = report.target_met ? 'TARGET-PASS' : report.gate_passed ? 'TARGET-MISS' : 'FAIL';
  console.log(`[ui-performance-android-access] ${status} ${interaction} (${scope}): p95=${report.p95_frame_ms}ms smooth=${report.target_smooth_frame_ratio} surface=${surface}`);
}

async function capture(name, target = page) {
  const path = resolve(outputDir, `android-access-${sanitizeLitePerformanceName(name)}.png`);
  await target.screenshot({ path, animations: 'disabled' });
  console.log(`[ui-performance-android-access] screenshot ${name}: ${path}`);
}

async function manageIndex(dialog, mobile) {
  if (mobile) {
    const back = await firstVisible(dialog.getByRole('button', { name: /All access settings/i }), 'Manage Access index Back');
    await back.click();
    await dialog.locator('[data-access-manage-view="index"]').waitFor({ state: 'visible' });
  }
}

await gotoScreen('identity');
const account = await firstVisible(page.locator('[data-identity-horizon="account"]'), 'Access identity hero');
await measure({
  interaction: 'screen-steady',
  scope: 'access-initial-paint-and-hero',
  surface: 'Access initial page / identity hero / protection rows',
  action: async () => {
    await account.waitFor({ state: 'visible' });
    await firstVisible(page.getByText('Passkeys', { exact: true }), 'Access Passkeys protection row');
    await firstVisible(page.getByText('Sessions', { exact: true }), 'Access Sessions protection row');
    await assertDock('initial Access page');
  },
  settleMs: 720,
  evidenceId: 'identity.access-center.initial-paint',
});
await capture('landing');

await measure({
  interaction: 'section-switch',
  scope: 'access-theme-switch',
  surface: 'Access-scoped Daylight/Dark theme switch',
  action: async () => {
    const appearance = await firstVisible(page.getByLabel('Appearance'), 'Appearance control');
    await appearance.selectOption('dark');
    await page.locator('html[data-lite-theme="dark"]').waitFor({ state: 'attached' });
    await appearance.selectOption('light');
    await page.locator('html[data-lite-theme="light"]').waitFor({ state: 'attached' });
  },
  evidenceId: 'identity.access-center.theme-switch',
});

const manageButton = await firstVisible(page.getByRole('button', { name: 'Manage Access', exact: true }), 'Manage Access button');
await measure({
  interaction: 'manage-open',
  scope: 'access-manage-open',
  surface: 'Access Manage opening',
  action: async () => {
    await manageButton.click();
    await page.getByRole('dialog', { name: /Manage access/i }).waitFor({ state: 'visible', timeout: 20_000 });
  },
  evidenceId: 'identity.access-center.manage-open',
});
const dialog = await firstVisible(page.getByRole('dialog', { name: /Manage access/i }), 'Manage Access dialog');
const mobile = (await dialog.getAttribute('data-lite-identity-manage-layout')) === 'mobile-sheet';
if (!mobile) physicalNotes.push('Android target exposed a non-mobile Manage layout; mobile snap evidence was not applicable.');
await measure({
  interaction: 'screen-steady',
  scope: 'access-manage-index',
  surface: 'Access Manage grouped native index',
  action: async () => { await dialog.locator('[data-access-manage-view="index"]').waitFor({ state: 'visible' }); },
  settleMs: 520,
  evidenceId: 'identity.access-center.manage-index',
});
await capture('manage-index', dialog);

const accessNav = dialog.locator('nav[aria-label="Manage Access sections"]');
const navButton = (name) => accessNav.getByRole('button', { name, exact: true });

await measure({
  interaction: 'section-switch',
  scope: 'access-passkeys',
  surface: 'Access Manage / Passkeys',
  action: async () => {
    await (await firstVisible(navButton('Passkeys'), 'Passkeys navigation')).click();
    await dialog.locator('[data-identity-manage-section="passkeys"]').waitFor({ state: 'visible' });
  },
  evidenceId: 'identity.access-center.passkeys',
});
await manageIndex(dialog, mobile);

await measure({
  interaction: 'section-switch',
  scope: 'access-sessions',
  surface: 'Access Manage / Sessions',
  action: async () => {
    await (await firstVisible(navButton('Sessions'), 'Sessions navigation')).click();
    await dialog.locator('[data-identity-manage-section="sessions"]').waitFor({ state: 'visible' });
  },
  evidenceId: 'identity.access-center.sessions',
});

const currentSession = await firstVisible(dialog.getByRole('button', { name: /Current session/i }), 'current session Details');
let details;
await measure({
  interaction: 'nested-detail-open',
  scope: 'access-current-session-details',
  surface: 'Access Manage / selected current session Details',
  action: async () => {
    await currentSession.click();
    details = await firstVisible(page.getByRole('dialog', { name: /Access Details/i }), 'Access Details dialog');
  },
  evidenceId: 'identity.access-center.session-details',
});
await capture('session-details', details);
await measure({
  interaction: 'nested-detail-close',
  scope: 'access-current-session-details-return',
  surface: 'Access Details / return to Manage',
  action: async () => {
    await (await firstVisible(details.getByRole('button', { name: /Back to Manage Access/i }), 'Access Details Back')).click();
    await details.waitFor({ state: 'hidden', timeout: 10_000 });
  },
  evidenceId: 'identity.access-center.session-details-back',
});
await manageIndex(dialog, mobile);

await measure({
  interaction: 'section-switch',
  scope: 'access-recovery',
  surface: 'Access Manage / Recovery',
  action: async () => {
    await (await firstVisible(navButton('Recovery'), 'Recovery navigation')).click();
    await dialog.locator('[data-identity-manage-section="recovery"]').waitFor({ state: 'visible' });
  },
  evidenceId: 'identity.access-center.recovery',
});
const confirmationTrigger = await firstVisible(dialog.getByRole('button', { name: 'Generate New Codes' }), 'protected recovery confirmation');
await measure({
  interaction: 'confirmation-render',
  scope: 'access-protected-recovery-confirmation',
  surface: 'Access protected confirmation presentation; cancelled only',
  action: async () => {
    await confirmationTrigger.click();
    const confirmation = await firstVisible(page.getByRole('dialog', { name: 'Generate new recovery codes?' }), 'protected confirmation dialog');
    await capture('protected-confirmation', confirmation);
    await (await firstVisible(confirmation.getByRole('button', { name: 'Cancel', exact: true }), 'confirmation Cancel')).click();
  },
  evidenceId: 'identity.access-center.protected-confirmation',
});
await manageIndex(dialog, mobile);

await measure({
  interaction: 'section-switch',
  scope: 'access-activity',
  surface: 'Access Manage / Access activity',
  action: async () => {
    await (await firstVisible(navButton('Access activity'), 'Access activity navigation')).click();
    await dialog.locator('[data-identity-manage-section="activity"]').waitFor({ state: 'visible' });
  },
  evidenceId: 'identity.access-center.activity',
});
await manageIndex(dialog, mobile);

await measure({
  interaction: 'section-switch',
  scope: 'access-settings',
  surface: 'Access Manage / Access settings',
  action: async () => {
    await (await firstVisible(navButton('Access settings'), 'Access settings navigation')).click();
    await dialog.locator('[data-identity-manage-section="settings"]').waitFor({ state: 'visible' });
  },
  evidenceId: 'identity.access-center.settings',
});

if (mobile) {
  await measure({
    interaction: 'overlay-open',
    scope: 'access-mobile-compact-medium-expanded-snap',
    surface: 'Access Manage mobile sheet snapping',
    action: async () => {
      const grip = await firstVisible(dialog.getByRole('button', { name: /Resize sheet, currently/ }), 'Access sheet resize grip');
      await grip.focus();
      await page.keyboard.press('Home');
      if (await dialog.getAttribute('data-lite-sheet-snap') !== 'compact') fail('Access mobile snap did not reach compact.');
      await page.keyboard.press('PageDown');
      if (await dialog.getAttribute('data-lite-sheet-snap') !== 'medium') fail('Access mobile snap did not reach medium.');
      await page.keyboard.press('End');
      if (await dialog.getAttribute('data-lite-sheet-snap') !== 'expanded') fail('Access mobile snap did not reach expanded.');
      await page.keyboard.press('Home');
    },
    evidenceId: 'identity.access-center.mobile-snaps',
  });
}

await measure({
  interaction: 'list-scroll',
  scope: 'access-scrolling-and-dock',
  surface: 'Access content scroll with global navigation dock',
  action: async () => {
    const close = await firstVisible(page.getByRole('button', { name: 'Close identity access' }), 'Close Access Manage');
    await close.click();
    await dialog.waitFor({ state: 'hidden', timeout: 10_000 });
    await exerciseScroll();
    await assertDock('Access scrolling');
  },
  evidenceId: 'identity.access-center.scroll-dock',
});

await measure({
  interaction: 'screen-navigation',
  scope: 'access-repeated-navigation',
  surface: 'Access repeated global navigation round trip',
  action: async () => {
    const home = await firstVisible(page.getByRole('button', { name: 'Home', exact: true }), 'Home global navigation');
    await home.click();
    await waitForScreen('home');
    const access = await firstVisible(page.getByRole('button', { name: 'Access', exact: true }), 'Access global navigation');
    await access.click();
    await waitForScreen('identity');
    await assertDock('Access repeated navigation');
  },
  evidenceId: 'identity.access-center.repeated-navigation',
});
await capture('final-access');

const requiredInteractions = ['screen-steady', 'manage-open', 'section-switch', 'nested-detail-open', 'nested-detail-close', 'confirmation-render', 'overlay-open', 'list-scroll', 'screen-navigation'];
const missing = requiredInteractions.filter((interaction) => !exercisedInteractions.has(interaction));
if (missing.length) fail(`Access-only physical qualification missed interaction ids: ${missing.join(', ')}`);

const summary = {
  schema_version: '1.0.0',
  status: failures || targetMisses ? 'target_miss' : 'qualified',
  qualification_scope: 'access',
  source_commit: commit,
  android_chrome_version: androidChromeVersion,
  evidence_count: evidenceCount,
  target_misses: targetMisses,
  hard_gate_misses: failures,
  physical_notes: physicalNotes,
  sanitized: true,
};
await writeFile(resolve(outputDir, 'android-access-summary.json'), `${JSON.stringify(summary, null, 2)}\n`, 'utf8');
await page.close().catch(() => {});
await browser.close().catch(() => {});

if (failures || targetMisses) {
  if (failures) console.error(`[ui-performance-android-access] ${failures} sample(s) exceeded the hard render gate.`);
  if (targetMisses) console.error(`[ui-performance-android-access] ${targetMisses} sample(s) missed the 60 FPS production target.`);
  process.exit(1);
}
console.log(`[ui-performance-android-access] ${evidenceCount} physical Access-only evidence samples met the existing target and hard gate.`);
