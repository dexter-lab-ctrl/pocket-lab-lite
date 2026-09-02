import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function expectNoBlockingAxeViolations(page: Page, selector: string) {
  const result = await new AxeBuilder({ page })
    .include(selector)
    .disableRules(['color-contrast'])
    .analyze();
  const blocking = result.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''));
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

const MANAGE_CASES = [
  ['home', /Workspace details/i, '[role="dialog"]'],
  ['catalog', /^Manage$/i, '[role="dialog"]'],
  ['devices', /Manage Test-Phone-4/i, '.lite-device-details-panel'],
  ['security', /Manage Security details/i, '[role="dialog"]'],
  ['identity', /Manage Access/i, '[role="dialog"]'],
  ['rules', /Manage Safety Rules/i, '[role="dialog"]'],
  ['recovery', /Manage Recovery/i, '[role="dialog"]'],
] as const;

for (const [screenId, openerName, surfaceSelector] of MANAGE_CASES) {
  test(`${screenId} Manage-open state has no serious or critical Axe violations`, async ({ page }) => {
    await installScenario(page, 'healthy');
    await page.goto(`/?screen=${screenId}`);
    await waitForLiteScreenToSettle(page, screenId);

    const opener = page.getByRole('button', { name: openerName }).first();
    await expect(opener).toBeVisible();
    await opener.focus();
    await opener.click();

    const surface = page.locator(`${surfaceSelector}:visible`).first();
    await expect(surface).toBeVisible();
    if (surfaceSelector === '[role="dialog"]') {
      await expect(surface).toHaveAttribute('aria-modal', 'true');
      const ariaLabel = await surface.getAttribute('aria-label');
      const labelledBy = await surface.getAttribute('aria-labelledby');
      expect(Boolean(ariaLabel || labelledBy), `${screenId}: dialog must have an accessible name`).toBe(true);
      await expect.poll(() => page.evaluate(() => Boolean(document.activeElement?.closest?.('[role="dialog"]')))).toBe(true);
    } else {
      await expect(surface).toHaveAttribute('role', 'region');
      await expect(surface).toHaveAttribute('aria-label', /details/i);
    }

    await expectNoBlockingAxeViolations(page, surfaceSelector);
  });
}

const ATTENTION_CASES = [
  ['home', 'lifecycle-attention'],
  ['security', 'security-urgent'],
  ['rules', 'rules-validation-error'],
  ['recovery', 'recovery-restore-blocked'],
] as const;

for (const [screenId, scenario] of ATTENTION_CASES) {
  test(`${screenId} attention/error state stays accessible`, async ({ page }) => {
    await installScenario(page, scenario);
    await page.goto(`/?screen=${screenId}`);
    await waitForLiteScreenToSettle(page, screenId);
    const selector = `[data-lite-screen-id="${screenId}"]`;
    await expect(page.locator(selector)).toBeVisible();
    await expectNoBlockingAxeViolations(page, selector);
  });
}

test('mobile Manage overlay remains accessible at 200 percent text', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?screen=security');
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
  await waitForLiteScreenToSettle(page, 'security');
  await page.getByRole('button', { name: /Manage Security details/i }).click();

  const dialog = page.locator('[role="dialog"]:visible').first();
  await expect(dialog).toBeVisible();
  await expectNoBlockingAxeViolations(page, '[role="dialog"]');

  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();
  if (box) {
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(391);
  }
});

test('scoped Manage contrast pilot enables color-contrast without changing the global Axe gate', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await page.getByRole('button', { name: 'Workspace details' }).click();
  const dialog = page.locator('[role="dialog"]:visible').first();
  await expect(dialog).toBeVisible();

  const contrast = await new AxeBuilder({ page })
    .include('[role="dialog"]')
    .withRules(['color-contrast'])
    .analyze();
  expect(contrast.violations, JSON.stringify(contrast.violations, null, 2)).toEqual([]);
});
