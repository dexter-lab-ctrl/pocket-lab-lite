import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import { LITE_QUALIFIED_PERFORMANCE_INTERACTIONS } from './lite-performance-contract';
import { LITE_UI_PERFORMANCE_MATRIX } from '../../src/performance/litePerformanceMatrix.js';
import {
  exerciseLiteScroll,
  expectLitePerformanceBudget,
  installLiteFrameSampler,
  measureLiteInteraction,
  writeLitePerformanceEvidence,
} from './lite-performance-helpers';

const SCREEN_CASES = [
  ['home', 'healthy'],
  ['catalog', 'healthy'],
  ['devices', 'devices-repairing'],
  ['security', 'security-full-running'],
  ['identity', 'identity-password-change-required'],
  ['rules', 'rules-disabled'],
  ['recovery', 'recovery-backup-running'],
] as const;

function interactionId(interaction: typeof LITE_QUALIFIED_PERFORMANCE_INTERACTIONS[number], scope = '') {
  if (!LITE_QUALIFIED_PERFORMANCE_INTERACTIONS.includes(interaction)) {
    throw new Error(`Unknown Lite performance interaction: ${interaction}`);
  }
  return scope ? `${scope}:${interaction}` : interaction;
}

function matrixEvidence(screen: string, interaction: typeof LITE_QUALIFIED_PERFORMANCE_INTERACTIONS[number], surface: string) {
  const entry = LITE_UI_PERFORMANCE_MATRIX.find((item) => (
    item.screen === screen && item.interaction === interaction && item.nestedSurface === surface
  ));
  if (!entry) throw new Error(`Missing UI performance matrix entry for ${screen} / ${surface} / ${interaction}`);
  return entry.evidenceId;
}

test.beforeEach(async ({ page }) => {
  await installLiteFrameSampler(page);
});

for (const [screenId, scenario] of SCREEN_CASES) {
  test(`[interaction] ${screenId} stays within the UI frame gate during visible work`, async ({ page }, testInfo) => {
    await installScenario(page, scenario);
    await page.goto(`/?screen=${screenId}`);
    await waitForLiteScreenToSettle(page, screenId);
    await expect(page.locator(`[data-lite-screen-id="${screenId}"]`)).toBeVisible();

    const report = await measureLiteInteraction(
      page,
      testInfo,
      interactionId('screen-steady', screenId),
      async () => {
        await exerciseLiteScroll(page);
      },
      { settleMs: 180, mode: 'mocked' },
    );

    expectLitePerformanceBudget(report);
    await writeLitePerformanceEvidence(testInfo, report);
  });
}

test('[interaction] cross-tab navigation stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');

  const report = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('screen-navigation', 'home-to-devices'),
    async () => {
      const devicesButton = page.getByRole('button', { name: /^Devices$/ }).first();
      await devicesButton.hover().catch(() => null);
      await devicesButton.click();
      await waitForLiteScreenToSettle(page, 'devices');
    },
    { settleMs: 800, mode: 'mocked' },
  );

  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});

const MANAGE_CASES = [
  ['home', 'healthy', /Workspace details/i, '[role="dialog"]'],
  ['catalog', 'catalog-ready', /^Manage$/i, '[role="dialog"]'],
  ['devices', 'healthy', /Manage Test-Phone-4/i, '.lite-device-details-panel'],
  ['security', 'healthy', /Manage Security details/i, '[role="dialog"]'],
  ['identity', 'healthy', /Manage Access/i, '[role="dialog"]'],
  ['rules', 'healthy', /Manage Safety Rules/i, '[role="dialog"]'],
  ['recovery', 'healthy', /Manage Recovery/i, '[role="dialog"]'],
] as const;

for (const [screenId, scenario, openerName, surfaceSelector] of MANAGE_CASES) {
  test(`[interaction] ${screenId} Manage-open stays inside the render budget`, async ({ page }, testInfo) => {
    await installScenario(page, scenario);
    await page.goto(`/?screen=${screenId}`);
    await waitForLiteScreenToSettle(page, screenId);

    const opener = page.getByRole('button', { name: openerName }).first();
    await expect(opener).toBeVisible();

    const report = await measureLiteInteraction(
      page,
      testInfo,
      interactionId('manage-open', screenId),
      async () => {
        await opener.click();
        await expect(page.locator(`${surfaceSelector}:visible`).first()).toBeVisible();
      },
      { settleMs: 560, mode: 'mocked' },
    );

    expectLitePerformanceBudget(report);
    await writeLitePerformanceEvidence(testInfo, report);
  });
}

