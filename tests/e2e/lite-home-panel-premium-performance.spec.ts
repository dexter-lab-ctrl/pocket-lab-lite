import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';
import {
  expectLitePerformanceBudget, installLiteFrameSampler,
  measureLiteInteraction, writeLitePerformanceEvidence,
} from './lite-performance-helpers';

// PR #588's unchanged hard gates. Authored only, intentionally not sampled.
test.beforeEach(async ({ page }) => { await installLiteFrameSampler(page); });

for (const kind of ['workspace','activity'] as const) {
  test(`[interaction] Azure Home ${kind} premium panel open, navigate and close`, async ({ page }, info) => {
    await installScenario(page, 'healthy');
    await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page, 'home');
    const report = await measureLiteInteraction(page, info, `azure-home-${kind}-premium-open`, async () => {
      await page.getByRole('button', { name: kind === 'workspace' ? 'Workspace details' : 'View activity' }).click();
      await expect(page.getByRole('dialog', { name: kind === 'workspace' ? 'Workspace details' : 'Recent activity' })).toBeVisible();
    }, { settleMs: 900, mode: 'mocked' });
    expectLitePerformanceBudget(report);
    await writeLitePerformanceEvidence(info, report);
    const dialog = page.getByRole('dialog', { name: kind === 'workspace' ? 'Workspace details' : 'Recent activity' });
    const nav = dialog.locator('.lite-home-details-nav');
    const switchReport = await measureLiteInteraction(page, info, `azure-home-${kind}-section-switch`, async () => {
      await nav.getByRole('button', { name: kind === 'workspace' ? 'Diagnostics' : 'History' }).click();
    }, { settleMs: 900, mode: 'mocked' });
    expectLitePerformanceBudget(switchReport);
    await writeLitePerformanceEvidence(info, switchReport);
    const closeReport = await measureLiteInteraction(page, info, `azure-home-${kind}-close`, async () => {
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
    }, { settleMs: 900, mode: 'mocked' });
    expectLitePerformanceBudget(closeReport);
    await writeLitePerformanceEvidence(info, closeReport);
  });
  test(`[interaction] Azure Home ${kind} theme and geometry cost`, async ({ page }, info) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await installScenario(page, 'healthy');
    await page.goto('/?screen=home');
    await waitForLiteScreenToSettle(page, 'home');
    await page.getByRole('button', { name: kind === 'workspace' ? 'Workspace details' : 'View activity' }).click();
    const dialog = page.getByRole('dialog', { name: kind === 'workspace' ? 'Workspace details' : 'Recent activity' });
    const title = kind === 'workspace' ? 'Workspace details' : 'Recent activity';
    for (const [name, action] of [
      ['move', async () => { await dialog.getByRole('button', { name: `Move ${title} panel` }).focus(); await page.keyboard.press('ArrowLeft'); }],
      ['resize', async () => { await dialog.getByRole('button', { name: `Resize ${title} panel` }).focus(); await page.keyboard.press('ArrowLeft'); }],
      ['theme', async () => { await page.evaluate(() => {
        const root = document.documentElement;
        root.dataset.liteTheme = root.dataset.liteTheme === 'dark' ? 'light' : 'dark';
      }); }],
    ] as const) {
      const result = await measureLiteInteraction(page, info, `azure-home-${kind}-${name}`, action,
        { settleMs: 900, mode: 'mocked' });
      expectLitePerformanceBudget(result);
      await writeLitePerformanceEvidence(info, result);
    }
  });
}

test('[interaction] Azure Home mobile Activity scroll/hide/reveal costs', async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 760 });
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await page.getByRole('button', { name: 'View activity' }).click();
  const dialog = page.getByRole('dialog', { name: 'Recent activity' });
  const body = dialog.locator('.lite-home-panel-scroll');
  await body.evaluate((node) => {
    // Long controlled, mock-only scroll span for low-power regression sampling.
    const filler = document.createElement('div');
    filler.style.height = '1400px';
    filler.dataset.perfFiller = 'true';
    node.appendChild(filler);
  });
  const report = await measureLiteInteraction(page, info, 'azure-home-activity-mobile-scroll-navigation', async () => {
    await body.evaluate((node) => {
      node.scrollTop = 260;
      node.dispatchEvent(new Event('scroll'));
      node.scrollTop = 90;
      node.dispatchEvent(new Event('scroll'));
    });
  }, { settleMs: 900, mode: 'mocked' });
  expectLitePerformanceBudget(report);
  await writeLitePerformanceEvidence(info, report);
});
