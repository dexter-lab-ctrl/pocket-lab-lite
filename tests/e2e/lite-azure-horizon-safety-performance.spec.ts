import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// DEFINED — NOT RUN. PR #588/#589 remain authoritative for budgets and Android attribution.
// Supplemental synthetic browser interaction samples, not proof of 60 FPS or physical performance.
for (const theme of ['light', 'dark'] as const) {
  for (const width of [390, 1280]) {
    test(`Azure Safety supplemental interactions: ${theme}, ${width}px`, async ({ page }, testInfo) => {
      await page.setViewportSize({ width, height: 900 });
      await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'security-quick-healthy');
      const started = performance.now();
      await page.goto('/?screen=security');
      await waitForLiteScreenToSettle(page, 'security');
      const firstPaintMs = performance.now() - started;
      const startManage = performance.now();
      await page.getByRole('button', { name: 'Manage Security details' }).click();
      const panel = page.getByRole('dialog', { name: 'Manage Safety' });
      await expect(panel).toBeVisible();
      const manageOpenMs = performance.now() - startManage;
      const startSwitch = performance.now();
      await panel.getByRole('tab', { name: 'Open Checks in Security Manage' }).click();
      await expect(panel.getByRole('tabpanel', { name: 'Checks' })).toBeVisible();
      await panel.getByRole('tab', { name: 'Open History in Security Manage' }).click();
      await expect(panel.getByRole('tabpanel', { name: 'History' })).toBeVisible();
      const profileAndHistorySwitchMs = performance.now() - startSwitch;
      let geometryMs: number | null = null;
      if (width >= 701) {
        const startGeometry = performance.now();
        await panel.getByRole('button', { name: 'Move Safety panel' }).focus();
        await page.keyboard.press('ArrowLeft');
        await panel.getByRole('button', { name: 'Resize Safety panel' }).focus();
        await page.keyboard.press('ArrowUp');
        geometryMs = performance.now() - startGeometry;
      }
      const samples = { theme, width, firstPaintMs, manageOpenMs, profileAndHistorySwitchMs, geometryMs,
        contract: 'PR #588/#589 performance thresholds preserved; this is supplemental only' };
      expect([firstPaintMs, manageOpenMs, profileAndHistorySwitchMs, geometryMs]
        .filter((value): value is number => value !== null)
        .every((value) => Number.isFinite(value) && value >= 0)).toBe(true);
      await testInfo.attach('azure-safety-synthetic-interaction-timings', {
        body: JSON.stringify(samples, null, 2), contentType: 'application/json',
      });
    });
  }
}
