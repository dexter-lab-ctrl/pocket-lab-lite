// VERIFIED — mocked desktop/mobile Manage hardening is covered by this suite.
// Device management stays backend-projected and uses the existing mocked fleet.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function openDevices(page: Page, scenario = 'devices-online', appearance = 'light') {
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), appearance);
  await installScenario(page, scenario);
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
}
async function manage(page: Page) {
  await page.getByRole('button', { name: /^Manage / }).first().click();
  const dialog = page.getByRole('dialog', { name: /^Manage / });
  await expect(dialog).toBeVisible();
  return dialog;
}

test.describe('Devices native Manage hardening — verified', () => {
  test('desktop uses persistent navigation and shared geometry controls', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await openDevices(page);
    const panel = await manage(page);
    await expect(panel.getByRole('navigation', { name: 'Device management sections' })).toBeVisible();
    await expect(panel.locator('[data-device-manage-layout="desktop"]')).toBeVisible();
    for (const section of ['Connection', 'Health', 'Services', 'History', 'Technical']) {
      await panel.getByRole('button', { name: section, exact: true }).click();
      await expect(panel.locator('[data-active-device-section="' + section.toLowerCase() + '"]')).toBeVisible();
    }
    await panel.getByRole('button', { name: 'Resize device details panel' }).focus();
    await page.keyboard.press('Shift+ArrowLeft');
    await panel.getByRole('button', { name: /Reset device details panel/ }).click();
    await panel.getByRole('button', { name: 'Close device details' }).click();
    await expect(panel).toHaveCount(0);
  });

  for (const width of [320, 360, 430]) {
    test('mobile index → detail → Back → index → Close at ' + width + 'px', async ({ page }) => {
      await page.setViewportSize({ width, height: 800 });
      await openDevices(page);
      const opener = page.getByRole('button', { name: /^Manage / }).first();
      const panel = await manage(page);
      await expect(panel.locator('[data-manage-view="index"]')).toBeVisible();
      await panel.getByRole('button', { name: 'Health', exact: true }).click();
      await expect(panel.locator('[data-manage-view="detail"]')).toBeVisible();
      await expect(panel.locator('[data-active-device-section="health"]')).toBeVisible();
      await panel.getByRole('button', { name: 'Back to all device settings' }).click();
      await expect(panel.locator('[data-manage-view="index"]')).toBeVisible();
      await panel.getByRole('button', { name: 'Services', exact: true }).click();
      await expect(panel.locator('[data-active-device-section="services"]')).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(panel.locator('[data-manage-view="index"]')).toBeVisible();
      await panel.getByRole('button', { name: 'Close device details' }).click();
      await expect(panel).toHaveCount(0);
      await expect(opener).toBeFocused();
    });
  }

  test('mobile sheet size controls remain independent of navigation', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDevices(page);
    const dialog = await manage(page);
    await dialog.getByRole('button', { name: 'Make device sheet smaller' }).click();
    await expect(dialog.getByText('compact', { exact: true })).toBeVisible();
    await dialog.getByRole('button', { name: 'Expand device sheet' }).click();
    await dialog.getByRole('button', { name: 'Health', exact: true }).click();
    await expect(dialog.locator('[data-active-device-section="health"]')).toBeVisible();
    await dialog.getByRole('button', { name: 'Back to all device settings' }).click();
    await expect(dialog.getByRole('button', { name: 'Connection', exact: true })).toBeVisible();
  });

  test('protected server hides peer-only actions while keeping device facts', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await openDevices(page, 'devices-protected-host');
    const dialog = await manage(page);
    const nav = dialog.getByRole('navigation', { name: 'Device management sections' });
    await expect(nav.getByRole('button', { name: 'Roles', exact: true })).toHaveCount(0);
    await expect(nav.getByRole('button', { name: 'Backup', exact: true })).toHaveCount(0);
    await expect(nav.getByRole('button', { name: 'Overview', exact: true })).toBeVisible();
  });

  test('saved remote-access data never proves current command reachability', async ({ page }) => {
    await openDevices(page, 'offline-saved');
    await page.getByText('Connections & Topology').click();
    await expect(page.getByText('Saved state', { exact: true }).first()).toBeVisible();
    await expect(page.locator('.lite-remote-access-panel code')).toHaveCount(0);
  });

  test('connectivity, recovery and health remain independent projected states', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await openDevices(page, 'devices-repairing');
    const panel = await manage(page);
    await panel.getByRole('button', { name: 'Connection', exact: true }).click();
    await expect(panel.getByText('Supervisor / recovery')).toBeVisible();
    await expect(panel.getByText('Command delivery')).toBeVisible();
    await panel.getByRole('button', { name: 'Health', exact: true }).click();
    await expect(panel.getByText('Recovery', { exact: true }).first()).toBeVisible();
  });

  test('visual semantics, modal focus and readable controls have no serious/critical a11y issues', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDevices(page, 'devices-online');
    const dialog = await manage(page);
    const scan = await new AxeBuilder({ page }).include('[role="dialog"][aria-label^="Manage"]').analyze();
    expect(scan.violations.filter((v) => ['critical', 'serious'].includes(v.impact || ''))).toEqual([]);
    await dialog.getByRole('button', { name: 'Close device details' }).click();
  });
});
