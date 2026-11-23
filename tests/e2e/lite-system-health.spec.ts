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
  await expect(screen.getByRole('heading', { name: 'What needs attention' })).toBeVisible();
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
  await expect(screen.getByText(/No current concerns observed/i)).toHaveCount(0);
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
  await expect(dialog.getByText(/No repair executor is enabled/i)).toBeVisible();
  expect(seenWrites).toEqual([]);
});

test('Home exposes a compact System Health summary with direct navigation', async ({ page }) => {
  await installScenario(page, 'system-health-attention');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await expect(page.getByRole('heading', { name: 'System Health' })).toBeVisible();
  await page.getByRole('button', { name: 'Open System Health' }).click();
  await expect(page.locator('[data-lite-screen-id="system-health"]')).toBeVisible();
});


// H5 qualification definitions — mocked only, NOT EXECUTED in the H0–H6 implementation.
test('current and saved concerns have distinct grouping without raw IDs', async ({ page }) => {
  await installScenario(page, 'system-health-mixed');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  const screen = page.locator('[data-system-health-page="true"]');
  await expect(screen.locator('[data-health-concern="current"]')).toHaveCount(1);
  await expect(screen.locator('[data-health-saved-preview="true"]')).toBeVisible();
  await expect(screen).not.toContainText('runtime.consumer.reconnect');
  await screen.getByRole('button', { name: 'Manage System Health' }).click();
  const panel = page.getByRole('dialog', { name: /System Health Manage/i });
  await panel.getByRole('button', { name: 'Problems & Diagnosis' }).click();
  await expect(panel.getByRole('heading', { name: 'Current confirmed concerns' })).toBeVisible();
  await expect(panel.getByRole('heading', { name: 'Saved concerns requiring revalidation' })).toBeVisible();
  await expect(panel.getByText('Recheck needed').first()).toBeVisible();
});

test('review issue discloses a cause narrative without enabling repair', async ({ page }) => {
  await installScenario(page, 'system-health-attention');
  const repairWrites: string[] = [];
  page.on('request', request => {
    if (request.method() === 'POST' && /\/system-health\/.*\/repair(?:\?|$)/.test(request.url())) repairWrites.push(request.url());
  });
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  await page.getByRole('button', { name: 'Review issue' }).first().click();
  const panel = page.getByRole('dialog', { name: /System Health Manage/i });
  await expect(panel.getByRole('heading', { name: 'What happened' })).toBeVisible();
  await expect(panel.getByRole('heading', { name: 'Cause assessment' })).toBeVisible();
  await expect(panel.getByRole('button', { name: 'Fix', exact: true })).toHaveCount(0);
  await panel.getByText('Advanced technical details').click();
  await expect(panel.getByText('Incident ID')).toBeVisible();
  expect(repairWrites).toEqual([]);
});

test('previous unresolved evidence stays unconfirmed in saved-only scenario', async ({ page }) => {
  await installScenario(page, 'system-health-saved-only');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  const screen = page.locator('[data-system-health-page="true"]');
  await expect(screen.locator('[data-health-overview="unknown"]')).toBeVisible();
  await expect(screen.locator('[data-health-saved-preview="true"]')).toBeVisible();
  await expect(screen.locator('[data-health-concern="current"]')).toHaveCount(0);
  await expect(screen.getByRole('button', { name: /Diagnose & Fix/i })).toHaveCount(0);
});

test('missing or malformed target identity does not appear as a raw path', async ({ page }) => {
  await installScenario(page, 'system-health-malformed-target');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  await expect(page.locator('[data-system-health-page="true"]')).not.toContainText('../../unsafe');
});

test('System Health Manage supports keyboard entry and Escape dismissal', async ({ page }) => {
  await installScenario(page, 'system-health-attention');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  const trigger = page.getByRole('button', { name: 'Manage System Health' });
  await trigger.focus();
  await page.keyboard.press('Enter');
  const panel = page.getByRole('dialog', { name: /System Health Manage/i });
  await expect(panel).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(panel).not.toBeVisible();
});

for (const width of [320, 360, 390, 430, 768, 1024, 1280, 1440]) {
  test(`System Health at ${width}px has no horizontal overflow or clipped Manage access`, async ({ page }) => {
    await page.setViewportSize({ width, height: 850 });
    await installScenario(page, 'system-health-mixed');
    await page.goto('/?screen=system-health');
    await waitForLiteScreenToSettle(page, 'system-health');
    await expect(page.getByRole('button', { name: 'Manage System Health' })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(overflow).toBe(false);
    await page.getByRole('button', { name: 'Manage System Health' }).click();
    await expect(page.getByRole('dialog', { name: /System Health Manage/i })).toBeVisible();
  });
}

test('reduced-motion and accessible detail disclosure remain usable', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await installScenario(page, 'system-health-attention');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  await page.getByRole('button', { name: 'Review issue' }).first().click();
  const panel = page.getByRole('dialog', { name: /System Health Manage/i });
  const report = await new AxeBuilder({ page }).include('[data-system-health-page="true"]').analyze();
  expect(report.violations.filter(v => ['critical', 'serious'].includes(v.impact || ''))).toEqual([]);
  await expect(panel).toBeVisible();
});

test('Manage itself passes serious/critical Axe checks including portal content', async ({ page }) => {
  await installScenario(page, 'system-health-mixed');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  await page.getByRole('button', { name: 'Manage System Health' }).click();
  const panel = page.getByRole('dialog', { name: /System Health Manage/i });
  await expect(panel).toBeVisible();
  const report = await new AxeBuilder({ page }).include('[role="dialog"]').analyze();
  expect(report.violations.filter(v => ['critical', 'serious'].includes(v.impact || ''))).toEqual([]);
});

test('System Health haptic uses shared native feedback and respects reduced motion', async ({ page }) => {
  await page.addInitScript(() => {
    (window as Window & { __hapticCount?: number }).__hapticCount = 0;
    Object.defineProperty(navigator, 'vibrate', {
      configurable: true,
      value: () => {
        (window as Window & { __hapticCount?: number }).__hapticCount! += 1;
        return true;
      },
    });
  });
  await installScenario(page, 'system-health-attention');
  await page.goto('/?screen=system-health');
  await waitForLiteScreenToSettle(page, 'system-health');
  await page.getByRole('button', { name: 'Manage System Health' }).click();
  expect(await page.evaluate(() => (window as Window & { __hapticCount?: number }).__hapticCount)).toBeGreaterThan(0);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const before = await page.evaluate(() => (window as Window & { __hapticCount?: number }).__hapticCount);
  await page.getByRole('button', { name: 'Close', exact: false }).first().click();
  expect(await page.evaluate(() => (window as Window & { __hapticCount?: number }).__hapticCount)).toBe(before);
});
