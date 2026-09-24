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
import { LITE_UI_PERFORMANCE_MATRIX } from '../../../src/performance/litePerformanceMatrix.js';

const cdpUrl = String(process.env.LITE_ANDROID_CDP_URL || '').trim();
const baseUrl = String(process.env.LITE_BASE_URL || '').trim();
const browserBridge = String(process.env.POCKETLAB_HARNESS_BROWSER_BRIDGE || '').trim();
const browserBridgeEnabled = process.env.LITE_QUALIFICATION_BROWSER_BRIDGE === '1';
const outputDir = resolve('.pocketlab-dev/performance');
const screens = ['home', 'catalog', 'devices', 'security', 'identity', 'rules', 'recovery'];
const MINIMUM_FRAME_COUNT = 20;

function fail(message) {
  console.error(`[ui-performance-android] ${message}`);
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
    // Fall through to fail closed.
  }
  fail('UI performance evidence requires an exact 40-character source commit.');
}

function validateEndpoint(value, label) {
  let parsed;
  try {
    parsed = new URL(value);
  } catch {
    fail(`${label} must be a valid URL`);
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) fail(`${label} must use http:// or https://`);
  if (parsed.username || parsed.password) fail(`${label} must not include credentials`);
  return parsed;
}

function matrixEvidence(screen, interaction, nestedSurface) {
  const entry = LITE_UI_PERFORMANCE_MATRIX.find((item) => (
    item.screen === screen
    && item.interaction === interaction
    && item.nestedSurface === nestedSurface
  ));
  if (!entry) fail(`No source-owned UI performance matrix entry for ${screen} / ${nestedSurface} / ${interaction}.`);
  return entry.evidenceId;
}

validateEndpoint(cdpUrl, 'LITE_ANDROID_CDP_URL');
const base = validateEndpoint(baseUrl, 'LITE_BASE_URL');
const commit = sourceCommit();

await rm(outputDir, { recursive: true, force: true });
await mkdir(outputDir, { recursive: true });

const browser = await chromium.connectOverCDP(cdpUrl);
const contexts = browser.contexts();
if (!contexts.length) fail('Android Chrome did not expose a browser context over CDP.');
const context = contexts[0];
if (browserBridge) {
  await context.setExtraHTTPHeaders({
    'X-Pocket-Lab-Qualification-Bridge': browserBridge,
  });
}
const page = await context.newPage();

// Physical qualification must prove that Android loaded a fresh candidate
// built from this exact checkout.  The manifest is served by the loopback
// candidate server, never by the installed Server Phone PWA, and contains no
// authority or credential material.
const candidateManifestUrl = new URL('/__pocketlab_qualification__/candidate.json', base).toString();
const candidateManifestResponse = await page.goto(candidateManifestUrl, { waitUntil: 'domcontentloaded' });
if (!candidateManifestResponse || !candidateManifestResponse.ok()) {
  fail('The Android base URL did not expose the required exact-SHA candidate manifest.');
}
let candidateManifest;
try {
  candidateManifest = JSON.parse(await page.locator('body').innerText());
} catch {
  fail('The Android candidate manifest was not valid JSON.');
}
if (candidateManifest?.source_commit !== commit || candidateManifest?.sanitized !== true) {
  fail('The Android candidate manifest source SHA does not match the requested exact commit.');
}
if (candidateManifestResponse.headers()['x-pocket-lab-candidate-sha'] !== commit) {
  fail('The Android candidate response header did not prove the requested exact commit.');
}
await page.evaluate(async () => {
  const registrations = await navigator.serviceWorker?.getRegistrations?.() || [];
  await Promise.all(registrations.map((registration) => registration.unregister()));
  await navigator.serviceWorker?.getRegistrations?.();
});
const candidatePageResponse = await page.goto(new URL('/?screen=home', base).toString(), { waitUntil: 'domcontentloaded' });
if (!candidatePageResponse || !candidatePageResponse.ok()) {
  fail('The Android candidate page did not load.');
}
const candidateMeta = await page.locator('meta[name="pocketlab-candidate-sha"]').getAttribute('content').catch(() => null);
if (candidateMeta !== commit) {
  fail('The Android rendered page did not expose the requested exact candidate SHA.');
}

