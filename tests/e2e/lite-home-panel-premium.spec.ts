import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// AUTHORED, NOT EXECUTED. Mocked only; no runtime mutations or CI assumptions.
async function openHome(page: Page, theme: 'light' | 'dark' | 'system' = 'dark', scenario = 'healthy') {
  await page.addInitScript((mode) => localStorage.setItem('pocketlab:appearance', mode), theme);
  await installScenario(page, scenario);
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
}
async function panel(page: Page, kind: 'workspace' | 'activity') {
  await page.getByRole('button', { name: kind === 'workspace' ? 'Workspace details' : 'View activity' }).click();
  const dialog = page.getByRole('dialog', { name: kind === 'workspace' ? 'Workspace details' : 'Recent activity' });
  await expect(dialog).toBeVisible();
  return dialog;
}
async function scrollNav(dialog: import('@playwright/test').Locator, label: string) {
  const nav = dialog.getByRole('navigation', { name: label });
  const scroll = dialog.locator('.lite-home-panel-scroll');
  // Deterministic scroll span, independent of mock event-count variations.
  await scroll.evaluate((node) => {
    const filler = document.createElement('div');
    filler.style.height = '1500px';
    filler.dataset.testFiller = 'true';
    node.append(filler);
    node.scrollTop = 150;
    node.dispatchEvent(new Event('scroll'));
  });
  await expect(nav).toHaveAttribute('data-tabs-hidden', 'true');
  await scroll.evaluate((node) => { node.scrollTop = 70; node.dispatchEvent(new Event('scroll')); });
  await expect(nav).toHaveAttribute('data-tabs-hidden', 'false');
  await scroll.evaluate((node) => { node.scrollTop = 0; node.dispatchEvent(new Event('scroll')); });
  await expect(nav).toHaveAttribute('data-tabs-hidden', 'false');
}
for (const width of [320,360,375,390,430,768,1024,1440]) {
  for (const kind of ['workspace','activity'] as const) {
    test(`Home ${kind} panel bounds, tab and card separation at ${width}px`, async ({ page }) => {
      await page.setViewportSize({ width, height: 850 });
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await openHome(page, 'light');
      const dialog = await panel(page, kind);
      const rect = await dialog.boundingBox();
      expect(rect).not.toBeNull();
      if (rect) {
        expect(rect.x).toBeGreaterThanOrEqual(-1);
        expect(rect.x + rect.width).toBeLessThanOrEqual(width + 1);
      }
      await expect(dialog).toHaveAttribute('data-home-panel-layout', width >= 701 ? 'desktop-movable' : 'mobile-sheet');
      const firstCard = dialog.locator(kind === 'workspace' ? '.lite-home-workspace-section .lite-action-row' : '.lite-home-activity-counts > div').first();
      const nav = dialog.locator('.lite-home-details-nav');
      if (await firstCard.count()) {
        const cardRect = await firstCard.boundingBox();
        const navRect = await nav.boundingBox();
        if (cardRect && navRect) expect(cardRect.y).toBeGreaterThanOrEqual(navRect.y + navRect.height + 4);
      }
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)).toBe(false);
      if (width < 701) {
        await expect(dialog.getByRole('button', { name: /^Move .* panel$/ })).toHaveCount(0);
        await expect(dialog.getByRole('button', { name: /^Resize .* panel$/ })).toHaveCount(0);
      }
    });
  }
}
for (const kind of ['workspace','activity'] as const) {
  test(`Home ${kind} navigation retracts, reveals, focuses and changes sections`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 780 });
    await openHome(page);
    const dialog = await panel(page, kind);
    const navName = kind === 'workspace' ? 'Workspace details sections' : 'Activity sections';
    await scrollNav(dialog, navName);
    const nav = dialog.getByRole('navigation', { name: navName });
    const first = nav.getByRole('button').first();
    await first.focus();
    await expect(nav).toHaveAttribute('data-tabs-hidden', 'false');
    const target = nav.getByRole('button', { name: kind === 'workspace' ? 'Diagnostics' : 'History' });
    await target.click();
    await expect(target).toHaveAttribute('aria-current', 'page');
    await expect(nav).toHaveAttribute('data-tabs-hidden', 'false');
    await expect(dialog.locator('.lite-home-panel-scroll')).toHaveJSProperty('scrollTop', 0);
  });
  test(`Home ${kind} portal follows live Light/Dark/System changes without closing`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark', reducedMotion: 'reduce' });
    await openHome(page, 'system');
    const dialog = await panel(page, kind);
    const layer = page.locator('.lite-home-panel-layer[data-lite-overlay-portal]');
    await expect(layer).toHaveClass(/theme-pocket-lite-dark/);
    await page.emulateMedia({ colorScheme: 'light' });
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme', 'light');
    await expect(layer).toHaveClass(/theme-pocket-lite-daylight/);
    await page.emulateMedia({ colorScheme: 'dark' });
    await expect(layer).toHaveClass(/theme-pocket-lite-dark/);
    await expect(dialog).toBeVisible();
    await expect(dialog.locator('.lite-home-details-nav button[aria-current="page"]')).toHaveCount(1);
  });
  test(`Home ${kind} desktop move/resize/reset stays in viewport`, async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 });
    await openHome(page, 'dark');
    const dialog = await panel(page, kind);
    const title = kind === 'workspace' ? 'Workspace details' : 'Recent activity';
    const before = await dialog.boundingBox();
    const move = dialog.getByRole('button', { name: `Move ${title} panel` });
    await move.focus();
    await page.keyboard.press('ArrowLeft');
    const moved = await dialog.boundingBox();
    if (before && moved) expect(moved.x).toBeLessThan(before.x);
    const resize = dialog.getByRole('button', { name: `Resize ${title} panel` });
    await resize.focus();
    await page.keyboard.press('ArrowLeft');
    const resized = await dialog.boundingBox();
    if (resized && moved) expect(resized.width).toBeLessThanOrEqual(moved.width);
    await dialog.getByRole('button', { name: `Reset ${title} position and size` }).click();
    await page.setViewportSize({ width: 780, height: 640 });
    const clamped = await dialog.boundingBox();
    if (clamped) {
      expect(clamped.x).toBeGreaterThanOrEqual(-1);
      expect(clamped.x + clamped.width).toBeLessThanOrEqual(781);
    }
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
  });
  for (const theme of ['light','dark'] as const) {
    test(`Home ${kind} ${theme} semantic contrast and Axe AA`, async ({ page }) => {
      await page.setViewportSize({ width: 390, height: 844 });
      await openHome(page, theme);
      const dialog = await panel(page, kind);
      const colors = await dialog.evaluate((element, panelKind) => {
        const selectors = ['.lite-overlay-head', '.lite-home-panel-scroll', '.lite-home-details-nav',
          '.lite-home-details-nav button', panelKind === 'workspace' ? '.lite-action-row' : '.lite-home-activity-counts > div'];
        return selectors.flatMap((selector) => {
          const node = element.querySelector(selector);
          return node ? [{ selector, background: getComputedStyle(node).backgroundColor,
            color: getComputedStyle(node).color }] : [];
        });
      }, kind);
      expect(colors.length).toBeGreaterThan(3);
      for (const color of colors) {
        if (theme === 'dark') {
          expect(color.background).not.toBe('rgb(255, 255, 255)');
          expect(color.background).not.toBe('rgb(231, 242, 255)');
        }
        expect(color.color).not.toBe(color.background);
      }
      const axe = await new AxeBuilder({ page }).include('[role="dialog"]')
        .withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
      expect(axe.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual([]);
    });
  }
}
test('Home history review remains a private explicit action and unavailable state is readable', async ({ page }) => {
  await openHome(page, 'dark', 'offline-saved');
  const dialog = await panel(page, 'activity');
  await dialog.getByRole('button', { name: 'History', exact: true }).click();
  await expect(dialog.getByText(/private review position/i)).toBeVisible();
  await expect(dialog.getByRole('button', { name: /Mark activity reviewed/i })).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: /Close Home details/i })).toBeVisible();
});
test('Home 200% text and reduced motion remain usable in mobile panels', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 760 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await openHome(page, 'dark');
  await page.addStyleTag({ content: 'html{font-size:200%}' });
  for (const kind of ['workspace','activity'] as const) {
    const dialog = await panel(page, kind);
    await expect(dialog.locator('.lite-home-details-nav')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)).toBe(false);
    const motion = await dialog.locator('.lite-home-details-nav').evaluate((node) => getComputedStyle(node).transitionDuration);
    expect(motion).toMatch(/0s|0.0s/);
    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
  }
});
