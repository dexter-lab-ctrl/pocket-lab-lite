// AUTHORED — NOT RUN · implementation-only session. Synthetic MSW only; never operate on live Recovery.
import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function openRecovery(page: import('@playwright/test').Page, scenario: string, theme: string) {
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=recovery');
  await waitForLiteScreenToSettle(page, 'recovery');
}

for (const theme of ['light', 'dark', 'system']) {
  test(`Recovery Center calm overview and guarded actions — ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openRecovery(page, 'recovery-verified', theme);
    await expect(page.getByRole('heading', { name: 'Recovery Center' })).toBeVisible();
    await expect(page.locator('[data-recovery-readiness="compact"]')).toBeVisible();
    await expect(page.locator('[data-recovery-activity="compact"]')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Back Up Now' })).toBeVisible();
    const dimensions = await page.evaluate(() => ({ width: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.width + 1);
    await page.getByRole('button', { name: 'Manage Recovery' }).click();
    const panel = page.getByRole('dialog', { name: /Manage backups and recovery/i });
    await expect(panel).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await panel.getByRole('button', { name: 'Expand', exact: true }).click();
    await expect(panel).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await panel.getByRole('button', { name: 'Compact', exact: true }).click();
    await expect(panel).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await panel.getByRole('button', { name: /Resize sheet/i }).focus();
    await page.keyboard.press('End');
    await expect(panel).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await page.keyboard.press('Escape');
    await expect(panel).toHaveCount(0);
  });

  test(`Recovery Restore Assistant cannot dispatch by navigation — ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    let restorePosts = 0;
    page.on('request', (request) => {
      if (request.method() === 'POST' && /\/api\/lite\/recovery\/restore$/.test(new URL(request.url()).pathname)) restorePosts += 1;
    });
    await openRecovery(page, 'recovery-unverified', theme);
    await page.getByRole('button', { name: 'Manage Recovery' }).click();
    const panel = page.getByRole('dialog', { name: /Manage backups and recovery/i });
    await panel.getByRole('tab', { name: 'Restore' }).click();
    await expect(panel.locator('[data-recovery-assistant="presentation-only"]')).toBeVisible();
    await panel.getByRole('button', { name: /Step 3: Review safety checks/ }).click();
    await panel.getByRole('button', { name: /Step 4: Confirm and restore/ }).click();
    await expect(panel.locator('.lite-recovery-manage-action-row').filter({ hasText: 'Restore selected backup' })
      .getByRole('button', { name: 'Restore', exact: true })).toBeDisabled();
    expect(restorePosts).toBe(0);
  });
}

for (const width of [320, 360, 375, 390, 430, 768, 1024, 1280, 1440]) {
  test(`Recovery Center responsive typography and horizontal overflow — ${width}`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await openRecovery(page, 'recovery-verified', 'light');
    const box = await page.locator('.lite-recovery-center-hero').boundingBox();
    expect(box).not.toBeNull();
    const horizontal = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(horizontal).toBeLessThanOrEqual(1);
    await page.getByRole('button', { name: 'Manage Recovery' }).click();
    const dialog = page.getByRole('dialog', { name: /Manage backups and recovery/i });
    await dialog.getByRole('tab', { name: 'Restore' }).click();
    const titles = await dialog.locator('.lite-recovery-assistant-steps button').count();
    expect(titles).toBe(4);
  });
}

test('Recovery Center text scaling and desktop Move/Resize/Reset remain accessible', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openRecovery(page, 'recovery-preview-ready', 'dark');
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
  await page.getByRole('button', { name: 'Manage Recovery' }).click();
  const dialog = page.getByRole('dialog', { name: /Manage backups and recovery/i });
  const move = dialog.getByRole('button', { name: 'Move Recovery panel' });
  await move.focus();
  await page.keyboard.press('ArrowLeft');
  const resize = dialog.getByRole('button', { name: 'Resize Recovery panel' });
  await resize.focus();
  await page.keyboard.press('ArrowDown');
  await dialog.getByRole('button', { name: /Reset Recovery panel/ }).click();
  await expect(dialog).toBeVisible();
});

test('Recovery Center theme parity authoring: geometry is not theme-dependent', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await openRecovery(page, 'recovery-verified', 'light');
  const measure = async () => page.locator('.lite-recovery-center-hero').evaluate((el) => {
    const rect = el.getBoundingClientRect(), style = getComputedStyle(el);
    return { width: Math.round(rect.width), height: Math.round(rect.height), padding: style.padding, radius: style.borderRadius };
  });
  const light = await measure();
  await page.evaluate(() => localStorage.setItem('pocketlab:appearance', 'dark'));
  await page.reload();
  await waitForLiteScreenToSettle(page, 'recovery');
  const dark = await measure();
  expect(dark).toEqual(light);
  // Contrast, axe and visual snapshots must be qualified later — not run here.
});

test('Recovery Centre authored source contract: no destructive restore on readiness selection', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await openRecovery(page, 'recovery-preview-ready', 'light');
  let restorePosts = 0;
  page.on('request', request => {
    if (request.method() === 'POST' && /\/api\/lite\/recovery\/restore$/.test(new URL(request.url()).pathname)) restorePosts += 1;
  });
  await page.locator('.lite-recovery-readiness-steps button').first().click();
  await expect(page.getByRole('dialog', { name: /Back Up readiness/i })).toBeVisible();
  await page.getByRole('dialog', { name: /Back Up readiness/i }).getByRole('button', { name: /Close security details/i }).click();
  expect(restorePosts).toBe(0);
});
