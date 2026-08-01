import type { Page } from '@playwright/test';

export const LITE_TABS = [
  ['Home', 'home'],
  ['App Catalog', 'catalog'],
  ['Devices', 'devices'],
  ['Security', 'security'],
  ['Recovery', 'recovery'],
  ['Identity & Access', 'identity'],
  ['Rules', 'rules'],
] as const;

export async function installScenario(page: Page, scenario = 'healthy') {
  await page.addInitScript((value) => {
    localStorage.setItem('POCKETLAB_MOCK_SCENARIO', value);
    localStorage.removeItem('pocketlab_lite_safe_snapshots');
  }, scenario);
}

export function watchApiFailures(page: Page) {
  const failures: string[] = [];
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const text = message.text();
    const locationUrl = message.location().url || '';
    const isGenericResource404 = /^Failed to load resource: the server responded with a status of 404/i.test(text);

    // API HTTP failures are recorded with their URL by the response/request listeners below.
    // Chromium's duplicate generic resource console entry has no actionable URL, so keeping it
    // would turn unrelated assets such as favicon/manifest probes into false Lite API failures.
    if (isGenericResource404 && !locationUrl.includes('/api/lite/')) return;

    failures.push(`CONSOLE ${locationUrl ? `${locationUrl} ` : ''}${text}`);
  });
  page.on('pageerror', (error) => failures.push(`PAGEERROR ${error.message}`));
  page.on('response', (response) => {
    if (!response.url().includes('/api/lite/')) return;
    if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`);
  });
  page.on('requestfailed', (request) => {
    if (request.url().includes('/api/lite/')) failures.push(`FAILED ${request.url()} ${request.failure()?.errorText || ''}`);
  });
  return failures;
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export async function openTab(page: Page, label: string, screenId: string) {
  const shortLabel = label.split(' ')[0];
  const accessibleName = new RegExp(`^(${escapeRegex(label)}|${escapeRegex(shortLabel)})$`, 'i');
  const button = page.getByRole('button', { name: accessibleName }).locator(':visible').first();
  await button.click();
  await page.locator(`[data-lite-screen-id="${screenId}"]`).waitFor({ state: 'visible' });
}


export async function waitForLiteScreenToSettle(page: Page, screenId: string, options: { timeoutMs?: number; stableSamples?: number; intervalMs?: number } = {}) {
  const timeoutMs = options.timeoutMs ?? 15_000;
  const stableSamples = options.stableSamples ?? 4;
  const intervalMs = options.intervalMs ?? 250;
  const screen = page.locator(`[data-lite-screen-id="${screenId}"]`);
  await screen.waitFor({ state: 'visible', timeout: timeoutMs });
  await page.evaluate(async () => {
    if ('fonts' in document) await document.fonts.ready;
  });

  const deadline = Date.now() + timeoutMs;
  let consecutive = 0;
  let previous = '';

  while (Date.now() < deadline) {
    const signature = await screen.evaluate((element) => {
      const rect = element.getBoundingClientRect();
      const busy = element.querySelectorAll('[aria-busy="true"], [data-loading="true"]').length;
      const textLength = (element.textContent || '').trim().length;
      return [
        Math.round(rect.width),
        Math.round(rect.height),
        element.scrollHeight,
        textLength,
        busy,
      ].join(':');
    });

    const busyCount = Number(signature.split(':').at(-1) || '0');
    if (signature === previous && busyCount === 0) {
      consecutive += 1;
      if (consecutive >= stableSamples) return;
    } else {
      consecutive = 0;
      previous = signature;
    }
    await page.waitForTimeout(intervalMs);
  }

  throw new Error(`Lite screen ${screenId} did not settle within ${timeoutMs}ms`);
}
