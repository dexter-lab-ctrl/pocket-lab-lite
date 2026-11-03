import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORED — NOT EXECUTED. Mocked browser qualification only; never a real scan.
const widths = [320, 360, 375, 390, 430, 768, 1280, 1440] as const;
const properties = [
  'paddingTop','paddingRight','paddingBottom','paddingLeft',
  'marginTop','marginRight','marginBottom','marginLeft',
  'gap','rowGap','columnGap','fontFamily','fontSize','fontWeight',
  'lineHeight','letterSpacing','borderTopWidth','borderRightWidth',
  'borderBottomWidth','borderLeftWidth','minHeight','alignItems',
] as const;

async function startSafety(page: Page, scenario = 'security-quick-healthy', width = 390) {
  await page.setViewportSize({ width, height: width < 701 ? 844 : 900 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await installScenario(page, scenario);
  await page.goto('/?screen=security');
  await waitForLiteScreenToSettle(page, 'security');
}

async function theme(page: Page, selection: 'light'|'dark'|'system', systemDark = false) {
  await page.emulateMedia({ colorScheme: systemDark ? 'dark' : 'light', reducedMotion: 'reduce' });
  await page.evaluate((choice) => localStorage.setItem('pocketlab:appearance', choice), selection);
  await page.reload();
  await waitForLiteScreenToSettle(page, 'security');
}

async function geometry(page: Page, selector: string) {
  return page.locator(selector).first().evaluate((node, props) => {
    const rect = node.getBoundingClientRect();
    const style = getComputedStyle(node);
    const metrics: Record<string, string> = {};
    for (const prop of props) metrics[prop] = style[prop as keyof CSSStyleDeclaration] as string;
    return { rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }, metrics };
  }, properties);
}
function assertEquivalent(a: Awaited<ReturnType<typeof geometry>>, b: Awaited<ReturnType<typeof geometry>>) {
  for (const prop of properties) expect(b.metrics[prop], prop).toBe(a.metrics[prop]);
  for (const axis of ['x','y','width','height'] as const)
    expect(Math.abs(a.rect[axis] - b.rect[axis]), axis + ' outside 2px rounding tolerance').toBeLessThanOrEqual(2);
}

test.describe('Azure Safety native theme-independent density — authored only', () => {
  for (const width of widths) {
    test('Daylight, Dark, System-light and System-dark geometry parity at ' + width, async ({ page }) => {
      await startSafety(page, 'security-quick-healthy', width);
      const selectors = ['[data-safety-native-hero="true"]','[data-safety-native-destinations="true"]','.lite-safety-native-score','.lite-safety-native-destination'];
      const baselines = [];
      for (const [selection, dark] of [['light',false],['dark',true],['system',false],['system',true]] as const) {
        await theme(page, selection, dark);
        const expected = selection === 'system' ? dark ? 'dark' : 'light' : selection;
        await expect(page.locator('html')).toHaveAttribute('data-lite-theme', expected);
        baselines.push(await Promise.all(selectors.map((sel) => geometry(page,sel))));
      }
      for (let i = 1; i < baselines.length; i++)
        for (let j = 0; j < selectors.length; j++) assertEquivalent(baselines[0][j],baselines[i][j]);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 2)).toBe(true);
    });
  }
  for (const width of [390, 768, 1280, 1440]) {
    test('Manage panel/index/selected-content geometry stays theme neutral at ' + width, async ({ page }) => {
      await startSafety(page, 'security-quick-healthy', width);
      const samples = [];
      for (const appearance of ['light','dark'] as const) {
        await theme(page, appearance, appearance === 'dark');
        await page.getByRole('button', { name: 'Manage Security details' }).click();
        const panel = page.getByRole('dialog', { name: 'Manage Safety' });
        await expect(panel).toBeVisible();
        await panel.getByRole('button', { name: 'Open Coverage in Manage Safety' }).click();
        samples.push(await Promise.all([
          geometry(page,'.lite-security-manage-shell'),
          geometry(page,'.lite-safety-native-workspace'),
          geometry(page,'.lite-safety-native-detail'),
        ]));
        await panel.getByRole('button', { name: 'Close security details' }).click();
      }
      for (let i = 0; i < samples[0].length; i++) assertEquivalent(samples[0][i],samples[1][i]);
    });
  }
});

