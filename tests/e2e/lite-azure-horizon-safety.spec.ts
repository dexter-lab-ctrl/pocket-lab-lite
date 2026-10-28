import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// DEFINED — NOT EXECUTED. Synthetic MSW states only. Never start a real device scan.
const sections = ['Overview', 'Checks', 'Changes', 'Issues', 'Coverage', 'Check path', 'Evidence', 'History', 'Technical details'];
async function openSafety(page: Page, scenario = 'security-quick-healthy', theme: 'light' | 'dark' | 'system' = 'dark') {
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
}
async function openManage(page: Page, scenario = 'security-quick-healthy', theme: 'light' | 'dark' | 'system' = 'dark') {
  await openSafety(page, scenario, theme);
  await page.getByRole('button', { name: 'Manage Security details' }).click();
  const dialog = page.getByRole('dialog', { name: 'Manage Safety' });
  await expect(dialog).toBeVisible();
  return dialog;
}
async function assertNoPageOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}

test.describe('Azure Horizon Safety P0–P3 semantic and interaction contract', () => {
  for (const theme of ['light', 'dark', 'system'] as const) {
    test(`backend-reported overview keeps score, scope, issues and evidence separate — ${theme}`, async ({ page }) => {
      await openSafety(page, 'security-quick-healthy', theme);
      await expect(page.getByRole('heading', { name: 'Safety Center', level: 1 })).toBeVisible();
      await expect(page.getByRole('heading', { name: 'Safety overview' })).toBeVisible();
      await expect(page.locator('.lite-security-horizon-facts > div')).toHaveCount(3);
      await expect(page.getByRole('region', { name: 'Needs attention' })).toBeVisible();
      await expect(page.getByRole('region', { name: 'Coverage and checks' })).toBeVisible();
      await expect(page.getByRole('region', { name: 'Recent safety checks' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Manage Security details' })).toHaveCount(1);
      expect(['light', 'dark']).toContain(await page.locator('html').getAttribute('data-lite-theme'));
    });
    test(`nine Manage sections support keyboard tabs and safe close — ${theme}`, async ({ page }) => {
      const dialog = await openManage(page, 'security-quick-healthy', theme);
      await expect(dialog.getByRole('tab')).toHaveCount(9);
      for (const label of sections) {
        const tab = dialog.getByRole('tab', { name: `Open ${label} in Security Manage` });
        await tab.click();
        await expect(tab).toHaveAttribute('aria-selected', 'true');
        await expect(dialog.getByRole('tabpanel', { name: label })).toBeVisible();
      }
      const first = dialog.getByRole('tab', { name: 'Open Overview in Security Manage' });
      await first.focus();
      await page.keyboard.press('ArrowRight');
      await expect(dialog.getByRole('tab', { name: 'Open Checks in Security Manage' })).toHaveAttribute('aria-selected', 'true');
      await page.keyboard.press('End');
      await expect(dialog.getByRole('tab', { name: 'Open Technical details in Security Manage' })).toHaveAttribute('aria-selected', 'true');
      await page.keyboard.press('Home');
      await expect(first).toHaveAttribute('aria-selected', 'true');
      await page.keyboard.press('Escape');
      await expect(dialog).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Manage Security details' })).toBeFocused();
    });
    test(`WCAG AA accessibility covers Safety summary and Manage — ${theme}`, async ({ page }) => {
      await openSafety(page, 'security-action-needed', theme);
      const audit = async () => {
        const report = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
        expect(report.violations.filter((v) => ['critical', 'serious'].includes(v.impact || '')), JSON.stringify(report.violations)).toEqual([]);
      };
      await audit();
      const dialog = page.getByRole('dialog', { name: 'Manage Safety' });
      await page.getByRole('button', { name: 'Manage Security details' }).click();
      await audit();
      await dialog.getByRole('tab', { name: 'Open Coverage in Security Manage' }).click();
      await audit();
    });
  }

  test('first run does not render a made-up reported score', async ({ page }) => {
    await openSafety(page, 'security-first-run');
    await expect(page.getByRole('img', { name: 'Safety score not reported' })).toBeVisible();
    await expect(page.locator('.lite-security-horizon-facts')).toContainText('Not checked');
  });
  test('missing/scanner-unavailable result remains scoped and reviewable', async ({ page }) => {
    await openSafety(page, 'security-scanner-unavailable');
    await expect(page.getByRole('region', { name: 'Coverage and checks' })).toBeVisible();
    await page.getByRole('button', { name: 'View coverage' }).click();
    const dialog = page.getByRole('dialog', { name: 'Manage Safety' });
    await expect(dialog.getByRole('tab', { name: 'Open Coverage in Security Manage' })).toHaveAttribute('aria-selected', 'true');
  });
  test('Full Scan requires confirmation before any scan request', async ({ page }) => {
    await openSafety(page);
    const unsafeRequests: string[] = [];
    page.on('request', (request) => {
      if (request.method() !== 'GET' && /\/api\/lite\/security\/check|\/api\/lite\/security\/scan/.test(request.url())) unsafeRequests.push(request.url());
    });
    await page.getByRole('button', { name: 'Run Full Scan' }).click();
    const confirm = page.getByRole('dialog', { name: 'Full Local Check' });
    await expect(confirm).toBeVisible();
    await expect(confirm).toContainText('charging is recommended');
    expect(unsafeRequests).toEqual([]);
    await confirm.getByRole('button', { name: 'Cancel' }).click();
  });
  test('App Scan requires PhotoPrism-specific confirmation and skips media', async ({ page }) => {
    await openSafety(page);
    await page.getByRole('button', { name: 'Run App Scan' }).click();
    const confirm = page.getByRole('dialog', { name: 'Check PhotoPrism' });
    await expect(confirm).toBeVisible();
    await expect(confirm).toContainText(/skips your photo library/i);
    await confirm.getByRole('button', { name: 'Cancel' }).click();
  });
  test('saved or offline results are labeled and unsafe actions remain blocked', async ({ page }) => {
    await openSafety(page, 'offline-saved');
    await expect(page.getByText(/Showing saved state|Saved result/i).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /Reconnect to run Quick Scan/i })).toBeDisabled();
  });

  for (const width of [320, 360, 375, 390, 430, 600, 700, 701, 768, 1024, 1440]) {
    test(`responsive Safety and Manage at ${width}px: no desktop controls on mobile`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      const panel = await openManage(page, 'security-quick-healthy');
      await expect(panel).toHaveAttribute('data-security-manage-layout', width >= 701 ? 'desktop-movable' : 'mobile-sheet');
      if (width < 701) {
        await expect(panel.getByRole('button', { name: 'Move Safety panel' })).toHaveCount(0);
        await expect(panel.getByRole('button', { name: 'Resize Safety panel' })).toHaveCount(0);
      }
      await assertNoPageOverflow(page);
      const box = await panel.boundingBox();
      if (box) {
        expect(box.x).toBeGreaterThanOrEqual(-1);
        expect(box.x + box.width).toBeLessThanOrEqual(width + 1);
      }
    });
  }
  test('desktop geometry uses only dedicated handles, clamps, and resets', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    const panel = await openManage(page);
    const initial = await panel.boundingBox();
    await panel.getByRole('button', { name: 'Move Safety panel' }).focus();
    await page.keyboard.press('ArrowLeft');
    await panel.getByRole('button', { name: 'Resize Safety panel' }).focus();
    await page.keyboard.press('ArrowUp');
    const moved = await panel.boundingBox();
    if (initial && moved) expect(moved.x).toBeLessThanOrEqual(initial.x);
    await panel.getByRole('button', { name: 'Reset Safety panel position and size' }).click();
    await assertNoPageOverflow(page);
  });
  test('320px at 200% text and reduced motion keeps core controls reachable', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 844 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await openSafety(page, 'security-action-needed');
    await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
    await expect(page.getByRole('button', { name: 'Run Quick Scan' })).toBeVisible();
    await assertNoPageOverflow(page);
    await page.getByRole('button', { name: 'Manage Security details' }).click();
    await expect(page.getByRole('dialog', { name: 'Manage Safety' })).toBeVisible();
  });
});
