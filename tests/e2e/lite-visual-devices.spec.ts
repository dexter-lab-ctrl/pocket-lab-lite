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

async function expectPortalOwned(locator) {
  const ownership = await locator.evaluate((element) => ({
    inAppShell: Boolean(element.closest('.pocket-app-shell')),
    inScreenStage: Boolean(element.closest('.lite-screen-stage')),
  }));
  expect(ownership.inAppShell).toBe(true);
  expect(ownership.inScreenStage).toBe(false);
}

async function backgroundAlpha(locator) {
  return locator.evaluate((element) => {
    const value = window.getComputedStyle(element).backgroundColor.trim();
    const rgba = value.match(/^rgba\([^,]+,[^,]+,[^,]+,\s*([0-9.]+)\)$/i);
    if (rgba) return Number(rgba[1]);
    if (/^rgb\(/i.test(value)) return 1;
    return 0;
  });
}

async function openFirstRemovalReview(page) {
  await page.locator('.lite-device-card-disclosure').evaluateAll((items) => {
    items.forEach((item) => { (item as HTMLDetailsElement).open = true; });
  });

  const removeAction = page.getByRole('button', { name: /^(Remove device|Review removal)$/ }).first();
  await expect(removeAction).toBeVisible();
  await removeAction.scrollIntoViewIfNeeded();
  await removeAction.click();
  return removeAction;
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

test('Manage stays legible in the current viewport and returns focus to its device', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');

  const manage = page.getByRole('button', { name: /^Manage / }).first();
  await manage.scrollIntoViewIfNeeded();
  await manage.click();

  const panel = page.locator('.lite-device-details-focus-anchor');
  const detailsCard = panel.locator('.lite-device-details-panel');
  const backdrop = page.locator('.lite-device-action-backdrop');
  await expectInViewport(panel, page);
  await expectPortalOwned(panel);
  await expect(panel).toBeFocused();
  await expect(detailsCard).toBeVisible();
  await expect(backdrop).toBeVisible();
  expect(await backgroundAlpha(panel)).toBeGreaterThanOrEqual(0.98);
  expect(await backgroundAlpha(detailsCard)).toBeGreaterThanOrEqual(0.98);
  expect(await backgroundAlpha(backdrop)).toBeGreaterThanOrEqual(0.30);

  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
  await expect(manage).toBeFocused();
});

test('Removal review opens as a contextual sheet and restores the initiating action focus', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });

  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
  const removeAction = await openFirstRemovalReview(page);

  const panel = page.locator('.lite-device-remove-panel');
  await expectInViewport(panel, page);
  await expectPortalOwned(panel);
  await expect(panel).toBeFocused();
  await expect(panel).toHaveAttribute('role', 'region');
  await expect(panel).toHaveAttribute('aria-label', /Remove old device:/);
  await expect(panel).toHaveCSS('overflow-y', 'auto');

  await page.getByRole('button', { name: 'Keep device' }).click();
  await expect(panel).toHaveCount(0);
  await expect(removeAction).toBeFocused();
});

test('Removal review remains scrollable and keeps destructive actions reachable on a short mobile viewport', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mocked-mobile', 'Constrained mobile scroll reachability is qualified once in the mobile project.');
  await installScenario(page, 'healthy');
  await page.emulateMedia({ reducedMotion: 'reduce' });

  // Open a real removable device at the project's normal mobile viewport first.
  // The Devices fleet is virtualized, so shrinking to a very short viewport before
  // selection can legitimately unmount the stale removable card. This regression is
  // specifically about the already-open contextual sheet remaining usable when the
  // viewport becomes constrained (rotation, split-screen, keyboard, small handset).
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
  await openFirstRemovalReview(page);

  const panel = page.locator('.lite-device-remove-panel');
  await expect(panel).toBeVisible();
  await expectPortalOwned(panel);

  await page.setViewportSize({ width: 390, height: 568 });
  await expectInViewport(panel, page);
  await expect(panel).toHaveCSS('overflow-y', 'auto');

  const scrollMetrics = await panel.evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(scrollMetrics.scrollHeight).toBeGreaterThan(scrollMetrics.clientHeight);

  const scrollResult = await panel.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
    return {
      scrollTop: element.scrollTop,
      maxScrollTop: element.scrollHeight - element.clientHeight,
    };
  });
  expect(scrollResult.scrollTop).toBeGreaterThan(0);
  expect(scrollResult.scrollTop).toBeGreaterThanOrEqual(scrollResult.maxScrollTop - 1);

  const continueButton = panel.getByRole('button', { name: 'Continue to confirmation' });
  await expectInViewport(continueButton, page);
  await continueButton.focus();
  await expect(continueButton).toBeFocused();
  await expectInViewport(continueButton, page);
  await continueButton.click();

  const confirmButton = panel.getByRole('button', { name: 'Confirm removal' });
  await expectInViewport(confirmButton, page);
});
