import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORED / NOT EXECUTED. Mocked fixture only. Never submit protected mutations.
async function openAccess(page: Page, scenario = 'identity-summary', theme: 'light' | 'dark' | 'system' = 'light') {
  await page.addInitScript((choice) => localStorage.setItem('pocketlab:appearance', choice), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=identity');
  await waitForLiteScreenToSettle(page, 'identity');
}
async function manage(page: Page, scenario = 'identity-summary') {
  await openAccess(page, scenario);
  await page.getByRole('button', { name: 'Manage Access' }).click();
  const dialog = page.getByRole('dialog', { name: /Manage access/i });
  await expect(dialog).toBeVisible();
  return dialog;
}

test.describe('Azure Horizon native Access P1–P6 — authored, NOT RUN', () => {
  test('one identity hero, native protection rows and truthful empty activity', async ({ page }) => {
    await openAccess(page);
    await expect(page.getByRole('heading', { name: 'Access', level: 1 })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Access profile' })).toBeVisible();
    for (const label of ['Passkeys', 'Sessions', 'Account recovery']) {
      await expect(page.locator('.lite-access-settings-row').filter({ hasText: label })).toHaveCount(1);
    }
    await expect(page.locator('.lite-id-primary-grid')).toHaveCount(0);
    await expect(page.locator('.lite-id-journey')).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Manage Access' })).toHaveCount(1);
  });

  test('mobile index, focused section, Back, Close and focus return are independent', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const dialog = await manage(page, 'identity-premium-multiple');
    await expect(dialog.locator('[data-access-manage-view="index"]')).toBeVisible();
    await dialog.getByRole('button', { name: 'Passkeys', exact: true }).click();
    await expect(dialog.locator('[data-access-manage-view="section"]')).toBeVisible();
    await expect(dialog.getByRole('button', { name: /All access settings/i })).toBeVisible();
    await dialog.getByRole('button', { name: /All access settings/i }).click();
    await expect(dialog.locator('[data-access-manage-view="index"]')).toBeVisible();
    await dialog.getByRole('button', { name: 'Sessions', exact: true }).click();
    await page.keyboard.press('Escape');
    await expect(dialog.locator('[data-access-manage-view="index"]')).toBeVisible();
    await dialog.getByRole('button', { name: /Close identity access/i }).click();
    await expect(dialog).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Manage Access' })).toBeFocused();
  });

  test('nested detail and protected confirmation keep independent overlay stacks', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const dialog = await manage(page, 'identity-premium-multiple');
    await dialog.getByRole('button', { name: 'Sessions', exact: true }).click();
    await dialog.getByRole('button', { name: /^Other session/i }).first().click();
    const detail = page.getByRole('dialog', { name: /Access Details/i });
    await expect(detail).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await expect(detail.getByRole('button', { name: /Back to Manage Access/i })).toBeVisible();
    await detail.getByRole('button', { name: 'Sign out session' }).click();
    const confirmation = page.getByRole('dialog', { name: /Sign out this session/i });
    await expect(confirmation).toBeVisible();
    await expect(confirmation).not.toHaveAttribute('data-lite-sheet-snap', /compact|medium|expanded/);
    await page.keyboard.press('Escape');
    await expect(confirmation).toHaveCount(0);
    await expect(dialog).toBeVisible();
  });

  test('snapping operates only via the grip and never auto-confirms', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    const dialog = await manage(page);
    const grip = dialog.getByRole('button', { name: /Resize sheet, currently/i });
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await grip.focus();
    await page.keyboard.press('End');
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'expanded');
    await page.keyboard.press('Home');
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'compact');
    await page.keyboard.press('ArrowUp');
    await expect(dialog).toHaveAttribute('data-lite-sheet-snap', 'medium');
    await expect(dialog).toBeVisible();
  });

  test('desktop Move / Reset / Resize and panel-container responsive collapse', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    const dialog = await manage(page);
    const move = dialog.getByRole('button', { name: /Move access panel/i });
    const resize = dialog.getByRole('button', { name: /Resize access panel/i });
    await expect(move).toBeVisible();
    await expect(resize).toBeVisible();
    await expect(dialog.locator('.lite-id-native-index')).toBeVisible();
    await expect(dialog.locator('.lite-id-native-detail')).toBeVisible();
    await resize.focus();
    for (let i = 0; i < 8; i += 1) await page.keyboard.press('ArrowLeft');
    await expect(dialog.getByRole('button', { name: /Close identity access/i })).toBeVisible();
    await dialog.getByRole('button', { name: /Reset access panel/i }).click();
  });

  for (const width of [320, 360, 390, 430, 768, 1024, 1440]) {
    test('viewport ' + width + 'px: no page overflow and reachable controls', async ({ page }) => {
      await page.setViewportSize({ width, height: 850 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      const dialog = await manage(page, 'identity-premium-long-text');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
      await expect(dialog.getByRole('button', { name: /Close identity access/i })).toBeVisible();
    });
  }

  for (const role of ['owner','admin','operator','auditor','viewer']) {
    test('Enterprise ' + role + ' presentation retains backend-controlled operations', async ({ page }) => {
      const dialog = await manage(page, 'identity-enterprise-' + role);
      await dialog.getByRole('button', { name: 'Roles & Access' }).click();
      await expect(dialog).toContainText(/Effective capability matrix/i);
      await expect(dialog).toContainText(new RegExp(role, 'i'));
    });
  }

  test('Personal Mode hides Enterprise people administration', async ({ page }) => {
    const dialog = await manage(page);
    await expect(dialog.getByRole('button', { name: 'People & roles' })).toHaveCount(0);
  });

  test('saved Access information cannot register a passkey', async ({ page }) => {
    const dialog = await manage(page, 'identity-owner-operation-offline');
    await dialog.getByRole('button', { name: 'Passkeys' }).click();
    await expect(dialog.getByRole('button', { name: /Add Passkey/i })).toBeDisabled();
  });

  test('accessibility, 200% text zoom, reduced motion and sheet scroll containment', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const dialog = await manage(page, 'identity-premium-long-text');
    await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
    await expect(dialog).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    const results = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
    expect(results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual([]);
  });
});

// Cross-theme comparison operates on the same fixture and viewport, not a color-based layout override.
test('Daylight vs Dark geometry parity candidate — NOT RUN', async ({ page }) => {
  const collect = async (theme: 'light' | 'dark') => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openAccess(page, 'identity-premium-multiple', theme);
    const selectors = ['.lite-access-hero','.lite-access-settings-card','.lite-access-settings-row',
      '.lite-access-activity-card','.lite-access-section > h2','.lite-access-hero-action .pocket-button'];
    const result: Record<string, {x:number;y:number;width:number;height:number}|null> = {};
    for (const selector of selectors) {
      const box = await page.locator(selector).first().boundingBox();
      result[selector] = box ? { x:box.x, y:box.y, width:box.width, height:box.height } : null;
    }
    return result;
  };
  const light = await collect('light');
  const dark = await collect('dark');
  for (const selector of Object.keys(light)) {
    expect(light[selector]).not.toBeNull();
    for (const measure of ['x','y','width','height'] as const) {
      expect(Math.abs((light[selector]?.[measure] || 0) - (dark[selector]?.[measure] || 0)),
        selector + ':' + measure).toBeLessThanOrEqual(2);
    }
  }
});
