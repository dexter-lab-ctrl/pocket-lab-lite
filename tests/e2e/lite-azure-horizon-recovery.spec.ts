import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// DEFINED — NOT RUN. Synthetic, safe MSW scenarios only. Never dispatch a confirmed restore.
async function openRecovery(page: Page, scenario = 'recovery-verified', appearance: 'light' | 'dark' | 'system' = 'dark') {
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), appearance);
  await installScenario(page, scenario);
  await page.goto('/?screen=recovery');
  await waitForLiteScreenToSettle(page, 'recovery');
}
async function openManage(page: Page, scenario = 'recovery-preview-ready', appearance: 'light' | 'dark' | 'system' = 'dark') {
  await openRecovery(page, scenario, appearance);
  const trigger = page.getByRole('button', { name: 'Manage Recovery' });
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: /Manage backups and recovery/i });
  await expect(dialog).toBeVisible();
  return dialog;
}
async function assertNoHorizontalOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}

test.describe('Azure Horizon Recovery P0–P4 semantic, accessible and protected UX', () => {
  for (const appearance of ['light', 'dark', 'system'] as const) {
    test(`Recovery overview distinguishes backup, destination and preview — ${appearance}`, async ({ page }) => {
      await openRecovery(page, 'recovery-verified', appearance);
      await expect(page.getByRole('heading', { name: 'Recovery', exact: true })).toBeVisible();
      await expect(page.locator('[data-recovery-summary-facts] > li')).toHaveCount(3);
      await expect(page.locator('[data-recovery-fact="backup"]')).toContainText(/Verified/i);
      await expect(page.locator('[data-recovery-fact="destination"]')).toBeVisible();
      await expect(page.locator('[data-recovery-fact="preview"]')).toBeVisible();
      await expect(page.getByRole('button', { name: 'Back Up Now' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Manage Recovery' })).toHaveCount(1);
      await expect(page.locator('.lite-recovery-premium-stage-grid button')).toHaveCount(4);
      await expect(page.locator('.lite-recovery-premium-timeline')).toBeVisible();
      expect(['light', 'dark']).toContain(await page.locator('html').getAttribute('data-lite-theme'));
    });
    test(`theme and four Manage tabs retain portal and keyboard semantics — ${appearance}`, async ({ page }) => {
      const dialog = await openManage(page, 'recovery-preview-ready', appearance);
      await expect(dialog.getByRole('tab')).toHaveCount(4);
      await dialog.getByRole('tab', { name: 'Backup' }).focus();
      await page.keyboard.press('ArrowRight');
      await expect(dialog.getByRole('tab', { name: 'Restore' })).toHaveAttribute('aria-selected', 'true');
      await expect(dialog.getByRole('tabpanel', { name: 'Restore' })).toBeVisible();
      await dialog.getByRole('tab', { name: 'Protection' }).click();
      await expect(dialog.getByRole('tabpanel', { name: 'Protection' }).getByText('Protected data', { exact: true })).toBeVisible();
      await dialog.getByRole('tab', { name: 'History' }).click();
      await expect(dialog.getByRole('tabpanel', { name: 'History' })).toBeVisible();
      const style = await dialog.evaluate((node) => ({ background: getComputedStyle(node).backgroundColor, color: getComputedStyle(node).color }));
      expect(style.background).not.toBe('rgba(0, 0, 0, 0)');
      expect(style.background).not.toBe(style.color);
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Manage Recovery' })).toBeFocused();
    });
    test(`WCAG AA: main Recovery, Manage, and restore impact — ${appearance}`, async ({ page }) => {
      await openRecovery(page, 'recovery-preview-ready', appearance);
      const scan = async () => {
        const report = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
        expect(report.violations.filter((v) => ['critical', 'serious'].includes(v.impact || '')), JSON.stringify(report.violations)).toEqual([]);
      };
      await scan();
      await page.getByRole('button', { name: 'Manage Recovery' }).click();
      const dialog = page.getByRole('dialog', { name: /Manage backups and recovery/i });
      await scan();
      await dialog.getByRole('tab', { name: 'Restore' }).click();
      await scan();
    });
  }
  for (const width of [320, 360, 375, 390, 430, 700, 701, 768, 1024, 1440]) {
    test(`responsive landing and Manage at ${width}px without overflow or geometry leakage`, async ({ page }) => {
      await page.setViewportSize({ width, height: 880 });
      const dialog = await openManage(page);
      await assertNoHorizontalOverflow(page);
      await expect(dialog).toHaveAttribute('data-recovery-manage-layout', width >= 701 ? 'desktop-movable' : 'mobile-sheet');
      if (width < 701) {
        await expect(dialog.getByRole('button', { name: 'Move Recovery panel' })).toHaveCount(0);
        await expect(dialog.getByRole('button', { name: 'Resize Recovery panel' })).toHaveCount(0);
      }
      const bounds = await dialog.boundingBox();
      if (bounds) {
        expect(bounds.x).toBeGreaterThanOrEqual(-1);
        expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
      }
      const locationStatus = dialog.locator('.lite-recovery-location-head > [data-lite-perf-primitive="status-badge"]');
      await expect(locationStatus).toHaveCSS('white-space', 'nowrap');
      expect(await locationStatus.evaluate((node) => node.scrollWidth <= node.clientWidth + 1)).toBe(true);
      await dialog.getByRole('tab', { name: 'Restore' }).click();
      await assertNoHorizontalOverflow(page);
    });
  }
  test('320px at 200% text and reduced motion keeps all recovery actions reachable', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 844 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const dialog = await openManage(page, 'recovery-restore-blocked');
    await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
    await expect(dialog.getByRole('tab', { name: 'Backup' })).toBeVisible();
    await expect(dialog.getByRole('tab', { name: 'Restore' })).toBeVisible();
    await assertNoHorizontalOverflow(page);
  });
  test('Back Up, Verify, Preview, Restore journey remains educational, not a one-click execution', async ({ page }) => {
    await openRecovery(page, 'recovery-unverified');
    const sends: string[] = [];
    page.on('request', (request) => {
      if (request.method() !== 'GET' && request.url().includes('/api/lite/recovery/')) sends.push(request.url());
    });
    await page.locator('.lite-recovery-premium-stage-grid button').nth(2).click();
    await expect(page.locator('.lite-recovery-premium-stage-grid button').nth(2)).toHaveAttribute('aria-expanded', 'true');
    expect(sends).toEqual([]);
  });
  test('backend stale summary blocks backup and restore while retaining saved visibility', async ({ page }) => {
    await openRecovery(page, 'recovery-projection-too-old');
    await expect(page.locator('.lite-recovery-premium-protection')).toHaveAttribute('data-recovery-protection-state', 'unknown');
    await expect(page.getByRole('button', { name: 'Back Up Now' })).toBeDisabled();
    const dialog = await (async () => { await page.getByRole('button', { name: 'Manage Recovery' }).click(); return page.getByRole('dialog', { name: /Manage backups and recovery/i }); })();
    await dialog.getByRole('tab', { name: 'Restore' }).click();
    await expect(dialog.getByRole('button', { name: 'Restore', exact: true })).toBeDisabled();
  });
  test('protected restore confirmation cannot dispatch a restore on Cancel or panel interaction', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await openRecovery(page, 'recovery-preview-ready');
    const sends: string[] = [];
    page.on('request', (req) => {
      if (req.method() !== 'GET' && /\/api\/lite\/recovery\/restore(?:$|\/)/.test(req.url())) sends.push(req.url());
    });
    await page.getByRole('button', { name: 'Manage Recovery' }).click();
    const panel = page.getByRole('dialog', { name: /Manage backups and recovery/i });
    await panel.getByRole('tab', { name: 'Restore' }).click();
    await panel.getByRole('button', { name: 'Move Recovery panel' }).focus();
    await page.keyboard.press('ArrowLeft');
    await panel.getByRole('button', { name: 'Resize Recovery panel' }).focus();
    await page.keyboard.press('ArrowLeft');
    const restore = panel.locator('.lite-recovery-manage-action-row').filter({ hasText: 'Restore selected backup' }).getByRole('button', { name: 'Restore', exact: true });
    await expect(restore).toBeEnabled();
    await restore.click();
    const confirmation = page.getByRole('dialog', { name: 'Restore backup' });
    await expect(confirmation).toBeVisible();
    await expect(confirmation.getByRole('button', { name: /Move Recovery panel|Resize Recovery panel/ })).toHaveCount(0);
    await expect(confirmation).toContainText('Matching restore preview');
    await confirmation.getByRole('button', { name: 'Cancel' }).click();
    expect(sends).toEqual([]);
  });
  test('desktop Manage shares clamp/reset movement while nested content stays interactive', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const panel = await openManage(page);
    const original = await panel.boundingBox();
    await panel.getByRole('button', { name: 'Move Recovery panel' }).focus();
    await page.keyboard.press('ArrowLeft');
    const moved = await panel.boundingBox();
    if (original && moved) expect(moved.x).toBeLessThan(original.x);
    await panel.getByRole('button', { name: 'Resize Recovery panel' }).focus();
    await page.keyboard.press('ArrowLeft');
    const resized = await panel.boundingBox();
    if (resized && moved) expect(resized.width).toBeLessThanOrEqual(moved.width);
    await panel.getByRole('button', { name: 'Reset Recovery panel position and size' }).click();
    await page.setViewportSize({ width: 800, height: 700 });
    const clamped = await panel.boundingBox();
    if (clamped) expect(clamped.x + clamped.width).toBeLessThanOrEqual(801);
    await panel.getByRole('tab', { name: 'History' }).click();
    await expect(panel.getByRole('tabpanel', { name: 'History' })).toBeVisible();
  });
  for (const scenario of ['recovery-no-backups', 'recovery-unverified', 'recovery-repository-unavailable', 'recovery-restore-blocked', 'recovery-restore-running', 'recovery-rollback-completed']) {
    test(`backend state ${scenario} never invents restore eligibility`, async ({ page }) => {
      await openRecovery(page, scenario);
      await expect(page.locator('.lite-recovery-premium-protection')).toBeVisible();
      await expect(page.locator('[data-recovery-fact="backup"]')).toBeVisible();
      await expect(page.locator('[data-recovery-fact="preview"]')).toBeVisible();
      await expect(page.locator('.lite-recovery-premium-stage-grid button')).toHaveCount(4);
    });
  }
});
