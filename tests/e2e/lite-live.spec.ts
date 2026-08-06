import { execFileSync } from 'node:child_process';
import { mkdir, rename, unlink, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';
import {
  LITE_TABS,
  openTab,
  waitForLiteScreenToSettle,
  watchApiFailures,
} from './lite-test-helpers';

type SafeObservation = {
  headings: string[];
  button_names: string[];
  button_enabled: Record<string, boolean>;
  status_labels: string[];
  screen_text: string;
  server_identity_visible: boolean;
  tailscale_ip_visible: boolean;
  protection_toggle_pressed: boolean | null;
  home_cpu_note: string;
  recovery_status: string;
  recovery_summary: string;
  latest_backup_id: string;
  stale_warning_visible: boolean;
  backup_action_disabled: boolean;
  status_label: string;
  summary_label: string;
};

const PARITY_DOMAIN_BY_SCREEN: Record<string, string> = {
  home: 'home',
  catalog: 'apps',
  devices: 'devices',
  security: 'security',
  identity: 'identity',
  rules: 'rules',
  recovery: 'recovery',
};

function sourceCommit() {
  const configured = (process.env.LITE_PARITY_SOURCE_COMMIT || '').trim();
  if (/^[0-9a-f]{40}$/.test(configured)) return configured;
  return execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim();
}

function escapeRegExp(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function sanitizeRuntimeText(value: string, sensitiveValues: string[] = []) {
  let sanitized = value;
  for (const item of sensitiveValues) {
    const candidate = String(item || '').trim();
    if (!candidate) continue;
    sanitized = sanitized.replace(new RegExp(escapeRegExp(candidate), 'gi'), '[private-identity]');
  }
  return sanitized
    .replace(/-----BEGIN [A-Z ]*PRIVATE KEY-----/gi, '[redacted-key]')
    .replace(/\bBearer\s+[A-Za-z0-9._~+/=-]{12,}/gi, 'Bearer [redacted]')
    .replace(/\b(password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s,]+/gi, '$1=[redacted]')
    .replace(/\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/gi, '[private-identity]')
    .replace(/\b(?:10|127|169\.254|172\.(?:1[6-9]|2\d|3[01])|192\.168|100)\.(?:\d{1,3}\.){2}\d{1,3}\b/g, '[private-address]')
    .replace(/[A-Za-z0-9.-]+\.ts\.net\b/gi, '[tailnet-host]')
    .replace(/\/data\/data\/com\.termux\/files\/(?:home|usr)(?:\/[^\s]*)?/gi, '[private-path]')
    .replace(/\/home\/[^/\s]+\/[^\s]*/g, '[private-path]')
    .replace(/((?:nats|https?):\/\/)[^\s/@]+:[^\s@]+@/gi, '$1[redacted]@')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 12_000);
}

type RuntimePrivacyContext = {
  sensitive_values: string[];
  server_identity_visible: boolean;
  tailscale_ip_visible: boolean;
};

function collectSensitiveValues(value: unknown, output: Set<string>) {
  if (Array.isArray(value)) {
    value.slice(0, 100).forEach((item) => collectSensitiveValues(item, output));
    return;
  }
  if (!value || typeof value !== 'object') return;
  const sensitiveKeys = new Set([
    'device_id', 'device_name', 'email', 'fqdn', 'host_name', 'hostname', 'identity_id',
    'ip', 'node_id', 'tailnet_ip', 'tailscale_ip', 'user_name', 'username',
  ]);
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    if (sensitiveKeys.has(key) && typeof item === 'string' && item.trim()) output.add(item.trim());
    if (typeof item === 'object' && item !== null) collectSensitiveValues(item, output);
  }
}

async function runtimePrivacyContext(page: Page, domain: string, screenText: string): Promise<RuntimePrivacyContext> {
  const endpoint = domain === 'home'
    ? '/api/lite/status'
    : domain === 'devices'
      ? '/api/lite/fleet'
      : domain === 'identity'
        ? '/api/lite/identity'
        : '';
  if (!endpoint) return { sensitive_values: [], server_identity_visible: false, tailscale_ip_visible: false };
  const response = await page.request.get(endpoint, { headers: { Accept: 'application/json', 'Cache-Control': 'no-cache' } });
  if (!response.ok()) return { sensitive_values: [], server_identity_visible: false, tailscale_ip_visible: false };
  const payload = await response.json();
  const sensitive = new Set<string>();
  collectSensitiveValues(payload, sensitive);
  let serverName = '';
  let tailscaleIp = '';
  if (domain === 'home') {
    serverName = String(payload?.device?.name || payload?.device_name || payload?.hostname || '');
    if (serverName) sensitive.add(serverName);
  } else if (domain === 'devices') {
    const devices = Array.isArray(payload?.devices) ? payload.devices : [];
    for (const device of devices.slice(0, 100)) {
      for (const item of [device?.name, device?.device_name, device?.hostname, device?.id, device?.device_id]) {
        if (typeof item === 'string' && item.trim()) sensitive.add(item.trim());
      }
    }
    const server = devices.find((item: Record<string, unknown>) => item?.protected_server_host === true || item?.role === 'server_host');
    serverName = String(server?.name || server?.device_name || server?.hostname || '');
    tailscaleIp = String(payload?.remote_access?.ip || payload?.remote_access?.tailscale_ip || '');
  }
  const normalizedScreen = screenText.toLocaleLowerCase();
  return {
    sensitive_values: [...sensitive].sort((left, right) => right.length - left.length).slice(0, 200),
    server_identity_visible: Boolean(serverName && normalizedScreen.includes(serverName.toLocaleLowerCase())),
    tailscale_ip_visible: Boolean(tailscaleIp && normalizedScreen.includes(tailscaleIp.toLocaleLowerCase())),
  };
}

