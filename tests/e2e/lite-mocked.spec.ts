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

  test('Home keeps secondary capacity and healthy status detail behind accessible disclosures', async ({ page }) => {
    await page.goto('/?screen=home');
    const home = page.locator('[data-lite-screen-id="home"]');
    const deviceDetails = page.locator('[data-home-device-details="true"]');
    const statusDetails = page.locator('[data-home-status-details="true"]');

    await expect(home.getByRole('button', { name: 'View device details' })).toHaveAttribute('aria-expanded', 'false');
    await expect(home.getByRole('button', { name: 'View all areas' })).toHaveAttribute('aria-expanded', 'false');
    await expect(deviceDetails).toBeHidden();
    await expect(statusDetails).toBeHidden();

    await home.getByRole('button', { name: 'View device details' }).click();
    await expect(home.getByRole('button', { name: 'Hide device details' })).toHaveAttribute('aria-expanded', 'true');
    await expect(deviceDetails).toBeVisible();
    await expect(deviceDetails).toContainText(/Storage|Pocket Lab data/i);

    await home.getByRole('button', { name: 'View all areas' }).press('Enter');
    await expect(home.getByRole('button', { name: 'Hide all areas' })).toHaveAttribute('aria-expanded', 'true');
    await expect(statusDetails).toBeVisible();
    await expect(statusDetails.locator('.lite-home-premium-service')).toHaveCount(6);

    await home.locator('.lite-home-premium-overview').getByRole('button', { name: 'Open Apps' }).click();
    await expect(page.locator('[data-lite-screen-id="catalog"]')).toBeVisible();
  });

  test('Home gives a ready workspace a smooth, reduced-motion-safe pulse', async ({ page }) => {
    await page.goto('/?screen=home');
    const workflow = page.locator('[data-home-workflow-state]');

    await expect(workflow).toBeVisible();
    await expect(workflow).toContainText('Workspace pulse');
    await expect(workflow.locator('.lite-home-workflow-node')).toHaveCount(4);
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await workflow.evaluate((element) => {
      element.classList.remove('motion-rest', 'motion-checking');
      element.classList.add('motion-live');
    });
    const isVerticalWorkflow = (page.viewportSize()?.width || 0) < 768;
    await expect(workflow.locator('.lite-home-workflow-line i').first()).toHaveCSS(
      'animation-name',
      isVerticalWorkflow ? 'liteHomeWorkflowSweepVertical' : 'liteHomeWorkflowSweep',
    );

    await page.emulateMedia({ reducedMotion: 'reduce' });
    await expect(workflow.locator('.lite-home-workflow-line i').first()).toHaveCSS('animation-name', 'none');
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

    await expect(home.locator('.lite-home-premium-service-preview').getByText('Safety needs immediate attention.')).toBeVisible();
    await expect(home.getByRole('button', { name: 'View all areas' })).toHaveAttribute('aria-expanded', 'false');
  });

  test('Home keeps saved information truthful while secondary detail remains collapsed', async ({ page }) => {
    await installScenario(page, 'offline-saved');
    await page.setViewportSize({ width: 320, height: 568 });
    await page.goto('/?screen=home');
    const home = page.locator('[data-lite-screen-id="home"]');
    await expect(home).toContainText('Showing saved information');
    await expect(home.getByRole('button', { name: 'View device details' })).toHaveAttribute('aria-expanded', 'false');
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
        type: 'security.scan.snapshot',
        event_id: 500,
        run_id: 'security-stale-mock-001',
        profile: 'quick',
        status: 'succeeded',
        active_scan: false,
        snapshot: true,
      });
    });
    await expect(page.locator('.lite-toast', { hasText: 'Safety check completed' })).toHaveCount(0);

    terminalDelivered = true;
    await page.evaluate(() => {
      const source = window.__liteControlledSecurityEvents.instances
        .find((item) => item.url.includes('/api/lite/security/events') && !item.closed);
      const terminal = {
        type: 'security.scan.snapshot',
        event_id: 501,
        run_id: 'security-mock-002',
        profile: 'quick',
        status: 'succeeded',
        percent: 100,
        active_scan: false,
        snapshot: true,
        updated_at: '2026-08-31T10:00:00.000Z',
      };
      source.emit(terminal);
      source.emit({ ...terminal, type: 'security.scan.completed', event_id: 502, snapshot: false, status: 'completed' });
    });

    const completionToast = page.locator('.lite-toast', { hasText: 'Safety check completed' });
    await expect(completionToast).toHaveCount(1);
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
    await identity.getByRole('button', { name: 'Manage access' }).click();
    await expect(page.getByRole('dialog', { name: 'Manage access' })).toContainText(/current and other owner sessions remain distinct/i);
    await expect(identity).not.toContainText('local-admin');

    await page.goto('/?screen=rules');
    const rules = page.locator('[data-lite-screen-id="rules"]');
    await expect(rules).toBeVisible();
    await expect(rules).toContainText('Safety Rules');
    await expect(rules).toContainText('Protected');
    await expect(rules).toContainText('Sensitive changes are checked first');
    await expect(rules).toContainText('Apps, devices, and identity changes are evaluated by Pocket Lab before they continue.');
    await expect(rules).not.toContainText('Open Policy Agent');
    await expect(rules).not.toContainText('Rego');
    await expect(rules).not.toContainText('package pocketlab');
  });

  test('Enterprise Rules simulation, approvals and exception UX remain bounded', async ({ page }) => {
    await page.goto('/?screen=rules');
    const rules = page.locator('[data-lite-screen-id="rules"]');
    await expect(rules.getByRole('heading', { name: 'Rules governance', exact: true })).toBeVisible();

    await rules.getByRole('button', { name: 'Simulate' }).click();
    await expect(rules.getByText('This does not execute the action', { exact: true })).toBeVisible();
    await expect(rules.getByLabel('Simulation context')).toBeVisible();
    await rules.getByLabel('Target reference').fill('mock-app');
    await rules.getByRole('button', { name: 'Run simulation' }).click();
    await expect(rules).toContainText(/Allowed in this simulation|Blocked in this simulation|Passkey confirmation required/i);
    await rules.getByLabel('Simulation context').selectOption('synthetic');
    await expect(rules.getByText('Supported hypothetical facts')).toBeVisible();
    await expect(rules.getByText('Recent passkey assurance')).toBeVisible();

    await rules.getByRole('button', { name: 'Decisions' }).click();
    await expect(rules.getByRole('heading', { name: 'Decision explorer', exact: true })).toBeVisible();
    await expect(rules).not.toContainText('raw policy input');

    await rules.getByRole('button', { name: 'Approvals' }).click();
    await expect(rules.getByRole('heading', { name: 'Device removal approvals', exact: true })).toBeVisible();
    await expect(rules).toContainText(/exact-target|exact-Rules-revision/i);
    await expect(rules).not.toContainText('Requesting identity ID');

    await rules.getByRole('button', { name: 'Exceptions' }).click();
    await expect(rules.getByRole('heading', { name: 'Temporary exceptions', exact: true })).toBeVisible();
    await expect(rules).toContainText(/Expires automatically|Read-only exception view/i);
    await expect(rules).not.toContainText('Human ID');

    await rules.getByRole('button', { name: 'Health' }).click();
    await expect(rules.getByRole('heading', { name: 'Rules health', exact: true })).toBeVisible();
    await expect(rules).toContainText(/Not all conflicts are analyzable by this model|Advanced analysis is not available to this role/i);
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
      await page.getByRole('button', { name: 'Manage access' }).click();
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
      await page.getByRole('button', { name: 'Manage Safety Rules' }).click();
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
      const devices = page.locator('[data-lite-screen-id="devices"]');
      await expect(devices).toBeVisible();
      await expect(devices).toContainText(/Remote access (ready|not ready)/);
      await expect(devices).toContainText('Devices');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);

      const serverCard = devices.locator('.lite-device-card-server');
      await expect(serverCard).toContainText('Server host');
      await expect(serverCard).toContainText('Protected control device');
      await expect(serverCard.getByRole('button', { name: /remove|review/i })).toHaveCount(0);

      const addDisclosure = devices.locator('.lite-devices-add-disclosure');
      await addDisclosure.locator('summary').click();
      await expect(addDisclosure).toHaveAttribute('open', '');
      const addCard = addDisclosure.locator('.lite-devices-add-card');
      await expect(addCard).toContainText('Add a device');
      expect(await addCard.evaluate((element) => {
        const rect = element.getBoundingClientRect();
        return rect.left >= 0 && rect.right <= window.innerWidth + 1;
      })).toBe(true);

      const details = devices.getByRole('button', { name: 'Details' }).first();
      await details.click();
      const detailPanel = devices.locator('.lite-device-details-panel');
      await expect(detailPanel).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(details).toBeFocused();
      expect(await page.evaluate(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)).toBe(true);
    }
  });
});
