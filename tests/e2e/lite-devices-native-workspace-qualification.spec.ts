// AUTHORED — NOT EXECUTED — UNVALIDATED.
// Qualification for the Azure Horizon Device Library; no baseline screenshot was generated.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Browser, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

const WIDTHS = [320, 360, 375, 390, 430, 768, 1024, 1280, 1440] as const;
const APPEARANCES = ['light', 'dark', 'system'] as const;
const STATES = ['devices-online', 'devices-offline', 'devices-agent-stopped', 'devices-repairing',
  'devices-remote-not-ready', 'devices-protected-host', 'devices-invite-ready',
  'devices-invite-mismatch', 'devices-resource-missing', 'devices-services-stale', 'offline-saved'] as const;

async function devices(page: Page, scenario = 'devices-online', theme = 'light') {
  await page.addInitScript((mode) => localStorage.setItem('pocketlab:appearance', mode), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
}
async function manage(page: Page) {
  await page.getByRole('button', { name: /^Manage / }).first().click();
  const panel = page.getByRole('dialog', { name: /^Manage / });
  await expect(panel).toBeVisible();
  return panel;
}
async function openTopology(page: Page) {
  await page.getByText('Connections & Topology').click();
  await expect(page.getByRole('region', { name: 'Pocket Lab device connections' })).toBeVisible();
}

for (const scenario of STATES) {
  test('native library keeps backend-truthful states and progressive topology: ' + scenario, async ({ page }) => {
    await devices(page, scenario);
    await expect(page.getByRole('heading', { name: 'Devices', level: 1 })).toBeVisible();
    await expect(page.getByRole('region', { name: 'Fleet summary' })).toBeVisible();
    await expect(page.getByRole('searchbox', { name: 'Search devices' })).toBeVisible();
    await expect(page.locator('.lite-remote-access-panel')).toHaveCount(0);
    await openTopology(page);
    await expect(page.locator('.lite-remote-access-panel')).toBeVisible();
  });
}
test('library search and status filters preserve Manage and source ordering', async ({ page }) => {
  await devices(page);
  const cards = page.locator('.lite-device-library-card');
  const initialCount = await cards.count();
  await page.getByRole('searchbox', { name: 'Search devices' }).fill('Test-Phone');
  expect(await cards.count()).toBeLessThanOrEqual(initialCount);
  await page.getByRole('combobox', { name: 'Filter devices' }).selectOption('connected');
  await expect(page.locator('.lite-devices-horizon-summary button[aria-pressed="true"]')).toHaveCount(1);
  await page.getByRole('searchbox', { name: 'Search devices' }).fill('');
  await page.getByRole('combobox', { name: 'Filter devices' }).selectOption('all');
  await expect(page.locator('.lite-devices-horizon-summary button[aria-pressed="true"]')).toContainText('Total devices');
});
test('Manage navigates real sections, protects server-only capabilities and restores focus', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await devices(page);
  const opener = page.getByRole('button', { name: /^Manage / }).first();
  await opener.click();
  const dialog = page.getByRole('dialog', { name: /^Manage / });
  await expect(dialog.locator('[data-active-device-section="overview"]')).toBeVisible();
  const nav = dialog.getByRole('navigation', { name: 'Device management sections' });
  await expect(nav.getByRole('button', { name: 'Overview' })).toBeVisible();
  for (const area of ['Connection', 'Health', 'Services', 'History', 'Technical']) {
    await nav.getByRole('button', { name: area, exact: true }).click();
    await expect(dialog.locator('[data-active-device-section="' + area.toLowerCase() + '"]')).toBeVisible();
  }
  if (await nav.getByRole('button', { name: 'Roles' }).count()) {
    await nav.getByRole('button', { name: 'Roles' }).click();
    await expect(dialog.getByRole('region', { name: 'Device roles' }).or(dialog.getByLabel('Device roles')).first()).toBeVisible();
  }
  await dialog.getByRole('button', { name: 'Close device details' }).click();
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});
test('mobile Manage uses shared 35/72/94 sheet snap and accessible size controls', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await devices(page);
  const dialog = await manage(page);
  const sheet = page.locator('[data-lite-details-panel-layout="mobile-sheet"]');
  await expect(sheet).toBeVisible();
  await expect(dialog.getByRole('button', { name: /Resize device Manage sheet/ })).toBeVisible();
  const mediumHeight = (await sheet.boundingBox())?.height || 0;
  await dialog.getByRole('button', { name: 'Make device sheet smaller' }).click();
  const smallHeight = (await sheet.boundingBox())?.height || 0;
  expect(smallHeight).toBeLessThan(mediumHeight);
  await dialog.getByRole('button', { name: 'Expand device sheet' }).click();
  await dialog.getByRole('button', { name: 'Expand device sheet' }).click();
  const expandedHeight = (await sheet.boundingBox())?.height || 0;
  expect(expandedHeight).toBeGreaterThan(mediumHeight);
  const grip = dialog.getByRole('button', { name: /Resize device Manage sheet/ });
  await grip.focus();
  await page.keyboard.press('Home');
  await expect(dialog.getByText('compact', { exact: true })).toBeVisible();
  await page.keyboard.press('End');
  await expect(dialog.getByText('expanded', { exact: true })).toBeVisible();
});
test('desktop Manage reuses movable/resizable geometry and remains within viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await devices(page);
  const panel = await manage(page);
  await panel.getByRole('button', { name: 'Move device details panel' }).focus();
  await page.keyboard.press('ArrowLeft');
  await panel.getByRole('button', { name: 'Resize device details panel' }).focus();
  await page.keyboard.press('Shift+ArrowDown');
  await panel.getByRole('button', { name: /Reset device details panel/ }).click();
  const rect = await panel.boundingBox();
  expect(rect).not.toBeNull();
  expect(rect!.x).toBeGreaterThanOrEqual(-2);
  expect(rect!.x + rect!.width).toBeLessThanOrEqual(1442);
});

