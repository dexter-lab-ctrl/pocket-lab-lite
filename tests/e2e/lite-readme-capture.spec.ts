import { test } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// No captures are run by merely importing this file. Explicit opt-in
// and mocked-backend qualification are required. Output stays local.
const captureEnabled = process.env.POCKETLAB_README_CAPTURE === '1'
  && process.env.VITE_POCKETLAB_MOCKS === '1'
  && process.env.LITE_E2E_MODE === 'mocked';

const views = [
  ['home', 'home'],
  ['devices', 'devices'],
  ['apps', 'catalog'],
  ['safety', 'security'],
  ['recovery', 'recovery'],
] as const;

for (const [name, screen] of views) {
  for (const width of [390, 1440]) {
    test('README mocked capture ' + name + ' at ' + width, async ({ page }) => {
      test.skip(!captureEnabled, 'Explicit mocked-only README screenshot capture is not enabled');
      await page.setViewportSize({ width, height: width < 500 ? 844 : 960 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.addInitScript(() => localStorage.setItem('pocketlab:appearance', 'dark'));
      await installScenario(page, 'healthy');
      await page.goto('/?screen=' + screen);
      await waitForLiteScreenToSettle(page, screen);
      const out = resolve('.pocketlab-dev/readme-captures');
      mkdirSync(out, { recursive: true });
      await page.screenshot({
        path: resolve(out, 'readme-' + name + '-' + width + '-MOCKED.png'),
        animations: 'disabled',
        fullPage: true,
      });
    });
  }
}
