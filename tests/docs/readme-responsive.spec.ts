import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Static authored-SVG regression only. GitHub-render validation is a
// separate deferred manual qualification, including both GitHub themes.
const artwork = {
  desktop: readFileSync(resolve('docs/assets/brand/readme-hero-desktop.svg'), 'utf8'),
  mobile: readFileSync(resolve('docs/assets/brand/readme-hero-mobile.svg'), 'utf8'),
  architecture: readFileSync(resolve('docs/assets/diagrams/readme-control-flow.svg'), 'utf8'),
};
const toData = (svg: string) => 'data:image/svg+xml;base64,' + Buffer.from(svg).toString('base64');

for (const width of [320, 375, 430, 768, 1024, 1440, 1920]) {
  test('README image layout stays inside viewport: ' + width, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const mobile = toData(artwork.mobile);
    const desktop = toData(artwork.desktop);
    const architecture = toData(artwork.architecture);
    await page.setContent(
      '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width, initial-scale=1">' +
      '<style>*{box-sizing:border-box}body{margin:0}main{width:100%;max-width:1200px;margin:auto;padding:12px}' +
      'picture,img{display:block;max-width:100%;height:auto;margin:12px auto}</style></head><body><main>' +
      '<picture><source media="(max-width: 640px)" srcset="' + mobile + '">' +
      '<img src="' + desktop + '" alt="Pocket Lab Lite illustrated control plane"></picture>' +
      '<img src="' + architecture + '" alt="Pocket Lab Lite control architecture"></main></body></html>',
    );
    await expect(page.locator('img')).toHaveCount(2);
    for (const image of await page.locator('img').all()) {
      await expect(image).toBeVisible();
      expect(await image.evaluate((e: HTMLImageElement) => e.naturalWidth)).toBeGreaterThan(0);
      expect(await image.evaluate((e: HTMLImageElement) => e.getBoundingClientRect().right)).toBeLessThanOrEqual(width);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    expect(await page.locator('picture img').evaluate((e: HTMLImageElement) => e.currentSrc))
      .toBe(width <= 640 ? mobile : desktop);
  });
}
