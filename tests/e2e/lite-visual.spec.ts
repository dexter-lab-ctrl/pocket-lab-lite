import { expect, test } from '@playwright/test';
import { installScenario, LITE_TABS, openTab, waitForLiteScreenToSettle } from './lite-test-helpers';

async function normalizeTransientChrome(page) {
  const sheet = page.locator('.mobile-more-sheet');
  const backdrop = page.locator('.mobile-more-backdrop');

  // Escape safely closes modal/navigation state where supported.
  await page.keyboard.press('Escape');

  if (await sheet.count()) {
    const isOpen = await sheet.evaluate((element) =>
      element.classList.contains('mobile-more-sheet-open') ||
      element.getAttribute('aria-hidden') === 'false'
    );

    if (isOpen) {
      const close = sheet.getByRole('button', { name: 'Close navigation' });
      if (await close.isVisible()) {
        await close.click();
      }
    }

    await expect(sheet).toHaveAttribute('aria-hidden', 'true');
    await expect(sheet).not.toHaveClass(/mobile-more-sheet-open/);
    await expect(sheet).toHaveCSS('visibility', 'hidden');
  }

  await expect(backdrop).toHaveCount(0);

  // Let React layout and any CSS transition bookkeeping settle.
  await page.evaluate(() => new Promise((resolve) =>
    requestAnimationFrame(() => requestAnimationFrame(resolve))
  ));
}

test('canonical Lite tab screenshots remain stable', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?screen=home');

  for (const [label, screenId] of LITE_TABS) {
    // Canonical visual baselines must exclude transient navigation overlays.
    await normalizeTransientChrome(page);
    await openTab(page, label, screenId);
    await waitForLiteScreenToSettle(page, screenId);
    await normalizeTransientChrome(page);
    await waitForLiteScreenToSettle(page, screenId);

    await expect(page.locator(`[data-lite-screen-id="${screenId}"]`)).toHaveScreenshot(`${screenId}.png`, {
      animations: 'disabled',
      caret: 'hide',
      maxDiffPixelRatio: 0.02,
    });
  }
});