function sanitizeBooleanMap(value: Record<string, boolean>, sensitiveValues: string[]) {
  const safe: Record<string, boolean> = {};
  for (const [key, enabled] of Object.entries(value)) {
    const sanitized = sanitizeRuntimeText(key, sensitiveValues).slice(0, 120);
    // Dynamic user-facing labels must never become evidence property names.
    // Only stable, allowlisted semantic action identifiers are retained.
    if (/^open$/i.test(sanitized)) safe.Open = enabled;
  }
  return safe;
}

function validateSafeObservationPayload(payload: unknown) {
  if (!payload || typeof payload !== 'object') throw new Error('parity observation must be an object');
  const item = payload as Record<string, unknown>;
  if (item.schema_version !== '2.0.0' || item.evidence_kind !== 'frontend' || item.status !== 'observed' || item.sanitized !== true) {
    throw new Error('parity observation identity is invalid');
  }
  if (!/^[0-9a-f]{40}$/.test(String(item.source_commit || ''))) throw new Error('parity source commit is invalid');
  if (!['live-desktop', 'live-mobile'].includes(String(item.browser_project || ''))) throw new Error('parity browser project is invalid');
  const release = String(item.release_tag || '');
  if (release && !/^lite-\d{4}\.\d{2}\.\d{2}\.\d+$/.test(release)) throw new Error('parity release tag is invalid');
  const observations = item.observations;
  if (!observations || typeof observations !== 'object' || Array.isArray(observations)) throw new Error('parity observations are invalid');

  const forbiddenKey = /(password|passwd|token|api[_-]?key|secret|credential|raw_payload|raw_response|raw_row|environment)/i;
  const forbiddenText = [
    /-----BEGIN [A-Z ]*PRIVATE KEY-----/i,
    /\bBearer\s+[A-Za-z0-9._~+/=-]{12,}/i,
    /\b(?:password|passwd|token|api[_-]?key|secret)\s*[:=]\s*[^\s,]+/i,
    /\b(?:10|127|169\.254|172\.(?:1[6-9]|2\d|3[01])|192\.168|100)\.(?:\d{1,3}\.){2}\d{1,3}\b/,
    /[A-Za-z0-9.-]+\.ts\.net\b/i,
    /\/data\/data\/com\.termux\/files\/(?:home|usr)(?:\/|\b)/i,
    /\/home\/[^/\s]+\//i,
    /(?:nats|https?):\/\/[^\s/]+:[^\s@]+@/i,
  ];
  const inspect = (value: unknown, depth = 0): void => {
    if (depth > 5) throw new Error('parity observation nesting exceeds limit');
    if (typeof value === 'string') {
      if (value.length > 12_000 || forbiddenText.some((pattern) => pattern.test(value))) throw new Error('parity observation contains unsafe text');
      return;
    }
    if (value === null || typeof value === 'boolean' || typeof value === 'number') return;
    if (Array.isArray(value)) {
      if (value.length > 100) throw new Error('parity observation array exceeds limit');
      value.forEach((entry) => inspect(entry, depth + 1));
      return;
    }
    if (typeof value === 'object') {
      const entries = Object.entries(value as Record<string, unknown>);
      if (entries.length > 100) throw new Error('parity observation object exceeds limit');
      for (const [key, entry] of entries) {
        if (forbiddenKey.test(key)) throw new Error('parity observation contains a forbidden key');
        inspect(entry, depth + 1);
      }
      return;
    }
    throw new Error('parity observation contains an unsupported value');
  };
  inspect(observations);
  if (Buffer.byteLength(`${JSON.stringify(payload)}\n`, 'utf8') > 64_000) throw new Error('parity observation exceeds 64000 bytes');
}

