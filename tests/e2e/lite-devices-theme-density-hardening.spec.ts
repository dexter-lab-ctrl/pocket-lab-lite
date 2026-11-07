// AUTHORED — NOT EXECUTED — UNVALIDATED.
// Screenshot baseline approval belongs to the separate qualification session.
// Follows the PR #636 computed-style parity contract: same geometry, semantic colors.
import { expect, test, type Browser, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

const WIDTHS = [320, 360, 430, 768, 1024, 1440] as const;
const THEMES = ['light', 'dark', 'system'] as const;
const GEOMETRY = [
  'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft',
  'marginTop', 'marginRight', 'marginBottom', 'marginLeft',
  'gap', 'rowGap', 'columnGap', 'fontSize', 'lineHeight',
  'borderTopWidth', 'borderRadius', 'minHeight',
] as const;

async function renderDevices(browser: Browser, width: number, theme: typeof THEMES[number], scenario: string) {
  const context = await browser.newContext({ viewport: { width, height: 900 }, reducedMotion: 'reduce' });
  const page = await context.newPage();
  await page.emulateMedia({ colorScheme: theme === 'system' ? 'dark' : 'light' });
  await page.addInitScript((appearance) => localStorage.setItem('pocketlab:appearance', appearance), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=devices');
  await waitForLiteScreenToSettle(page, 'devices');
  await page.evaluate(() => document.fonts.ready);
  return page;
}

async function manage(page: Page, section: string) {
  await page.getByRole('button', { name: /^Manage / }).first().click();
  const dialog = page.getByRole('dialog', { name: /^Manage / });
  await dialog.getByRole('button', { name: section, exact: true }).click();
  return dialog;
}

async function geometry(page: Page, selector: string) {
  const match = page.locator(selector).first();
  if (!(await match.count()) || !(await match.isVisible())) return null;
  return match.evaluate((element, keys) => {
    const style = getComputedStyle(element);
    const rect = element.getBoundingClientRect();
    const values: Record<string, string> = {};
    for (const key of keys) values[key] = style[key as keyof CSSStyleDeclaration] as string;
    return { values, rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height } };
  }, GEOMETRY);
}

for (const width of WIDTHS) {
  test('Devices Light/Dark/System geometry parity at ' + width + 'px', async ({ browser }) => {
    const pages: Page[] = [];
    try {
      for (const theme of THEMES) pages.push(await renderDevices(browser, width, theme, 'devices-online'));
      for (const selector of [
        '.lite-devices-horizon-summary',
        '.lite-device-library-card',
        '.lite-devices-library-tools',
        '.lite-devices-topology-workspace',
      ]) {
        const base = await geometry(pages[0], selector);
        for (const page of pages.slice(1)) {
          const current = await geometry(page, selector);
          expect(Boolean(current), selector + ' visibility').toBe(Boolean(base));
          if (!base || !current) continue;
          for (const prop of GEOMETRY) expect(current.values[prop], selector + ' ' + prop).toBe(base.values[prop]);
          for (const axis of ['width', 'height'] as const)
            expect(Math.abs(current.rect[axis] - base.rect[axis]), selector + ' ' + axis).toBeLessThanOrEqual(2);
        }
      }
      for (const page of pages) {
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
        const dialog = await manage(page, width <= 430 ? 'Health' : 'Connection');
        await expect(dialog).toBeVisible();
      }
      for (const selector of [
        '.lite-device-manage-workspace',
        '.lite-device-manage-nav-row',
        '.lite-device-details-panel-head',
        '.lite-device-manage-content',
      ]) {
        const base = await geometry(pages[0], selector);
        for (const page of pages.slice(1)) {
          const current = await geometry(page, selector);
          expect(Boolean(current), selector + ' presence').toBe(Boolean(base));
          if (!base || !current) continue;
          for (const prop of GEOMETRY) expect(current.values[prop], selector + ' ' + prop).toBe(base.values[prop]);
        }
      }
    } finally {
      for (const page of pages) await page.context().close();
    }
  });
}

const SCENARIOS = [
  { id: 'devices-online', label: 'online' },
  { id: 'devices-offline', label: 'offline' },
  { id: 'devices-repairing', label: 'repairing' },
  { id: 'offline-saved', label: 'saved' },
  { id: 'devices-remote-not-ready', label: 'remote-not-ready' },
  { id: 'devices-long-name', label: 'long-names' },
] as const;
test.describe('Devices visual candidates — baselines NOT captured', () => {
  for (const item of SCENARIOS) {
    test(item.label + ' desktop/mobile semantic surfaces', async ({ browser }) => {
      for (const width of [360, 1440]) {
        const page = await renderDevices(browser, width, 'dark', item.id);
        try {
          await expect(page.locator('.lite-screen-stage-devices')).toHaveScreenshot(
            'devices-' + item.label + '-' + width + '.png',
            { animations: 'disabled' },
          );
          const panel = await manage(page, 'Health');
          await expect(panel).toHaveScreenshot('devices-manage-health-' + item.label + '-' + width + '.png',
            { animations: 'disabled' });
        } finally {
          await page.context().close();
        }
      }
    });
  }
});
