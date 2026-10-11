import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function expectNoBlockingAxeViolations(page, selector) {
  const result = await new AxeBuilder({ page })
    .include(selector)
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
    await expect(backup).toContainText(/Server Phone destination/i);
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
    await installScenario(page, 'photo-backup-malformed');
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


test.describe('P3 Photo Backup readiness and recovery presentation', () => {
  test('separates current readiness from latest historical failure', async ({ page }) => {
    await installScenario(page, 'photo-backup-interrupted');
    const backup = await openPhotoBackup(page);
    await expect(backup.getByRole('group', { name: 'Current backup readiness' })).toBeVisible();
    await expect(backup.getByRole('group', { name: 'Latest backup details' })).toBeVisible();
    await expect(backup).toContainText(/Latest backup outcome/i);
    await expect(backup.getByRole('button', { name: 'Retry' })).toBeEnabled();
  });

  test('shows protected storage reserve as separate hard and planning budgets', async ({ page }) => {
    await installScenario(page, 'photo-backup-partial');
    const backup = await openPhotoBackup(page);
    const destination = backup.getByRole('group', { name: 'Server Phone destination storage' });
    await expect(destination).toContainText(/Hard reserve/i);
    await expect(destination).toContainText(/Planning reserve/i);
    await expect(destination).toContainText(/Safe upload budget/i);
    await expect(destination).toContainText(/15%|2 GiB/i);
  });

  test('shows accessible semantic progress and selection controls', async ({ page }) => {
    await installScenario(page, 'photo-backup-running');
    const backup = await openPhotoBackup(page);
    await expect(backup.getByRole('progressbar', { name: 'Photo backup progress' })).toBeVisible();
    await expect(backup.getByRole('group', { name: 'Photo backup actions' })).toBeVisible();
    await expect(backup.getByRole('group', { name: 'Photo collections' })).toBeVisible();
    await expectNoBlockingAxeViolations(page, '.lite-device-photo-backup');
  });

  test('source failure offers recovery without falsely calling previous backup current', async ({ page }) => {
    await installScenario(page, 'photo-backup-source-offline');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/Reconnect this device/i);
    await expect(backup.getByRole('button', { name: 'Back up photos' })).toBeDisabled();
    await expect(backup.getByRole('button', { name: 'Check status' })).toBeEnabled();
  });

  test('malformed status remains recoverable and never enables an unsafe start', async ({ page }) => {
    await installScenario(page, 'photo-backup-malformed');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/Status unavailable|Current readiness could not be confirmed|Needs attention/i);
    await expect(backup.getByRole('button', { name: 'Back up photos' })).toBeDisabled();
    await expect(backup.getByRole('button', { name: 'Check status' })).toBeEnabled();
    await expect(page.locator('[data-lite-screen-id="devices"]')).toBeVisible();
  });

  test('photo backup UI remains available at mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installScenario(page, 'photo-backup-partial');
    const backup = await openPhotoBackup(page);
    await expect(backup.getByRole('group', { name: 'Current backup readiness' })).toBeVisible();
    await expect(backup.getByRole('button', { name: 'Retry' })).toBeVisible();
    await expect(backup.getByRole('button', { name: 'Check status' })).toBeVisible();
  });

  test('stale active progress stays stoppable but does not claim a live percentage', async ({ page }) => {
    await installScenario(page, 'photo-backup-progress-stale');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/fresh transfer progress is unavailable/i);
    await expect(backup).toContainText(/do not treat this as completion/i);
    await expect(backup.getByRole('button', { name: 'Stop backup' })).toBeEnabled();
    await expect(backup.getByRole('progressbar', { name: 'Photo backup progress' })).toHaveCount(0);
  });

  test('unknown destination capacity never fabricates zero bytes or enables start', async ({ page }) => {
    await installScenario(page, 'photo-backup-storage-unknown');
    const backup = await openPhotoBackup(page);
    const destination = backup.getByRole('group', { name: 'Server Phone destination storage' });
    await expect(destination).toContainText(/capacity could not be verified/i);
    await expect(destination).not.toContainText('0 B');
    await expect(backup.getByRole('button', { name: 'Back up photos' })).toBeDisabled();
  });

  test('destination identity mismatch remains fail-closed and actionable', async ({ page }) => {
    await installScenario(page, 'photo-backup-destination-mismatch');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/Destination storage changed/i);
    await expect(backup.getByRole('button', { name: 'Back up photos' })).toBeDisabled();
  });

  test('saved snapshot is visible but cannot authorize a new backup', async ({ page }) => {
    await installScenario(page, 'photo-backup-saved');
    const backup = await openPhotoBackup(page);
    await expect(backup).toContainText(/cached or degraded snapshot/i);
    await expect(backup).toContainText(/refresh to confirm current readiness/i);
    await expect(backup.getByRole('button', { name: 'Back up photos' })).toBeDisabled();
  });

  test('action failures show reason guidance without upstream details', async ({ page }) => {
    await installScenario(page, 'photo-backup-action-failure');
    const backup = await openPhotoBackup(page);
    await backup.getByRole('button', { name: 'Back up photos' }).click();
    const alert = backup.getByRole('alert').last();
    await expect(alert).toContainText(/destination checksum did not match/i);
    await expect(alert).not.toContainText(/credential=secret|upstream detail/i);
  });

  test('partial state has a reviewed visual regression snapshot', async ({ page }) => {
    await installScenario(page, 'photo-backup-partial');
    const backup = await openPhotoBackup(page);
    await expect(backup).toHaveScreenshot('photo-backup-partial.png', { animations: 'disabled' });
  });
});