async function atomicWriteObservation(filePath: string, payload: unknown) {
  validateSafeObservationPayload(payload);
  await mkdir(dirname(filePath), { recursive: true });
  const temporary = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  await writeFile(temporary, `${JSON.stringify(payload, null, 2)}\n`, 'utf8');
  await rename(temporary, filePath);
}

async function collectSafeObservation(page: Page, screenId: string): Promise<SafeObservation> {
  return page.locator(`[data-lite-screen-id="${screenId}"]`).evaluate((element) => {
    const clone = element.cloneNode(true) as HTMLElement;
    clone.querySelectorAll('pre, code, input, textarea, [data-copy-command], .lite-invite-command, .lite-bootstrap-command').forEach((node) => node.remove());
    const text = (node: Element | null) => (node?.textContent || '').replace(/\s+/g, ' ').trim();
    const unique = (values: string[]) => [...new Set(values.filter(Boolean))].slice(0, 80);
    const buttons = [...element.querySelectorAll('button')].filter((button) => {
      const style = window.getComputedStyle(button);
      return style.display !== 'none' && style.visibility !== 'hidden';
    });
    const buttonEnabled: Record<string, boolean> = {};
    for (const button of buttons) {
      const name = text(button).slice(0, 120);
      if (name && !(name in buttonEnabled)) buttonEnabled[name] = !button.hasAttribute('disabled') && button.getAttribute('aria-disabled') !== 'true';
    }
    const screenText = text(clone).slice(0, 12_000);
    const ipVisible = /\b(?:10|127|169\.254|172\.(?:1[6-9]|2\d|3[01])|192\.168|100)\.(?:\d{1,3}\.){2}\d{1,3}\b/.test(screenText);
    const resource = [...element.querySelectorAll('.lite-home-premium-resource')].find((node) => /Memory and CPU/i.test(text(node)));
    const recoveryStatus = element.querySelector('[data-testid="parity-recovery-status"]');
    const recoverySummary = element.querySelector('[data-testid="parity-recovery-summary"]');
    const backup = element.querySelector('[data-testid="parity-latest-backup-id"]');
    const toggle = element.querySelector('[aria-pressed]');
    const backupAction = [...element.querySelectorAll('button')].find((button) => /Back Up Now|Refresh to continue/i.test(text(button)));
    return {
      headings: unique([...element.querySelectorAll('h1, h2, h3')].map(text)),
      button_names: unique(buttons.map(text)),
      button_enabled: buttonEnabled,
      status_labels: unique([...element.querySelectorAll('[role="status"], .lite-home-pill, .lite-status-badge, [data-status]')].map(text)),
      screen_text: screenText,
      server_identity_visible: false,
      tailscale_ip_visible: ipVisible,
      protection_toggle_pressed: toggle ? toggle.getAttribute('aria-pressed') === 'true' : null,
      home_cpu_note: text(resource?.querySelector('em')).slice(0, 240),
      recovery_status: text(recoveryStatus).slice(0, 120),
      recovery_summary: text(recoverySummary).slice(0, 240),
      latest_backup_id: backup?.getAttribute('data-backup-id') || '',
      stale_warning_visible: Boolean(element.querySelector('[data-testid="recovery-projection-stale"]')),
      backup_action_disabled: Boolean(backupAction?.hasAttribute('disabled') || backupAction?.getAttribute('aria-disabled') === 'true'),
      status_label: text(recoveryStatus).slice(0, 120),
      summary_label: text(recoverySummary).slice(0, 240),
    };
  });
}