test('[interaction] Home Technical details disclosure stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await page.getByRole('button', { name: 'Workspace details' }).click();
  const sheet = page.getByRole('dialog', { name: /Workspace details/i });
  await expect(sheet).toBeVisible();
  const disclosure = sheet.locator('details').filter({ hasText: 'Technical details' }).first();
  await expect(disclosure).toBeVisible();

  const openReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('nested-detail-open', 'home-workspace-technical-details'),
    async () => {
      await disclosure.locator('summary').click();
      await expect(disclosure).toHaveAttribute('open', '');
    },
    {
      settleMs: 440,
      mode: 'mocked',
      evidenceId: matrixEvidence('home', 'nested-detail-open', 'Workspace details / Technical details'),
    },
  );
  expectLitePerformanceBudget(openReport);
  await writeLitePerformanceEvidence(testInfo, openReport);

  const closeReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('nested-detail-close', 'home-workspace-technical-details'),
    async () => {
      await disclosure.locator('summary').click();
      await expect(disclosure).not.toHaveAttribute('open', '');
    },
    {
      settleMs: 420,
      mode: 'mocked',
      evidenceId: matrixEvidence('home', 'nested-detail-close', 'Workspace details / Technical details'),
    },
  );
  expectLitePerformanceBudget(closeReport);
  await writeLitePerformanceEvidence(testInfo, closeReport);
});

test('[interaction] Apps Manage section and action details stay inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'catalog-ready');
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page, 'catalog');
  await page.getByRole('button', { name: /^Manage$/i }).first().click();
  const sheet = page.getByRole('dialog', { name: /Manage PhotoPrism/i });
  await expect(sheet).toBeVisible();

  const sectionReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('section-switch', 'catalog-manage-recovery'),
    async () => {
      await sheet.getByRole('tab', { name: 'Recovery', exact: true }).click();
      await expect(sheet.getByRole('tab', { name: 'Recovery', exact: true })).toHaveAttribute('aria-selected', 'true');
    },
    {
      settleMs: 480,
      mode: 'mocked',
      evidenceId: matrixEvidence('catalog', 'section-switch', 'PhotoPrism Manage / action sections'),
    },
  );
  expectLitePerformanceBudget(sectionReport);
  await writeLitePerformanceEvidence(testInfo, sectionReport);

  const detailsButton = sheet.locator('.lite-app-action-details-button').first();
  await expect(detailsButton).toBeVisible();
  const detailsReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('nested-detail-open', 'catalog-action-details'),
    async () => {
      await detailsButton.click();
      await expect(sheet.locator('.lite-app-action-details-panel:visible').first()).toBeVisible();
    },
    {
      settleMs: 480,
      mode: 'mocked',
      evidenceId: matrixEvidence('catalog', 'nested-detail-open', 'PhotoPrism Manage / action details'),
    },
  );
  expectLitePerformanceBudget(detailsReport);
  await writeLitePerformanceEvidence(testInfo, detailsReport);
});