await page.addInitScript(() => {
  let active = null;
  window.__POCKETLAB_ANDROID_FRAME_SAMPLER__ = {
    start(name) {
      if (active?.raf) cancelAnimationFrame(active.raf);
      active?.observers?.forEach((observer) => observer.disconnect());
      const sample = {
        name: String(name || 'interaction').slice(0, 96),
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
          const longTaskObserver = new PerformanceObserver((list) => {
            list.getEntries().forEach((entry) => sample.longTasks.push(Number(entry.duration) || 0));
          });
          longTaskObserver.observe({ entryTypes: ['longtask'] });
          sample.observers.push(longTaskObserver);
        } catch {}
        try {
          const loafObserver = new PerformanceObserver((list) => {
            list.getEntries().forEach((entry) => sample.longAnimationFrames.push(Number(entry.duration) || 0));
          });
          loafObserver.observe({ type: 'long-animation-frame', buffered: false });
          sample.observers.push(loafObserver);
        } catch {}
        try {
          const eventObserver = new PerformanceObserver((list) => {
            list.getEntries().forEach((entry) => sample.eventDurations.push(Number(entry.duration) || 0));
          });
          eventObserver.observe({ type: 'event', buffered: false, durationThreshold: 16 });
          sample.observers.push(eventObserver);
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
  };
});

let failures = 0;
let targetMisses = 0;
let evidenceCount = 0;
const exercisedInteractions = new Set();

async function firstVisible(locator, label) {
  const count = await locator.count();
  for (let index = 0; index < count; index += 1) {
    const candidate = locator.nth(index);
    if (await candidate.isVisible().catch(() => false)) return candidate;
  }
  fail(`Could not find visible ${label}.`);
}

async function gotoScreen(screenId) {
  const target = new URL(base.href);
  target.searchParams.set('screen', screenId);
  await page.goto(target.href, { waitUntil: 'domcontentloaded', timeout: 30_000 });
  await page.locator(`[data-lite-screen-id="${screenId}"]`).waitFor({ state: 'visible', timeout: 20_000 });
  await page.evaluate(async () => {
    if ('fonts' in document) await document.fonts.ready;
  });
  await page.waitForTimeout(500);
}

async function exerciseScroll(duration = 900) {
  await page.evaluate(async (scrollDuration) => {
    const root = document.scrollingElement || document.documentElement;
    const startTop = root.scrollTop;
    const maxScroll = Math.max(0, root.scrollHeight - window.innerHeight);
    const distance = Math.min(maxScroll, Math.max(220, Math.round(window.innerHeight * 0.55)));
    await new Promise((resolve) => {
      const startedAt = performance.now();
      const step = (now) => {
        const phase = Math.min(1, (now - startedAt) / scrollDuration);
        const wave = (1 - Math.cos(phase * Math.PI * 2)) / 2;
        if (distance > 0) root.scrollTop = Math.min(maxScroll, startTop + (distance * wave));
        if (phase < 1) requestAnimationFrame(step);
        else {
          root.scrollTop = startTop;
          resolve();
        }
      };
      requestAnimationFrame(step);
    });
  }, duration);
}

async function measurePhase4Interaction({
  interaction,
  scope,
  surface,
  action,
  evidenceId = null,
  settleMs = 180,
}) {
  if (!LITE_PERFORMANCE_INTERACTIONS.includes(interaction)) {
    fail(`Unknown Phase 4 interaction id: ${interaction}`);
  }

  const evidenceInteraction = sanitizeLitePerformanceName(`android-cdp:${scope}:${interaction}`);
  await page.evaluate((name) => window.__POCKETLAB_ANDROID_FRAME_SAMPLER__?.start(name), evidenceInteraction);

  await action();
  if (settleMs > 0) await page.waitForTimeout(settleMs);

  const raw = await page.evaluate(() => window.__POCKETLAB_ANDROID_FRAME_SAMPLER__?.stop?.() || null);
  if (!raw) fail(`frame sampler returned no evidence for ${interaction} (${scope})`);

  const summary = summarizeLiteFrames(raw.intervals || [], {
    longTasks: raw.longTasks || [],
    longAnimationFrames: raw.longAnimationFrames || [],
    eventDurations: raw.eventDurations || [],
    warmupFrames: 3,
  });

  if (summary.frame_count < MINIMUM_FRAME_COUNT) {
    fail(`${interaction} (${scope}) produced only ${summary.frame_count} measured frames; at least ${MINIMUM_FRAME_COUNT} are required.`);
  }

  const viewport = page.viewportSize();
  const report = {
    schema_version: LITE_PERFORMANCE_SCHEMA_VERSION,
    interaction: evidenceInteraction,
    performance_evidence_id: evidenceId ? sanitizeLitePerformanceName(evidenceId) : null,
    phase4_interaction: interaction,
    interaction_scope: scope,
    interaction_surface: surface,
    mode: 'live',
    qualification_surface: 'android-cdp',
    browser_project: 'android-cdp',
    source_commit: commit,
    candidate_manifest_verified: true,
    candidate_manifest_source_commit: candidateManifest.source_commit,
    candidate_manifest_schema_version: candidateManifest.schema_version,
    sanitized: true,
    viewport: viewport ? { width: viewport.width, height: viewport.height } : null,
    ...summary,
  };

  const fileName = [
    'ui-performance-android-cdp',
    sanitizeLitePerformanceName(scope),
    sanitizeLitePerformanceName(interaction),
  ].join('-') + '.json';
  await writeFile(resolve(outputDir, fileName), JSON.stringify(report, null, 2) + '\n', 'utf8');

  exercisedInteractions.add(interaction);
  evidenceCount += 1;
  const status = report.target_met ? 'TARGET-PASS' : report.gate_passed ? 'TARGET-MISS' : 'FAIL';
  console.log(
    `[ui-performance-android] ${status} ${interaction} (${scope}): p95=${report.p95_frame_ms}ms smooth=${report.target_smooth_frame_ratio} surface=${surface}`,
  );
  if (!report.gate_passed) failures += 1;
  if (!report.target_met) targetMisses += 1;

  return report;
}

async function measureNestedInteraction({
  screen,
  nestedSurface,
  interaction,
  scope,
  surface,
  action,
  settleMs = 440,
}) {
  return measurePhase4Interaction({
    interaction,
    scope,
    surface,
    action,
    settleMs,
    evidenceId: matrixEvidence(screen, interaction, nestedSurface),
  });
}

// Phase 4: screen-steady on all seven Lite screens.
for (const screenId of screens) {
  await gotoScreen(screenId);
  await measurePhase4Interaction({
    interaction: 'screen-steady',
    scope: screenId,
    surface: `[data-lite-screen-id="${screenId}"]`,
    action: async () => {
      await page.waitForTimeout(720);
    },
    settleMs: 0,
  });
}

// Phase 4: real tab navigation through the rendered Pocket Lab navigation.
await gotoScreen('home');
await measurePhase4Interaction({
  interaction: 'screen-navigation',
  scope: 'home-to-devices',
  surface: 'Pocket Lab Lite navigation',
  action: async () => {
    const devicesButton = await firstVisible(page.getByRole('button', { name: /^Devices$/ }), 'Devices navigation button');
    await devicesButton.click();
    await page.locator('[data-lite-screen-id="devices"]').waitFor({ state: 'visible', timeout: 20_000 });
  },
  settleMs: 700,
});

// Phase 4: representative Manage open/close using the always-read-only Home workspace details surface.
await gotoScreen('home');
const workspaceDetailsButton = await firstVisible(
  page.getByRole('button', { name: /Workspace details/i }),
  'Workspace details button',
);
await measurePhase4Interaction({
  interaction: 'manage-open',
  scope: 'home-workspace',
  surface: 'Home Workspace details',
  action: async () => {
    await workspaceDetailsButton.click();
    await page.locator('[role="dialog"]:visible').first().waitFor({ state: 'visible', timeout: 10_000 });
  },
  settleMs: 420,
});
const workspaceDialog = await firstVisible(page.getByRole('dialog', { name: /Workspace details/i }), 'Home Workspace details dialog');
const workspaceTechnicalDetails = workspaceDialog.locator('details').filter({ hasText: 'Technical details' }).first();
await measureNestedInteraction({
  screen: 'home',
  nestedSurface: 'Workspace details / Technical details',
  interaction: 'nested-detail-open',
  scope: 'home-workspace-technical-details',
  surface: 'Home Workspace details / Technical details',
  action: async () => {
    await workspaceTechnicalDetails.locator('summary').click();
    await workspaceTechnicalDetails.waitFor({ state: 'visible' });
  },
});
await measureNestedInteraction({
  screen: 'home',
  nestedSurface: 'Workspace details / Technical details',
  interaction: 'nested-detail-close',
  scope: 'home-workspace-technical-details',
  surface: 'Home Workspace details / Technical details',
  action: async () => {
    await workspaceTechnicalDetails.locator('summary').click();
  },
});
await measurePhase4Interaction({
  interaction: 'manage-close',
  scope: 'home-workspace',
  surface: 'Home Workspace details',
  action: async () => {
    await page.keyboard.press('Escape');
    await page.locator('[role="dialog"]:visible').first().waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => null);
    if (await page.locator('[role="dialog"]:visible').count()) fail('Home Workspace details did not close after Escape.');
  },
  settleMs: 320,
});

// Deep Apps coverage stays in the prepared PhotoPrism Manage projection. The
// section switch and Details panel do not submit an app operation.
await gotoScreen('catalog');
const catalogManageButton = await firstVisible(page.getByRole('button', { name: /^Manage$/i }), 'Apps Manage button');
await catalogManageButton.click();
const catalogManage = await firstVisible(page.getByRole('dialog', { name: /Manage PhotoPrism/i }), 'PhotoPrism Manage dialog');
const catalogRecoveryTab = catalogManage.getByRole('tab', { name: 'Recovery', exact: true });
await measureNestedInteraction({
  screen: 'catalog',
  nestedSurface: 'PhotoPrism Manage / action sections',
  interaction: 'section-switch',
  scope: 'catalog-photoprism-manage',
  surface: 'PhotoPrism Manage / action sections',
  action: async () => {
    await catalogRecoveryTab.click();
    await catalogRecoveryTab.waitFor({ state: 'visible' });
  },
  settleMs: 480,
});
const catalogDetailsButton = catalogManage.locator('.lite-app-action-details-button').first();
await measureNestedInteraction({
  screen: 'catalog',
  nestedSurface: 'PhotoPrism Manage / action details',
  interaction: 'nested-detail-open',
  scope: 'catalog-photoprism-action-details',
  surface: 'PhotoPrism Manage / action details',
  action: async () => {
    await catalogDetailsButton.click();
    await catalogManage.locator('.lite-app-action-details-panel:visible').first().waitFor({ state: 'visible' });
  },
  settleMs: 480,
});

// Deep Devices coverage opens the prepared server-host detail projection only.
// Diagnostics, health history, and the detail scroll are all read-only.
await gotoScreen('devices');
const deviceManageButton = await firstVisible(page.getByRole('button', { name: /^Manage /i }), 'device Manage button');
await deviceManageButton.click();
const deviceDetailsPanel = await firstVisible(
  page.getByRole('region', { name: /details/i }),
  'device details panel',
);
const deviceDiagnostics = deviceDetailsPanel.locator('details.lite-device-advanced-details');
await measureNestedInteraction({
  screen: 'devices',
  nestedSurface: 'Device details / Diagnostics and history',
  interaction: 'nested-detail-open',
  scope: 'devices-diagnostics-history',
  surface: 'Device details / Diagnostics and history',
  action: async () => {
    await deviceDiagnostics.locator('summary').click();
  },
});
const deviceHealthHistory = deviceDetailsPanel.getByRole('button', { name: 'Show health history' });
await measureNestedInteraction({
  screen: 'devices',
  nestedSurface: 'Device details / health history',
  interaction: 'history-open',
  scope: 'devices-health-history',
  surface: 'Device details / health history',
  action: async () => {
    await deviceHealthHistory.click();
    await deviceDetailsPanel.getByRole('region', { name: 'Device health history' }).waitFor({ state: 'visible' });
  },
});
await measureNestedInteraction({
  screen: 'devices',
  nestedSurface: 'Device details / long detail surface',
  interaction: 'nested-scroll',
  scope: 'devices-details-panel',
  surface: 'Device details / long detail surface',
  action: async () => {
    await deviceDetailsPanel.evaluate(async (element) => {
      const started = performance.now();
      const startTop = element.scrollTop;
      await new Promise((resolve) => {
        const step = (now) => {
          const progress = Math.min(1, (now - started) / 420);
          element.scrollTop = startTop + (element.scrollHeight - element.clientHeight - startTop) * progress;
          if (progress < 1) requestAnimationFrame(step);
          else resolve();
        };
        requestAnimationFrame(step);
      });
      element.scrollTop = startTop;
    });
  },
});

// Phase 4: representative overlay open/close using the Security details sheet.
// This remains UI-only and does not start a Security scan.
await gotoScreen('security');
const securityManageButton = await firstVisible(
  page.getByRole('button', { name: /Manage Security details/i }),
  'Manage Security details button',
);
await measurePhase4Interaction({
  interaction: 'overlay-open',
  scope: 'security-manage',
  surface: 'Security Manage overlay',
  action: async () => {
    await securityManageButton.click();
    await page.locator('[data-lite-sheet-variant="security"]:visible').first().waitFor({ state: 'visible', timeout: 10_000 });
  },
  settleMs: 420,
});
await measurePhase4Interaction({
  interaction: 'overlay-close',
  scope: 'security-manage',
  surface: 'Security Manage overlay',
  action: async () => {
    await page.keyboard.press('Escape');
    await page.locator('[data-lite-sheet-variant="security"]:visible').first().waitFor({ state: 'hidden', timeout: 10_000 }).catch(() => null);
    if (await page.locator('[data-lite-sheet-variant="security"]:visible').count()) fail('Security Manage overlay did not close after Escape.');
  },
  settleMs: 320,
});

// Deep Security coverage uses prepared history and finding projections. It
// never starts a scan or submits a remediation action.
await gotoScreen('security');
const securityManageForHistory = await firstVisible(
  page.getByRole('button', { name: /Manage Security details/i }),
  'Security Manage button',
);
await securityManageForHistory.click();
const securityManageHistory = await firstVisible(
  page.locator('[data-lite-sheet-variant="security"]:visible').first(),
  'Security Manage sheet',
);
await measureNestedInteraction({
  screen: 'security',
  nestedSurface: 'Security Manage / history details',
  interaction: 'history-open',
  scope: 'security-manage-history',
  surface: 'Security Manage / history details',
  action: async () => {
    await securityManageHistory.getByRole('tab', { name: /History/ }).click();
    await securityManageHistory.getByRole('button', { name: 'Open Security history details' }).click();
    await page.locator('[data-security-phase3-responsive-shell="true"]:visible').first().waitFor({ state: 'visible' });
  },
  settleMs: 900,
});

await gotoScreen('security');
const securityManageForFinding = await firstVisible(
  page.getByRole('button', { name: /Manage Security details/i }),
  'Security Manage button for finding details',
);
await securityManageForFinding.click();
const securityManageIssues = await firstVisible(
  page.locator('[data-lite-sheet-variant="security"]:visible').first(),
  'Security Manage sheet for findings',
);
await securityManageIssues.getByRole('tab', { name: /Issues/ }).click();
const findingDetailsButton = await firstVisible(
  securityManageIssues.getByRole('button', { name: /View details for/i }).first(),
  'Security finding details button',
);
await page.waitForTimeout(240);
await measureNestedInteraction({
  screen: 'security',
  nestedSurface: 'Security Manage / finding details',
  interaction: 'finding-detail-open',
  scope: 'security-manage-finding',
  surface: 'Security Manage / finding details',
  action: async () => {
    await findingDetailsButton.click();
    await page.getByRole('dialog', { name: /Dependency risk|Secret-like value/ }).waitFor({ state: 'visible' });
  },
  settleMs: 900,
});

// Phase 4: explicit list/page scrolling on a content-rich screen.
await gotoScreen('recovery');
await measurePhase4Interaction({
  interaction: 'list-scroll',
  scope: 'recovery',
  surface: 'Recovery screen scroll surface',
  action: async () => {
    await exerciseScroll(900);
  },
  settleMs: 180,
});

// Identity and Rules coverage stops at presentation. No confirmation is
// accepted and no identity or policy mutation is submitted.
await gotoScreen('identity');
const manageAccessButton = await firstVisible(page.getByRole('button', { name: /Manage Access/i }), 'Identity Manage Access button');
await manageAccessButton.click();
const identityManage = await firstVisible(page.locator('.lite-identity-manage-sheet:visible'), 'Identity Manage sheet');
const recoveryCodesButton = identityManage.getByRole('button', { name: 'Generate New Codes' });
await measureNestedInteraction({
  screen: 'identity',
  nestedSurface: 'Manage access / protected confirmation presentation',
  interaction: 'confirmation-render',
  scope: 'identity-recovery-confirmation',
  surface: 'Identity Manage / recovery confirmation',
  action: async () => {
    await recoveryCodesButton.click();
    await page.getByRole('dialog', { name: 'Generate new recovery codes?' }).waitFor({ state: 'visible' });
  },
  settleMs: 480,
});
await page.getByRole('button', { name: 'Cancel' }).click();

await gotoScreen('rules');
const manageRulesButton = await firstVisible(page.getByRole('button', { name: /Manage Safety Rules/i }), 'Rules Manage button');
await manageRulesButton.click();
const rulesManage = await firstVisible(page.getByRole('dialog', { name: /Manage Safety Rules/i }), 'Rules Manage dialog');
const rulesTechnicalDetails = rulesManage.locator('details.lite-rules-advanced-details');
await measureNestedInteraction({
  screen: 'rules',
  nestedSurface: 'Manage Safety Rules / Technical status',
  interaction: 'nested-detail-open',
  scope: 'rules-technical-status',
  surface: 'Manage Safety Rules / Technical status',
  action: async () => {
    await rulesTechnicalDetails.locator('summary').click();
  },
});

// Recovery exercises only section navigation and the Verify-backup detail
// projection. Restore apply and backup creation remain untouched.
await gotoScreen('recovery');
const manageRecoveryButton = await firstVisible(page.getByRole('button', { name: 'Manage backups and recovery' }), 'Recovery Manage button');
await manageRecoveryButton.click();
const recoveryManage = await firstVisible(page.locator('[data-lite-sheet-variant="manage"]:visible').first(), 'Recovery Manage sheet');
const recoveryHistoryTab = recoveryManage.getByRole('tab', { name: 'History', exact: true });
await measureNestedInteraction({
  screen: 'recovery',
  nestedSurface: 'Manage recovery / section tabs',
  interaction: 'section-switch',
  scope: 'recovery-manage-history',
  surface: 'Manage recovery / section tabs',
  action: async () => {
    await recoveryHistoryTab.click();
    await recoveryHistoryTab.waitFor({ state: 'visible' });
  },
  settleMs: 480,
});
const recoveryRestoreTab = recoveryManage.getByRole('tab', { name: 'Restore', exact: true });
await recoveryRestoreTab.click();
const verifyBackupDetails = await firstVisible(
  recoveryManage.getByRole('button', { name: /Details: Verify backup/i }),
  'Recovery Verify backup details button',
);
await measureNestedInteraction({
  screen: 'recovery',
  nestedSurface: 'Manage recovery / action details',
  interaction: 'nested-detail-open',
  scope: 'recovery-verify-details',
  surface: 'Manage recovery / action details',
  action: async () => {
    await verifyBackupDetails.click();
    await page.getByRole('dialog', { name: 'Verify Backup' }).waitFor({ state: 'visible' });
  },
  settleMs: 500,
});

// Phase 4: truthful read-only progress/feedback lifecycle.
//
// Starting a Security scan, backup, restore, agent restart, device enrollment, Rules
// activation, or Identity mutation would distort physical UI measurements and cross
// the live read-only qualification boundary. The physical renderer therefore maps
// progress-update, toast-settle, and refresh-feedback onto the real Home refresh
// lifecycle. Evidence records this exact surface instead of claiming a write-backed
// completion toast was exercised.
await gotoScreen('home');
const refreshControl = page.locator('.lite-refresh-control').first();
const refreshButton = await firstVisible(refreshControl.getByRole('button'), 'Home Refresh button');

await measurePhase4Interaction({
  interaction: 'progress-update',
  scope: 'home-refresh',
  surface: 'Home read-only refresh status lifecycle',
  action: async () => {
    await refreshButton.click();
    await page.locator('.lite-refresh-status-popover:visible').waitFor({ state: 'visible', timeout: 10_000 });
    await page.waitForTimeout(760);
  },
  settleMs: 120,
});

await page.locator('.lite-refresh-status-popover').waitFor({ state: 'hidden', timeout: 7_000 });

await measurePhase4Interaction({
  interaction: 'toast-settle',
  scope: 'home-transient-feedback',
  surface: 'Home refresh transient status popover (read-only physical analogue)',
  action: async () => {
    await refreshButton.click();
    const feedback = page.locator('.lite-refresh-status-popover');
    await feedback.waitFor({ state: 'visible', timeout: 10_000 });
    await feedback.waitFor({ state: 'hidden', timeout: 7_000 });
  },
  settleMs: 0,
});

await measurePhase4Interaction({
  interaction: 'refresh-feedback',
  scope: 'home',
  surface: 'Home refresh status popover',
  action: async () => {
    await refreshButton.click();
    await page.locator('.lite-refresh-status-popover:visible').waitFor({ state: 'visible', timeout: 10_000 });
  },
  settleMs: 420,
});

const missingInteractions = LITE_PERFORMANCE_INTERACTIONS.filter((interaction) => !exercisedInteractions.has(interaction));
if (missingInteractions.length) {
  fail(`physical Android qualification did not exercise Phase 4 interaction ids: ${missingInteractions.join(', ')}`);
}

await page.close();

if (failures || targetMisses) {
  if (failures) console.error(`[ui-performance-android] ${failures} evidence sample(s) exceeded the hard render gate.`);
  if (targetMisses) console.error(`[ui-performance-android] ${targetMisses} evidence sample(s) missed the 60 FPS production target.`);
  process.exit(1);
}

console.log(
  `[ui-performance-android] ${evidenceCount} physical-browser evidence samples covered all Phase 4 interaction ids and met the 60 FPS production target`,
);
process.exit(0);