test.describe('Native mobile Manage snap and accessibility — mocked, not executed', () => {
  for (const width of [320,360,375,390,430]) {
    test('Compact / Medium / Expanded never dismiss Manage at ' + width, async ({ page }) => {
      await startSafety(page,'security-quick-healthy',width);
      await page.getByRole('button', { name: 'Manage Security details' }).click();
      const sheet = page.getByRole('dialog', { name: 'Manage Safety' });
      await expect(sheet).toHaveAttribute('data-lite-sheet-snap','medium');
      await sheet.getByRole('button', { name: 'Compact' }).click();
      await expect(sheet).toHaveAttribute('data-lite-sheet-snap','compact');
      await sheet.getByRole('button', { name: 'Expand' }).click();
      await expect(sheet).toHaveAttribute('data-lite-sheet-snap','medium');
      await sheet.getByRole('button', { name: 'Expand' }).click();
      await expect(sheet).toHaveAttribute('data-lite-sheet-snap','expanded');
      const grip = sheet.getByRole('button', { name: /Resize sheet, currently expanded/i });
      await grip.focus();
      await page.keyboard.press('Home');
      await expect(sheet).toHaveAttribute('data-lite-sheet-snap','compact');
      await page.keyboard.press('End');
      await expect(sheet).toHaveAttribute('data-lite-sheet-snap','expanded');
      await sheet.getByRole('button',{ name:'Open Evidence in Manage Safety' }).click();
      await expect(sheet.getByRole('button', { name: 'Back to Manage Safety' })).toBeVisible();
      await sheet.getByRole('button', { name: 'Back to Manage Safety' }).click();
      await expect(sheet.getByRole('navigation', { name: 'Manage Safety sections' })).toBeVisible();
      await expect(sheet).toBeVisible();
    });
  }
  test('keyboard, reduced motion and 200% text preserve accessible controls', async ({ page }) => {
    await startSafety(page,'security-action-needed',320);
    await page.addStyleTag({ content:'html { font-size:200%; }' });
    await page.getByRole('button',{ name:'Manage Security details' }).click();
    const sheet = page.getByRole('dialog',{ name:'Manage Safety' });
    await expect(sheet.getByRole('navigation',{ name:'Manage Safety sections' })).toBeVisible();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
    expect(results.violations.filter((v) => ['critical','serious'].includes(v.impact || ''))).toEqual([]);
    await page.keyboard.press('Escape');
    await expect(sheet).toHaveCount(0);
  });
});

test.describe('Native Safety reported-state contract — mocked, not executed', () => {
  for (const scenario of ['security-first-run','security-quick-healthy','security-action-needed',
    'security-scanner-unavailable','security-profile-stale','security-full-running',
    'security-app-check-healthy','offline-saved']) {
    test('preserves reported scenario ' + scenario, async ({ page }) => {
      await startSafety(page,scenario);
      await expect(page.locator('[data-safety-native-hero="true"]')).toBeVisible();
      await expect(page.locator('[data-safety-native-destinations="true"]')).toBeVisible();
      await expect(page.locator('[data-safety-native-hero="true"] .lite-safety-native-hero-actions > button.pocket-button')).toHaveCount(1);
      if (scenario === 'security-first-run')
        await expect(page.getByRole('img',{ name:'Safety score not reported' })).toBeVisible();
      if (scenario === 'offline-saved')
        await expect(page.getByRole('button',{ name:'Reconnect to run Quick Scan' })).toBeDisabled();
    });
  }
});
