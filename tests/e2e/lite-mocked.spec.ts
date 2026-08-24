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

  test('Identity and Rules remain separate truthful Lite-friendly security surfaces', async ({ page }) => {
    await page.goto('/?screen=identity');
    const identity = page.locator('[data-lite-screen-id="identity"]');
    await expect(identity).toBeVisible();
    await expect(identity).toContainText('Identity & Access');
    await expect(identity).toContainText('Access posture');
    await expect(identity).toContainText('Passkeys');
    await expect(identity).toContainText('Sessions');
    await expect(identity).toContainText('Recovery');
    await expect(identity).toContainText(/fixed idle and absolute expiry/i);
    await expect(identity).not.toContainText('local-admin');

    await page.goto('/?screen=rules');
    const rules = page.locator('[data-lite-screen-id="rules"]');
    await expect(rules).toBeVisible();
    await expect(rules).toContainText('Safety Rules');
    await expect(rules).toContainText('Protections active');
    await expect(rules).toContainText('Sensitive changes stay deliberate');
    await expect(rules).toContainText(/Passkey when needed/i);
    await expect(rules).not.toContainText('Open Policy Agent');
    await expect(rules).not.toContainText('Rego');
    await expect(rules).not.toContainText('package pocketlab');
  });

  test('Enterprise Rules simulation, approvals and exception UX remain bounded', async ({ page }) => {
    await page.goto('/?screen=rules');
    const rules = page.locator('[data-lite-screen-id="rules"]');
    await expect(rules.getByRole('heading', { name: 'Rules governance', exact: true })).toBeVisible();

    await rules.getByRole('button', { name: 'Simulate' }).click();
    await expect(rules.getByText('This does not execute the action', { exact: true })).toBeVisible();
    await expect(rules.getByLabel('Simulation context')).toBeVisible();
    await rules.getByLabel('Target reference').fill('mock-app');
    await rules.getByRole('button', { name: 'Run simulation' }).click();
    await expect(rules).toContainText(/Allowed in this simulation|Blocked in this simulation|Passkey confirmation required/i);
    await rules.getByLabel('Simulation context').selectOption('synthetic');
    await expect(rules.getByText('Supported hypothetical facts')).toBeVisible();
    await expect(rules.getByText('Recent passkey assurance')).toBeVisible();

    await rules.getByRole('button', { name: 'Decisions' }).click();
    await expect(rules.getByRole('heading', { name: 'Decision explorer', exact: true })).toBeVisible();
    await expect(rules).not.toContainText('raw policy input');

    await rules.getByRole('button', { name: 'Approvals' }).click();
    await expect(rules.getByRole('heading', { name: 'Device removal approvals', exact: true })).toBeVisible();
    await expect(rules).toContainText(/exact-target|exact-Rules-revision/i);
    await expect(rules).not.toContainText('Requesting identity ID');

    await rules.getByRole('button', { name: 'Exceptions' }).click();
    await expect(rules.getByRole('heading', { name: 'Temporary exceptions', exact: true })).toBeVisible();
    await expect(rules).toContainText(/Expires automatically|Read-only exception view/i);
    await expect(rules).not.toContainText('Human ID');

    await rules.getByRole('button', { name: 'Health' }).click();
    await expect(rules.getByRole('heading', { name: 'Rules health', exact: true })).toBeVisible();
    await expect(rules).toContainText(/Not all conflicts are analyzable by this model|Advanced analysis is not available to this role/i);
    await expect(rules).not.toContainText('package pocketlab');
  });
});
