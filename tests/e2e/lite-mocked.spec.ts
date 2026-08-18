import { expect, test } from '@playwright/test';
import { installScenario, LITE_TABS, openTab, watchApiFailures } from './lite-test-helpers';

test.describe('Pocket Lab Lite mocked contract path', () => {
  test.beforeEach(async ({ page }) => {
    await installScenario(page, 'healthy');
  });

  test('renders every Lite tab through API helpers and TanStack Query', async ({ page }) => {
    const failed = watchApiFailures(page);
    await page.goto('/?screen=home');
    await expect(page.getByText('Pocket Lab Lite').first()).toBeVisible();

    for (const [label, screenId] of LITE_TABS) {
      await openTab(page, label, screenId);
      await expect(page.locator(`[data-lite-screen-id="${screenId}"]`)).toBeVisible();
    }

    expect(failed, `unexpected Lite API failures: ${failed.join(', ')}`).toEqual([]);
  });

  test('Recovery projection-too-old response stays truthful', async ({ page }) => {
    await installScenario(page, 'recovery-projection-too-old');
    await page.goto('/?screen=recovery');
    await expect(page.locator('[data-lite-screen-id="recovery"]')).toBeVisible();
    await expect(page.locator('[data-lite-screen-id="recovery"]')).toContainText(/saved|stale|projection|recovery/i);
  });

  test('Security app profile is shown separately from overall posture', async ({ page }) => {
    await installScenario(page, 'security-app-check-healthy');
    await page.goto('/?screen=security');
    await expect(page.locator('[data-lite-screen-id="security"]')).toBeVisible();
    await expect(page.locator('[data-lite-screen-id="security"]')).toContainText(/Safety|Security/i);
  });

  test('Identity and Rules remain separate truthful security surfaces', async ({ page }) => {
    await page.goto('/?screen=identity');
    const identity = page.locator('[data-lite-screen-id="identity"]');
    await expect(identity).toBeVisible();
    await expect(identity).toContainText('Identity & Access');
    await expect(identity).toContainText(/owner|session|recovery/i);
    await expect(identity).not.toContainText('local-admin');

    await page.goto('/?screen=rules');
    const rules = page.locator('[data-lite-screen-id="rules"]');
    await expect(rules).toBeVisible();
    await expect(rules).toContainText('Safety Rules');
    await expect(rules).toContainText('Open Policy Agent');
    await expect(rules).toContainText('mock-policy-revision');
    await expect(rules).not.toContainText('package pocketlab');
  });

});