test('[interaction] Devices nested details and health history stay inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'devices-resource-complete');
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
  const manage = page.getByRole('button', { name: /Manage Pocket Lab Lite Server/i });
  await expect(manage).toBeVisible();
  await manage.click();
  const panel = page.getByRole('region', { name: /Pocket Lab Lite Server details/i });
  await expect(panel).toBeVisible();

  const advanced = panel.locator('details.lite-device-advanced-details');
  const detailReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('nested-detail-open', 'devices-diagnostics-history'),
    async () => {
      await advanced.locator('summary').click();
      await expect(advanced).toHaveAttribute('open', '');
    },
    {
      settleMs: 440,
      mode: 'mocked',
      evidenceId: matrixEvidence('devices', 'nested-detail-open', 'Device details / Diagnostics and history'),
    },
  );
  expectLitePerformanceBudget(detailReport);
  await writeLitePerformanceEvidence(testInfo, detailReport);

  const healthHistory = panel.getByRole('button', { name: 'Show health history' });
  await expect(healthHistory).toBeVisible();
  const historyReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('history-open', 'devices-health-history'),
    async () => {
      await healthHistory.click();
      await expect(panel.getByRole('region', { name: 'Device health history' })).toBeVisible();
    },
    {
      settleMs: 440,
      mode: 'mocked',
      evidenceId: matrixEvidence('devices', 'history-open', 'Device details / health history'),
    },
  );
  expectLitePerformanceBudget(historyReport);
  await writeLitePerformanceEvidence(testInfo, historyReport);

  const scrollReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('nested-scroll', 'devices-details-panel'),
    async () => {
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
    },
    {
      settleMs: 440,
      mode: 'mocked',
      evidenceId: matrixEvidence('devices', 'nested-scroll', 'Device details / long detail surface'),
    },
  );
  expectLitePerformanceBudget(scrollReport);
  await writeLitePerformanceEvidence(testInfo, scrollReport);
});

test('[interaction] Security history details stay inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'security-action-needed');
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
  await page.getByRole('button', { name: /Manage Security details/i }).click();
  const manage = page.locator('[data-lite-sheet-variant="security"]:visible').first();
  await expect(manage).toBeVisible();

  const historyReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('history-open', 'security-manage-history'),
    async () => {
      await manage.getByRole('tab', { name: /History/ }).click();
      await manage.getByRole('button', { name: 'Open Security history details' }).click();
      await expect(page.locator('[data-security-phase3-responsive-shell="true"]:visible').first()).toBeVisible();
    },
    {
      settleMs: 900,
      mode: 'mocked',
      evidenceId: matrixEvidence('security', 'history-open', 'Security Manage / history details'),
    },
  );
  expectLitePerformanceBudget(historyReport);
  await writeLitePerformanceEvidence(testInfo, historyReport);
});

test('[interaction] Security finding details stay inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'security-action-needed');
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
  await page.getByRole('button', { name: /Manage Security details/i }).click();
  const manage = page.locator('[data-lite-sheet-variant="security"]:visible').first();
  await expect(manage).toBeVisible();

  await manage.getByRole('tab', { name: /Issues/ }).click();
  const findingTrigger = manage.getByRole('button', { name: /View details for/i }).first();
  await expect(findingTrigger).toBeVisible();
  await page.waitForTimeout(240);

  const findingReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('finding-detail-open', 'security-manage-finding'),
    async () => {
      await findingTrigger.click();
      await expect(page.getByRole('dialog', { name: /Dependency risk|Secret-like value/ })).toBeVisible();
    },
    {
      settleMs: 900,
      mode: 'mocked',
      evidenceId: matrixEvidence('security', 'finding-detail-open', 'Security Manage / finding details'),
    },
  );
  expectLitePerformanceBudget(findingReport);
  await writeLitePerformanceEvidence(testInfo, findingReport);
});

test('[interaction] Identity confirmation rendering stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'identity-summary');
  await page.goto('/?screen=identity');
  await waitForLiteScreenToSettle(page, 'identity');
  await page.getByRole('button', { name: /Manage Access/i }).click();
  const manage = page.locator('.lite-identity-manage-sheet:visible');
  await expect(manage).toBeVisible();
  const confirmationReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('confirmation-render', 'identity-recovery'),
    async () => {
      await manage.getByRole('button', { name: 'Generate New Codes' }).click();
      await expect(page.getByRole('dialog', { name: 'Generate new recovery codes?' })).toBeVisible();
    },
    {
      settleMs: 480,
      mode: 'mocked',
      evidenceId: matrixEvidence('identity', 'confirmation-render', 'Manage access / protected confirmation presentation'),
    },
  );
  expectLitePerformanceBudget(confirmationReport);
  await writeLitePerformanceEvidence(testInfo, confirmationReport);
  await page.getByRole('button', { name: 'Cancel' }).click();
});

