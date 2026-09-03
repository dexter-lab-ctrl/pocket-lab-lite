import { expect, test } from '@playwright/test';
import { installScenario, LITE_TABS, openTab, watchApiFailures } from './lite-test-helpers';

const PREMIUM_VIEWPORTS = [
  { width: 320, height: 568 },
  { width: 390, height: 844 },
  { width: 430, height: 932 },
  { width: 768, height: 1024 },
  { width: 1280, height: 720 },
  { width: 1440, height: 900 },
] as const;

const PREMIUM_SCREENS = [
  ['Home', 'home'],
  ['Security', 'security'],
  ['Identity & Access', 'identity'],
  ['Rules', 'rules'],
] as const;

async function waitForLiveDevices(page) {
  const devices = page.locator('[data-lite-screen-id="devices"]');
  await expect(devices).toBeVisible();

  const healthyCard = devices
    .locator('.lite-device-card')
    .filter({ hasText: 'Test-Phone-4' });

  await expect(healthyCard).toBeVisible({ timeout: 20_000 });

  const connected = healthyCard.locator(
    '[data-connection-state="connected"]',
  );

  // A safe fleet snapshot may legitimately hydrate first and remain fresh
  // inside TanStack's Devices stale window. Tests that assert current
  // connection topology must explicitly request current backend truth,
  // exactly as the user would from the Devices screen.
  if (!(await connected.isVisible().catch(() => false))) {
    const refresh = devices.getByRole('button', {
      name: /^Refresh(?: Devices)?$/i,
    }).first();

    await expect(refresh).toBeVisible();
    await refresh.click();
  }

  await expect(connected).toBeVisible({ timeout: 20_000 });
  await expect(devices).not.toContainText(
    'Showing saved device information',
    { timeout: 20_000 },
  );

  return devices;
}

