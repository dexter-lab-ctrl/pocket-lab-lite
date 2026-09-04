import { expect, test } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

async function expectInViewport(locator, page) {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  const viewport = page.viewportSize();
  expect(box).not.toBeNull();
  expect(viewport).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(0);
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width + 1);
  expect(box!.y + Math.min(box!.height, viewport!.height)).toBeLessThanOrEqual(viewport!.height + 1);
}

test('Devices progressive connection flow remains visually intentional', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');

  const devices = page.locator('[data-lite-screen-id="devices"]');
  await expect(devices).toHaveScreenshot('devices-progressive-flow.png', {
    animations: 'disabled',
    caret: 'hide',
    maxDiffPixelRatio: 0.02,
  });
});

test('Manage stays in the current viewport and returns focus to its device', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');

  const manage = page.getByRole('button', { name: /^Manage / }).first();
  await manage.scrollIntoViewIfNeeded();
  await manage.click();

  const panel = page.locator('.lite-device-details-focus-anchor');
  await expectInViewport(panel, page);
  await expect(panel).toBeFocused();

  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  await expect(manage).toBeFocused();
});

test('Removal review opens as a contextual sheet and restores the initiating action focus', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });

  await page.route('**/api/lite/devices/*/removal-assessment', async (route) => {
    const match = route.request().url().match(/\/devices\/([^/]+)\/removal-assessment/);
    const nodeId = decodeURIComponent(match?.[1] || 'old-device');
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        node_id: nodeId,
        device_name: 'Old Device',
        allowed: true,
        safe_to_remove: true,
        protected: false,
        policy: 'ready',
        confirmation_required: true,
        assessment_revision: 'visual-assessment-1',
        awareness_revision: 7,
        blockers: [],
        warnings: [{
          code: 'historical_join_blocked',
          summary: 'A previous mismatched join was blocked. The enrolled device record can still be removed after confirmation.',
        }],
        recommended_actions: [],
        staleness_state: 'stale',
      }),
    });
  });

  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');

  await page.locator('.lite-device-card-disclosure').evaluateAll((items) => {
    items.forEach((item) => { (item as HTMLDetailsElement).open = true; });
  });

  const removeAction = page.getByRole('button', { name: /^(Remove device|Review removal)$/ }).first();
  await expect(removeAction).toBeVisible();
  await removeAction.scrollIntoViewIfNeeded();
  await removeAction.click();

  const panel = page.locator('.lite-device-remove-panel');
  await expectInViewport(panel, page);
  await expect(panel).toBeFocused();
  await expect(panel).toHaveAttribute('role', 'region');
  await expect(panel).toHaveAttribute('aria-label', /Remove old device:/);

  await page.getByRole('button', { name: 'Keep device' }).click();
  await expect(panel).toHaveCount(0);
  await expect(removeAction).toBeFocused();
});
