import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Source authored, NOT EXECUTED. No native baseline screenshots generated.
for (const theme of ['light', 'dark'] as const) {
  for (const width of [320, 360, 390, 430, 768] as const) {
    test('native dock at viewport bottom without transparent bleed: ' + theme + ' / ' + width, async ({ page }) => {
      await page.setViewportSize({ width, height: 844 });
      await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), theme);
      await installScenario(page, 'security-quick-healthy');
      await page.goto('/?screen=security');
      await waitForLiteScreenToSettle(page, 'security');
      const dock = page.locator('body > nav.pocket-nav-dock');
      await expect(dock).toBeVisible();
      const geometry = await dock.evaluate((node) => {
        const box = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        const main = document.querySelector('.pocket-main');
        const mainStyle = main ? getComputedStyle(main) : null;
        return {
          bottom: box.bottom, left: box.left, right: box.right, width: box.width,
          height: box.height, viewportHeight: innerHeight, viewportWidth: innerWidth,
          bottomInset: style.bottom, position: style.position,
          background: style.backgroundColor, scrollClearance: parseFloat(mainStyle?.paddingBottom || '0'),
        };
      });
      expect(geometry.position).toBe('fixed');
      expect(Math.abs(geometry.viewportHeight - geometry.bottom)).toBeLessThanOrEqual(2);
      expect(geometry.left).toBeGreaterThanOrEqual(-1);
      expect(geometry.right).toBeLessThanOrEqual(geometry.viewportWidth + 1);
      expect(geometry.scrollClearance).toBeGreaterThan(geometry.height);
      expect(geometry.background).toMatch(/^rgb\\(/);
      await expect(dock.locator('.pocket-nav-button[aria-current="page"]')).toHaveCount(1);
    });
  }
}
test('dock gains an elevated edge when the page is scrolled and remains visible', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installScenario(page, 'security-quick-healthy');
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
  const dock = page.locator('body > nav.pocket-nav-dock');
  await page.evaluate(() => window.scrollTo(0, 400));
  await expect(dock).toHaveAttribute('data-lite-scroll-elevated', 'true');
  await expect(dock).toBeInViewport();
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect(dock).toHaveAttribute('data-lite-scroll-elevated', 'false');
});
test('global feedback applies to active mobile navigation when vibration is supported', async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__liteVibrations = [];
    Object.defineProperty(navigator, 'vibrate', {
      configurable: true, value: (pattern: unknown) => { (window as any).__liteVibrations.push(pattern); return true; },
    });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await installScenario(page, 'security-quick-healthy');
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
  await page.getByRole('navigation', { name: 'Pocket Lab sections' }).getByRole('button', { name: 'Devices' }).click();
  // Desktop emulation may report fine pointer. Dispatch a keyboard activation to
  // assert the shared fallback independently of the test runner's device profile.
  await page.evaluate(() => document.querySelector('.pocket-nav-dock .pocket-nav-button')
    ?.dispatchEvent(new MouseEvent('click', { bubbles: true, detail: 0 })));
  const calls = await page.evaluate(() => (window as any).__liteVibrations);
  expect(calls).toContain(8);
});
