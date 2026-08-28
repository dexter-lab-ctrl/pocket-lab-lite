import { expect, test } from '@playwright/test';

const DOCS_PREFIX = '/pocket-lab-lite/';

async function expectNoDocumentOverflow(page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
  );
  expect(overflow).toBe(false);
}

test('Release Inventory renders promoted evidence as a responsive enterprise catalog', async ({ page }) => {
  await page.goto(`${DOCS_PREFIX}generated/development/release-inventory/`);

  const content = page.locator('.md-content');
  const releaseKpis = content.locator('.pl-kpi-grid').first();

  await expect(content.getByRole('heading', { level: 1, name: 'Release inventory' })).toBeVisible();
  await expect(releaseKpis.getByText('Promoted releases', { exact: true })).toBeVisible();
  await expect(content.getByText('lite-2026.08.19.2', { exact: true }).first()).toBeVisible();
  await expect(content.getByText('lite-2026.08.12.2', { exact: true }).first()).toBeVisible();
  await expect(content.getByText('3/3 verified', { exact: true }).first()).toBeVisible();

  const disclosure = content.getByText('Artifact integrity and full digests', { exact: true }).first();
  await expect(disclosure).toBeVisible();
  await disclosure.click();
  await expect(content.getByRole('columnheader', { name: 'SHA-256' }).first()).toBeVisible();
  await expect(content.getByRole('rowheader', { name: 'dist.zip' }).first()).toBeVisible();

  const procedure = content.getByRole('link', { name: 'Open Evidence & Promotion' });
  await expect(procedure).toHaveAttribute('href', /release\/evidence-promotion\/$/);
  await expectNoDocumentOverflow(page);
});

test('Evidence and Promotion explains the release lifecycle responsively', async ({ page }) => {
  await page.goto(`${DOCS_PREFIX}release/evidence-promotion/`);

  await expect(page.getByRole('heading', { level: 1, name: 'Evidence & Promotion' })).toBeVisible();
  await expect(page.locator('.pl-journey-stepper .pl-journey-step')).toHaveCount(6);
  await expect(page.getByText('LITE_E2E_LIVE=1 task lite:check:release', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('task lite:release:dry-run', { exact: false }).first()).toBeVisible();
  await expect(page.getByText('lite-YYYY.MM.DD.N', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('dist.zip', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('checksums.txt', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('pocketlab-lite-release.json', { exact: true }).first()).toBeVisible();
  await expect(page.getByText('repair_existing_release=true', { exact: true }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: 'Open Release Inventory' })).toHaveAttribute(
    'href',
    /generated\/development\/release-inventory\/$/,
  );
  await expectNoDocumentOverflow(page);
});

test('Release and Change hub exposes the contextual release procedure', async ({ page }) => {
  await page.goto(`${DOCS_PREFIX}generated/enterprise/hubs/release-change/`);

  await expect(page.getByRole('heading', { level: 1, name: 'Release & Change' })).toBeVisible();
  await expect(page.getByRole('heading', { level: 2, name: 'Release procedure' })).toBeVisible();
  const link = page.getByRole('link', { name: 'Open Evidence & Promotion' });
  await expect(link).toHaveAttribute('href', /release\/evidence-promotion\/$/);
  await expectNoDocumentOverflow(page);
});
