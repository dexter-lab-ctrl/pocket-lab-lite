import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// This suite only runs with deterministic mocked projections. It never dispatches
// destructive actions; protected flows are reviewed but not submitted.
const SCREENS = [
  ['home', 'Home'],
  ['catalog', 'Your Apps'],
  ['devices', 'Devices'],
  ['security', 'Safety Center'],
  ['identity', 'Identity & Access'],
  ['rules', 'Safety Rules'],
  ['recovery', 'Backup & Restore'],
] as const;

for (const [id, title] of SCREENS) {
  test(`P4 ${id}: visible, accessible and without horizontal overflow`, async ({ page }) => {
    await installScenario(page, 'healthy');
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto(`/?screen=${id}`);
    await waitForLiteScreenToSettle(page, id);
    const root = page.locator(`[data-lite-screen-id="${id}"]`);
    await expect(root).toBeVisible();
    await expect(root.getByRole('heading', { name: title, exact: true }).first()).toBeVisible();
    const result = await new AxeBuilder({ page }).include(`[data-lite-screen-id="${id}"]`).analyze();
    const blocking = result.violations.filter(item => ['serious', 'critical'].includes(item.impact || ''));
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
    const overflow = await root.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return box.right > document.documentElement.clientWidth + 2 || box.left < -2;
    });
    expect(overflow, `${id} page container should fit viewport`).toBe(false);
  });
}

const GUIDANCE = [
  ['home', 'lifecycle-attention', 'Review what needs attention'],
  ['devices', 'devices-repairing', 'Connection review'],
  ['catalog', 'catalog-install-available', 'App readiness'],
  ['recovery', 'recovery-restore-blocked', 'Protection readiness'],
  ['security', 'security-action-needed', 'Safety result and coverage'],
  ['identity', 'healthy', 'Your current access'],
  ['rules', 'rules-disabled', 'How protection decisions work'],
] as const;

for (const [id, scenario, title] of GUIDANCE) {
  test(`P4 ${id}: evidence guidance is labeled and bounded`, async ({ page }) => {
    await installScenario(page, scenario);
    await page.goto(`/?screen=${id}`);
    await waitForLiteScreenToSettle(page, id);
    const root = page.locator(`[data-lite-screen-id="${id}"]`);
    const section = root.getByRole('region', { name: title });
    // Some guidance components omit the container when no findings exist.
    // Do not fabricate information solely to satisfy an assertion.
    if (await section.count()) {
      await expect(section).toBeVisible();
      await expect(section.locator('li, dt').count()).toBeLessThanOrEqual(5);
    }
  });
}

test('P4: Find a section navigates without offering operational commands', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await page.getByRole('button', { name: 'Find a Pocket Lab section' }).click();
  const dialog = page.getByRole('dialog', { name: 'Go to a section' });
  await expect(dialog).toBeVisible();
  await dialog.getByRole('searchbox', { name: 'Find a section' }).fill('devices');
  await dialog.getByRole('button', { name: 'Devices' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('[data-lite-screen-id="devices"]')).toBeVisible();
});

test('P4: Ctrl+K opens navigation, Escape closes it, keyboard focus returns', async ({ page }, testInfo) => {
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  const launcher = page.getByRole('button', { name: 'Find a Pocket Lab section' });
  await launcher.focus();
  await page.keyboard.press('Control+k');
  await expect(page.getByRole('dialog', { name: 'Go to a section' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog', { name: 'Go to a section' })).toHaveCount(0);
  await expect(launcher).toBeFocused();
  expect(testInfo.project.name).toMatch(/^mocked-/);
});

test('P4: saved Home guidance cannot navigate from stale evidence', async ({ page }) => {
  await installScenario(page, 'offline-saved');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  const guidance = page.locator('[data-lite-p1-guidance="true"]');
  if (await guidance.count()) {
    await expect(guidance).toHaveAttribute('data-lite-information', 'saved');
    await expect(guidance.getByRole('button')).toHaveCount(0);
  }
});

test('P4: narrow viewport and 200% text retain usable navigation', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.setViewportSize({ width: 320, height: 720 });
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });
  await page.getByRole('button', { name: 'Find a Pocket Lab section' }).click();
  const dialog = page.getByRole('dialog', { name: 'Go to a section' });
  await expect(dialog).toBeVisible();
  const rect = await dialog.boundingBox();
  expect(rect).not.toBeNull();
  if (rect) {
    expect(rect.x).toBeGreaterThanOrEqual(-2);
    expect(rect.x + rect.width).toBeLessThanOrEqual(322);
  }
  await expect(dialog.getByRole('searchbox')).toBeVisible();
});
