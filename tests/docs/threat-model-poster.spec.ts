import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const DOCS_PREFIX = '/pocket-lab-lite/';
const THREAT_MODEL = `${DOCS_PREFIX}generated/enterprise/threat-model/`;

test('Threat Model poster is static, accessible, deterministic, and mobile-safe', async ({ page }, testInfo) => {
  const failedRequests: string[] = [];
  const consoleFailures: string[] = [];
  const externalRequests: string[] = [];

  page.on('console', (message) => {
    if (message.type() === 'error') consoleFailures.push(`${message.type()}: ${message.text()}`);
  });
  page.on('response', (response) => {
    if (response.status() >= 400) failedRequests.push(`${response.status()} ${response.request().method()} ${response.url()}`);
  });
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!['127.0.0.1', 'localhost'].includes(url.hostname)) {
      externalRequests.push(`${request.method()} ${request.resourceType()} ${request.url()}`);
    }
  });

  await page.goto(THREAT_MODEL);
  await expect(page.getByRole('heading', { name: 'Threat Model', level: 1 })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'How control moves — and where trust changes' })).toBeVisible();

  const poster = page.locator('[data-pl-threat-poster="true"]');
  const object = poster.locator('#pl-threat-model-svg');
  await expect(poster).toBeVisible();
  await expect(object).toBeVisible();

  await expect.poll(async () => object.evaluate((node: HTMLObjectElement) => Boolean(node.contentDocument?.documentElement))).toBe(true);

  const modes = ['understand', 'threats', 'controls'];
  const strides = ['all', 'Spoofing', 'Tampering', 'Repudiation', 'Information Disclosure', 'Denial of Service', 'Elevation of Privilege'];
  const pairwise = [
    ['understand', 'all'],
    ['threats', 'Spoofing'],
    ['controls', 'Tampering'],
    ['understand', 'Repudiation'],
    ['threats', 'Information Disclosure'],
    ['controls', 'Denial of Service'],
    ['threats', 'Elevation of Privilege'],
  ] as const;

  expect(modes).toHaveLength(3);
  expect(strides).toHaveLength(7);

  for (const [mode, stride] of pairwise) {
    await poster.locator(`[data-threat-poster-mode="${mode}"]`).click();
    await poster.locator(`[data-stride-lens="${stride}"]`).click();
    const state = await object.evaluate((node: HTMLObjectElement) => ({
      mode: node.contentDocument?.documentElement.dataset.posterMode,
      stride: node.contentDocument?.documentElement.dataset.strideLens,
    }));
    expect(state).toEqual({ mode, stride });
  }

  const guardrails = poster.locator('[data-threat-guardrails="toggle"]');
  await guardrails.click();
  await expect(guardrails).toHaveAttribute('aria-pressed', 'true');
  expect(await object.evaluate((node: HTMLObjectElement) => node.contentDocument?.documentElement.classList.contains('show-guardrails'))).toBe(true);

  await page.goto(`${THREAT_MODEL}?atlas-threat=THR-BROWSER-SPOOFING#security-atlas`);
  await expect(page).toHaveURL(/\/threat-model\/catalog\/\?atlas-threat=THR-BROWSER-SPOOFING#security-atlas$/);
  await expect(page.getByRole('heading', { name: 'Security Atlas Catalog', level: 1 })).toBeVisible();

  await page.goto(`${THREAT_MODEL}?atlas-attack-path=AP-04#security-atlas`);
  await expect(page.locator('#threat-selection')).toContainText('Attack path AP-04');

  /*
   * Desktop explicitly exercises the poster button hover state before Axe.
   * This guards against theme regressions that can otherwise make small
   * control text fail WCAG AA only under pointer interaction.
   */
  if (testInfo.project.name === 'docs-desktop') {
    await page.locator('[data-threat-guardrails="toggle"]').hover();
  }

  const axe = await new AxeBuilder({ page }).include('.md-content').analyze();
  const serious = axe.violations.filter((item) => ['serious', 'critical'].includes(item.impact || ''));
  expect(serious, JSON.stringify(serious, null, 2)).toEqual([]);

  if (testInfo.project.name === 'docs-mobile') {
    const overflow = await page.locator('.md-content').evaluate((element) => ({
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
