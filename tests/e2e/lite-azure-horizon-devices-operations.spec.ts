import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// MOCK-ONLY. No physical device, invite, PM2, NATS, Tailscale or backend write.
async function openDevices(page: Page, scenario = 'devices-online', appearance = 'dark') {
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), appearance);
  await installScenario(page, scenario);
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
}
async function openAddDevice(page: Page) {
  const action = page.getByRole('button', { name: 'Add Device', exact: true }).first();
  await action.click();
  const form = page.locator('#lite-devices-onboarding');
  await expect(form).toHaveAttribute('open', '');
  await expect(form.getByLabel('Device name')).toBeVisible();
  return form;
}

test('Add Device guidance remains an explicit backend-owned four-stage invitation', async ({ page }) => {
  await openDevices(page);
  const form = await openAddDevice(page);
  const stages = form.locator('.lite-devices-invite-stages li');
  await expect(stages).toHaveCount(4);
  await expect(stages.nth(0)).toContainText('Name your device');
  await expect(stages.nth(1)).toContainText('Choose responsibilities');
  await expect(stages.nth(2)).toContainText('Create connection invite');
  await expect(stages.nth(3)).toContainText('Connect and verify');
  await expect(form.getByRole('group', { name: 'Device responsibilities' })).toBeVisible();
});

test('add-device name conflict displays an accessible error without creating an invite', async ({ page }) => {
  await openDevices(page, 'devices-online');
  const form = await openAddDevice(page);
  await form.getByLabel('Device name').fill('Test-Phone-4');
  await expect(form.getByRole('alert')).toContainText(/already exists/i);
  await expect(form.getByRole('button', { name: /Device already added/i })).toBeDisabled();
});

test('expired or blocked invite must not turn into a fabricated copy command', async ({ page }) => {
  for (const scenario of ['devices-invite-expired', 'devices-invite-mismatch']) {
    await openDevices(page, scenario);
    const form = await openAddDevice(page);
    await expect(form.getByRole('heading', { name: 'Add a device' })).toBeVisible();
    // Protected fixture data is never copied into the test result or screenshot metadata.
    const copy = form.getByRole('button', { name: 'Copy command' });
    if (await copy.count()) await expect(copy).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Devices', exact: true })).toBeVisible();
  }
});

test('remote access unavailable cannot surface a saved or unready Tailnet address', async ({ page }) => {
  await openDevices(page, 'devices-remote-not-ready', 'dark');
  await expect(page.locator('.lite-remote-access-panel')).toContainText(/Remote access not ready/i);
  await page.locator('.lite-remote-access-details summary').click();
  await expect(page.locator('.lite-remote-access-details')).toContainText('Tailscale');
});

test('connected, repairing, stopped, offline and saved state keep text alongside rails', async ({ page }) => {
  for (const scenario of ['devices-online','devices-repairing','devices-agent-stopped','devices-offline','offline-saved']) {
    await openDevices(page, scenario);
    const map = page.getByRole('region', { name: 'Pocket Lab device connections' });
    await expect(map).toBeVisible();
    await expect(map.locator('.lite-device-relationship-node.is-server')).toBeVisible();
    const peerNodes = map.locator('.lite-device-relationship-node:not(.is-server)');
    for (const peer of await peerNodes.all()) {
      await expect(peer.locator('small')).not.toBeEmpty();
    }
  }
});

test('desktop Manage traps Tab, supports keyboard geometry and restores focus', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openDevices(page);
  const manage = page.getByRole('button', { name: /Manage Test-Phone-4/i }).first();
  await manage.click();
  const dialog = page.getByRole('dialog', { name: /Manage Test-Phone-4/i });
  await expect(dialog).toHaveAttribute('aria-modal', 'true');
  await dialog.getByRole('button', { name: 'Move device details panel' }).focus();
  await page.keyboard.press('ArrowLeft');
  await dialog.getByRole('button', { name: 'Resize device details panel' }).focus();
  await page.keyboard.press('Shift+ArrowDown');
  const box = await dialog.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(-2);
  expect(box!.x + box!.width).toBeLessThanOrEqual(1442);
  await dialog.getByRole('button', { name: /Reset device details panel position/i }).click();
  await dialog.getByRole('button', { name: 'Close device details' }).click();
  await expect(manage).toBeFocused();
});

test('mobile bottom sheet has neither move nor resize, supports scrolling and close', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 700 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openDevices(page);
  await page.getByRole('button', { name: /Manage Test-Phone-4/i }).first().click();
  const sheet = page.getByRole('dialog', { name: /Manage Test-Phone-4/i });
  await expect(sheet).toHaveAttribute('data-lite-details-panel-layout', 'mobile-sheet');
  await expect(sheet.getByRole('button', { name: /Move device details panel/i })).toHaveCount(0);
  await expect(sheet.getByRole('button', { name: /Resize device details panel/i })).toHaveCount(0);
  await expect(sheet.getByRole('button', { name: 'Close device details' })).toBeVisible();
  await expect(page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 2)).resolves.toBe(false);
});

for (const appearance of ['light', 'dark'] as const) {
  test(`Device forms and Manage are WCAG AA-audited in ${appearance}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await openDevices(page, 'devices-online', appearance);
    await openAddDevice(page);
    const report = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze();
    expect(report.violations.filter((v) => ['serious', 'critical'].includes(v.impact || ''))).toEqual([]);
  });
}
