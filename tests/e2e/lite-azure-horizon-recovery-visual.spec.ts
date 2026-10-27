import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Canonical synthetic Recovery baselines captured and reviewed during stabilization.
// Screenshots contain MSW state only; they are not evidence of a production restore.
for (const theme of ['light', 'dark', 'system'] as const) {
  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1440]) {
    test(`Recovery Azure overview: ${theme} ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: width < 701 ? 844 : 900 });
      await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'recovery-verified');
      await page.goto('/?screen=recovery');
      await waitForLiteScreenToSettle(page, 'recovery');
      await expect(page.locator('.lite-recovery-premium-screen')).toHaveScreenshot(
        `recovery-${theme}-overview-${width}.png`, { animations: 'disabled' },
      );
    });
  }
  for (const scenario of [
    'recovery-no-backups', 'recovery-unverified', 'recovery-preview-ready',
    'recovery-repository-unavailable', 'recovery-projection-too-old',
    'recovery-backup-running', 'recovery-restore-running', 'recovery-rollback-completed',
  ]) {
    test(`Recovery Azure state: ${theme} ${scenario}`, async ({ page }) => {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, scenario);
      await page.goto('/?screen=recovery');
      await waitForLiteScreenToSettle(page, 'recovery');
      if (scenario === 'recovery-rollback-completed') {
        await expect(page.getByText('Rollback completed from the pre-restore checkpoint.', { exact: true }).first()).toBeVisible();
      }
      await expect(page.locator('.lite-recovery-premium-screen')).toHaveScreenshot(
        `recovery-${theme}-${scenario}.png`, { animations: 'disabled' },
      );
    });
  }
  for (const width of [390, 768, 1280]) {
    for (const section of ['Backup', 'Restore', 'Protection', 'History'] as const) {
      test(`Recovery Manage: ${theme} ${width}px ${section}`, async ({ page }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
        await installScenario(page, 'recovery-preview-ready');
        await page.goto('/?screen=recovery');
        await waitForLiteScreenToSettle(page, 'recovery');
        await page.getByRole('button', { name: 'Manage Recovery' }).click();
        const panel = page.getByRole('dialog', { name: /Manage backups and recovery/i });
        await panel.getByRole('tab', { name: section }).click();
        if (section === 'History') {
          await expect(panel.locator('.lite-recovery-history-card')).toBeVisible();
          await expect(panel.locator('.lite-recovery-history-loading')).toHaveCount(0);
        }
        await expect(panel).toHaveScreenshot(
          `recovery-${theme}-manage-${width}-${section.toLowerCase()}.png`, { animations: 'disabled' },
        );
      });
    }
  }
}
for (const theme of ['light', 'dark', 'system'] as const) {
  test(`Recovery database rollback details: ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
    await installScenario(page, 'recovery-rollback-completed');
    await page.goto('/?screen=recovery');
    await waitForLiteScreenToSettle(page, 'recovery');
    await page.getByRole('button', { name: 'Manage Recovery' }).click();
    const manage = page.getByRole('dialog', { name: /Manage backups and recovery/i });
    await manage.getByRole('tab', { name: 'Protection' }).click();
    await manage.getByRole('button', { name: 'Protection details' }).click();
    const database = page.getByRole('dialog', { name: /Pocket Lab data protection/i });
    const progress = database.locator('[aria-label="Database recovery progress"]');
    await expect(progress).toBeVisible();
    await progress.scrollIntoViewIfNeeded();
    await expect(progress.getByText('Rolled back — restore not committed', { exact: true })).toBeVisible();
    await expect(progress.getByText('Checkpoint saved', { exact: true })).toBeVisible();
    await expect(progress).toHaveScreenshot(`recovery-${theme}-database-rollback.png`, { animations: 'disabled' });
  });
}
// DEFINED — BASELINE CAPTURE AND APPROVAL DEFERRED. Do not auto-approve.
for (const theme of ['light', 'dark'] as const) {
  test(`Recovery blocked prerequisite guidance visual candidate: ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
    await installScenario(page, 'recovery-restore-blocked');
    await page.goto('/?screen=recovery');
    await waitForLiteScreenToSettle(page, 'recovery');
    await page.getByRole('button', { name: 'Manage Recovery' }).click();
    const panel = page.getByRole('dialog', { name: /Manage backups and recovery/i });
    await panel.getByRole('tab', { name: 'Restore' }).click();
    await expect(panel.locator('.lite-recovery-action-disabled-reason')).toBeVisible();
    await expect(panel).toHaveScreenshot(`recovery-${theme}-mobile-blocked-prerequisites-candidate.png`, { animations: 'disabled' });
  });
}
test('Recovery protected confirmation visual — synthetic preview, no restore dispatched', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await installScenario(page, 'recovery-preview-ready');
  await page.goto('/?screen=recovery');
  await waitForLiteScreenToSettle(page, 'recovery');
  await page.getByRole('button', { name: 'Manage Recovery' }).click();
  const panel = page.getByRole('dialog', { name: /Manage backups and recovery/i });
  await panel.getByRole('tab', { name: 'Restore' }).click();
  const button = panel.locator('.lite-recovery-manage-action-row').filter({ hasText: 'Restore selected backup' })
    .getByRole('button', { name: 'Restore', exact: true });
  await expect(button).toBeEnabled();
  await button.click();
  const confirmation = page.getByRole('dialog', { name: 'Restore backup' });
  await expect(confirmation).toHaveScreenshot('recovery-protected-confirmation.png', { animations: 'disabled' });
  await confirmation.getByRole('button', { name: 'Cancel' }).click();
});
test('Recovery desktop shared geometry visual after move and resize', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await installScenario(page, 'recovery-preview-ready');
  await page.goto('/?screen=recovery');
  await waitForLiteScreenToSettle(page, 'recovery');
  await page.getByRole('button', { name: 'Manage Recovery' }).click();
  const panel = page.getByRole('dialog', { name: /Manage backups and recovery/i });
  const move = panel.getByRole('button', { name: 'Move Recovery panel' });
  await move.focus(); await page.keyboard.press('ArrowLeft');
  const resize = panel.getByRole('button', { name: 'Resize Recovery panel' });
  await resize.focus(); await page.keyboard.press('ArrowDown');
  await expect(panel).toHaveScreenshot('recovery-desktop-moved-resized.png', { animations: 'disabled' });
});
test('Recovery 200% mobile long-content presentation reference', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 844 });
  await installScenario(page, 'recovery-restore-blocked');
  await page.goto('/?screen=recovery');
  await waitForLiteScreenToSettle(page, 'recovery');
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
  await expect(page.locator('.lite-recovery-premium-screen')).toHaveScreenshot('recovery-320-zoom200.png', { animations: 'disabled' });
});
