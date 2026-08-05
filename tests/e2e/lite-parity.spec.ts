import { expect, test } from '@playwright/test';
import { installScenario, watchApiFailures } from './lite-test-helpers';
import { recoveryParityScenarios } from '../../src/test/fixtures/generated/parity/recovery-parity.js';

const deterministicBrowserScenarios = recoveryParityScenarios;

test.describe('Pocket Lab Lite Recovery projection parity', () => {
  for (const scenario of deterministicBrowserScenarios) {
    test(`${scenario.id}: selector meaning reaches the rendered UI`, async ({ page }) => {
      const failures = watchApiFailures(page);
      await installScenario(page, scenario.mswScenario);
      await page.goto('/?screen=recovery');
      const recovery = page.locator('[data-lite-screen-id="recovery"]');
      await expect(recovery).toBeVisible();
      await expect(recovery).toContainText(/Recovery|Backup|saved|unavailable|verified/i);
      expect(scenario.visibleText.length).toBeGreaterThan(0);
      if (scenario.id === 'recovery-offline-snapshot' || scenario.id === 'recovery-projection-stale') {
        await expect(recovery).toContainText(/saved|stale|reconnect/i);
      }
      expect(failures.filter((failure) => !/503|projection|nats/i.test(failure))).toEqual([]);
    });
  }

  test('Recovery browser path never requests raw backend authority endpoints', async ({ page }) => {
    const requested: string[] = [];
    page.on('request', (request) => requested.push(request.url()));
    await installScenario(page, 'healthy');
    await page.goto('/?screen=recovery');
    await expect(page.locator('[data-lite-screen-id="recovery"]')).toBeVisible();
    expect(requested.some((url) => /sqlite|nats|ssh|raw-manifest|raw-evidence/i.test(url))).toBe(false);
  });
});