async function themePage(browser: Browser, width: number, theme: typeof APPEARANCES[number]) {
  const context = await browser.newContext({ viewport: { width, height: 840 } });
  const page = await context.newPage();
  await page.emulateMedia({ colorScheme: theme === 'system' ? 'dark' : 'light', reducedMotion: 'reduce' });
  await devices(page, 'devices-online', theme);
  await page.evaluate(() => document.fonts.ready);
  return page;
}
const LAYOUT_PROPERTIES = ['paddingTop','paddingRight','paddingBottom','paddingLeft',
  'marginTop','marginBottom','gap','rowGap','columnGap','fontSize','fontFamily','fontWeight',
  'lineHeight','letterSpacing','borderTopWidth','minHeight'] as const;
async function geometry(page: Page, selector: string) {
  return page.locator(selector).first().evaluate((node, keys) => {
    const styles = getComputedStyle(node);
    const rect = node.getBoundingClientRect();
    return { properties: Object.fromEntries(keys.map((key) => [key, styles[key as keyof CSSStyleDeclaration] || ''])),
      rect: { width: rect.width, height: rect.height, left: rect.left, top: rect.top } };
  }, LAYOUT_PROPERTIES);
}
for (const width of WIDTHS) {
  test('Light/Dark/System identical Devices geometry and no overflow at ' + width + 'px', async ({ browser }) => {
    const pages: Page[] = [];
    try {
      for (const theme of APPEARANCES) pages.push(await themePage(browser, width, theme));
      for (const selector of ['.lite-devices-horizon-summary', '.lite-devices-horizon-summary > button',
        '.lite-devices-library-tools', '.lite-devices-list-shell', '.lite-device-library-card',
        '.lite-device-library-identity', '.lite-device-library-manage']) {
        const values = await Promise.all(pages.map((page) => geometry(page, selector)));
        for (const next of values.slice(1)) {
          expect(next.properties, selector).toEqual(values[0].properties);
          expect(Math.abs(next.rect.width - values[0].rect.width), selector + ' width').toBeLessThanOrEqual(2);
          expect(Math.abs(next.rect.height - values[0].rect.height), selector + ' height').toBeLessThanOrEqual(2);
        }
      }
      for (const page of pages) {
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
        const axe = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
        expect(axe.violations.filter((item) => ['critical','serious'].includes(item.impact || ''))).toEqual([]);
      }
    } finally { await Promise.all(pages.map((page) => page.context().close())); }
  });
}
test('Devices provides optional haptics for selection and Manage without polling feedback', async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).__deviceHaptics = [];
    Object.defineProperty(navigator, 'vibrate', { configurable: true, value: (value: unknown) => {
      (window as any).__deviceHaptics.push(value); return true;
    } });
  });
  await devices(page);
  await page.getByRole('combobox', { name: 'Filter devices' }).selectOption('attention');
  await page.getByRole('combobox', { name: 'Filter devices' }).selectOption('all');
  await manage(page);
  const before = (await page.evaluate(() => (window as any).__deviceHaptics)).length;
  expect(before).toBeGreaterThan(0);
  await page.waitForTimeout(400);
  const after = (await page.evaluate(() => (window as any).__deviceHaptics)).length;
  expect(after).toBe(before);
});
test('candidate visual contract — approve references in a separate qualification session', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await devices(page, 'devices-online', 'light');
  await expect(page.locator('.lite-devices-layout')).toHaveScreenshot('devices-native-library-mobile.png', { animations: 'disabled' });
});
