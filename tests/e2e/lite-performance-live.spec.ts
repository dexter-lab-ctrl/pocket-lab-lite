import { expect, test, type Locator, type Page } from '@playwright/test';
import { openTab, waitForLiteScreenToSettle } from './lite-test-helpers';
import { LITE_UI_PERFORMANCE_MATRIX } from '../../src/performance/litePerformanceMatrix.js';
import {
  exerciseLiteScroll,
  expectLitePerformanceBudget,
  installLiteFrameSampler,
  measureLiteInteraction,
  writeLitePerformanceEvidence,
} from './lite-performance-helpers';

const LIVE_TABS = ['home', 'catalog', 'devices', 'security', 'identity', 'rules', 'recovery'] as const;
const REQUESTED_INTERACTION = String(process.env.LITE_QUALIFICATION_INTERACTION || '').trim().toLowerCase();
const LIVE_INTERACTION_IDS = new Set([
  ...LIVE_TABS.slice(1).map((screenId) => `live-navigation:${screenId}`),
  ...LIVE_TABS.map((screenId) => `live-scroll:${screenId}`),
  'live-deep:home-technical-open',
  'live-deep:home-technical-close',
  'live-deep:catalog-section-switch',
  'live-deep:catalog-action-details',
  'live-deep:devices-diagnostics-open',
  'live-deep:devices-health-history',
  'live-deep:devices-nested-scroll',
  'live-deep:security-history',
  'live-deep:security-finding-details',
  'live-deep:identity-confirmation',
  'live-deep:rules-technical-status',
  'live-deep:recovery-section-switch',
  'live-deep:recovery-action-details',
]);

if (REQUESTED_INTERACTION && !LIVE_INTERACTION_IDS.has(REQUESTED_INTERACTION)) {
  throw new Error(`Unsupported live qualification interaction: ${REQUESTED_INTERACTION}`);
}

function interactionRequested(id: string) {
  return !REQUESTED_INTERACTION || REQUESTED_INTERACTION === id.toLowerCase();
}

function matrixEvidence(screen: string, interaction: string, nestedSurface: string) {
  const entry = LITE_UI_PERFORMANCE_MATRIX.find((item) => (
    item.screen === screen && item.interaction === interaction && item.nestedSurface === nestedSurface
  ));
  if (!entry) throw new Error(`Missing UI performance matrix entry for ${screen} / ${nestedSurface} / ${interaction}`);
  return entry.evidenceId;
}

async function prepareLiveScreen(page: Page, screenId: string) {
  await page.goto(`/?screen=${screenId}`);
  await waitForLiteScreenToSettle(page, screenId);
  await expect(page.locator(`[data-lite-screen-id="${screenId}"]`)).toBeVisible();
}

async function exercisePanelScroll(panel: Locator): Promise<void> {
  await panel.evaluate(async (element) => {
    const started = performance.now();
    const startTop = element.scrollTop;
    await new Promise<void>((resolve) => {
      const step = (now: number) => {
        const progress = Math.min(1, (now - started) / 420);
        element.scrollTop = startTop + (element.scrollHeight - element.clientHeight - startTop) * progress;
        if (progress < 1) requestAnimationFrame(step);
        else resolve();
      };
      requestAnimationFrame(step);
    });
    element.scrollTop = startTop;
  });
}

