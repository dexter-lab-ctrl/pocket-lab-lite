import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Locator, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

// P0/P1 authored qualification. Scroll is native browser geometry: no
// dispatchEvent('scroll') shortcuts and no assumed backend state.
type Panel = 'workspace' | 'activity';
const label = (kind: Panel) => kind === 'workspace' ? 'Workspace details' : 'Recent activity';
const navLabel = (kind: Panel) => kind === 'workspace' ? 'Workspace details sections' : 'Activity sections';

async function openPanel(page: Page, kind: Panel, appearance = 'dark', scenario = 'healthy') {
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), appearance);
  await installScenario(page, scenario);
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await page.getByRole('button', { name: kind === 'workspace' ? 'Workspace details' : 'View activity' }).click();
  const dialog = page.getByRole('dialog', { name: label(kind) });
  await expect(dialog).toBeVisible();
  return dialog;
}

async function makeRealScrollRange(dialog: Locator) {
  const scroll = dialog.locator('.lite-home-panel-scroll');
  await scroll.evaluate((node) => {
    const filler = document.createElement('section');
    filler.setAttribute('aria-hidden', 'true');
    filler.dataset.homeScrollFixture = 'true';
    filler.style.cssText = 'min-height:1400px;pointer-events:none;contain:layout';
    node.append(filler);
  });
  await expect.poll(() => scroll.evaluate((node) => node.scrollHeight - node.clientHeight))
    .toBeGreaterThan(350);
  return scroll;
}
async function moveNativeScroll(scroll: Locator, top: number) {
  await scroll.evaluate((node, y) => { node.scrollTo({ top: y, behavior: 'instant' }); }, top);
  await expect.poll(() => scroll.evaluate((node) => node.scrollTop))
    .toBeGreaterThanOrEqual(Math.max(0, top - 8));
}

for (const kind of ['workspace', 'activity'] as const) {
  for (const width of [390, 1280]) for (const appearance of ['light','dark'] as const) {
    test(`${kind} ${appearance} ${width}px: pointer section then immediate native scroll retract/reveal`, async ({ page }) => {
      await page.setViewportSize({ width, height: 780 });
      const dialog = await openPanel(page, kind, appearance);
      const nav = dialog.getByRole('navigation', { name: navLabel(kind) });
      const firstTarget = kind === 'workspace' ? 'Service health' : 'Running';
      await nav.getByRole('button', { name: firstTarget, exact: true }).click();
      await expect(nav.getByRole('button', { name: firstTarget })).toHaveAttribute('aria-current', 'page');
      await expect(nav).toHaveAttribute('data-tabs-keyboard-focused', 'false');
      const scroll = await makeRealScrollRange(dialog);
      await moveNativeScroll(scroll, 240);
      await expect(nav).toHaveAttribute('data-tabs-hidden', 'true');
      const collapsed = await nav.evaluate((node) => node.getBoundingClientRect().height);
      expect(collapsed).toBeLessThanOrEqual(1);
      await scroll.evaluate((node) => node.scrollTo({ top: 90, behavior: 'instant' }));
      await expect(nav).toHaveAttribute('data-tabs-hidden', 'false');
      await nav.getByRole('button', { name: kind === 'workspace' ? 'Diagnostics' : 'History' }).click();
      await expect(scroll).toHaveJSProperty('scrollTop', 0);
      await moveNativeScroll(scroll, 210);
      await expect(nav).toHaveAttribute('data-tabs-hidden', 'true');
      await scroll.evaluate((node) => node.scrollTo({ top: 0, behavior: 'instant' }));
      await expect(nav).toHaveAttribute('data-tabs-hidden', 'false');
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)).toBe(false);
    });
  }

  test(`${kind}: keyboard navigation restores visible strip without disabling focus outline`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 780 });
    const dialog = await openPanel(page, kind);
    const nav = dialog.getByRole('navigation', { name: navLabel(kind) });
    const scroll = await makeRealScrollRange(dialog);
    await moveNativeScroll(scroll, 230);
    await expect(nav).toHaveAttribute('data-tabs-hidden', 'true');
    // Keyboard intent is handled by the shared hook, not :focus-within alone.
    await scroll.focus();
    await page.keyboard.press('Tab');
    const tab = nav.getByRole('button').first();
    await tab.focus();
    await expect(nav).toHaveAttribute('data-tabs-hidden', 'false');
    await expect(nav).toHaveAttribute('data-tabs-keyboard-focused', 'true');
    await expect(tab).toBeFocused();
    expect(await tab.evaluate((node) => getComputedStyle(node).outlineStyle !== 'none')).toBe(true);
    await scroll.hover();
    await page.mouse.wheel(0, 260);
    await expect(nav).toHaveAttribute('data-tabs-keyboard-focused', 'false');
  });

  test(`${kind}: System appearance change retains panel, selection and scroll owner`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 780 });
    await page.emulateMedia({ colorScheme: 'dark' });
    const dialog = await openPanel(page, kind, 'system');
    const nav = dialog.getByRole('navigation', { name: navLabel(kind) });
    const selected = kind === 'workspace' ? 'Service health' : 'History';
    await nav.getByRole('button', { name: selected }).click();
    const scroll = await makeRealScrollRange(dialog);
    await moveNativeScroll(scroll, 200);
    await page.emulateMedia({ colorScheme: 'light' });
    await expect(dialog).toBeVisible();
    await expect(nav.getByRole('button', { name: selected })).toHaveAttribute('aria-current','page');
    await expect(scroll).toHaveJSProperty('scrollTop', 200);
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme','light');
    await page.emulateMedia({ colorScheme: 'dark' });
    await expect(page.locator('html')).toHaveAttribute('data-lite-theme','dark');
  });

  test(`${kind}: Axe WCAG 2.2 AA in Black panel, focus and controls`, async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 760 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const dialog = await openPanel(page, kind, 'dark');
    const results = await new AxeBuilder({ page }).include('[role="dialog"]')
      .withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
    expect(results.violations.filter((item) => item.impact === 'serious' || item.impact === 'critical')).toEqual([]);
    await expect(dialog.getByRole('button', { name: /Close Home details/ })).toBeVisible();
  });
}

for (const width of [320, 360, 375, 390, 430]) {
  test(`workflow ${width}px Black mobile: nodes, connectors, no overflow`, async ({ page }) => {
    await page.setViewportSize({ width, height: 780 });
    const dialog = await openPanel(page, 'workspace', 'dark');
    await dialog.getByRole('button', { name: 'Service health' }).click();
    const flow = dialog.locator('.lite-home-workflow');
    await expect(flow.getByRole('listitem')).toHaveCount(4);
    await expect(flow.locator('.lite-home-workflow-line')).toHaveCount(3);
    const css = await flow.evaluate((node) => {
      const visual = node.querySelector('.lite-home-workflow-visual')!;
      const icon = node.querySelector('.lite-home-workflow-node > svg')!;
      return { columns: getComputedStyle(visual).gridTemplateColumns,
        iconWidth: icon.getBoundingClientRect().width,
        flowRight: node.getBoundingClientRect().right,
        panelRight: node.closest('[role="dialog"]')!.getBoundingClientRect().right };
    });
    expect(css.columns.split(' ')).toHaveLength(1);
    expect(css.iconWidth).toBeGreaterThanOrEqual(20);
    expect(css.flowRight).toBeLessThanOrEqual(css.panelRight + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2)).toBe(false);
  });
}
