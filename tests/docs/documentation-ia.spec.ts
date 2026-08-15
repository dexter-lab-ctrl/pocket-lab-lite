import { expect, test } from '@playwright/test';

const DOCS_PREFIX = '/pocket-lab-lite/';
const HUBS = [
  ['Start Here', 'generated/enterprise/hubs/start-here/'],
  ['Use', 'generated/enterprise/hubs/use/'],
  ['Operate', 'generated/enterprise/hubs/operate/'],
  ['Understand', 'generated/enterprise/hubs/understand/'],
  ['Build & Test', 'generated/enterprise/hubs/build-test/'],
  ['Security & Assurance', 'generated/enterprise/hubs/security-assurance/'],
  ['Release & Change', 'generated/enterprise/hubs/release-change/'],
  ['Reference', 'generated/enterprise/hubs/reference/'],
];

for (const [title, path] of HUBS) {
  test(`IA hub ${title} is readable, linked, and responsive`, async ({ page }) => {
    await page.goto(`${DOCS_PREFIX}${path}`);
    await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible();
    await expect(page.locator('.pl-card-grid .pl-card').first()).toBeVisible();
    await expect(page.locator('.pl-card-grid a.pl-intent-link').first()).toHaveAttribute('href', /.+/);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(overflow).toBe(false);
  });
}

test('Feature Journey preserves canonical drill-down and static provenance', async ({ page }) => {
  await page.goto(`${DOCS_PREFIX}generated/enterprise/journeys/devices/`);
  await expect(page.getByRole('heading', { level: 1, name: 'Devices Feature Journey' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'What the feature does' })).toBeVisible();
  await expect(page.getByRole('heading', { level: 2, name: /^Architecture\b/i })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Frontend and FastAPI ownership' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Events and execution' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Security controls and threat boundaries' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Evidence and audit projection' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Tests and validation' })).toBeVisible();
  await expect(page.getByText('source-derived', { exact: false }).first()).toBeVisible();
});

test('Threat Model specialist navigation and canonical deep links survive IA restructuring', async ({ page }) => {
  await page.goto(`${DOCS_PREFIX}generated/enterprise/threat-model/`);
  await expect(page.getByRole('heading', { level: 1, name: /Threat Model/ })).toBeVisible();
  await page.goto(`${DOCS_PREFIX}generated/enterprise/threat-model/attack-paths/`);
  await expect(page.getByRole('heading', { level: 1, name: /attack paths/i })).toBeVisible();
  await page.goto(`${DOCS_PREFIX}generated/enterprise/knowledgebase/knowledge-graph/`);
  await expect(page.getByRole('heading', { level: 1, name: /Knowledge Graph/i })).toBeVisible();
});
