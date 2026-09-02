import { expect, test, type Page } from '@playwright/test';
import { installScenario, LITE_TABS, openTab, waitForLiteScreenToSettle } from './lite-test-helpers';

const VIEWPORTS = [
  { width: 320, height: 568 },
  { width: 390, height: 844 },
  { width: 430, height: 932 },
  { width: 768, height: 1024 },
  { width: 1280, height: 720 },
] as const;

const LONG_TITLE = 'A deliberately long Pocket Lab Lite status title for a self-hosted workspace with several descriptive words and no abbreviated safety meaning';
const LONG_SUMMARY = 'This deterministic worst-plausible summary is intentionally verbose so wrapping, action reachability, progressive disclosure, and responsive containment regressions are detected before merge without changing backend-owned state.';
const LONG_DEVICE = 'Family-Storage-and-Photo-Archive-Android-Device-With-A-Very-Long-Friendly-Name-2026';
const LONG_APP = 'PhotoPrism Family Archive and Long-Term Private Photo Library';
const LONG_IDENTITY = 'primary-pocket-lab-owner-with-a-deliberately-long-display-name@example-self-hosted.invalid';

async function assertNoHorizontalOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1)).toBe(true);
}

async function injectWorstPlausibleCopy(page: Page, screenId: string) {
  await page.evaluate(({ screenId, longTitle, longSummary, longDevice, longApp, longIdentity }) => {
    const screen = document.querySelector(`[data-lite-screen-id="${screenId}"]`);
    if (!screen) return;
    const storyHeadline = screen.querySelector('.lite-operational-story strong');
    const storySummary = screen.querySelector('.lite-operational-story p');
    if (storyHeadline) storyHeadline.textContent = longTitle;
    if (storySummary) storySummary.textContent = longSummary;

    if (screenId === 'catalog') {
      const appName = screen.querySelector('.lite-catalog-app-card h2, .lite-catalog-app-card h3, .lite-catalog-app-card strong');
      if (appName) appName.textContent = longApp;
      const appSummary = screen.querySelector('.lite-catalog-app-card p');
      if (appSummary) appSummary.textContent = longSummary;
    }
    if (screenId === 'devices') {
      const deviceCard = screen.querySelector('.lite-device-card');
      const deviceName = deviceCard?.querySelector('h2, h3, strong');
      if (deviceName) deviceName.textContent = longDevice;
      const deviceSummary = deviceCard?.querySelector('p');
      if (deviceSummary) deviceSummary.textContent = longSummary;
    }
    if (screenId === 'identity') {
      const candidates = Array.from(screen.querySelectorAll('span, strong, small, p'));
      const ownerValue = candidates.find((node) => /owner|session|identity/i.test(node.textContent || ''));
      if (ownerValue) ownerValue.textContent = longIdentity;
    }
  }, { screenId, longTitle: LONG_TITLE, longSummary: LONG_SUMMARY, longDevice: LONG_DEVICE, longApp: LONG_APP, longIdentity: LONG_IDENTITY });
  await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

async function assertLastControlReachable(page: Page, screenId: string) {
  const screen = page.locator(`[data-lite-screen-id="${screenId}"]`);
  const controls = screen.locator('button:visible, a:visible');
  const count = await controls.count();
  if (!count) return;
  const target = controls.nth(count - 1);
  await target.scrollIntoViewIfNeeded();
  await expect(target).toBeVisible();
  const reachable = await target.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const nav = document.querySelector('.mobile-bottom-nav, .lite-bottom-nav, [data-lite-bottom-nav]');
    const navRect = nav?.getBoundingClientRect();
    const visibleBottom = navRect && navRect.height > 0 ? Math.min(window.innerHeight, navRect.top) : window.innerHeight;
    return rect.width > 0 && rect.height > 0 && rect.top < visibleBottom && rect.bottom > 0;
  });
  expect(reachable, `${screenId}: last meaningful control should remain reachable above fixed navigation`).toBe(true);
}

for (const viewport of VIEWPORTS) {
  test(`worst-plausible content remains contained at ${viewport.width}x${viewport.height}`, async ({ page }) => {
    await installScenario(page, 'healthy');
    await page.setViewportSize(viewport);
    await page.goto('/?screen=home');

    for (const [label, screenId] of LITE_TABS) {
      await openTab(page, label, screenId);
      await waitForLiteScreenToSettle(page, screenId);
      await injectWorstPlausibleCopy(page, screenId);
      await assertNoHorizontalOverflow(page);
      await assertLastControlReachable(page, screenId);
    }
  });
}

test('long content remains contained with a 200 percent root text stress', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.setViewportSize({ width: 320, height: 568 });
  await page.goto('/?screen=home');
  await page.addStyleTag({ content: 'html { font-size: 200% !important; }' });

  for (const [label, screenId] of LITE_TABS) {
    await openTab(page, label, screenId);
    await waitForLiteScreenToSettle(page, screenId);
    await injectWorstPlausibleCopy(page, screenId);
    await assertNoHorizontalOverflow(page);
    await assertLastControlReachable(page, screenId);
  }
});

test('representative mobile Manage dialogs contain long copy and remain scrollable', async ({ page }) => {
  await installScenario(page, 'healthy');
  await page.setViewportSize({ width: 390, height: 844 });

  const flows = [
    ['home', /Workspace details/i],
    ['catalog', /^Manage$/i],
    ['security', /Manage Safety/i],
    ['identity', /Manage Access/i],
    ['rules', /Manage Safety Rules/i],
    ['recovery', /Manage Recovery/i],
  ] as const;

  for (const [screenId, openerName] of flows) {
    await page.goto(`/?screen=${screenId}`);
    await waitForLiteScreenToSettle(page, screenId);
    await page.getByRole('button', { name: openerName }).locator(':visible').first().click();
    const dialog = page.locator('[role="dialog"]:visible').first();
    await expect(dialog).toBeVisible();
    await dialog.evaluate((element, longSummary) => {
      const target = element.querySelector('p, small');
      if (target) target.textContent = `${longSummary} ${longSummary}`;
    }, LONG_SUMMARY);
    await page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));

    const contained = await dialog.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      return rect.left >= -1 && rect.right <= window.innerWidth + 1 && element.scrollWidth <= element.clientWidth + 1;
    });
    expect(contained, `${screenId}: Manage dialog should stay inside the mobile viewport`).toBe(true);
    await assertNoHorizontalOverflow(page);
    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
  }
});
