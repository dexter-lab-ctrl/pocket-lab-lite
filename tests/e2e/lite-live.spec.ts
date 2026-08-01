import { expect, test } from '@playwright/test';
import { LITE_TABS, openTab, watchApiFailures } from './lite-test-helpers';

test.describe('Pocket Lab Lite live read-only smoke', () => {
  test.skip(process.env.LITE_E2E_LIVE !== '1', 'Set LITE_E2E_LIVE=1 after starting Caddy, FastAPI, SQLite, NATS/JetStream, worker, and PWA.');

  test('Caddy and FastAPI render every current Lite tab without write actions', async ({ page }) => {
    const failed = watchApiFailures(page);
    const statusResponse = page.waitForResponse((response) => response.url().includes('/api/lite/status'));
    await page.goto('/?screen=home');
    const response = await statusResponse;
    expect(response.ok()).toBeTruthy();
    const payload = await response.json();
    expect(payload).toHaveProperty('overall');

    for (const [label, screenId] of LITE_TABS) {
      await openTab(page, label, screenId);
    }
    expect(failed, `unexpected live Lite API failures: ${failed.join(', ')}`).toEqual([]);
  });
});
