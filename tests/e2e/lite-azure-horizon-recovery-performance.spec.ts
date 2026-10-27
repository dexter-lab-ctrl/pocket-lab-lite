import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// DEFINED — NOT RUN. Supplemental interaction samples only; PR #588/#589 budgets
// and Android baseline attribution remain the unchanged qualification authority.
for (const appearance of ['light', 'dark'] as const) {
  for (const width of [390, 1280]) {
    test(`Azure Recovery interaction timing: ${appearance} ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), appearance);
      await installScenario(page, 'recovery-preview-ready');
      const clock = () => Date.now();
      const started = clock();
      await page.goto('/?screen=recovery');
      await waitForLiteScreenToSettle(page, 'recovery');
      const firstPaintMs = clock() - started;
      const stageStarted = clock();
      await page.locator('.lite-recovery-premium-stage-grid button').nth(1).click();
      const journeyMs = clock() - stageStarted;
      const openStarted = clock();
      await page.getByRole('button', { name: 'Manage Recovery' }).click();
      const panel = page.getByRole('dialog', { name: /Manage backups and recovery/i });
      await expect(panel).toBeVisible();
      const manageOpenMs = clock() - openStarted;
      const switchStarted = clock();
      await panel.getByRole('tab', { name: 'Restore' }).click();
      await expect(panel.getByRole('tabpanel', { name: 'Restore' })).toBeVisible();
      await panel.getByRole('tab', { name: 'History' }).click();
      await expect(panel.getByRole('tabpanel', { name: 'History' })).toBeVisible();
      const sectionSwitchMs = clock() - switchStarted;
      let keyboardGeometryMs: number | null = null;
      if (width >= 701) {
        const geometryStarted = clock();
        await panel.getByRole('button', { name: 'Move Recovery panel' }).focus();
        await page.keyboard.press('ArrowLeft');
        await panel.getByRole('button', { name: 'Resize Recovery panel' }).focus();
        await page.keyboard.press('ArrowLeft');
        keyboardGeometryMs = clock() - geometryStarted;
      }
      const measurements = { firstPaintMs, journeyMs, manageOpenMs, sectionSwitchMs, keyboardGeometryMs };
      expect(Object.values(measurements).filter((value): value is number => value !== null).every(value => value >= 0 && Number.isFinite(value))).toBe(true);
      await testInfo.attach('azure-recovery-interaction-samples', {
        body: JSON.stringify({ ...measurements, width, appearance, contract: 'PR588-PR589 unchanged; supplemental only' }, null, 2),
        contentType: 'application/json',
      });
    });
  }
}
