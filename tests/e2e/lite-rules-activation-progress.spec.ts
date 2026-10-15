import { expect, test } from '@playwright/test';
import { installScenario } from './lite-test-helpers';

async function installRulesActivationFetch(page, terminal: 'success' | 'not_completed') {
  await page.addInitScript(({ terminalState }) => {
    const originalFetch = window.fetch.bind(window);
    const phases = ['pending', 'validating', 'switching', 'restarting', 'verifying'];
    window.__rulesActivationPhase = -1;
    window.__rulesActivationTerminal = terminalState;

    window.fetch = async (input, init) => {
      const requestUrl = typeof input === 'string' ? input : input.url;
      const url = new URL(requestUrl, window.location.origin);
      const method = String(init?.method || (typeof input === 'string' ? 'GET' : input.method) || 'GET').toUpperCase();

      if (url.pathname === '/api/lite/enterprise/rules/source-sync' && method === 'POST') {
        window.__rulesActivationPhase = 0;
        return new Response(JSON.stringify({
          status: 'queued',
          accepted: true,
          activation_required: true,
          summary: 'Safety Rules update was accepted. The supervisor will stage, restart and verify it.',
          operation: {
            operation_id: 'plo-ui-progress',
            candidate_revision_id: 'plr-ui-candidate',
            state: 'pending',
          },
        }), { status: 202, headers: { 'Content-Type': 'application/json' } });
      }

      if (url.pathname === '/api/lite/enterprise/rules/source-sync/status' && method === 'GET') {
        const phase = window.__rulesActivationPhase;
        if (phase >= 0 && phase < phases.length) {
          const current = phases[phase];
          const shouldStop = terminalState === 'not_completed' && current === 'validating';
          window.__rulesActivationPhase = shouldStop ? 99 : phase + 1;
          return new Response(JSON.stringify({
            source: {
              durable: true,
              active_revision: 'plr-old',
              known_good_revision: 'plr-old',
              repository_revision: 'plr-ui-candidate',
              source_update_required: true,
              activation_in_progress: true,
              activation_operation: {
                operation_id: 'plo-ui-progress',
                candidate_revision_id: 'plr-ui-candidate',
                state: current,
                created_at: '2026-09-04T17:30:00Z',
                updated_at: '2026-09-04T17:30:03Z',
              },
            },
            sanitized: true,
            policy_source_exposed: false,
            runtime_command_exposed: false,
          }), { headers: { 'Content-Type': 'application/json' } });
        }
        const succeeded = terminalState === 'success';
        return new Response(JSON.stringify({
          source: {
            durable: true,
            active_revision: succeeded ? 'plr-ui-candidate' : 'plr-old',
            known_good_revision: succeeded ? 'plr-ui-candidate' : 'plr-old',
            repository_revision: 'plr-ui-candidate',
            source_update_required: !succeeded,
            activation_in_progress: false,
            activation_operation: null,
          },
          sanitized: true,
          policy_source_exposed: false,
          runtime_command_exposed: false,
        }), { headers: { 'Content-Type': 'application/json' } });
      }

      if (url.pathname === '/api/lite/policy' && method === 'GET') {
        const response = await originalFetch(input, init);
        const payload = await response.clone().json();
        const phase = window.__rulesActivationPhase;
        const started = phase >= 0;
        const terminalReached = phase >= phases.length || phase === 99;
        const succeeded = terminalReached && terminalState === 'success';
        payload.active_policy = {
          ...(payload.active_policy || {}),
          revision: succeeded ? 'plr-ui-candidate' : 'plr-old',
          repository_revision: 'plr-ui-candidate',
          known_good_revision: succeeded ? 'plr-ui-candidate' : 'plr-old',
          source_update_required: !succeeded,
          source_update_available: !succeeded,
          activation_in_progress: started && !terminalReached,
        };
        payload.engine = {
          ...(payload.engine || {}),
          healthy: true,
          loopback_only: true,
          endpoint_exposed_to_browser: false,
        };
        payload.status = succeeded ? 'ready' : 'degraded';
        payload.degraded_reason = succeeded ? '' : started && !terminalReached ? 'policy_activation_pending' : 'policy_source_update_pending';
        payload.summary = succeeded
          ? 'Safety Rules are active and ready for protected changes.'
          : started && !terminalReached
            ? 'Safety Rules are being updated and verified. Protected changes remain fail-closed until verification finishes.'
            : 'A Safety Rules update is ready. The Owner must confirm it before protected changes can continue.';
        return new Response(JSON.stringify(payload), {
          status: response.status,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      return originalFetch(input, init);
    };
  }, { terminalState: terminal });
}

test.describe('Rules governed activation progress — source truth only', () => {
  test.beforeEach(async ({ page }) => {
    await installScenario(page, 'healthy');
    await page.setViewportSize({ width: 390, height: 844 });
  });
  for (const terminal of ['success', 'not_completed'] as const) {
    test('does not invent success after operation disappears: ' + terminal, async ({ page }) => {
      await installRulesActivationFetch(page, terminal);
      await page.goto('/?screen=rules');
      const rules = page.locator('[data-lite-screen-id="rules"]');
      await rules.getByRole('button', { name: 'Manage Safety Rules' }).click();
      const sheet = page.getByRole('dialog', { name: 'Manage Safety Rules' });
      await sheet.getByRole('button', { name: 'Update Safety Rules' }).click();
      const rail = sheet.locator('.lite-rules-activation-premium');
      await expect(rail).toBeVisible();
      await expect(rail).toContainText('Accepted');
      await expect(rail).toContainText('Checking');
      await expect(rail).toContainText('Applying');
      await expect(rail).toContainText('Verifying');
      // The fixture eventually omits the operation object. The UI must keep
      // uncertainty rather than claiming activation success from a missing event.
      await expect(rail).toHaveAttribute('data-rules-activation-state', 'uncertain', { timeout: 20_000 });
      await expect(rail).not.toContainText('Server-reported activation success');
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    });
  }
});
