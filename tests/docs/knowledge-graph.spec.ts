import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const DOCS_PREFIX = '/pocket-lab-lite/';
const KNOWLEDGE_GRAPH = `${DOCS_PREFIX}generated/enterprise/knowledgebase/knowledge-graph/`;

test('Knowledge Graph explorer is deterministic, accessible, and mobile-safe', async ({ page }, testInfo) => {
  const failedRequests: string[] = [];
  const consoleFailures: string[] = [];
  const externalRequests: string[] = [];

  page.on('console', (message) => {
    if (message.type() === 'error') {
      consoleFailures.push(`${message.type()}: ${message.text()}`);
    }
  });
  page.on('response', (response) => {
    if (response.status() >= 400) {
      failedRequests.push(`${response.status()} ${response.request().method()} ${response.url()}`);
    }
  });
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
      externalRequests.push(`${request.method()} ${request.resourceType()} ${request.url()}`);
    }
  });

  await page.goto(KNOWLEDGE_GRAPH);
  await expect(page.getByRole('heading', { name: 'Knowledge Graph' })).toBeVisible();
  await expect(page.locator('.pl-kg-kpis')).toBeVisible();
  await expect(page.locator('.pl-kg-integrity')).toBeVisible();
  await expect(page.locator('.pl-kg-ontology img')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Entity taxonomy' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Relation taxonomy' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Domain connectivity' })).toBeVisible();

  const explorer = page.locator('[data-pl-knowledge-graph="true"]');
  await expect(explorer).toBeVisible();
  const search = page.getByLabel('Search entities');
  await expect(search).toBeVisible();

  await search.fill('node agent');
  const firstResult = explorer.locator('.pl-kg-result').first();
  await expect(firstResult).toBeVisible();
  await firstResult.click();

  const inspector = explorer.locator('[data-kg-inspector]');
  await expect(inspector).toContainText('Entity inspector');
  await expect(inspector).toContainText('Source provenance');
  await expect(inspector).toContainText(/Direct relationships \(\d+\)/);

  const provenance = inspector.locator('details.pl-kg-relation-card').first();
  if (await provenance.count()) {
    await provenance.locator('summary').click();
    await expect(provenance).toContainText('Stable relation ID');
    await expect(provenance).toContainText('Derivation');
    await expect(provenance).toContainText('Evidence');
  }

  const axe = await new AxeBuilder({ page }).include('.md-content').analyze();
  const serious = axe.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''));
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);

  if (testInfo.project.name === 'docs-mobile') {
    const overflow = await explorer.evaluate((element) => ({
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      viewportWidth: document.documentElement.clientWidth,
      bodyScrollWidth: document.body.scrollWidth,
    }));
    expect(overflow.scrollWidth).toBeLessThanOrEqual(overflow.clientWidth + 1);
    expect(overflow.bodyScrollWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1);
  }

  expect(externalRequests, externalRequests.join('\n')).toEqual([]);
  expect(consoleFailures, consoleFailures.join('\n')).toEqual([]);
  expect(failedRequests, failedRequests.join('\n')).toEqual([]);
});