test.describe('Pocket Lab Lite mocked contract path', () => {
  test.beforeEach(async ({ page }) => {
    await installScenario(page, 'healthy');
  });

  test('renders every Lite tab through API helpers and TanStack Query', async ({ page }) => {
    const failed = watchApiFailures(page);
    await page.goto('/?screen=home');
    await expect(page.getByText('Pocket Lab Lite').first()).toBeVisible();

    for (const [label, screenId] of LITE_TABS) {
      await openTab(page, label, screenId);
      await expect(page.locator(`[data-lite-screen-id="${screenId}"]`)).toBeVisible();
    }

    expect(failed, `unexpected Lite API failures: ${failed.join(', ')}`).toEqual([]);
  });

  test('Home keeps secondary workspace detail in the explicit accessible sheet', async ({ page }) => {
    await page.goto('/?screen=home');
    const home = page.locator('[data-lite-screen-id="home"]');

    await expect(home.getByRole('button', { name: 'Workspace details' })).toBeVisible();
    await expect(home).not.toContainText(/Storage|Pocket Lab data/i);

    const opener = home.getByRole('button', { name: 'Workspace details' });
    await opener.click();
    const sheet = page.getByRole('dialog', { name: 'Workspace details' });
    await expect(sheet).toBeVisible();
    await expect(sheet).toContainText(/Storage|Pocket Lab data/i);
    await page.keyboard.press('Escape');
    await expect(sheet).toBeHidden();
    await expect(opener).toBeFocused();

    await home.getByRole('button', { name: 'Open' }).first().click();
    await expect(page.locator('[data-lite-screen-id="catalog"]')).toBeVisible();
  });

  test('Home keeps a ready workspace calm while respecting reduced-motion preference', async ({ page }) => {
    await page.goto('/?screen=home');
    const home = page.locator('[data-lite-screen-id="home"]');

    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(home).toBeVisible();
    await expect(home.locator('[data-home-workflow-state]')).toHaveCount(0);
    expect(await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true);
  });

  test('Home surfaces an attention area without opening healthy workspace detail', async ({ page }) => {
    await page.addInitScript((statusPayload) => {
      const originalFetch = window.fetch.bind(window);
      window.fetch = (input, init) => {
        const url = new URL(typeof input === 'string' ? input : input.url, window.location.origin);
        if (url.pathname === '/api/lite/status') {
          return Promise.resolve(new Response(JSON.stringify(statusPayload), {
            headers: { 'Content-Type': 'application/json' },
          }));
        }
        return originalFetch(input, init);
      };
    }, {
      overall: 'degraded',
      checked_at: '2026-08-31T16:00:00.000Z',
      device: { name: 'Pocket Lab Lite' },
      summary: { apps_available: 1, devices_known: 1, security_findings: 1, remote_access_ready: true },
      telemetry: { free_space_mb: 256000, total_space_mb: 512000, memory_usage_mb: 512, memory_total_mb: 2048 },
      services: [
        { name: 'Security', status: 'unhealthy' },
        { name: 'App Catalog', status: 'healthy' },
        { name: 'Device Fleet', status: 'healthy' },
      ],
    });
    await page.goto('/?screen=home');
    const home = page.locator('[data-lite-screen-id="home"]');

    await expect(home.locator('.lite-operational-story')).toContainText(/attention|safety|review/i);
    await expect(home.getByRole('button', { name: 'Workspace details' })).toBeVisible();
  });

  test('Home keeps saved information truthful while secondary detail remains collapsed', async ({ page }) => {
    await installScenario(page, 'offline-saved');
    await page.setViewportSize({ width: 320, height: 568 });
    await page.goto('/?screen=home');
    const home = page.locator('[data-lite-screen-id="home"]');
    await expect(home).toContainText('Showing saved information');
    await expect(home.getByRole('button', { name: 'Workspace details' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  });

  test('Recovery projection-too-old response stays truthful', async ({ page }) => {
    await installScenario(page, 'recovery-projection-too-old');
    await page.goto('/?screen=recovery');
    await expect(page.locator('[data-lite-screen-id="recovery"]')).toBeVisible();
    await expect(page.locator('[data-lite-screen-id="recovery"]')).toContainText(/saved|stale|projection|recovery/i);
  });

  test('Security app profile is shown separately from overall posture', async ({ page }) => {
    await installScenario(page, 'security-app-check-healthy');
    await page.goto('/?screen=security');
    await expect(page.locator('[data-lite-screen-id="security"]')).toBeVisible();
    await expect(page.locator('[data-lite-screen-id="security"]')).toContainText(/Safety|Security/i);
  });

  test('an accepted Security run reconciles one root terminal snapshot across navigation', async ({ page }) => {
    await page.addInitScript(() => {
      Object.defineProperty(navigator, 'onLine', { configurable: true, get: () => true });
      window.__liteHapticCalls = [];
      Object.defineProperty(navigator, 'vibrate', {
        configurable: true,
        value: (pattern) => { window.__liteHapticCalls.push(pattern); return true; },
      });
      if (navigator.serviceWorker) {
        Object.defineProperty(navigator.serviceWorker, 'controller', { configurable: true, get: () => null });
      }
      class ControlledEventSource {
        static instances = [];
        constructor(url) {
          this.url = String(url);
          this.closed = false;
          this.listeners = new Map();
          ControlledEventSource.instances.push(this);
          window.setTimeout(() => this.onopen?.({ type: 'open' }), 0);
        }
        addEventListener(type, listener) {
          const listeners = this.listeners.get(type) || [];
          listeners.push(listener);
          this.listeners.set(type, listeners);
        }
        removeEventListener(type, listener) {
          this.listeners.set(type, (this.listeners.get(type) || []).filter((item) => item !== listener));
        }
        close() { this.closed = true; }
        emit(payload) {
          const event = { data: JSON.stringify(payload) };
          this.onmessage?.(event);
          (this.listeners.get(payload.type) || []).forEach((listener) => listener(event));
        }
      }
      window.EventSource = ControlledEventSource;
      window.__liteControlledSecurityEvents = ControlledEventSource;
    });

    const requestsAfterTerminal: string[] = [];
    let terminalDelivered = false;
    page.on('request', (request) => {
      if (terminalDelivered && request.url().includes('/api/lite/')) requestsAfterTerminal.push(request.url());
    });

    await page.goto('/?screen=security');
    expect(await page.evaluate(async () => (await fetch('/api/lite/security/summary')).status)).toBe(200);
    const acceptedScan = page.waitForResponse((response) => (
      response.url().includes('/api/lite/security/check') && response.status() === 202
    ));
    await page.getByRole('button', { name: 'Run Quick Scan' }).click();
    await acceptedScan;
    // The click opens the screen-local stream while the request is in flight.
    // Once the server accepts the run, the root stream replaces it before any
    // navigation occurs; capture that settled owner rather than the transient.
    await expect.poll(() => page.evaluate(() => window.__liteControlledSecurityEvents.instances
      .filter((source) => source.url.includes('/api/lite/security/events')).length)).toBeGreaterThanOrEqual(2);
    await expect.poll(() => page.evaluate(() => window.__liteControlledSecurityEvents.instances
      .filter((source) => source.url.includes('/api/lite/security/events') && !source.closed).length)).toBe(1);
    const ownerId = await page.evaluate(() => window.__liteControlledSecurityEvents.instances
      .findIndex((source) => source.url.includes('/api/lite/security/events') && !source.closed));

    await openTab(page, 'Home', 'home');
    await expect(page.locator('[data-lite-screen-id="security"]')).not.toBeVisible();
    await expect.poll(() => page.evaluate(() => ({
      active: window.__liteControlledSecurityEvents.instances
        .filter((source) => source.url.includes('/api/lite/security/events') && !source.closed).length,
      owner: window.__liteControlledSecurityEvents.instances.findIndex((source) => (
        source.url.includes('/api/lite/security/events') && !source.closed
      )),
    }))).toEqual({ active: 1, owner: ownerId });

    await page.evaluate(() => {
      const source = window.__liteControlledSecurityEvents.instances
        .find((item) => item.url.includes('/api/lite/security/events') && !item.closed);
      source.emit({
        type: 'security.scan.completed',
        event_id: 500,
        run_id: 'security-2026-08-31T165957Z-wrong-run',
        profile: 'quick',
        status: 'succeeded',
        active_scan: false,
        snapshot: false,
      });
    });
    await expect(page.locator('.lite-toast', { hasText: 'Safety check completed' })).toHaveCount(0);

    const hapticCallsBeforeTerminal = await page.evaluate(() => window.__liteHapticCalls.length);
    terminalDelivered = true;
    await page.evaluate(() => {
      const source = window.__liteControlledSecurityEvents.instances
        .find((item) => item.url.includes('/api/lite/security/events') && !item.closed);
      const terminal = {
        type: 'security.scan.completed',
        event_id: 501,
        run_id: 'security-2026-08-31t165957z-2226321f',
        profile: 'quick',
        status: 'succeeded',
        percent: 100,
        active_scan: false,
        snapshot: false,
        updated_at: '2026-08-31T10:00:00.000Z',
      };
      source.emit(terminal);
      source.emit({ ...terminal, event_id: 502, run_id: 'security-2026-08-31T165957Z-2226321f' });
    });

    const completionToast = page.locator('.lite-toast', { hasText: 'Safety check completed' });
    await expect(completionToast).toHaveCount(1);
    expect(await page.evaluate((before) => window.__liteHapticCalls.slice(before), hapticCallsBeforeTerminal)).toEqual([[10, 30, 14]]);
    await expect.poll(() => page.evaluate(() => window.__liteControlledSecurityEvents.instances
      .filter((source) => source.url.includes('/api/lite/security/events') && !source.closed).length)).toBe(0);
    expect(requestsAfterTerminal.filter((url) => /\/api\/lite\/(identity|policy|fleet|catalog|recovery)(?:\?|$)/.test(url))).toEqual([]);

    const refreshedSecurity = page.waitForRequest((request) => (
      /\/api\/lite\/security(?:\/summary)?(?:\?|$)/.test(request.url())
    ));
    await openTab(page, 'Security', 'security');
    await refreshedSecurity;
    await expect(page.locator('[data-lite-screen-id="security"]')).toContainText(/No urgent safety issues|Protected|Safety score/i);
    await expect(completionToast).toHaveCount(1);

    // A historical result delivered after the accepted observation is cleared
    // must remain presentation-only and never recreate the global notice.
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('security:scan-completed', {
      detail: {
        run_id: 'security-historical-mock-000',
        profile: 'quick',
        status: 'succeeded',
      },
    })));
    await expect(completionToast).toHaveCount(1);
  });

  test('Identity and Rules remain separate truthful Lite-friendly security surfaces', async ({ page }) => {
    await page.goto('/?screen=identity');
    const identity = page.locator('[data-lite-screen-id="identity"]');
    await expect(identity).toBeVisible();
    await expect(identity).toContainText('Identity & Access');
    await expect(identity.getByLabel('Access posture')).toBeVisible();
    await expect(identity).toContainText('Passkeys');
    await expect(identity).toContainText('Sessions');
    await expect(identity).toContainText('Recovery');
    await identity.getByRole('button', { name: /Manage access/i }).click();
    await expect(page.getByRole('dialog', { name: 'Manage access' })).toContainText(/Manage your own passkeys, sessions, recovery/i);
    await expect(identity).not.toContainText('local-admin');

    await page.goto('/?screen=rules');
    const rules = page.locator('[data-lite-screen-id="rules"]');
    await expect(rules).toBeVisible();
    await expect(rules).toContainText('Safety Rules');
    await expect(rules).toContainText('Protected');
    await expect(rules).toContainText('Protected changes are checked first');
    await expect(rules).toContainText('Pocket Lab evaluates sensitive changes on the server before they continue.');
    await expect(rules).toContainText('Protected app, device and Identity changes are checked before they continue.');
    await expect(rules).not.toContainText('Open Policy Agent');
    await expect(rules).not.toContainText('Rego');
    await expect(rules).not.toContainText('package pocketlab');
  });

  test('Enterprise Rules simulation, approvals and exception UX remain bounded', async ({ page }) => {
    // Enterprise-only assertions use an explicit Enterprise Owner fixture. The
    // default healthy mock remains Personal Mode so Enterprise never becomes
    // the accidental default Lite UX.
    await installScenario(page, 'identity-enterprise-owner');
    await page.goto('/?screen=rules');
    const rules = page.locator('[data-lite-screen-id="rules"]');
    await expect(rules.getByRole('heading', { name: 'Rules governance', exact: true })).toBeVisible();

    await rules.getByRole('button', { name: 'Test a change', exact: true }).click();
    await expect(rules.getByText('This never executes the real action', { exact: true })).toBeVisible();
    await expect(rules.getByLabel('Context')).toBeVisible();
    await rules.getByLabel('Target reference').fill('mock-app');
    await rules.getByRole('button', { name: 'Run simulation', exact: true }).click();
    await expect(rules).toContainText(/Allowed in this simulation|Blocked in this simulation|Passkey confirmation would be required/i);
    await rules.getByLabel('Context').selectOption('synthetic');
    await expect(rules.getByText('Supported hypothetical facts')).toBeVisible();
    await expect(rules.getByText('Recent passkey assurance')).toBeVisible();

    await rules.getByRole('button', { name: 'Activity', exact: true }).click();
    await expect(rules.getByRole('heading', { name: 'Rules activity', exact: true })).toBeVisible();
    await expect(rules).not.toContainText('raw policy input');

    await rules.getByRole('button', { name: 'Requests', exact: true }).click();
    await expect(rules.getByRole('heading', { name: 'Review requests', exact: true })).toBeVisible();
    await expect(rules).toContainText(/exact-target|exact-Rules-revision/i);
    await expect(rules).not.toContainText('Requesting identity ID');

    await rules.getByRole('button', { name: 'Temporary access', exact: true }).click();
    await expect(rules.getByRole('heading', { name: 'Temporary access', exact: true })).toBeVisible();
    await expect(rules).toContainText(/Exact scope only|Expires/i);
    await expect(rules).not.toContainText('Human ID');

    await rules.getByRole('button', { name: 'Protection', exact: true }).click();
    await expect(rules.getByRole('heading', { name: 'Runtime facts', exact: true })).toBeVisible();
    await expect(rules).toContainText(/Analysis boundary|Only direct registered-action coverage is provable/i);
    await expect(rules).not.toContainText('package pocketlab');
  });

  test('premium surfaces stay within each required viewport', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mocked-desktop', 'The exact matrix is run once in Chromium to avoid duplicating the suite.');
    await page.emulateMedia({ reducedMotion: 'reduce' });

    for (const viewport of PREMIUM_VIEWPORTS) {
      await page.setViewportSize(viewport);
      await page.goto('/?screen=home');
      await expect(page.locator('[data-lite-screen-id="home"]')).toBeVisible();

      for (const [label, screenId] of PREMIUM_SCREENS) {
        await openTab(page, label, screenId);
        const screen = page.locator(`[data-lite-screen-id="${screenId}"]`);
        await expect(screen).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
        expect(await screen.evaluate((element) => {
          const rect = element.getBoundingClientRect();
          return rect.left >= 0 && rect.right <= window.innerWidth + 1;
        })).toBe(true);
      }

      await openTab(page, 'Identity & Access', 'identity');
      await page.getByRole('button', { name: /Manage access/i }).click();
      const identitySheet = page.getByRole('dialog', { name: 'Manage access' });
      await expect(identitySheet).toBeVisible();
      expect(await identitySheet.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return rect.left >= 0 && rect.right <= window.innerWidth + 1;
      })).toBe(true);
      const identityClose = identitySheet.getByRole('button', { name: 'Close app actions' });
      await expect(identityClose).toBeVisible();
      await page.keyboard.press('Tab');
      expect(await page.evaluate(() => {
        const active = document.activeElement;
        if (!(active instanceof HTMLElement)) return false;
        const rect = active.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < window.innerHeight;
      })).toBe(true);
      await page.keyboard.press('Escape');

      await openTab(page, 'Rules', 'rules');
      await page.locator('.lite-rules-operational-story').getByRole('button', { name: 'Manage Safety Rules', exact: true }).click();
      const rulesSheet = page.getByRole('dialog', { name: 'Manage Safety Rules' });
      await expect(rulesSheet).toBeVisible();
      expect(await rulesSheet.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return rect.left >= 0 && rect.right <= window.innerWidth + 1;
      })).toBe(true);
      const rulesClose = rulesSheet.getByRole('button', { name: 'Close app actions' });
      await expect(rulesClose).toBeVisible();
      await page.keyboard.press('Escape');

      expect(await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true);
    }
  });

  test('Recovery keeps its summary and Manage workspace contained at each required viewport', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mocked-desktop', 'The exact Recovery matrix is run once in Chromium to avoid duplicating the suite.');
    await page.emulateMedia({ reducedMotion: 'reduce' });

    for (const viewport of PREMIUM_VIEWPORTS) {
      await page.setViewportSize(viewport);
      await page.goto('/?screen=recovery');
      const recovery = page.locator('[data-lite-screen-id="recovery"]');
      await expect(recovery).toBeVisible();
      await expect(recovery).toContainText(/Backup protection|Recovery information|Create your first protected backup/i);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

      const manage = recovery.getByRole('button', { name: 'Manage backups and recovery' });
      await manage.click();
      const sheet = page.getByRole('dialog', { name: 'Manage backups and recovery' });
      await expect(sheet).toBeVisible();
      await sheet.getByRole('tab', { name: 'Restore' }).click();
      await expect(sheet).toContainText('Review and restore safely');
      const close = sheet.getByRole('button', { name: 'Close app actions' });
      await expect(close).toBeVisible();
      expect(await sheet.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return rect.left >= 0 && rect.right <= window.innerWidth + 1;
      })).toBe(true);
      await page.keyboard.press('Escape');
      await expect(manage).toBeFocused();
      expect(await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true);
    }
  });

  test('Devices keeps the fleet summary and Add Device disclosure contained at each required viewport', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mocked-desktop', 'The exact Devices matrix is run once in Chromium to avoid duplicating the suite.');
    await page.emulateMedia({ reducedMotion: 'reduce' });

    for (const viewport of PREMIUM_VIEWPORTS) {
      await page.setViewportSize(viewport);
      await page.goto('/?screen=devices');
      const devices = await waitForLiveDevices(page);
      await expect(devices).toBeVisible();
      await expect(devices).toContainText(/Remote access\s*(Ready|not ready)/i);
      await expect(devices).toContainText('Devices');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

      const serverCard = devices.locator('.lite-device-card-server');
      await expect(serverCard).toContainText('Server host');
      await expect(serverCard).toContainText('Protected control device');
      await expect(serverCard.getByRole('button', { name: /remove|review/i })).toHaveCount(0);
      await expect(serverCard.locator('.lite-device-protected-host')).toContainText(/Pocket Lab Server.*Protected/i);
      await expect(serverCard.locator('.lite-device-flow-track')).toHaveCount(0);

      const addDisclosure = devices.locator('.lite-devices-add-disclosure');
      await addDisclosure.locator('summary').click();
      await expect(addDisclosure).toHaveAttribute('open', '');
      const addCard = addDisclosure.locator('.lite-devices-add-card');
      await expect(addCard).toContainText('Add a device');
      expect(await addCard.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return rect.left >= 0 && rect.right <= window.innerWidth + 1;
      })).toBe(true);

      const details = devices.getByRole('button', { name: 'Manage Test-Phone-4' });
      await details.click();
      const detailPanel = devices.locator('.lite-device-details-panel');
      await expect(detailPanel).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(details).toBeFocused();
      expect(await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true);
    }
  });

  test('Devices keeps healthy cards compact while preserving accessible connection and action state', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mocked-desktop', 'The Devices presentation contract is covered once in Chromium.');
    await page.goto('/?screen=devices');
    const devices = await waitForLiveDevices(page);
    const healthyCard = devices.locator('.lite-device-card').filter({ hasText: 'Test-Phone-4' });
    const serverCard = devices.locator('.lite-device-card-server');

    await expect(healthyCard.locator('[data-connection-state="connected"]')).toBeVisible();
    await expect(healthyCard.locator('.lite-device-flow-server')).toContainText('Server');
    await expect(healthyCard.locator('.lite-device-flow-device')).toContainText('Test-Phone-4');
    await expect(healthyCard.locator('.lite-device-card-disclosure')).not.toHaveAttribute('open', '');
    await expect(healthyCard.locator('.lite-device-trust-strip')).toBeHidden();
    await expect(
      healthyCard.getByRole('button', { name: 'Manage Test-Phone-4' }),
    ).toBeVisible();
    await expect(healthyCard.getByRole('button', { name: /restart agent|review removal|remove device/i })).toHaveCount(0);

    const more = healthyCard.locator('.lite-device-card-disclosure > summary');
    await more.press('Enter');
    await expect(healthyCard.locator('.lite-device-card-disclosure')).toHaveAttribute('open', '');
    await expect(healthyCard.locator('.lite-device-trust-strip')).toContainText(/identity|capabilities/i);

    await expect(serverCard.locator('[data-connection-state="server"]')).toBeVisible();
    await expect(serverCard.locator('.lite-device-protected-host')).toBeVisible();
    await expect(serverCard.locator('.lite-device-flow-track')).toHaveCount(0);
    await expect(serverCard).toContainText('Protected control device');
    await expect(serverCard.getByRole('button', { name: /remove|review removal/i })).toHaveCount(0);

    const remote = devices.locator('.lite-remote-access-not-ready');
    await expect(remote).toContainText('Remote access not ready');
  });

  test('Devices makes remote-access and reduced-motion connection states explicit', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mocked-desktop', 'The Devices motion contract is covered once in Chromium.');
    // Use the healthy fleet for topology/motion assertions.
    // Its prepared remote-access projection is still "not ready" in the
    // default mock, while device connectivity remains live and testable.
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/?screen=devices');
    const devices = await waitForLiveDevices(page);
    await expect(devices.locator('.lite-remote-access-not-ready')).toContainText('Remote access not ready');

    const connectedSignal = devices.locator('[data-connection-state="connected"] .lite-device-flow-signal').first();
    await expect(connectedSignal).toHaveCSS('animation-name', 'none');
    const disconnected = devices.locator('[data-connection-state="disconnected"]').first();
    await expect(disconnected).toBeVisible();
    await expect(disconnected).toHaveAttribute('aria-label', /disconnected/i);
    expect(await disconnected.locator('.lite-device-flow-break').evaluate((element) => {
      const marker = element.getBoundingClientRect();
      const surface = element.closest('.lite-device-connection-flow')?.getBoundingClientRect();
      return Boolean(surface && marker.left >= surface.left && marker.right <= surface.right && marker.top >= surface.top && marker.bottom <= surface.bottom);
    })).toBe(true);
  });

  test('Devices moves connection packets across their desktop and mobile tracks while keeping static states still', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mocked-desktop', 'The deterministic connection geometry contract is covered once in Chromium.');

    const freezePacketAt = async (signal: ReturnType<typeof page.locator>, animationName: string, elapsedSeconds: number) => {
      return signal.evaluate((element, { name, elapsed }) => {
        const signal = element as HTMLElement;
        signal.style.animation = `${name} 2.5s linear ${-elapsed}s paused both`;
        const track = signal.parentElement?.getBoundingClientRect();
        const packet = signal.getBoundingClientRect();
        if (!track) throw new Error('Connection packet has no track.');
        return { track: { x: track.x, y: track.y, width: track.width, height: track.height }, packet: { x: packet.x, y: packet.y, width: packet.width, height: packet.height } };
      }, { name: animationName, elapsed: elapsedSeconds });
    };

    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/?screen=devices');
    const devices = await waitForLiveDevices(page);
    const connectedSignal = devices.locator('[data-connection-state="connected"] .lite-device-flow-signal').first();
    await expect(connectedSignal).toHaveCSS('animation-name', 'lite-device-flow-packet-horizontal');
    const desktopStart = await freezePacketAt(connectedSignal, 'lite-device-flow-packet-horizontal', .6);
    const desktopEnd = await freezePacketAt(connectedSignal, 'lite-device-flow-packet-horizontal', 1.8);
    expect(desktopEnd.packet.x - desktopStart.packet.x).toBeGreaterThan(desktopStart.track.width * .4);
    await connectedSignal.evaluate((element) => { (element as HTMLElement).style.animation = ''; });

    await page.setViewportSize({ width: 390, height: 844 });
    await expect(connectedSignal).toHaveCSS('animation-name', 'lite-device-flow-packet-vertical');
    const mobileStart = await freezePacketAt(connectedSignal, 'lite-device-flow-packet-vertical', .6);
    const mobileEnd = await freezePacketAt(connectedSignal, 'lite-device-flow-packet-vertical', 1.8);
    expect(mobileEnd.packet.y - mobileStart.packet.y).toBeGreaterThan(mobileStart.track.height * .4);

    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(connectedSignal).toHaveCSS('animation-name', 'none');

    await page.emulateMedia({ reducedMotion: 'no-preference' });
    const fleetPayload = await page.evaluate(async () => {
      const response = await fetch('/api/lite/fleet');
      return response.json();
    }) as { devices: Array<{ id: string; [key: string]: unknown }> };
    const repairingFleetPayload = {
      ...fleetPayload,
      devices: fleetPayload.devices.map((device) => device.id === 'test-phone-4'
        ? { ...device, status: 'repairing', connection: 'repairing' }
        : device),
    };
    await page.addInitScript((payload) => {
      const originalFetch = window.fetch.bind(window);
      window.fetch = (input, init) => {
        const request = new Request(input, init);
        const url = new URL(request.url, window.location.origin);

        if (url.pathname === '/api/lite/fleet') {
          const readNonce = request.headers.get('X-PocketLab-Read-Nonce') || '';

          return Promise.resolve(new Response(JSON.stringify(payload), {
            headers: {
              'Content-Type': 'application/json',
              'X-PocketLab-Read-Nonce': readNonce,
            },
          }));
        }

        return originalFetch(input, init);
      };
    }, repairingFleetPayload);
    await page.goto('/?screen=devices');
    const repairingSignal = page.locator('[data-connection-state="repairing"] .lite-device-flow-signal').first();
    await expect(repairingSignal).toHaveCSS('animation-name', 'lite-device-flow-packet-vertical');
    await expect(repairingSignal).toHaveCSS('background-color', 'rgb(217, 119, 6)');
    await expect(page.locator('[data-connection-state="repairing"] .lite-device-connection-copy')).toContainText('Repairing connection');
    const repairingStart = await freezePacketAt(repairingSignal, 'lite-device-flow-packet-vertical', .6);
    const repairingEnd = await freezePacketAt(repairingSignal, 'lite-device-flow-packet-vertical', 1.8);
    expect(repairingEnd.packet.y - repairingStart.packet.y).toBeGreaterThan(repairingStart.track.height * .4);
    await expect(page.locator('[data-connection-state="disconnected"] .lite-device-flow-signal')).toHaveCSS('animation-name', 'none');
    await expect(page.locator('[data-connection-state="server"] .lite-device-protected-host')).toBeVisible();
    await expect(page.locator('[data-connection-state="server"] .lite-device-flow-signal')).toHaveCount(0);
  });

  test('Devices retains the backend-owned Add Device invite flow', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'mocked-desktop', 'The Devices invite flow is covered once in Chromium.');
    await page.addInitScript(() => {
      if (!navigator.serviceWorker) return;
      Object.defineProperty(navigator.serviceWorker, 'controller', {
        configurable: true,
        get: () => null,
      });
    });
    await installScenario(page, 'devices-add-ready');
    await page.goto('/?screen=devices');
    const devices = page.locator('[data-lite-screen-id="devices"]');
    await expect(devices.locator('.lite-remote-access-ready')).toContainText('Ready');
    await expect(devices.locator('.lite-remote-access-details')).not.toHaveAttribute('open', '');
    const addDisclosure = devices.locator('.lite-devices-add-disclosure');

    await addDisclosure.locator('summary').click();
    await addDisclosure.getByLabel('Device name').fill('Workshop tablet');
    await addDisclosure.getByRole('button', { name: 'Add Device', exact: true }).click();
    const invite = addDisclosure.locator('.lite-invite-card');
    await expect(invite).toBeVisible();
    await expect(invite).toContainText('Invite ready');
    await expect(invite.getByLabel('Connect this device command')).toBeVisible();
    await expect(invite.getByRole('button', { name: 'Copy command' })).toBeVisible();
  });
});
