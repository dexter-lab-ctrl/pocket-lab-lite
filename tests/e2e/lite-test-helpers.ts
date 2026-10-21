import type { Page } from '@playwright/test';

export const LITE_TABS = [
  ['Home', 'home'],
  ['Apps', 'catalog'],
  ['Devices', 'devices'],
  ['Safety', 'security'],
  ['Recovery', 'recovery'],
  ['Access', 'identity'],
  ['Rules', 'rules'],
] as const;

type LiteScreenId = typeof LITE_TABS[number][1];

const LITE_TAB_LABELS = Object.freeze(
  Object.fromEntries(LITE_TABS.map(([label, screenId]) => [screenId, label])) as Record<LiteScreenId, string>,
);

export async function installScenario(page: Page, scenario = 'healthy') {
  await page.addInitScript((value) => {
    localStorage.setItem('POCKETLAB_MOCK_SCENARIO', value);
    localStorage.removeItem('pocketlab_lite_safe_snapshots');
  }, scenario);
}

type ApiFailureWatchOptions = {
  allowReadDegraded?: boolean;
  onReadDegraded?: () => void;
};

export function watchApiFailures(page: Page, options: ApiFailureWatchOptions = {}) {
  const failures: string[] = [];
  const expectedReadDegradedUrls = new Set<string>();
  page.on('console', (message) => {
    if (message.type() !== 'error') return;
    const text = message.text();
    const locationUrl = message.location().url || '';
    const isGenericResource404 = /^Failed to load resource: the server responded with a status of 404/i.test(text);
    const isExpectedReadDegraded = options.allowReadDegraded
      && expectedReadDegradedUrls.has(locationUrl)
      && /status of 5\d\d/i.test(text);

    // API HTTP failures are recorded with their URL by the response/request listeners below.
    // Chromium's duplicate generic resource console entry has no actionable URL, so keeping it
    // would turn unrelated assets such as favicon/manifest probes into false Lite API failures.
    if (isExpectedReadDegraded || (isGenericResource404 && !locationUrl.includes('/api/lite/'))) return;

    failures.push(`CONSOLE ${locationUrl ? `${locationUrl} ` : ''}${text}`);
  });
  page.on('pageerror', (error) => failures.push(`PAGEERROR ${error.message}`));
  page.on('response', (response) => {
    if (!response.url().includes('/api/lite/')) return;
    const headers = response.headers();
    const isExpectedReadDegraded = options.allowReadDegraded
      && response.status() >= 500
      && headers['x-pocketlab-read-degraded'] === 'true'
      && headers['x-pocketlab-refresh-pending'] === 'true';
    if (isExpectedReadDegraded) {
      expectedReadDegradedUrls.add(response.url());
      options.onReadDegraded?.();
      return;
    }
    if (response.status() >= 400) failures.push(`${response.status()} ${response.url()}`);
  });
  page.on('requestfailed', (request) => {
    const url = request.url();
    const errorText = request.failure()?.errorText || '';

    const expectedEventsAbort =
      url.includes('/api/lite/events') &&
      errorText.includes('ERR_ABORTED');

    if (expectedEventsAbort) return;

    if (url.includes('/api/lite/')) {
      failures.push(`FAILED ${url} ${errorText}`);
    }
  });
  return failures;
}

function escapeRegex(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function openTab(page: Page, screenId: LiteScreenId): Promise<void>;
export function openTab(page: Page, label: string, screenId: LiteScreenId): Promise<void>;
export async function openTab(page: Page, labelOrScreenId: string, explicitScreenId?: LiteScreenId) {
  const screenId = explicitScreenId || labelOrScreenId as LiteScreenId;
  const label = explicitScreenId ? labelOrScreenId : LITE_TAB_LABELS[screenId];
  if (!label) throw new Error(`Unknown Lite screen id: ${screenId}`);

  const labels = [label, label.split(' ')[0]];
  if (screenId === 'catalog') labels.push('Apps');
  const accessibleName = new RegExp(`^(?:${[...new Set(labels)].map(escapeRegex).join('|')})$`, 'i');
  const button = page.getByRole('button', { name: accessibleName }).first();
  await button.click();
  await page.locator(`[data-lite-screen-id="${screenId}"]`).waitFor({ state: 'visible' });
}


export async function waitForLiteScreenToSettle(
  page: Page,
  screenId: string,
  options: {
    timeoutMs?: number;
    stableSamples?: number;
    intervalMs?: number;
    allowLoadingState?: boolean | (() => boolean);
  } = {},
) {
  const timeoutMs = options.timeoutMs ?? 15_000;
  const stableSamples = options.stableSamples ?? 4;
  const intervalMs = options.intervalMs ?? 250;
  const screen = page.locator(`[data-lite-screen-id="${screenId}"]`);
  await screen.waitFor({ state: 'visible', timeout: timeoutMs });
  if (screenId === 'catalog') {
    // The catalog's opening shell can be visually stable before its prepared
    // app projection arrives and does not expose aria-busy. Require the
    // authoritative heading and card before sampling layout stability.
    await page.getByRole('heading', { name: 'Your Apps', exact: true }).waitFor({ state: 'visible', timeout: timeoutMs });
    await screen.locator('.lite-catalog-app-card').first().waitFor({ state: 'visible', timeout: timeoutMs });
  }
  if (screenId === 'rules') {
    // The Rules route can expose its loading shell before the policy and
    // identity projections have hydrated. Require the authored Premium Rules
    // surface so response-driven layout work is not measured as steady-state
    // scrolling.
    await screen.locator('.lite-rules-premium-screen').waitFor({ state: 'visible', timeout: timeoutMs });
  }
  if (screenId === 'recovery') {
    // Recovery's opening shell can have a stable geometry before the
    // authoritative premium projection has hydrated. Require the authored
    // surface so visual and interaction checks do not capture the shell.
    await screen.locator('.lite-recovery-premium-screen').waitFor({ state: 'visible', timeout: timeoutMs });
  }
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
    const allowLoadingState = typeof options.allowLoadingState === 'function'
      ? options.allowLoadingState()
      : options.allowLoadingState === true;
    if (signature === previous && (busyCount === 0 || allowLoadingState)) {
      consecutive += 1;
      if (consecutive >= stableSamples) {
        // Recovery's mocked service-worker projection can deliver its final
        // operation snapshot immediately after the first stable geometry.
        // Keep that delivery outside scroll/visual measurements.
        if (screenId === 'recovery') await page.waitForTimeout(1000);
        return;
      }
    } else {
      consecutive = 0;
      previous = signature;
    }
    await page.waitForTimeout(intervalMs);
  }

  throw new Error(`Lite screen ${screenId} did not settle within ${timeoutMs}ms`);
}
