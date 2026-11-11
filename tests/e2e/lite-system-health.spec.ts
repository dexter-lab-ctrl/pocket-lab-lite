import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// Mock-only qualification source. Not executed in this implementation PR.
test('System Health has an accessible summary and native Manage on both layouts', async ({ page }) => {
  await installScenario(page, 'system-health-attention');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  const screen = page.locator('[data-lite-screen-id="system-health"]');
  await expect(screen.getByRole('heading', { name: 'System Health', exact: true })).toBeVisible();
  await expect(screen.getByRole('heading', { name: 'Active Problems' })).toBeVisible();
  await screen.getByRole('button', { name: /Manage System Health/i }).click();
  const dialog = page.getByRole('dialog', { name: /System Health Manage/i });
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveAttribute('aria-modal', 'true');
  const report = await new AxeBuilder({ page }).include('[data-system-health-page="true"]').analyze();
  expect(report.violations.filter(v => ['critical', 'serious'].includes(v.impact || ''))).toEqual([]);
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
});

test('stale data is never represented as healthy or repairable', async ({ page }) => {
  await installScenario(page, 'system-health-stale');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  const screen = page.locator('[data-system-health-page="true"]');
  await expect(screen.getByText(/saved information/i).first()).toBeVisible();
  await expect(screen.getByText(/No problems observed/i)).toHaveCount(0);
});

test('contextual Device entry opens the canonical System Health workspace', async ({ page }) => {
  await installScenario(page, 'devices-online');
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
  await page.getByRole('button', { name: 'Diagnose device health' }).click();
  await expect(page.locator('[data-lite-screen-id="system-health"]')).toBeVisible();
});

test('deep-linked incident opens diagnosis without initiating repair', async ({ page }) => {
  await installScenario(page, 'system-health-attention');
  const seenWrites: string[] = [];
  page.on('request', request => {
    if (request.method() === 'POST' && request.url().includes('/system-health/') && request.url().includes('/repair')) seenWrites.push(request.url());
  });
  await page.goto('/?screen=system-health&incident=health-111111111111111111111111');
  const dialog = page.getByRole('dialog', { name: /System Health Manage/i });
  await expect(dialog).toBeVisible();
  await expect(dialog.getByText(/repair executor is qualified/i)).toBeVisible();
  expect(seenWrites).toEqual([]);
});