test.describe('Pocket Lab Lite live UI performance qualification', () => {
  test.skip(
    process.env.LITE_E2E_LIVE !== '1',
    'Set LITE_E2E_LIVE=1 only against an explicitly prepared Pocket Lab Lite runtime.',
  );

  test.beforeEach(async ({ page }) => {
    await installLiteFrameSampler(page);
  });

  test('real runtime tab navigation meets the UI frame gate without write actions', async ({ page }, testInfo) => {
    await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page, 'home');

    for (const screenId of LIVE_TABS.slice(1)) {
      const interactionId = `live-navigation:${screenId}`;
      if (!interactionRequested(interactionId)) continue;
      const report = await measureLiteInteraction(
        page,
        testInfo,
        interactionId,
        async () => {
          await openTab(page, screenId);
          await waitForLiteScreenToSettle(page, screenId);
          await expect(page.locator(`[data-lite-screen-id="${screenId}"]`)).toBeVisible();
        },
        { settleMs: 1000, mode: 'live' },
      );
      expectLitePerformanceBudget(report);
      await writeLitePerformanceEvidence(testInfo, report);
    }
  });

  test('real runtime read-only scrolling meets the UI frame gate on every tab', async ({ page }, testInfo) => {
    await page.goto('/?screen=home');
    for (const screenId of LIVE_TABS) {
      const interactionId = `live-scroll:${screenId}`;
      if (!interactionRequested(interactionId)) continue;
      if (screenId !== 'home') await openTab(page, screenId);
      await waitForLiteScreenToSettle(page, screenId);

      const report = await measureLiteInteraction(
        page,
        testInfo,
        interactionId,
        async () => {
          await exerciseLiteScroll(page, 820);
        },
        { settleMs: 180, mode: 'live' },
      );
      expectLitePerformanceBudget(report);
      await writeLitePerformanceEvidence(testInfo, report);
    }
  });

  test('real runtime safe nested surfaces meet the UI frame gate', async ({ page }, testInfo) => {
    const requested = (id: string) => interactionRequested(id);

    if (requested('live-deep:home-technical-open') || requested('live-deep:home-technical-close')) {
      await prepareLiveScreen(page, 'home');
      await page.getByRole('button', { name: 'Workspace details' }).click();
      const sheet = page.getByRole('dialog', { name: /Workspace details/i });
      await expect(sheet).toBeVisible();
      const disclosure = sheet.locator('details').filter({ hasText: 'Technical details' }).first();
      await expect(disclosure).toBeVisible();

      if (requested('live-deep:home-technical-open')) {
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:home-technical-open',
          async () => {
            await disclosure.locator('summary').click();
            await expect(disclosure).toHaveAttribute('open', '');
          },
          {
            settleMs: 440,
            mode: 'live',
            evidenceId: matrixEvidence('home', 'nested-detail-open', 'Workspace details / Technical details'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }

      if (requested('live-deep:home-technical-close')) {
        if (!(await disclosure.getAttribute('open'))) {
          await disclosure.locator('summary').click();
          await expect(disclosure).toHaveAttribute('open', '');
        }
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:home-technical-close',
          async () => {
            await disclosure.locator('summary').click();
            await expect(disclosure).not.toHaveAttribute('open', '');
          },
          {
            settleMs: 420,
            mode: 'live',
            evidenceId: matrixEvidence('home', 'nested-detail-close', 'Workspace details / Technical details'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }
    }

    if (requested('live-deep:catalog-section-switch') || requested('live-deep:catalog-action-details')) {
      await prepareLiveScreen(page, 'catalog');
      await page.getByRole('button', { name: /^Manage$/i }).first().click();
      const sheet = page.locator('.lite-catalog-manage-layer:visible').first();
      await expect(sheet).toBeVisible();

      if (requested('live-deep:catalog-section-switch')) {
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:catalog-section-switch',
          async () => {
            await sheet.getByRole('tab', { name: 'Recovery', exact: true }).click();
            await expect(sheet.getByRole('tab', { name: 'Recovery', exact: true })).toHaveAttribute('aria-selected', 'true');
          },
          {
            settleMs: 480,
            mode: 'live',
            evidenceId: matrixEvidence('catalog', 'section-switch', 'PhotoPrism Manage / action sections'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }

      if (requested('live-deep:catalog-action-details')) {
        // The live projection's default Photos section contains only the
        // Connect/Import shortcuts, which intentionally have no detail
        // affordance. Recovery is the action-detail surface.
        const recoveryTab = sheet.getByRole('tab', { name: 'Recovery', exact: true });
        if ((await recoveryTab.getAttribute('aria-selected')) !== 'true') {
          await recoveryTab.click();
          await expect(recoveryTab).toHaveAttribute('aria-selected', 'true');
        }
        await expect(sheet.locator('.lite-app-action-details-button:visible').first()).toBeVisible({ timeout: 15_000 });
        const detailsButton = sheet.locator('.lite-app-action-details-button:visible').first();
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:catalog-action-details',
          async () => {
            await detailsButton.click();
            await expect(sheet.locator('.lite-app-action-details-panel:visible').first()).toBeVisible();
          },
          {
            settleMs: 480,
            mode: 'live',
            evidenceId: matrixEvidence('catalog', 'nested-detail-open', 'PhotoPrism Manage / action details'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }
    }

    if (
      requested('live-deep:devices-diagnostics-open')
      || requested('live-deep:devices-health-history')
      || requested('live-deep:devices-nested-scroll')
    ) {
      await prepareLiveScreen(page, 'devices');
      const manage = page.getByRole('button', { name: /^Manage /i }).first();
      await expect(manage).toBeVisible();
      await manage.click();
      const detailsPanel = page.locator('.lite-device-details-panel:visible').first();
      await expect(detailsPanel).toBeVisible({ timeout: 15_000 });

      if (requested('live-deep:devices-diagnostics-open')) {
        const advanced = detailsPanel.locator('details.lite-device-advanced-details').first();
        await expect(advanced).toBeVisible();
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:devices-diagnostics-open',
          async () => {
            await advanced.locator('summary').click();
            await expect(advanced).toHaveAttribute('open', '');
          },
          {
            settleMs: 440,
            mode: 'live',
            evidenceId: matrixEvidence('devices', 'nested-detail-open', 'Device details / Diagnostics and history'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }

      if (requested('live-deep:devices-health-history')) {
        const healthHistory = detailsPanel.getByRole('button', { name: 'Show health history' });
        await expect(healthHistory).toBeVisible();
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:devices-health-history',
          async () => {
            await healthHistory.click();
            await expect(detailsPanel.getByRole('region', { name: 'Device health history' })).toBeVisible();
          },
          {
            settleMs: 440,
            mode: 'live',
            evidenceId: matrixEvidence('devices', 'history-open', 'Device details / health history'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }

      if (requested('live-deep:devices-nested-scroll')) {
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:devices-nested-scroll',
          async () => {
            await exercisePanelScroll(detailsPanel);
          },
          {
            settleMs: 440,
            mode: 'live',
            evidenceId: matrixEvidence('devices', 'nested-scroll', 'Device details / long detail surface'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }
    }

    if (requested('live-deep:security-history') || requested('live-deep:security-finding-details')) {
      await prepareLiveScreen(page, 'security');
      await page.getByRole('button', { name: /Manage Security details/i }).click();
      const manage = page.locator('[data-lite-sheet-variant="security"]:visible').first();
      await expect(manage).toBeVisible();

      if (requested('live-deep:security-history')) {
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:security-history',
          async () => {
            await manage.getByRole('tab', { name: /History/ }).click();
            await manage.getByRole('button', { name: 'Open Security history details' }).click();
            await expect(page.locator('[data-security-phase3-responsive-shell="true"]:visible').first()).toBeVisible();
          },
          {
            settleMs: 900,
            mode: 'live',
            evidenceId: matrixEvidence('security', 'history-open', 'Security Manage / history details'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }

      if (requested('live-deep:security-finding-details')) {
        await manage.getByRole('tab', { name: /Issues/ }).click();
        const findingTrigger = manage.getByRole('button', { name: /View details for/i }).first();
        await expect(findingTrigger).toBeVisible();
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:security-finding-details',
          async () => {
            await findingTrigger.click();
            // Live qualification uses the backend-owned finding projection,
            // whose sanitized title is state-dependent. The responsive shell
            // marker is the stable current UI boundary for this read-only
            // detail surface.
            await expect(page.locator('[data-security-phase3-responsive-shell="true"]:visible').last()).toBeVisible();
          },
          {
            settleMs: 900,
            mode: 'live',
            evidenceId: matrixEvidence('security', 'finding-detail-open', 'Security Manage / finding details'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }
    }

    if (requested('live-deep:identity-confirmation')) {
      await prepareLiveScreen(page, 'identity');
      const manageAccess = page.getByRole('button', { name: /Manage Access/i }).first();
      if (!(await manageAccess.isVisible().catch(() => false))) {
        console.log('[ui-performance-live] UNAVAILABLE identity Manage Access: the current runtime is signed out; no human authentication or synthetic browser session is fabricated.');
      } else {
        await manageAccess.click();
        const manage = page.locator('.lite-identity-manage-sheet:visible');
        await expect(manage).toBeVisible();
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:identity-confirmation',
          async () => {
            await manage.getByRole('button', { name: 'Generate New Codes' }).click();
            await expect(page.getByRole('dialog', { name: 'Generate new recovery codes?' })).toBeVisible();
          },
          {
            settleMs: 480,
            mode: 'live',
            evidenceId: matrixEvidence('identity', 'confirmation-render', 'Manage access / protected confirmation presentation'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
        await page.getByRole('button', { name: 'Cancel' }).click();
      }
    }

    if (requested('live-deep:rules-technical-status')) {
      await prepareLiveScreen(page, 'rules');
      const manageRules = page.getByRole('button', { name: /Manage Safety Rules/i }).first();
      if (!(await manageRules.isVisible().catch(() => false))) {
        console.log('[ui-performance-live] UNAVAILABLE Rules Manage: the current runtime did not expose the Owner-gated surface; continuing safe read-only coverage.');
      } else {
        await manageRules.click();
        const sheet = page.getByRole('dialog', { name: /Manage Safety Rules/i });
        await expect(sheet).toBeVisible();
        const disclosure = sheet.locator('details.lite-rules-advanced-details');
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:rules-technical-status',
          async () => {
            await disclosure.locator('summary').click();
            await expect(disclosure).toHaveAttribute('open', '');
          },
          {
            settleMs: 440,
            mode: 'live',
            evidenceId: matrixEvidence('rules', 'nested-detail-open', 'Manage Safety Rules / Technical status'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }
    }

    if (requested('live-deep:recovery-section-switch') || requested('live-deep:recovery-action-details')) {
      await prepareLiveScreen(page, 'recovery');
      const manageRecovery = page.getByRole('button', { name: 'Manage backups and recovery' }).first();
      if (!(await manageRecovery.isVisible().catch(() => false))) {
        console.log('[ui-performance-live] UNAVAILABLE recovery Manage: the current runtime contained the Recovery section; no unsafe recovery operation is attempted.');
        return;
      }
      await manageRecovery.click();
      const sheet = page.locator('[data-lite-sheet-variant="manage"]:visible').first();
      if (!(await sheet.isVisible().catch(() => false))) {
        console.log('[ui-performance-live] UNAVAILABLE recovery Manage: the current runtime did not keep the safe read-only Manage surface available.');
        return;
      }

      if (requested('live-deep:recovery-section-switch')) {
        const historyTab = sheet.getByRole('tab', { name: 'History', exact: true }).first();
        if (!(await historyTab.isVisible().catch(() => false))) {
          console.log('[ui-performance-live] UNAVAILABLE recovery History: the current runtime did not expose the safe read-only History section.');
          return;
        }
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:recovery-section-switch',
          async () => {
            await historyTab.click();
            await expect(historyTab).toHaveAttribute('aria-selected', 'true');
          },
          {
            settleMs: 480,
            mode: 'live',
            evidenceId: matrixEvidence('recovery', 'section-switch', 'Manage recovery / section tabs'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }

      if (requested('live-deep:recovery-action-details')) {
        const restoreTab = sheet.getByRole('tab', { name: 'Restore', exact: true }).first();
        if (!(await restoreTab.isVisible().catch(() => false))) {
          console.log('[ui-performance-live] UNAVAILABLE recovery Restore: the current runtime did not expose a safe read-only Restore projection.');
          return;
        }
        await restoreTab.click();
        const details = sheet.getByRole('button', { name: /^Details:/ }).first();
        if (!(await details.isVisible().catch(() => false))) {
          console.log('[ui-performance-live] UNAVAILABLE recovery action details: the current runtime did not expose a safe read-only action detail projection.');
          return;
        }
        const report = await measureLiteInteraction(
          page,
          testInfo,
          'live-deep:recovery-action-details',
          async () => {
            await details.click();
            await expect(page.getByRole('dialog').filter({ hasText: /Verify|Restore|Backup/i }).first()).toBeVisible();
          },
          {
            settleMs: 500,
            mode: 'live',
            evidenceId: matrixEvidence('recovery', 'nested-detail-open', 'Manage recovery / action details'),
          },
        );
        expectLitePerformanceBudget(report);
        await writeLitePerformanceEvidence(testInfo, report);
      }
    }
  });
});
