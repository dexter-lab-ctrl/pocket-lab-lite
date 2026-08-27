import { test, expect } from '@playwright/test';

const DOCS_PREFIX = '/pocket-lab-lite/';
const OVERVIEW = `${DOCS_PREFIX}generated/enterprise/threat-model/`;
const EVIDENCE_ZONE = `${OVERVIEW}evidence-zone/`;

const noHorizontalOverflow = async (page: import('@playwright/test').Page) => {
  const overflow = await page.locator('.md-content').evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
    viewportWidth: document.documentElement.clientWidth,
    bodyScrollWidth: document.body.scrollWidth,
  }));
  expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
  expect(overflow.bodyScrollWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1);
};

test('Threat Model enterprise labels drill into detail pages and remain mobile-safe', async ({ page }, testInfo) => {
  await page.goto(OVERVIEW);
  const poster = page.locator('[data-pl-threat-poster="true"]');
  const object = poster.locator('#pl-threat-model-svg');
  await expect(object).toBeVisible();
  await expect.poll(async () => object.evaluate((node: HTMLObjectElement) => Boolean(node.contentDocument?.documentElement))).toBe(true);

  expect(await object.evaluate((node: HTMLObjectElement) => node.contentDocument?.querySelectorAll('image.brand-icon').length)).toBe(19);
  expect(await object.evaluate((node: HTMLObjectElement) => node.contentDocument?.querySelector('g.legend') === null)).toBe(true);
  expect(await object.evaluate((node: HTMLObjectElement) => Boolean(node.contentDocument?.querySelector('metadata[data-threat-legend="svg"]')))).toBe(true);
  const browserCue = await object.evaluate((node: HTMLObjectElement) => {
    const browser = node.contentDocument?.querySelector<SVGGElement>('.node[data-node="browser"]');
    const controls = Number(browser?.dataset.controlCount);
    const assets = Number(browser?.dataset.assetCount);
    const label = browser?.querySelector('.cue-link')?.textContent?.trim();
    return { assets, controls, label };
  });
  const plural = (count: number, noun: string) => `${count} ${noun}${count === 1 ? '' : 's'}`;
  expect(browserCue.label).toBe(`${plural(browserCue.controls, 'control')} · ${plural(browserCue.assets, 'asset')}`);

  await object.evaluate((node: HTMLObjectElement) => {
    const target = node.contentDocument?.querySelector<SVGGElement>('.node[data-node="browser"]');
    target?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  if (testInfo.project.name === 'docs-mobile') {
    const detail = poster.locator('#threat-selection');
    await expect(detail).toHaveAttribute('data-open', 'true');
    const close = detail.locator('.pl-threat-detail-close');
    await expect(close).toBeVisible();
    await close.click();
    await expect(detail).toHaveAttribute('data-open', 'false');
  }

  await object.evaluate((node: HTMLObjectElement) => {
    const cue = node.contentDocument?.querySelector<SVGTextElement>('.node[data-node="browser"] .cue-link');
    cue?.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
  });
  await expect(page).toHaveURL(new RegExp(`${DOCS_PREFIX}generated/enterprise/threat-model/browser/$`));
  await expect(page.getByRole('heading', { name: 'Assets' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Actors' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Controls' })).toBeVisible();
  await expect(page.getByText('CTRL-HUMAN-SESSION-CSRF', { exact: true })).toHaveCount(1);
  await expect(page.locator('.pl-threat-section-toggle')).not.toHaveCount(0);
  if (testInfo.project.name === 'docs-mobile') await noHorizontalOverflow(page);

  await page.goto(EVIDENCE_ZONE);
  await expect(page.getByRole('heading', { name: 'Promoted evidence → documentation' })).toBeVisible();
  await expect(
    page.getByText('does not create a tenth canonical threat boundary')
  ).toBeVisible();
  if (testInfo.project.name === 'docs-mobile') await noHorizontalOverflow(page);

  await page.goto(OVERVIEW);
  const fullscreen = page.locator('[data-threat-fullscreen="open"]');
  await expect(fullscreen).toBeVisible();
  if (testInfo.project.name === 'docs-mobile') {
    await fullscreen.click();
    await expect(poster).toHaveClass(/is-fullscreen/);
    await expect(page.locator('html')).toHaveAttribute('data-pl-threat-fullscreen', 'true');
    await poster.locator('[data-threat-fullscreen="close"]').click();
    await expect(poster).not.toHaveClass(/is-fullscreen/);
  } else {
    const popupPromise = page.waitForEvent('popup');
    await fullscreen.click();
    const popup = await popupPromise;
    await popup.waitForLoadState('domcontentloaded');
    await expect(popup).toHaveURL(/poster-fullscreen=1/);
    await expect(popup.locator('[data-pl-threat-poster="true"]')).toHaveClass(/is-fullscreen/);
    await popup.close();
  }
});
