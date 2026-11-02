import { expect, test, type Locator, type Page } from '@playwright/test';
import { installScenario, waitForLiteScreenToSettle } from './lite-test-helpers';

const SNAP_RATIOS = { compact: 0.35, medium: 0.72, expanded: 0.94 } as const;
type PanelKind = 'workspace' | 'activity';

async function openPanel(page: Page, kind: PanelKind, width = 390) {
  await page.setViewportSize({ width, height: 800 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.addInitScript((value) => localStorage.setItem('pocketlab:appearance', value), 'dark');
  await installScenario(page, 'healthy');
  await page.goto('/?screen=home');
  await waitForLiteScreenToSettle(page, 'home');
  await page.getByRole('button', { name: kind === 'workspace' ? 'Workspace details' : /View all activity/ }).click();
  const dialog = page.getByRole('dialog', { name: kind === 'workspace' ? 'Workspace details' : 'Recent activity' });
  await expect(dialog).toBeVisible();
  return dialog;
}

async function expectSnap(page: Page, dialog: Locator, state: keyof typeof SNAP_RATIOS) {
  await expect(dialog).toHaveAttribute('data-lite-sheet-snap', state);
  const expected = await page.evaluate((ratio) => {
    const viewport = Math.max(128, window.visualViewport?.height || window.innerHeight);
    return Math.min(Math.max(128, viewport * ratio), Math.max(128, viewport - 20));
  }, SNAP_RATIOS[state]);
  const actual = await dialog.evaluate((node) => node.getBoundingClientRect().height);
  expect(Math.abs(actual - expected), `${state} snap geometry`).toBeLessThanOrEqual(2);
}

async function dragGrip(page: Page, dialog: Locator, deltaY: number) {
  const grip = dialog.getByRole('button', { name: /Resize sheet, currently/ });
  const rect = await grip.boundingBox();
  expect(rect).not.toBeNull();
  if (!rect) return;
  const x = rect.x + rect.width / 2;
  const y = rect.y + rect.height / 2;
  await page.mouse.move(x, y);
  await page.mouse.down();
  await page.mouse.move(x, y + deltaY, { steps: 10 });
  await page.mouse.up();
}

async function addScrollFixture(dialog: Locator) {
  const scroll = dialog.locator('.lite-home-panel-scroll');
  await scroll.evaluate((node) => {
    const filler = document.createElement('section');
    filler.dataset.homeSnapScrollFixture = 'true';
    filler.setAttribute('aria-hidden', 'true');
    filler.style.cssText = 'min-height:1400px;pointer-events:none;contain:layout';
    node.append(filler);
  });
  await expect.poll(() => scroll.evaluate((node) => node.scrollHeight - node.clientHeight)).toBeGreaterThan(300);
  return scroll;
}

for (const kind of ['workspace', 'activity'] as const) {
  test(`${kind} Home panel reuses PR 634 three-point mobile snap behavior`, async ({ page }) => {
    const dialog = await openPanel(page, kind);
    await expectSnap(page, dialog, 'medium');

    await dialog.getByRole('button', { name: 'Compact', exact: true }).click();
    await expectSnap(page, dialog, 'compact');
    await dialog.getByRole('button', { name: 'Expand', exact: true }).click();
    await expectSnap(page, dialog, 'medium');
    await dialog.getByRole('button', { name: 'Expand', exact: true }).click();
    await expectSnap(page, dialog, 'expanded');
    await dialog.getByRole('button', { name: 'Compact', exact: true }).click();
    await expectSnap(page, dialog, 'medium');

    const grip = dialog.getByRole('button', { name: /Resize sheet, currently/ });
    await grip.focus();
    await page.keyboard.press('Home');
    await expectSnap(page, dialog, 'compact');
    await page.keyboard.press('End');
    await expectSnap(page, dialog, 'expanded');
    await page.keyboard.press('PageDown');
    await expectSnap(page, dialog, 'medium');

    await dragGrip(page, dialog, 270);
    await expectSnap(page, dialog, 'compact');
    await dragGrip(page, dialog, -540);
    await expectSnap(page, dialog, 'expanded');
    await dialog.getByRole('button', { name: 'Compact', exact: true }).click();
    await expectSnap(page, dialog, 'medium');

    const section = kind === 'workspace' ? 'Service health' : 'History';
    await dialog.getByRole('button', { name: section, exact: true }).click();
    await expect(dialog.locator('[data-home-settings-view="section"]')).toBeVisible();
    await expect(dialog.getByRole('heading', { name: section })).toBeVisible();
    const scroll = await addScrollFixture(dialog);
    await scroll.evaluate((node) => node.scrollTo({ top: 240, behavior: 'instant' }));
    await expect.poll(() => scroll.evaluate((node) => node.scrollTop)).toBeGreaterThan(200);
    await dialog.getByRole('button', { name: kind === 'workspace' ? /All workspace details sections/ : /All activity sections/ }).click();
    await expect(dialog.locator('[data-home-settings-view="index"]')).toBeVisible();
    await expectSnap(page, dialog, 'medium');

    await dialog.getByRole('button', { name: 'Close Home details' }).click();
    await expect(dialog).toHaveCount(0);
    await page.getByRole('button', { name: kind === 'workspace' ? 'Workspace details' : /View all activity/ }).click();
    const reopened = page.getByRole('dialog', { name: kind === 'workspace' ? 'Workspace details' : 'Recent activity' });
    await expect(reopened).toBeVisible();
    await expectSnap(page, reopened, 'medium');
  });
}

for (const kind of ['workspace', 'activity'] as const) {
  test(`${kind} Home desktop panel keeps shared desktop geometry instead of mobile snap`, async ({ page }) => {
    const dialog = await openPanel(page, kind, 1280);
    await expect(dialog).toHaveAttribute('data-home-panel-layout', 'desktop-movable');
    await expect(dialog).not.toHaveAttribute('data-lite-sheet-snap');
    await expect(dialog.locator('[data-lite-overlay-panel-tools="desktop"]')).toBeVisible();
    await expect(dialog.locator('.lite-sheet-mobile-snap-actions')).toHaveCount(0);
  });
}