test('[interaction] Rules Technical status disclosure stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=rules');
  await waitForLiteScreenToSettle(page, 'rules');
  await page.getByRole('button', { name: /Manage Safety Rules/i }).click();
  const sheet = page.getByRole('dialog', { name: /Manage Safety Rules/i });
  await expect(sheet).toBeVisible();
  const disclosure = sheet.locator('details.lite-rules-advanced-details');
  const report = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('nested-detail-open', 'rules-technical-status'),
    async () => {
      await disclosure.locator('summary').click();
      await expect(disclosure).toHaveAttribute('open', '');
    },
    {
      settleMs: 440,
      mode: 'mocked',
      evidenceId: matrixEvidence('rules', 'nested-detail-open', 'Manage Safety Rules / Technical status'),
    },
  );
  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});

test('[interaction] Recovery Manage sections and action details stay inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'recovery-verified');
  await page.goto('/?screen=recovery');
  await waitForLiteScreenToSettle(page, 'recovery');
  await page.getByRole('button', { name: 'Manage backups and recovery' }).click();
  const sheet = page.locator('[data-lite-sheet-variant="manage"]:visible').first();
  await expect(sheet).toBeVisible();

  const sectionReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('section-switch', 'recovery-manage-history'),
    async () => {
      await sheet.getByRole('tab', { name: 'History', exact: true }).click();
      await expect(sheet.getByRole('tab', { name: 'History', exact: true })).toHaveAttribute('aria-selected', 'true');
    },
    {
      settleMs: 480,
      mode: 'mocked',
      evidenceId: matrixEvidence('recovery', 'section-switch', 'Manage recovery / section tabs'),
    },
  );
  expectLitePerformanceBudget(sectionReport);
  await writeLitePerformanceEvidence(testInfo, sectionReport);

  await sheet.getByRole('tab', { name: 'Restore', exact: true }).click();
  const details = sheet.getByRole('button', { name: /Details: Verify backup/i });
  await expect(details).toBeVisible();
  const detailsReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('nested-detail-open', 'recovery-verify-details'),
    async () => {
      await details.click();
      await expect(page.getByRole('dialog', { name: 'Verify Backup' })).toBeVisible();
    },
    {
      settleMs: 500,
      mode: 'mocked',
      evidenceId: matrixEvidence('recovery', 'nested-detail-open', 'Manage recovery / action details'),
    },
  );
  expectLitePerformanceBudget(detailsReport);
  await writeLitePerformanceEvidence(testInfo, detailsReport);
});

test('[interaction] representative Manage-close stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'catalog-ready');
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page, 'catalog');

  await page.getByRole('button', { name: /^Manage$/i }).first().click();
  const sheet = page.locator('.lite-catalog-manage-layer:visible').first();
  await expect(sheet).toBeVisible();

  const report = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('manage-close', 'catalog'),
    async () => {
      await sheet.getByRole('button', { name: 'Close app actions' }).last().click();
      await expect(sheet).toBeHidden();
    },
    { settleMs: 360, mode: 'mocked' },
  );

  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});

test('[interaction] representative overlay open and close stay inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  const initialSecurityReads = Promise.all([
    page.waitForResponse((response) => response.url().includes('/api/lite/security/freshness') && response.ok()),
    page.waitForResponse((response) => response.url().includes('/api/lite/security/summary') && response.ok()),
  ]);
  await page.goto('/?screen=security');
  await initialSecurityReads;
  await waitForLiteScreenToSettle(page, 'security');

  const opener = page.getByRole('button', { name: /Manage Security details/i }).first();
  const sheet = page.locator('[data-lite-sheet-variant="security"]:visible').first();

  const openReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('overlay-open', 'security-manage'),
    async () => {
      await opener.click();
      await expect(sheet).toBeVisible();
    },
    { settleMs: 480, mode: 'mocked' },
  );
  expectLitePerformanceBudget(openReport);
  await writeLitePerformanceEvidence(testInfo, openReport);

  const closeReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('overlay-close', 'security-manage'),
    async () => {
      await sheet.getByRole('button', { name: 'Close security details' }).click();
      await expect(sheet).toBeHidden();
    },
    { settleMs: 360, mode: 'mocked' },
  );
  expectLitePerformanceBudget(closeReport);
  await writeLitePerformanceEvidence(testInfo, closeReport);
});

test('[interaction] explicit list scrolling stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'recovery-backup-running');
  await page.goto('/?screen=recovery');
  await waitForLiteScreenToSettle(page, 'recovery');

  const report = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('list-scroll', 'recovery'),
    async () => {
      await exerciseLiteScroll(page, 820);
    },
    { settleMs: 180, mode: 'mocked' },
  );

  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});

