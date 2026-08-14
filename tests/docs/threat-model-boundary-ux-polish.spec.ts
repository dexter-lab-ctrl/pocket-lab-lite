import { test, expect } from '@playwright/test';

const DOCS_PREFIX = '/pocket-lab-lite/';
const OVERVIEW = `${DOCS_PREFIX}generated/enterprise/threat-model/`;
const BROWSER_BOUNDARY = `${OVERVIEW}browser/`;
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

test('Threat Model boundary pages share enterprise anatomy and fullscreen stays platform-correct', async ({ page }, testInfo) => {
  await page.goto(BROWSER_BOUNDARY);
  await expect(page.locator('.pl-threat-boundary-summary')).toBeVisible();
  await expect(page.locator('.pl-threat-boundary-callout')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Runtime evidence & provenance' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Entry points' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Allowed flows' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Forbidden flows' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Threats' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Residual risk' })).toBeVisible();
  const evidenceLink = page
    .locator('.pl-threat-subnav a')
    .filter({ hasText: 'Promoted evidence → documentation' });

  await expect(evidenceLink).toBeVisible();
  await expect(evidenceLink).toHaveAttribute(
    'href',
    /evidence-zone\/?$/,
  );
  if (testInfo.project.name === 'docs-mobile') await noHorizontalOverflow(page);

  await page.goto(EVIDENCE_ZONE);
  await expect(page.getByRole('heading', { name: 'Promoted evidence → documentation' })).toBeVisible();
  await expect(page.getByText('does not create a tenth canonical threat boundary')).toBeVisible();
  for (const heading of [
    'Entry points',
    'Allowed flows',
    'Forbidden flows',
    'Threats',
    'Runtime evidence & provenance',
    'Residual risk',
  ]) {
    await expect(page.getByRole('heading', { name: heading })).toBeVisible();
  }
  await expect(page.locator('.pl-threat-boundary-summary')).toBeVisible();
  if (testInfo.project.name === 'docs-mobile') await noHorizontalOverflow(page);

  await page.goto(OVERVIEW);
  const poster = page.locator('[data-pl-threat-poster="true"]');
  const fullscreen = page.locator('[data-threat-fullscreen="open"]');
  await expect(fullscreen).toBeVisible();
  const overviewEvidenceLink = page
    .locator('.pl-threat-subnav a')
    .filter({ hasText: 'Promoted evidence → documentation' });

  await expect(overviewEvidenceLink).toBeVisible();
  await expect(overviewEvidenceLink).toHaveAttribute(
    'href',
    /evidence-zone\/?$/,
  );

  if (testInfo.project.name === 'docs-mobile') {
    await expect(fullscreen).toContainText('Full screen');
    await fullscreen.click();
    await expect(poster).toHaveClass(/is-fullscreen/);
    await expect(page.locator('html')).toHaveAttribute('data-pl-threat-fullscreen', 'true');
    await expect(poster.locator('[data-threat-fullscreen="close"]')).toBeVisible();
    await poster.locator('[data-threat-fullscreen="close"]').click();
    await expect(poster).not.toHaveClass(/is-fullscreen/);
    await noHorizontalOverflow(page);
  } else {
    await expect(fullscreen).toContainText('Open in new tab');
    await expect(poster).not.toHaveClass(/is-fullscreen/);
    const popupPromise = page.waitForEvent('popup');
    await fullscreen.click();
    const popup = await popupPromise;
    await popup.waitForLoadState('domcontentloaded');
    await expect(popup).toHaveURL(/poster-fullscreen=1/);
    expect(await popup.evaluate(() => window.name.startsWith('pocketlab-threat-poster-'))).toBe(true);
    await expect(popup.locator('[data-pl-threat-poster="true"]')).toHaveClass(/is-fullscreen/);
    await expect(poster).not.toHaveClass(/is-fullscreen/);
    await popup.close();
  }
});
