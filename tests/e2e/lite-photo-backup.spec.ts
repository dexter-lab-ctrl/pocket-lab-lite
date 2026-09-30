import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

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
