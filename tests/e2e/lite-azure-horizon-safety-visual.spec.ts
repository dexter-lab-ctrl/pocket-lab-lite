import { expect, test, type Locator, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function waitForSafetyVisualLayout(page: Page) {
  const shell = page.locator('[data-security-phase5-summary-first="true"]');
  await shell.waitFor({ state: 'visible' });
  let previous = '';
  let stableSamples = 0;
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const signature = await shell.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return [
        Math.round(rect.width),
        Math.round(rect.height),
        element.scrollHeight,
        (element.textContent || '').trim().length,
      ].join(':');
    });
    if (signature === previous) {
      stableSamples += 1;
      if (stableSamples >= 8) return;
    } else {
      previous = signature;
      stableSamples = 0;
    }
    await page.waitForTimeout(250);
  }
  throw new Error('Safety visual shell did not reach its final stable layout');
}

// Synthetic visual qualification uses only MSW fixtures. Never trigger a real
// Security scan or backend write from this suite.
async function showSafety(page: Page, theme: 'light'|'dark'|'system', scenario: string, width: number) {
  await page.setViewportSize({ width, height: width < 701 ? 844 : 900 });
  // React Spring is not a CSS animation, so Playwright's screenshot-level
  // animation disabling does not stop the Safety shell from settling while a
  // long mobile element is captured. The visual contract is the reduced-
  // motion end state, which also makes the 320px evidence reproducible.
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript(value => localStorage.setItem('pocketlab:appearance', value), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
  await waitForSafetyVisualLayout(page);
  // The refresh acknowledgement is time-based and can disappear after the
  // geometry has already become stable. Do not let that transient label choose
  // a different glyph-rasterization frame for an otherwise identical image.
  await page.waitForFunction(() => {
    const status = document.querySelector('[data-security-refresh-status="true"]');
    return !status || !/Fresh just now/i.test(status.textContent || '');
  }, undefined, { timeout: 10_000 });
}

async function captureSettledSafetyScreenshot(page: Page, locator: Locator) {
  // PNG encoding metadata can differ between identical Chromium captures, so
  // byte equality is not a useful stability signal. The explicit state wait
  // above is the contract. Prime the tall locator once so its scroll position
  // and text rasterization are established, then retain the second capture.
  await locator.screenshot({ animations: 'disabled', scale: 'css' });
  await page.waitForTimeout(250);
  return locator.screenshot({ animations: 'disabled', scale: 'css' });
}

async function expectSafetyScreenScreenshot(page: Page, snapshotName: string) {
  // The full screen is taller than the mobile viewport. Playwright's locator
  // matcher retries by scrolling it into view, which can move the fixed Lite
  // navigation and leave otherwise identical button glyphs rasterized on a
  // different row. Capture one settled element buffer instead.
  const screenshot = await captureSettledSafetyScreenshot(page, page.locator('[data-lite-screen-id="security"]'));
  // The CSS-scale mobile renderer can move only button glyph antialiasing by
  // one device row between equivalent captures. Keep this allowance below
  // 0.1% and retain strict layout/content comparison for the full screen.
  await expect(screenshot).toMatchSnapshot(snapshotName, { maxDiffPixelRatio: 0.001 });
}

function canonicalSafetyVisualScenario(scenario: string) {
  // These generated fixtures intentionally resolve to the same backend
  // payload. Share one visual contract so equivalent aliases cannot create
  // duplicate baselines with different rasterization frames.
  if (scenario === 'security-urgent' || scenario === 'security-unsupported-app-route') {
    return 'security-action-needed';
  }
  return scenario;
}

for (const theme of ['light', 'dark', 'system'] as const) {
  for (const width of [320, 360, 375, 390, 430, 768, 1024, 1440]) {
    test(`Safety hero and overview: ${theme} / ${width}px`, async ({ page }) => {
      await showSafety(page, theme, 'security-quick-healthy', width);
      // A locator screenshot of this long mobile shell includes the fixed Lite
      // navigation. Playwright's matcher retries locator screenshots by
      // scrolling the tall element, which moves that fixed navigation between
      // samples. Capture once after the explicit layout settle and compare the
      // resulting Playwright buffer so the visual contract remains intact.
      const overviewScreenshot = await captureSettledSafetyScreenshot(page, page.locator('[data-security-phase5-summary-first="true"]'));
      // Mobile Chromium can rasterize a small set of text glyphs differently
      // between otherwise identical captures. Keep the tall overview strict
      // on layout/content while allowing only this bounded 0.1% glyph delta.
      await expect(overviewScreenshot).toMatchSnapshot(`safety-azure-${theme}-overview-${width}.png`, {
        maxDiffPixelRatio: 0.001,
      });
      await expect(page.locator('[data-security-horizon-overview="true"]')).toHaveScreenshot(
        `safety-azure-${theme}-insights-${width}.png`, {
          animations: 'disabled',
          // The compact crop has fewer pixels, so the same mobile-only text
          // rasterization variance needs an explicit absolute ceiling too.
          maxDiffPixels: 500,
          maxDiffPixelRatio: 0.0025,
        });
    });
  }
  for (const scenario of [
    'security-quick-healthy', 'security-action-needed', 'security-urgent',
    'security-first-run', 'security-profile-stale', 'security-scanner-unavailable',
    'security-full-running', 'security-app-check-healthy', 'security-unsupported-app-route',
    'offline-saved',
  ]) {
    test(`Safety backend-state variants: ${theme} / ${scenario}`, async ({ page }) => {
      await showSafety(page, theme, scenario, 1280);
      await expectSafetyScreenScreenshot(
        page,
        `safety-azure-${theme}-state-${canonicalSafetyVisualScenario(scenario)}.png`,
      );
    });
  }
  for (const width of [390, 768, 1280]) {
    for (const section of [
      'Overview', 'Checks', 'Changes', 'Issues', 'Coverage',
      'Check path', 'Evidence', 'History', 'Technical details',
    ]) {
      test(`Safety Manage: ${theme} / ${width}px / ${section}`, async ({ page }) => {
        await showSafety(page, theme, 'security-quick-healthy', width);
        await page.getByRole('button', { name: 'Manage Security details' }).click();
        const dialog = page.getByRole('dialog', { name: 'Manage Safety' });
        await dialog.getByRole('tab', { name: `Open ${section} in Security Manage` }).click();
        await expect(dialog).toHaveScreenshot(
          `safety-azure-${theme}-manage-${width}-${section.toLowerCase().replaceAll(' ', '-')}.png`,
          {
            animations: 'disabled',
            // Keep the Manage surface strict while bounding mobile text
            // rasterization variance to a small, absolute glyph-only delta.
            maxDiffPixels: 250,
            maxDiffPixelRatio: 0.001,
          });
      });
    }
  }
}
test('Safety protected Full Scan confirmation — synthetic only', async ({ page }) => {
  await showSafety(page, 'dark', 'security-quick-healthy', 1280);
  await page.getByRole('button', { name: 'Run Full Scan' }).click();
  const dialog = page.getByRole('dialog', { name: 'Full Local Check' });
  await expect(dialog).toHaveScreenshot('safety-azure-full-confirmation.png', { animations: 'disabled' });
  await dialog.getByRole('button', { name: 'Cancel' }).click();
});
test('Safety protected App Scan confirmation — synthetic only', async ({ page }) => {
  await showSafety(page, 'light', 'security-quick-healthy', 390);
  await page.getByRole('button', { name: 'Run App Scan' }).click();
  const dialog = page.getByRole('dialog', { name: 'Check PhotoPrism' });
  await expect(dialog).toHaveScreenshot('safety-azure-app-confirmation.png', { animations: 'disabled' });
  await dialog.getByRole('button', { name: 'Cancel' }).click();
});
test('desktop shared geometry after keyboard move and resize', async ({ page }) => {
  await showSafety(page, 'dark', 'security-quick-healthy', 1280);
  await page.getByRole('button', { name: 'Manage Security details' }).click();
  const dialog = page.getByRole('dialog', { name: 'Manage Safety' });
  await dialog.getByRole('button', { name: 'Move Safety panel' }).focus();
  await page.keyboard.press('ArrowLeft');
  await dialog.getByRole('button', { name: 'Resize Safety panel' }).focus();
  await page.keyboard.press('ArrowDown');
  await expect(dialog).toHaveScreenshot('safety-azure-desktop-moved-resized.png', { animations: 'disabled' });
});
test('320px with 200% text and reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await showSafety(page, 'dark', 'security-action-needed', 320);
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
  await expectSafetyScreenScreenshot(page, 'safety-azure-320-zoom200-reduced-motion.png');
});
