import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Implementation-only coverage. No screenshots, baseline updates or executions in this PR.
async function openPhotos(page: Page, scenario = 'catalog-ready') {
  await installScenario(page, scenario);
  await page.goto('/?screen=catalog');
  await waitForLiteScreenToSettle(page, 'catalog');
  await page.getByRole('button', { name: 'Manage', exact: true }).first().click();
  const manage = page.getByRole('dialog', { name: /Manage PhotoPrism/i });
  await expect(manage).toBeVisible();
  const photos = manage.getByRole('tab', { name: 'Photos' });
  if (await photos.count()) await photos.click();
  return manage;
}

test.describe('Premium Apps — shared Details, Photos and backup', () => {
  test('keeps Details in the shared overlay without dismissing Manage on Escape', async ({ page }) => {
    const manage = await openPhotos(page);
    const flow = manage.getByRole('region', { name: 'Photo workflow' });
    await expect(flow).toBeVisible();
    await flow.getByRole('button', { name: 'View details' }).click();
    const details = page.getByRole('dialog', { name: /Import photos/i });
    await expect(details).toBeVisible();
    await expect(details.locator('.lite-app-premium-details')).toHaveCount(1);
    await expect(details).toContainText(/What happened|What changed/i);
    const technical = details.getByRole('button', { name: /Technical details/i });
    if (await technical.count()) await expect(technical).toHaveAttribute('aria-expanded', 'false');
    await page.keyboard.press('Escape');
    await expect(details).toHaveCount(0);
    await expect(manage).toBeVisible();
  });

  test('preserves compact connected-folder disclosure and a truthful three-step path', async ({ page }) => {
    const manage = await openPhotos(page);
    const flow = manage.locator('.lite-catalog-premium-flow-steps');
    await expect(flow.locator('li')).toHaveCount(3);
    await expect(flow).toContainText('Phone');
    await expect(flow).toContainText('Transfer');
    await expect(flow).toContainText('PhotoPrism');
    const backup = manage.getByRole('region', { name: 'Photo backup' });
    await expect(backup).toContainText('Protected WebDAV destination');
    await expect(backup.getByText('How photo backup works')).toBeVisible();
    await expect(backup.getByRole('button', { name: 'Review in Devices' })).toBeVisible();
    const folders = manage.getByRole('region', { name: 'Connected phone storage' });
    if (await folders.count()) {
      await expect(folders).toContainText('Read-only');
      const disclosure = folders.locator('details');
      if (await disclosure.count()) {
        await expect(disclosure).not.toHaveAttribute('open');
        await disclosure.locator('summary').click();
        await expect(disclosure).toHaveAttribute('open');
      }
    }
  });

  test('does not represent a connected folder as a completed import', async ({ page }) => {
    const manage = await openPhotos(page, 'app-media-not-ready');
    const flow = manage.getByRole('region', { name: 'Photo workflow' });
    await expect(flow).not.toContainText('Transfer complete');
    await expect(flow).not.toContainText('Photos backed up');
  });

  test('routes device-owned photo backup management to Devices', async ({ page }) => {
    const manage = await openPhotos(page);
    await manage.getByRole('region', { name: 'Photo backup' })
      .getByRole('button', { name: 'Review in Devices' }).click();
    await expect(page.locator('[data-lite-screen-id="devices"]')).toBeVisible();
  });

  test('keeps unavailable action reasons visible or expandable', async ({ page }) => {
    const manage = await openPhotos(page, 'app-media-not-ready');
    const importRow = manage.locator('[data-action-id="import_photos"]');
    if (await importRow.count()) {
      await expect(importRow).toContainText(/not ready|unavailable|connected|import/i);
      await expect(importRow.getByRole('button', { name: /details/i })).toBeVisible();
    }
  });

  for (const width of [320, 375, 390, 768]) {
    test(`Apps Manage fits ${width}px without clipping flow icons or action controls`, async ({ page }) => {
      await page.setViewportSize({ width, height: 760 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      const manage = await openPhotos(page);
      const flow = manage.locator('.lite-catalog-premium-flow-steps');
      await expect(flow.locator('li')).toHaveCount(3);
      const positions = await flow.locator('.lite-catalog-premium-flow-icon').evaluateAll((icons) =>
        icons.map((icon) => {
          const box = icon.getBoundingClientRect();
          return { y: box.top, x: box.left, right: box.right };
        }));
      expect(Math.max(...positions.map((item) => item.y)) - Math.min(...positions.map((item) => item.y))).toBeLessThanOrEqual(2);
      for (const position of positions) {
        expect(position.x).toBeGreaterThanOrEqual(0);
        expect(position.right).toBeLessThanOrEqual(width + 1);
      }
      const bounds = await manage.boundingBox();
      expect(bounds).not.toBeNull();
      if (bounds) {
        expect(bounds.x).toBeGreaterThanOrEqual(-1);
        expect(bounds.x + bounds.width).toBeLessThanOrEqual(width + 1);
      }
    });
  }

  test('200 percent text reflow keeps focused Details and controls scrollable', async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 700 });
    const manage = await openPhotos(page);
    await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
    await manage.getByRole('region', { name: 'Photo workflow' })
      .getByRole('button', { name: 'View details' }).click();
    const details = page.getByRole('dialog', { name: /Import photos/i });
    await expect(details).toBeVisible();
    const rect = await details.boundingBox();
    if (rect) {
      expect(rect.x).toBeGreaterThanOrEqual(-1);
      expect(rect.x + rect.width).toBeLessThanOrEqual(321);
    }
    await expect(details.getByRole('button', { name: /Close app actions/i })).toBeVisible();
  });

  test('reduced-motion flow is static outside reported execution', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const manage = await openPhotos(page);
    const stage = manage.locator('.lite-catalog-premium-flow');
    await expect(stage).toBeVisible();
    const animation = await stage.evaluate((element) => getComputedStyle(element).animationName);
    expect(animation).toBe('none');
  });
});
