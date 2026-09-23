import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import { LITE_QUALIFIED_PERFORMANCE_INTERACTIONS } from './lite-performance-contract';
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

test('[interaction] representative Manage-close stays inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'catalog-ready');
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page, 'catalog');

  await page.getByRole('button', { name: /^Manage$/i }).first().click();
  const sheet = page.locator('[data-lite-sheet-variant="manage"]:visible').first();
  await expect(sheet).toBeVisible();

  const report = await measureLiteInteraction(
    page,
    testInfo,
    interactionId('manage-close', 'catalog'),
    async () => {
      await page.getByRole('button', { name: 'Close app actions' }).click();
      await expect(sheet).toBeHidden();
    },
    { settleMs: 360, mode: 'mocked' },
  );

  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(testInfo, report);
});

test('[interaction] representative overlay open and close stay inside the render budget', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=security');
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
      await page.getByRole('button', { name: 'Close security details' }).click();
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
