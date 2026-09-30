import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function expectNoBlockingAxeViolations(page, selector) {
  const result = await new AxeBuilder({ page })
    .include(selector)
    .disableRules(['color-contrast'])
    .analyze();
  const blocking = result.violations.filter((item) => (
    ['serious', 'critical'].includes(item.impact || '')
  ));
  expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
}

async function openPhotoBackup(page) {
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
  const manage = page.getByRole('button', { name: /Manage Test-Phone-4/i });
  await expect(manage).toBeVisible();
  await manage.click();
  const details = page.locator('.lite-device-details-panel');
  await expect(details).toBeVisible();
  const backup = details.getByRole('region', { name: 'Photo backup' });
  await expect(backup).toBeVisible();
  return backup;
}

test.describe('Phase 1 Photo Backup mocked UX', () => {
  test('ready device starts a semantic photo backup request', async ({ page }) => {
    await installScenario(page, 'photo-backup-ready');
    const backup = await openPhotoBackup(page);
    const requestPromise = page.waitForRequest((request) => (
      request.method() === 'POST'
      && /\/api\/lite\/devices\/test-phone-4\/photo-backup$/.test(new URL(request.url()).pathname)
    ));
    await backup.getByRole('button', { name: 'Back up photos' }).click();
    const request = await requestPromise;
    expect(await request.postDataJSON()).toEqual({
      collections: ['camera', 'pictures', 'videos'],
    });
    await expect(backup).toContainText(/Ready|Photo backup queued/i);
  });

  test('running backup shows truthful progress and Stop backup', async ({ page }) => {
    await installScenario(page, 'photo-backup-running');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText('42%');
    await expect(backup).toContainText(/17 backed up/i);
    await expect(backup.getByRole('button', { name: 'Stop backup' })).toBeEnabled();
  });

  test('partial backup explains protected reserve and exposes Retry', async ({ page }) => {
    await installScenario(page, 'photo-backup-partial');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/protected Server Phone reserve/i);
    await expect(backup).toContainText(/10%/i);
    await expect(backup).toContainText(/4\.1 GB|4\.4 GB|GB/i);
    await expect(backup.getByRole('button', { name: 'Retry' })).toBeEnabled();
    await expect(backup).toContainText(/PhotoPrism is processing/i);
  });

  test('missing photo permission stays blocked without hiding enrollment state', async ({ page }) => {
    await installScenario(page, 'photo-backup-permission-missing');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/Allow photo access/i);
    await expect(backup.getByRole('button', { name: 'Back up photos' })).toBeDisabled();
  });

  test('interrupted backup is retryable and does not claim completion', async ({ page }) => {
    await installScenario(page, 'photo-backup-interrupted');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/interrupted/i);
    await expect(backup.getByRole('button', { name: 'Retry' })).toBeEnabled();
    await expect(backup).not.toContainText(/Transfer complete/i);
  });

  test('empty readable library is a successful no-op', async ({ page }) => {
    await installScenario(page, 'photo-backup-empty');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/Nothing new to back up/i);
    await expect(backup).not.toContainText(/Allow photo access/i);
  });

  test('completed and cancelled states remain truthful', async ({ page }) => {
    await installScenario(page, 'photo-backup-completed');
    let backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/Photos are backed up/i);
    await expect(backup).toContainText(/PhotoPrism is processing/i);

    await installScenario(page, 'photo-backup-cancelled');
    await page.reload();
    await waitForLiteScreenToSettle(page, 'devices');
    const manage = page.getByRole('button', { name: /Manage Test-Phone-4/i });
    await manage.click();
    backup = page.locator('.lite-device-details-panel').getByRole('region', { name: 'Photo backup' });
    await expect(backup).toContainText(/backup stopped/i);
    await expect(backup.getByRole('button', { name: 'Retry' })).toBeEnabled();
  });

  test('not-ready reasons stay distinct and actionable', async ({ page }) => {
    const cases = [
      ['photo-backup-remote-unavailable', /Remote access not ready/i],
      ['photo-backup-photoprism-unavailable', /PhotoPrism is not ready/i],
      ['photo-backup-source-offline', /device is offline/i],
    ];
    for (const [scenario, expected] of cases) {
      await installScenario(page, scenario);
      await page.goto('/?screen=devices');
      await waitForLiteScreenToSettle(page, 'devices');
      const manage = page.getByRole('button', { name: /Manage Test-Phone-4/i });
      await manage.click();
      const backup = page.locator('.lite-device-details-panel').getByRole('region', { name: 'Photo backup' });
      await expect(backup).toContainText(expected);
      await expect(backup.getByRole('button', { name: 'Back up photos' })).toBeDisabled();
    }
  });

  test('tool-not-ready exposes only the backend-owned repair action', async ({ page }) => {
    await installScenario(page, 'photo-backup-tool-not-ready');
    const backup = await openPhotoBackup(page);
    await expect(backup.getByRole('button', { name: 'Repair photo backup' })).toBeEnabled();
    await expect(backup.getByRole('button', { name: 'Back up photos' })).toBeDisabled();
  });

  test('partial state has no serious or critical accessibility violations', async ({ page }) => {
    await installScenario(page, 'photo-backup-partial');
    await openPhotoBackup(page);
    await expectNoBlockingAxeViolations(page, '.lite-device-photo-backup');
  });

  test('malformed photo-backup status never blanks Devices or invents a permission failure', async ({ page }) => {
    await installScenario(page, 'photo-backup-ready');
    await page.route('**/api/lite/devices/test-phone-4/photo-backup', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'unknown', sanitized: true }),
      });
    });
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/Needs attention|checking photo backup readiness/i);
    await expect(backup).not.toContainText(/Allow photo access/i);
    await expect(page.locator('[data-lite-screen-id="devices"]')).toBeVisible();
  });

  test('PhotoPrism Manage shows lightweight backup truth and sends control to Devices', async ({ page }) => {
    await installScenario(page, 'catalog-ready');
    await page.goto('/?screen=catalog');
    await waitForLiteScreenToSettle(page, 'catalog');
    const manage = page.getByRole('button', { name: 'Manage', exact: true }).first();
    await expect(manage).toBeEnabled();
    await manage.click();
    const dialog = page.getByRole('dialog', { name: /Manage PhotoPrism/i });
    await expect(dialog).toBeVisible();
    const truth = dialog.getByRole('region', { name: 'Photo backup' });
    await expect(truth).toBeVisible();
    await expect(truth).toContainText(/Managed by Pocket Lab/i);
    await expect(truth).toContainText(/Open a device in Devices/i);
    await expect(truth).not.toContainText(/password|token|credential|WebDAV URL/i);
  });
});