test('[interaction] truthful Security progress updates and completion toast stay inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.addInitScript(() => {
    class ControlledEventSource {
      static instances: ControlledEventSource[] = [];
      url: string;
      closed = false;
      listeners = new Map<string, Array<(event: MessageEvent) => void>>();
      onopen?: (event: Event) => void;
      onmessage?: (event: MessageEvent) => void;

      constructor(url: string | URL) {
        this.url = String(url);
        ControlledEventSource.instances.push(this);
        window.setTimeout(() => this.onopen?.(new Event('open')), 0);
      }

      addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
        const listeners = this.listeners.get(type) || [];
        const callback = typeof listener === 'function'
          ? listener as (event: MessageEvent) => void
          : (event: MessageEvent) => listener.handleEvent(event);
        listeners.push(callback);
        this.listeners.set(type, listeners);
      }

      removeEventListener(type: string, listener: EventListenerOrEventListenerObject) {
        if (typeof listener !== 'function') return;
        this.listeners.set(type, (this.listeners.get(type) || []).filter((item) => item !== listener));
      }

      close() {
        this.closed = true;
      }

      emit(payload: Record<string, unknown>) {
        const event = new MessageEvent('message', { data: JSON.stringify(payload) });
        this.onmessage?.(event);
        (this.listeners.get(String(payload.type || '')) || []).forEach((listener) => listener(event));
      }
    }

    (window as any).EventSource = ControlledEventSource;
    (window as any).__liteControlledSecurityEvents = ControlledEventSource;
  });

  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');

  let acceptedRunId = '';
  const acceptedScan = page.waitForResponse((response) => (
    response.url().includes('/api/lite/security/check') && response.status() === 202
  ));

  const progressReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('progress-update', 'security'),
    async () => {
      await page.getByRole('button', { name: 'Run Quick Scan' }).click();
      const response = await acceptedScan;
      const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
      acceptedRunId = String(payload.run_id || payload.job_id || payload.command_id || 'security-2026-08-31t165957z-2226321f');
      const progress = page.getByRole('progressbar', { name: 'Safety check progress' });
      await expect(progress).toBeVisible();
      await page.waitForTimeout(920);
      await expect(progress).toBeVisible();
    },
    { settleMs: 180, mode: 'mocked' },
  );

  expectLitePerformanceBudget(progressReport);
  await writeLitePerformanceEvidence(testInfo, progressReport);

  await expect.poll(() => page.evaluate(() => (window as any).__liteControlledSecurityEvents.instances
    .filter((source: any) => source.url.includes('/api/lite/security/events') && !source.closed).length)).toBeGreaterThanOrEqual(1);

  const toastReport = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('toast-settle', 'security-complete'),
    async () => {
      await page.evaluate((runId) => {
        const source = (window as any).__liteControlledSecurityEvents.instances
          .find((item: any) => item.url.includes('/api/lite/security/events') && !item.closed);
        source?.emit({
          type: 'security.scan.completed',
          event_id: 901,
          run_id: runId,
          profile: 'quick',
          status: 'succeeded',
          percent: 100,
          active_scan: false,
          snapshot: false,
          updated_at: '2026-08-31T10:00:00.000Z',
        });
      }, acceptedRunId);

      const toast = page.locator('.lite-toast', { hasText: 'Safety check completed' });
      await expect(toast).toBeVisible();
      await page.waitForTimeout(180);
      await toast.getByRole('button', { name: 'Dismiss message' }).click();
      await expect(toast).toHaveCount(0);
    },
    { settleMs: 220, mode: 'mocked' },
  );

  expectLitePerformanceBudget(toastReport);
  await writeLitePerformanceEvidence(testInfo, toastReport);
});

test('[interaction] Home refresh feedback stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');

  const refresh = page.getByRole('button', { name: /^Refresh$/ }).first();
  await expect(refresh).toBeVisible();

  const report = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('refresh-feedback', 'home'),
    async () => {
      await refresh.click();
      await expect(page.locator('.lite-refresh-status-popover')).toBeVisible();
    },
    { settleMs: 420, mode: 'mocked' },
  );

  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});
