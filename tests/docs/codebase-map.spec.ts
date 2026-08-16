import { expect, test } from '@playwright/test';

const PREFIX = '/pocket-lab-lite/generated/development/knowledge/codebase-map/';

test('Codebase Map is static, bounded, searchable, and deep-linkable', async ({ page }) => {
  const external: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (['127.0.0.1', 'localhost'].includes(url.hostname)) return;
    if (['http:', 'https:'].includes(url.protocol)) external.push(request.url());
  });

  await page.goto(PREFIX);
  await expect(
    page.getByRole('heading', { level: 1 }).filter({ hasText: 'Codebase Map' }).first()
  ).toBeVisible();
  await expect(page.locator('[data-cb-tree] .pl-codebase-tree-node').first()).toBeVisible();
  expect(await page.locator('[data-cb-tree] .pl-codebase-tree-node').count()).toBeLessThan(120);

  const search = page.locator('[data-cb-search]');
  await search.fill('generate_codebase_map.py');
  const generator = page.locator('[data-cb-tree] .pl-codebase-tree-node', { hasText: 'generate_codebase_map.py' }).first();
  await expect(generator).toBeVisible();
  await generator.click();
  await expect(page.locator('[data-cb-inspector]')).toContainText('scripts/docs/knowledge/generate_codebase_map.py');
  await expect(page).toHaveURL(/path=scripts%2Fdocs%2Fknowledge%2Fgenerate_codebase_map.py/);
  await expect(page.locator('[data-cb-inspector]')).toContainText('Uses');
  await expect(page.locator('[data-cb-inspector]')).toContainText('Used by');
  await expect(page.locator('[data-cb-inspector]')).toContainText('Bounded impact');
  expect(external).toEqual([]);
});

test('Codebase Map restores safe path state and rejects traversal', async ({ page }) => {
  await page.goto(`${PREFIX}?path=scripts/docs/knowledge/generate_codebase_map.py`);
  await expect(page.locator('[data-cb-inspector]')).toContainText('generate_codebase_map.py');

  await page.goto(`${PREFIX}?path=../../etc/passwd`);
  await expect(page.locator('[data-cb-inspector]')).toContainText('Path not found');
  await expect(page.locator('[data-cb-tree]')).toBeVisible();

  const mapOverflow = await page.evaluate(() => {
    const map = document.querySelector('.pl-codebase-map');

    return map
      ? map.scrollWidth > map.clientWidth + 2
      : true;
  });

  expect(mapOverflow).toBeFalsy();
});

test('Codebase Map filters locally and preserves browser history state', async ({ page }) => {
  await page.goto(PREFIX);
  const role = page.locator('[data-cb-role]');
  await role.selectOption('Build tooling');
  await expect(page.locator('[data-cb-tree] .pl-codebase-results-meta')).toContainText('matching paths');
  expect(await page.locator('[data-cb-tree] .pl-codebase-tree-node').count()).toBeGreaterThan(0);

  await role.selectOption('');
  const search = page.locator('[data-cb-search]');
  await search.fill('generate_codebase_map.py');
  await page.locator('[data-cb-tree] .pl-codebase-tree-node', { hasText: 'generate_codebase_map.py' }).first().click();
  await search.fill('generate_knowledge.py');
  await page.locator('[data-cb-tree] .pl-codebase-tree-node', { hasText: 'generate_knowledge.py' }).first().click();
  await page.goBack();
  await expect(page.locator('[data-cb-inspector]')).toContainText('generate_codebase_map.py');
});

test('Codebase Map fails closed when its static projection is missing', async ({ page }) => {
  await page.route('**/generated/assets/knowledge/repository-codebase-map.json', async (route) => {
    await route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
  });
  await page.goto(PREFIX);
  await expect(page.locator('[data-cb-tree]')).toContainText('Codebase Map unavailable');
  await expect(page.locator('[data-cb-inspector]')).toContainText('Static model remains authoritative');
});

test('Codebase Map remains usable with reduced motion', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto(PREFIX);
  await expect(page.locator('[data-cb-tree] .pl-codebase-tree-node').first()).toBeVisible();
  await page.locator('[data-cb-search]').fill('lite.py');
  await expect(page.locator('[data-cb-tree] .pl-codebase-tree-node').first()).toBeVisible();
});