test.describe('Pocket Lab Lite live read-only smoke', () => {
  test.skip(
    process.env.LITE_E2E_LIVE !== '1',
    'Set LITE_E2E_LIVE=1 after starting Caddy, FastAPI, SQLite, NATS/JetStream, worker, and PWA.'
  );

  test(
    'Caddy and FastAPI render every current Lite tab without write actions',
    async ({ page }) => {
      const failed = watchApiFailures(page);

      const statusResponse = page.waitForResponse(
        (response) =>
          response.url().includes('/api/lite/status')
      );

      await page.goto('/?screen=home');

      const response = await statusResponse;
      expect(response.ok()).toBeTruthy();

      const payload = await response.json();
      expect(payload).toHaveProperty('overall');

      for (const [label, screenId] of LITE_TABS) {
        await openTab(page, label, screenId);
      }

      expect(
        failed,
        `unexpected live Lite API failures: ${failed.join(', ')}`
      ).toEqual([]);
    }
  );

  test(
    'capture sanitized semantic observations for every Lite tab',
    async ({ page }, testInfo) => {
      await page.goto('/?screen=home');
      const source = sourceCommit();
      const releaseTag = (process.env.LITE_PARITY_RELEASE_TAG || '').trim();
      expect(source).toMatch(/^[0-9a-f]{40}$/);
      expect(releaseTag === '' || /^lite-\d{4}\.\d{2}\.\d{2}\.\d+$/.test(releaseTag)).toBeTruthy();

      const browserOutputRoot = resolve('.pocketlab-dev', 'validation', 'parity', 'browser');
      await mkdir(browserOutputRoot, { recursive: true });
      for (const domain of Object.values(PARITY_DOMAIN_BY_SCREEN)) {
        await unlink(resolve(browserOutputRoot, `${domain}-${testInfo.project.name}.json`), { force: true });
      }

      for (const [label, screenId] of LITE_TABS) {
        await openTab(page, label, screenId);
        await waitForLiteScreenToSettle(page, screenId, { timeoutMs: 20_000, stableSamples: 3, intervalMs: 250 });
        const raw = await collectSafeObservation(page, screenId);
        const domain = PARITY_DOMAIN_BY_SCREEN[screenId];
        const privacy = await runtimePrivacyContext(page, domain, raw.screen_text);
        const observations = {
          ...raw,
          server_identity_visible: privacy.server_identity_visible,
          tailscale_ip_visible: privacy.tailscale_ip_visible,
          screen_text: sanitizeRuntimeText(raw.screen_text, privacy.sensitive_values),
          headings: raw.headings.map((value) => sanitizeRuntimeText(value, privacy.sensitive_values)),
          button_names: raw.button_names.map((value) => sanitizeRuntimeText(value, privacy.sensitive_values)),
          button_enabled: sanitizeBooleanMap(raw.button_enabled, privacy.sensitive_values),
          status_labels: raw.status_labels.map((value) => sanitizeRuntimeText(value, privacy.sensitive_values)),
          home_cpu_note: sanitizeRuntimeText(raw.home_cpu_note, privacy.sensitive_values),
          recovery_status: sanitizeRuntimeText(raw.recovery_status, privacy.sensitive_values),
          recovery_summary: sanitizeRuntimeText(raw.recovery_summary, privacy.sensitive_values),
          latest_backup_id: sanitizeRuntimeText(raw.latest_backup_id, privacy.sensitive_values).slice(0, 160),
          status_label: sanitizeRuntimeText(raw.status_label, privacy.sensitive_values),
          summary_label: sanitizeRuntimeText(raw.summary_label, privacy.sensitive_values),
        };
        const payload = {
          schema_version: '2.0.0',
          evidence_kind: 'frontend',
          domain,
          status: 'observed',
          sanitized: true,
          captured_at: new Date().toISOString(),
          source_commit: source,
          release_tag: releaseTag,
          browser_project: testInfo.project.name,
          observations,
          error_code: '',
        };
        const output = resolve('.pocketlab-dev', 'validation', 'parity', 'browser', `${domain}-${testInfo.project.name}.json`);
        await atomicWriteObservation(output, payload);
      }
    }
  );

  test(
    'live Recovery projection meaning reaches the rendered UI',
    async ({ page }) => {
      const summaryResponse =
        page.waitForResponse(
          (response) =>
            response.url().includes(
              '/api/lite/recovery/summary'
            ) &&
            response.request().method() === 'GET' &&
            response.ok()
        );

      await page.goto('/?screen=recovery');

      const recovery = page.locator(
        '[data-lite-screen-id="recovery"]'
      );

      await expect(recovery).toBeVisible();

      const response = await summaryResponse;
      const payload = await response.json();

      await waitForLiteScreenToSettle(
        page,
        'recovery',
        {
          timeoutMs: 20_000,
          stableSamples: 4,
          intervalMs: 250,
        }
      );

      await expect(
        page.getByTestId(
          'parity-recovery-status'
        )
      ).toBeVisible();

      await expect(
        page.getByTestId(
          'parity-recovery-summary'
        )
      ).toBeVisible();

      const latestBackup =
        payload.latest_backup ||
        payload.last_backup ||
        {};

      if (latestBackup.backup_id) {
        await expect(
          page.getByTestId(
            'parity-latest-backup-id'
          )
        ).toHaveAttribute(
          'data-backup-id',
          latestBackup.backup_id
        );
      }

      const projectionStale =
        payload.read_degraded === true ||
        payload.degraded_reason ===
          'projection_too_old';

      const staleMessage = page.getByText(
        'Recovery information is old',
        { exact: true }
      );

      const backupButton = page.getByRole(
        'button',
        {
          name:
            /Back Up Now|Refresh to continue/i,
        }
      );

      if (projectionStale) {
        await expect(
          staleMessage
        ).toBeVisible();

        await expect(
          backupButton
        ).toBeDisabled();
      } else {
        await expect(
          staleMessage
        ).toHaveCount(0);
      }
    }
  );
});
